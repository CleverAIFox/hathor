"""화음 품질 어휘와 **교란 두 축**을 쓸어 낸다 (O-64 · D-0300 · D-0302).

**CLI에서 내려왔다** (D-0281의 계약). 쓸기는 `numpy` 계산이고 표시 계층은 계산하지 않는다 —
`test_표시_계층이_계산하지_않는다`가 그것을 지킨다.

### 실측이 끝났다 — O-64 (닫힘 D-0305)

`mix`(근음 포함) 기준. 판정은 **코퍼스 자기 순열 귀무와의 차**로만 한다.

| 품질 | 묶기1 | 묶기4 | 판정 |
|---|---|---|---|
| sus4 | **+0.0855** | **+0.1462** | 실재 |
| maj7 | **+0.0553** | +0.0418 | 실재 |
| m7 | **+0.0240** | +0.0423 | 실재 |
| maj | +0.0207 | +0.0022 | 약하다 |
| min | -0.0647 | -0.0889 | 없다 |
| dom7 | **-0.1208** | **-0.1436** | **없다** |

**4음 전체는 -0.0416으로 음수다.** *"코퍼스에 7화음이 실려 있다"*는 전제로는 틀렸는데,
품질별로는 셋이 양수이고 **그 셋이 O-64 (닫힘 D-0305)가 이름으로 지목한 셋이다.**

### 교란 1 — 근음이 빠진 스템 (실재했다)

`other`는 베이스를 뺀 것이고 저장소가 *"가장 깨끗하나 **베이스 근음을 버린다**"*고 적어
두었다 (`STEM_SETS` 표 · D-0073). **`other`만 봤으면 정반대로 읽었다.**

| 품질 | `other` | `mix` |
|---|---|---|
| sus4 | +0.0098 | **+0.0855** |
| maj7 | +0.0049 | **+0.0553** |
| maj | **+0.0934** | +0.0207 |

`sus4`(0·5·7)와 `maj7`(0·4·7·11)은 근음이 없으면 다른 화음의 전위와 구별되지 않는다.
**`dom7`은 근음을 넣어도 더 음수가 됐다** — 근음 누락 탓이 아니라 실제로 없다.

### 교란 2 — 창이 화음 전환을 걸친다

**C maj와 A min이 한 창에 들어가면 정확히 `Am7`의 음들이다.** 두 자로 쓸어 보고, **읽기
규칙은 합성 자료에서 먼저 확인했다** (O-25 넷째 줄).

| 자 | 번짐 코퍼스 | 진짜 코퍼스 |
|---|---|---|
| 원본 | +0.2148 | +0.7676 |
| 창 묶기 2 (`group_series` · D-0104) | **-0.0944** | **+0.8731** |
| 건너뛴 이웃 0.80 (`sustained_mask`) | **-0.0760** | **+0.8688** |

**차가 커지면 진짜고, 뒤집히면 번짐이다.** 첫 판에 *"커지면 번짐"*이라고 적었는데
**반대였다** — 묶기는 번짐을 늘리지 않고 평탄화한다. 합성으로 돌려 보고 알았다.

**실측에서 양수 셋 중 하나도 안 뒤집혔다** (D-0305). 번짐 교란은 배제됐다.

**인접 이웃으로는 못 가른다.** 50/50 블렌드 창은 양옆 순수 화음과 코사인이 0.93쯤이라 문턱
0.90을 통과하고, 번짐 코퍼스에서 `m7` +0.3597을 **+0.3777로 올렸다.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.harmony_quality import (
    QUALITIES,
    SUSTAINED_FLOOR,
    null_windows,
    quality_share,
    seventh_share,
    sustained_mask,
    verdicts,
)
from hathor.domain.services.key_estimation import group_series

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

GROUPS: tuple[int, ...] = (1, 2, 4)
"""창 묶기 배수. **1이 원본이며 같은 표에 둔다** — 원본이 없으면 비교가 아니다 (O-25)."""

FLOORS: tuple[float, ...] = (SUSTAINED_FLOOR, 0.90)
"""건너뛴 이웃 문턱.

**0.95를 뺐다.** 합성에서 잡음 0.2만 있어도 남는 창이 0개가 됐고, 창이 0인 열은 잴 것이
없다 — 그 자리에 `0.0000`을 찍으면 *"차가 없다"*로 읽히고 그것이 GR-0.5 위반이다.
"""


@dataclass(frozen=True, slots=True)
class QualityGap:
    """쓸기 한 칸의 결과. **창이 없으면 이 객체가 아예 없다** (`None`, GR-0.5)."""

    quality: dict[str, float]
    seventh: float
    windows: int

    def as_record(self) -> dict[str, object]:
        return {
            "quality_gap": {name: round(value, 6) for name, value in self.quality.items()},
            "seventh_gap": round(self.seventh, 6),
            "windows": self.windows,
        }


@dataclass(frozen=True, slots=True)
class QualitySweep:
    """쓸기 한 축 전체. `found`의 `None`은 **잴 창이 없었다**는 뜻이다."""

    labels: tuple[str, ...]
    found: tuple[QualityGap | None, ...]

    def as_record(self) -> dict[str, object]:
        return {
            label: None if item is None else item.as_record()
            for label, item in zip(self.labels, self.found, strict=True)
        }


def difference(windows: NDArray[np.float64], *, seed: int) -> QualityGap | None:
    """품질별 `실측 - 순열귀무`와 4음 차.

    **귀무를 매번 같은 자료에서 다시 뽑는다.** 묶거나 걸러낸 뒤의 창 집합은 원본과 다르므로
    원본의 귀무를 재사용하면 에너지 분포가 안 맞는다 — 귀무가 실측 구조를 재현해야 한다는
    O-25 다섯째 줄이 여기 걸린다.

    **판정할 창이 없으면 `None`이다.** `0.0`을 내면 *"차가 없다"*로 읽히고 그것이 거짓이다.
    """
    if windows.shape[0] == 0:
        return None
    measured = verdicts(windows)
    if not measured:
        return None
    baseline = verdicts(null_windows(windows, seed=seed))
    share = quality_share(measured)
    null_share = quality_share(baseline)
    return QualityGap(
        quality={name: share.get(name, 0.0) - null_share.get(name, 0.0) for name in QUALITIES},
        seventh=seventh_share(measured) - seventh_share(baseline),
        windows=len(measured),
    )


def stack(
    songs: Sequence[NDArray[np.float64]], *, factor: int = 1, floor: float | None = None
) -> NDArray[np.float64]:
    """곡별로 묶거나 걸러낸 뒤 쌓는다. **곡 경계를 넘어 묶지 않는다** (D-0302).

    넘어서 묶으면 어떤 곡의 마지막 창과 다음 곡의 첫 창이 한 화음으로 평균된다.
    """
    parts: list[NDArray[np.float64]] = []
    for series in songs:
        taken = np.asarray(series, dtype=np.float64)
        if factor > 1:
            taken = np.asarray(
                group_series(np.asarray(taken, dtype=np.float32), factor), dtype=np.float64
            )
        if floor is not None:
            taken = taken[sustained_mask(taken, floor=floor)]
        if taken.shape[0]:
            parts.append(taken)
    if not parts:
        return np.zeros((0, 12), dtype=np.float64)
    return np.vstack(parts)


def sweep_groups(songs: Sequence[NDArray[np.float64]], *, seed: int) -> QualitySweep:
    """교란 2a — 창을 길게 해 본다. **뒤집히면 번짐, 커지면 진짜다.**"""
    return QualitySweep(
        labels=tuple(f"묶기{factor}" for factor in GROUPS),
        found=tuple(difference(stack(songs, factor=factor), seed=seed) for factor in GROUPS),
    )


def sweep_sustained(songs: Sequence[NDArray[np.float64]], *, seed: int) -> QualitySweep:
    """교란 2b — 건너뛴 이웃이 닮은 창만 남긴다. **뒤집히면 번짐이다.**"""
    return QualitySweep(
        labels=tuple(f"문턱{floor:.2f}" for floor in FLOORS),
        found=tuple(difference(stack(songs, floor=floor), seed=seed) for floor in FLOORS),
    )
