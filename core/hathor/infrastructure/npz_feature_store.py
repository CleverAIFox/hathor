"""특징 산출물 저장. 벡터는 npz, 메타데이터는 JSONL이다.

벡터를 텍스트로 저장하지 않는다. float32 4바이트가 JSON에서 20바이트가
넘는 문자열이 되고 파싱도 훨씬 느리다. 1004곡 * 평균 23청크 * 768차원
* 5종(혼합+스템4)이면 npz로 약 350MB, JSON이면 2GB를 넘는다.

메타데이터는 조회·필터용이므로 텍스트로 둔다. 벡터와 메타를 분리하는
것은 규모와 무관한 표준 패턴이다.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from hathor.application.extract_features import TrackFeatures

FEATURES_DIRNAME = "features"
INDEX_SUFFIX = ".features.jsonl"
SUMMARY_SUFFIX = ".features.summary.json"
MIXTURE_KEY = "mixture"
VECTORS_DIRNAME = "vectors"
KEY_HASH_LENGTH = 16
BACKUP_SUFFIX = ".bak"
BATCH_LOCK_NAME = ".batch.lock"


class BatchAlreadyRunningError(RuntimeError):
    """같은 산출물 디렉터리에서 배치가 이미 돌고 있다 (O-7)."""


@dataclass(frozen=True, slots=True)
class CompactReport:
    """인덱스 정리 결과. 무엇을 몇 줄 버렸는지 남긴다."""

    total_lines: int
    kept: int
    duplicates_removed: int
    missing_vectors_dropped: int
    malformed_dropped: int

    @property
    def changed(self) -> bool:
        return bool(
            self.duplicates_removed or self.missing_vectors_dropped or self.malformed_dropped
        )


def vector_filename(source_key: str) -> str:
    """source_key를 파일명으로 쓸 수 없어 해시를 쓴다.

    source_key는 라이브러리 루트 기준 상대경로라 슬래시와 한글이 섞여 있다.
    새니타이즈는 서로 다른 경로가 같은 이름으로 충돌할 수 있고 경로 구조를
    그대로 재현하면 길이 제한에 걸린다. 해시는 길이가 고정되고 충돌이 없다.
    사람이 읽을 이름은 인덱스 JSONL이 제공한다.
    """
    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    return f"{digest[:KEY_HASH_LENGTH]}.npz"


def features_as_record(features: TrackFeatures) -> dict[str, object]:
    """키 순서를 고정한다. 2대 노트북 산출물이 바이트 단위로 같아야 한다(D-0009).

    기록 시각을 넣지 않는 것도 같은 이유다. 시각은 요약 파일명에만 둔다.
    """
    return {
        "source_key": features.source_key,
        "vector_file": vector_filename(features.source_key),
        "chunk_count": features.chunk_count,
        "feature_dim": int(features.mixture.shape[1]),
        "stem_names": sorted(features.stems),
    }


class NpzFeatureStore:
    """곡별 npz 파일과 누적 인덱스로 특징을 보관한다.

    스캔 산출물과 달리 실행마다 새 파일을 만들지 않는다. 1004곡 배치가
    다섯 시간이 걸리므로 중단 후 재개가 가능해야 하고, 그러려면 인덱스가
    실행 사이에 이어져야 한다.
    """

    def __init__(self, root: Path) -> None:
        self._root = root / FEATURES_DIRNAME

    @property
    def vectors_dir(self) -> Path:
        return self._root / VECTORS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self._root / f"index{INDEX_SUFFIX}"

    @property
    def batch_lock_path(self) -> Path:
        return self._root / BATCH_LOCK_NAME

    @contextmanager
    def batch_lock(self) -> Iterator[None]:
        """배치 중복 실행을 막는다 (O-7).

        O-7의 원인은 인덱스 append가 아니라 배치 자체가 두 번 돈 것이다.
        append는 O_APPEND + 200바이트라 리눅스에서 이미 원자적이었고,
        실제로 데이터도 깨지지 않았다. 막아야 하는 것은 프로세스 수준이다.

        PID 파일이 아니라 flock을 쓴다. 이 배치는 절전·발열·마운트 해제로
        네 번 죽었고 그때마다 정리 코드가 돌지 않았다. PID 파일이었다면
        죽은 잠금이 남아 다음 실행을 막는다. flock은 커널이 fd 수명에
        묶어 관리하므로 프로세스가 어떻게 죽든 자동으로 풀린다.

        내용은 사람이 읽기 위한 것이고 잠금 판정에는 쓰지 않는다.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        handle = self.batch_lock_path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.seek(0)
                holder = handle.read().strip() or "(미상)"
                raise BatchAlreadyRunningError(
                    f"배치가 이미 실행 중이다: {self.batch_lock_path} — {holder}"
                ) from exc
            handle.seek(0)
            handle.truncate()
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            handle.write(f"pid={os.getpid()} started={stamp}\n")
            handle.flush()
            yield
        finally:
            handle.close()  # 닫으면 잠금이 풀린다

    def read_records(self) -> list[dict[str, object]]:
        """인덱스를 기록 순서대로 읽는다. 중복은 그대로 둔다."""
        if not self.index_path.exists():
            return []
        records: list[dict[str, object]] = []
        with self.index_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def completed_keys(self) -> set[str]:
        """이미 기록된 source_key 집합. 재개 시 건너뛸 대상이다."""
        return {str(record["source_key"]) for record in self.read_records()}

    def compact_index(self, *, drop_missing: bool = True) -> CompactReport:
        """중복·고아 기록을 없애고 source_key 순으로 다시 쓴다 (O-7 정리).

        같은 키가 여럿이면 **마지막 기록을 남긴다.** npz는 같은 이름으로
        덮어써졌으므로 파일과 짝이 맞는 것은 나중 기록이다.

        정렬해서 쓰는 이유는 D-0009다. 지금 인덱스 순서는 배치가 몇 번
        중단됐고 어느 지점에서 재개됐는지에 따라 달라진다. 기기가 달라도
        같은 파일이 나와야 한다는 요구를 순서가 이미 깨고 있다.
        키 정렬은 이 순서 의존을 없앤다.

        `drop_missing`은 npz가 사라진 기록을 버린다. 그런 기록이 남아
        있으면 `completed_keys()`가 없는 파일을 완료로 보고해 재개가
        곡을 영영 건너뛴다.

        원본은 `.bak`으로 남긴다. 여러 번 돌려도 결과가 같다(멱등).
        """
        if not self.index_path.exists():
            return CompactReport(0, 0, 0, 0, 0)

        total = 0
        malformed = 0
        latest: dict[str, dict[str, object]] = {}
        with self.index_path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                total += 1
                try:
                    record = json.loads(line)
                    key = str(record["source_key"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    malformed += 1
                    continue
                latest[key] = record

        duplicates = total - malformed - len(latest)
        kept: list[dict[str, object]] = []
        missing = 0
        for key in sorted(latest):
            record = latest[key]
            if drop_missing and not (self.vectors_dir / str(record["vector_file"])).exists():
                missing += 1
                continue
            kept.append(record)

        content = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n" for record in kept
        ).encode("utf-8")

        # 내용이 같으면 쓰지 않는다. 두 번째 실행이 백업을 정리본으로
        # 덮어써 원본을 잃는 것을 막는다. 멱등성을 바이트 수준으로 만든다.
        if content != self.index_path.read_bytes():
            backup = self.index_path.with_suffix(self.index_path.suffix + BACKUP_SUFFIX)
            backup.write_bytes(self.index_path.read_bytes())
            temporary = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(self.index_path)

        return CompactReport(
            total_lines=total,
            kept=len(kept),
            duplicates_removed=duplicates,
            missing_vectors_dropped=missing,
            malformed_dropped=malformed,
        )

    def write_track(self, features: TrackFeatures) -> Path:
        """곡 하나를 저장하고 인덱스에 한 줄 덧붙인다.

        임시 파일에 쓰고 교체하므로 중단되어도 반쪽 npz가 남지 않는다.
        인덱스는 벡터 파일이 확정된 뒤에 쓴다. 순서가 반대면 재개 시
        없는 파일을 완료로 착각한다.
        """
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        target = self.vectors_dir / vector_filename(features.source_key)
        arrays = {MIXTURE_KEY: features.mixture, **features.stems}
        temporary = target.with_suffix(".npz.tmp")
        with temporary.open("wb") as stream:
            np.savez(stream, **arrays)  # type: ignore[arg-type]  # 스텁이 2번째 위치를 allow_pickle로 본다
        temporary.replace(target)
        with self.index_path.open("a", encoding="utf-8") as stream:
            # O_APPEND 자체로 이미 원자적이다. 잠금은 그 보장을 코드에
            # 드러내기 위한 것이며 O-7의 원인은 여기가 아니었다.
            # 실행 수준 방어는 batch_lock()이 한다.
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            line = json.dumps(features_as_record(features), ensure_ascii=False, sort_keys=False)
            stream.write(line + "\n")
        return target

    def write_summary(self, summary: dict[str, object]) -> Path:
        """실행별 요약. 인덱스와 달리 덮어쓰지 않고 실행마다 남긴다."""
        self._root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self._root / f"run-{stamp}{SUMMARY_SUFFIX}"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
