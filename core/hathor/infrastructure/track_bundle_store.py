"""곡별 산출물 묶음을 쓴다 (D-0203).

### 산출물이 자기를 설명한다

옛 묶음은 **아무것도 안 들었다.** `mert-layers`가 어느 모델·어느 입력으로
뽑혔는지 저장소 어디에도 없어 `stem_names`에 `layer03`이 들어 있는 것을 보고
**추측했다.** 재현이 불가능했고, 그래서 못 믿어 전부 다시 뽑는다.

여기서는 묶음마다 `manifest.json`이 붙는다 — 모델·커밋·층·홉·dtype·시각.
다음 사람이 `cat` 한 번으로 안다.

### 타임스탬프 폴더를 만들지 않는다

`scan-*.jsonl`이 셋(**둘은 md5가 같다**) · `keys-*.jsonl`이 열하나였다.
실행마다 새 이름이면 옛것은 **영원히 안 지워진다.** 곡 키로 한 자리에 쓰고
이력은 manifest가 든다.

### 이어받기는 곡 단위다

9시간짜리가 900곡에서 죽으면 처음부터는 못 간다. 곡이 끝난 뒤에야 파일이
제자리에 놓이므로 **반쯤 쓰다 만 묶음이 남지 않는다** — 남으면 그것이 다음
EDA의 재료가 된다.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    type Arrays = dict[str, np.ndarray[tuple[int, ...], np.dtype[np.float32]]]

MANIFEST_NAME = "manifest.json"
FAILURES_NAME = "failures.jsonl"
BUNDLE_SUFFIX = ".npz"


def bundle_name(source_key: str) -> str:
    """곡 키를 파일 이름으로 바꾼다. **원 키는 manifest가 든다.**

    제목에 슬래시·따옴표가 들어 있어 그대로 못 쓴다. 해시는 짧고 충돌이 없다.
    """
    return hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:16]


def repo_revision() -> str:
    """산출물을 만든 커밋. **코드가 바뀌면 산출물도 다른 것이다.**"""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


class TrackBundleStore:
    """곡별 npz와 곡별 manifest를 한 폴더에 쓴다."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, source_key: str) -> Path:
        return self._root / f"{bundle_name(source_key)}{BUNDLE_SUFFIX}"

    def has(self, source_key: str) -> bool:
        """**둘 다 있어야 끝난 것이다.** npz만 있으면 manifest를 쓰다 죽은 것이다."""
        stem = bundle_name(source_key)
        return (self._root / f"{stem}{BUNDLE_SUFFIX}").exists() and (
            self._root / f"{stem}.{MANIFEST_NAME}"
        ).exists()

    def write(self, source_key: str, arrays: Arrays, manifest: dict[str, object]) -> Path:
        """묶음을 쓴다. **npz를 먼저, manifest를 나중에.**

        순서가 규약이다 — `has`가 manifest로 완료를 판정하므로 뒤집으면
        반쯤 쓴 묶음이 끝난 것으로 보인다.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        stem = bundle_name(source_key)
        target = self._root / f"{stem}{BUNDLE_SUFFIX}"
        temporary = target.with_suffix(f"{BUNDLE_SUFFIX}.tmp")
        with temporary.open("wb") as stream:
            # 스텁이 2번째 위치를 `allow_pickle`로 본다 (`npz_feature_store`와 같다).
            np.savez_compressed(stream, **arrays)  # type: ignore[arg-type]
        temporary.replace(target)

        written = {
            "source_key": source_key,
            "bundle": target.name,
            "arrays": {name: list(value.shape) for name, value in sorted(arrays.items())},
            "revision": repo_revision(),
            "written_at": datetime.now(UTC).isoformat(),
            **manifest,
        }
        (self._root / f"{stem}.{MANIFEST_NAME}").write_text(
            json.dumps(written, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target

    def record_failure(self, source_key: str, reason: str) -> None:
        """**원인을 남긴다.** 지난 배치가 240곡을 원인 없이 잃었다."""
        self._root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "source_key": source_key,
                "reason": reason,
                "revision": repo_revision(),
                "recorded_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        )
        with (self._root / FAILURES_NAME).open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def counts(self) -> dict[str, int]:
        if not self._root.exists():
            return {"done": 0, "failed": 0}
        done = sum(1 for _ in self._root.glob(f"*.{MANIFEST_NAME}"))
        failures = self._root / FAILURES_NAME
        failed = (
            sum(1 for line in failures.read_text(encoding="utf-8").splitlines() if line.strip())
            if failures.exists()
            else 0
        )
        return {"done": done, "failed": failed}
