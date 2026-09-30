"""**묶은 것과 처음부터 그 길이로 뽑은 것이 같은가** — 실물 두 폴더를 맞댄다 (D-0104 · D-0320).

### 왜 이 파일이 있나

D-0319가 *"실물은 `ingest keys --series 2 --limit 40`이면 닫힌다"*고 적었다. **그 명령은
자료를 뽑을 뿐 대조를 안 한다.** 돌렸더니 조성 추정 보고가 나왔고 D-0104는 그대로 열려
있었다 — **D-0319 자신이 「주장 하나에 실행 하나」를 적은 판이다.**

`ingest`는 뽑고 `eval`이 판정한다. **뽑기 명령을 「닫힌다」의 자리에 적으면 안 된다.**

### 무엇을 맞대나

곡 파일 이름이 `sha1(source_key)[:16]-<스템>.npz`이므로(D-0105) **두 폴더를 해시로
짝짓는다.** 곡 목록이 달라도 겹치는 것만 든다.

    거리 = ½ Σ |group_series(짧은 창, k) - 긴 창|      k = 긴 창 / 짧은 창

### 0곡이면 그렇게 말한다

두 폴더가 **다른 스템**으로 뽑혔거나(분리 여부가 다르면 그렇다) 곡 집합이 안 겹치면
짝이 0이다. **그때 «거리 0»을 내면 통과로 읽힌다** — GR-0.5의 자리이며 `None`을 낸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.key_estimation import group_series

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

PRODUCTION_CEILING = 0.01
"""합성에서 잰 천장 (D-0319). **실물이 이것을 30~60배 넘었다** (D-0322).

| 스템 40곡 | 중앙 | 최대 |
|---|---|---|
| bass | **0.3548** | **0.5852** |
| vocals | 0.2973 | 0.4204 |
| other | 0.1895 | 0.2955 |
| mix | 0.1659 | 0.2949 |

**천장을 안 올린다.** 올리면 그것이 D-0058이다 — 이 수는 「전제가 깨졌다」를 말하고
있고 그것이 사실이다. 원인과 남은 선택은 D-0322가 든다.
"""

SUFFIX = ".npz"


@dataclass(frozen=True, slots=True)
class WindowMatch:
    """두 폴더를 맞댄 결과. **짝이 없으면 `gaps`가 비어 있다.**"""

    stem: str
    factor: int
    gaps: tuple[float, ...]
    short_windows: int
    long_windows: int

    @property
    def songs(self) -> int:
        return len(self.gaps)

    @property
    def median_gap(self) -> float | None:
        """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
        return float(np.median(self.gaps)) if self.gaps else None

    @property
    def max_gap(self) -> float | None:
        """**최대를 든다.** 평균은 곡 하나가 무너진 것을 감춘다."""
        return max(self.gaps) if self.gaps else None

    @property
    def holds(self) -> bool | None:
        """D-0104의 전제가 실물에서 서는가. **못 재면 `None`이다.**"""
        found = self.max_gap
        return None if found is None else found < PRODUCTION_CEILING

    def as_record(self) -> dict[str, object]:
        return {
            "stem": self.stem,
            "factor": self.factor,
            "songs": self.songs,
            "median_gap": None if self.median_gap is None else round(self.median_gap, 6),
            "max_gap": None if self.max_gap is None else round(self.max_gap, 6),
            "holds": self.holds,
        }


def stems(root: Path) -> tuple[str, ...]:
    """폴더에 실제로 있는 스템. **`SERIES_STEMS`를 믿지 않고 파일을 센다.**"""
    found = {path.name.split("-", 1)[1].removesuffix(SUFFIX) for path in root.glob(f"*{SUFFIX}")}
    return tuple(sorted(found))


def _series(path: Path) -> NDArray[np.float64] | None:
    with np.load(path, allow_pickle=False) as bundle:
        series = np.asarray(bundle["series"], dtype=np.float64)
    if series.ndim != 2 or series.shape[0] == 0 or series.shape[1] != 12:
        return None
    return series


def pairs(short_root: Path, long_root: Path, stem: str) -> list[tuple[Path, Path]]:
    """해시로 짝지은 파일 쌍. **곡 목록이 달라도 겹치는 것만 든다.**"""
    found: list[tuple[Path, Path]] = []
    for path in sorted(short_root.glob(f"*-{stem}{SUFFIX}")):
        twin = long_root / path.name
        if twin.exists():
            found.append((path, twin))
    return found


def compare(short_root: Path, long_root: Path, stem: str, factor: int) -> WindowMatch:
    """한 스템의 짝을 전부 재서 거리 목록을 낸다."""
    gaps: list[float] = []
    short_total = 0
    long_total = 0
    for short_path, long_path in pairs(short_root, long_root, stem):
        short = _series(short_path)
        long = _series(long_path)
        if short is None or long is None:
            continue
        short_total += short.shape[0]
        long_total += long.shape[0]
        grouped = group_series(np.asarray(short, dtype=np.float32), factor)
        count = min(len(grouped), len(long))
        if count < 1:
            continue
        gaps.append(max(0.5 * float(np.abs(grouped[i] - long[i]).sum()) for i in range(count)))
    return WindowMatch(
        stem=stem,
        factor=factor,
        gaps=tuple(gaps),
        short_windows=short_total,
        long_windows=long_total,
    )


def sweep(short_root: Path, long_root: Path, factor: int) -> tuple[WindowMatch, ...]:
    """두 폴더에 **함께 있는 스템**만 잰다. 하나도 없으면 빈 것을 낸다."""
    shared: Sequence[str] = tuple(
        stem for stem in stems(short_root) if stem in set(stems(long_root))
    )
    return tuple(compare(short_root, long_root, stem, factor) for stem in shared)
