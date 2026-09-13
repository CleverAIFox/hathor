"""온셋 포락선 저장소 (O-46 · D-0145).

`chroma_series_store`와 **같은 모양이다** — 곡마다 파일을 나누고 이름은 `source_key`의
해시다. 하나로 모으면 이어받기 중간에 죽었을 때 통째로 날아간다 (D-0075 · D-0105).

### 왜 홉을 파일에 적는가

포락선의 한 칸이 몇 초인지는 **자료의 성질이지 읽는 쪽의 약속이 아니다.** 안 적으면
나중에 홉을 바꿨을 때 옛 파일과 새 파일이 섞이고, **박 추정이 조용히 틀린다** —
D-0143이 주기 오차 0.8%로 위상이 통째로 뭉개지는 것을 실측했다.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

SUFFIX = ".onsets"
"""산출물 폴더 꼬리. `keys-<때>.onsets`이며 `.series`와 나란히 선다."""


def envelope_path(root: Path, source_key: str) -> Path:
    """곡 하나의 포락선 파일 위치.

    **파일 이름에 곡 제목을 쓰지 않는다** — 슬래시와 유니코드가 섞여 있고 기기마다
    다르게 정규화된다 (D-0105와 같은 근거).
    """
    stamp = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:16]
    return root / f"{stamp}.npz"


def write_envelope(
    root: Path, source_key: str, envelope: Sequence[float] | np.ndarray, *, hop_seconds: float
) -> None:
    """곡 하나의 포락선을 `npz`로 쓴다. **파일이 있으면 부르는 쪽이 건너뛴다.**"""
    if hop_seconds <= 0.0:
        raise ValueError("홉 길이는 양수여야 한다")
    root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        envelope_path(root, source_key),
        envelope=np.asarray(envelope, dtype=np.float32),
        hop_seconds=np.float64(hop_seconds),
        source_key=source_key,
    )


def load_envelope(root: Path, source_key: str) -> tuple[np.ndarray, float] | None:
    """`(포락선, 홉 초)`. 파일이 없으면 `None`이다."""
    path = envelope_path(root, source_key)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as bundle:
        return np.asarray(bundle["envelope"], dtype=np.float64), float(bundle["hop_seconds"])


def find_envelope_root(root: Path) -> Path | None:
    """가장 최근 포락선 폴더. 비어 있으면 건너뛴다 (D-0110과 같은 근거)."""
    ingest = root / "var" / "ingest"
    if not ingest.is_dir():
        return None
    for path in sorted(ingest.glob(f"keys-*{SUFFIX}"), reverse=True):
        if any(path.glob("*.npz")):
            return path
    return None
