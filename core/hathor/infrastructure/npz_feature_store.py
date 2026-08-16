"""특징 산출물 저장. 벡터는 npz, 메타데이터는 JSONL이다.

벡터를 텍스트로 저장하지 않는다. float32 4바이트가 JSON에서 20바이트가
넘는 문자열이 되고 파싱도 훨씬 느리다. 1004곡 * 평균 23청크 * 768차원
* 5종(혼합+스템4)이면 npz로 약 350MB, JSON이면 2GB를 넘는다.

메타데이터는 조회·필터용이므로 텍스트로 둔다. 벡터와 메타를 분리하는
것은 규모와 무관한 표준 패턴이다.
"""

from __future__ import annotations

import hashlib
import json
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

    def completed_keys(self) -> set[str]:
        """이미 기록된 source_key 집합. 재개 시 건너뛸 대상이다."""
        if not self.index_path.exists():
            return set()
        keys: set[str] = set()
        with self.index_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    keys.add(str(json.loads(line)["source_key"]))
        return keys

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
