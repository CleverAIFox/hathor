"""전이 사전이 **구간 길이에 안 흔들리는가** — 실물에서 잰다 (D-0103 · D-0316).

### 왜 이것이 따로 필요했나

PLAN이 *"D-0103은 `eval harmony-order --self-transition-sweep`이 닫는다"*고 적고 있었다.
**그 훑기는 D-0114의 것이고 D-0114는 이미 `자료 실물 표본 200곡`이다.** 다시 돌려도
D-0114를 재확인할 뿐 D-0103은 안 닫힌다 — 훑기는 «자기 전이를 올리면 판정이 어떻게
되나»를 묻고, D-0103은 «같은 진행을 길게 끌면 사전이 바뀌나»를 묻는다. **다른 물음이다.**

### 무엇을 재는가

곡의 크로마 시계열을 **그대로 늘인다** — 창마다 `factor`번 되풀이한다. 화음 진행은 한
칸도 안 바뀌고 **각 화음을 끄는 길이만 배가 된다.** D-0103의 표가 `구간/화음`을 1에서
8로 바꾼 것이 이것이다.

| 자 | 늘이면 |
|---|---|
| `drop_diagonal=True` (제품이 쓰는 것) | **안 움직여야 한다** |
| `drop_diagonal=False` | 대각선이 부풀어 **무너져야 한다** |

**둘 다 봐야 비교다** (O-25 (1)). 버린 쪽만 보면 «0이 나왔다»가 자의 성질인지 자료의
성질인지 모른다 — 늘 0을 내는 자도 0을 낸다 (D-0071).

### 자기 전이 몫은 **이 창 길이에서 버려지는 전이의 몫**이다

D-0103이 *"화성 리듬을 통째로 버린다"*고 적었고 **얼마나 버렸는지는 안 쟀다.** 창
경계에서 도수가 안 바뀌는 비율이 그 몫이며, 여기서 처음 실물로 낸다.

**화성 리듬의 눈금이 아니다** (D-0317). 정본 `chord_rhythm.self_transition_rate`가
*"창 길이가 이 값을 정하므로 곡의 성질이 아니다"*라고 적어 두었고 **참 화음 길이가
같은데도 8창 0.317이 16창 0.305로 내려갔다.** D-0316이 이 수를 «버린 것의 크기»라고만
적어 그 한계를 화면에서 떨어뜨렸다 — 고쳤다.

**그래도 쓸 수 있는 수다.** 「1초 창에서 관측된 전이 가운데 몇 할이 버려지는가」는 이
창 길이의 성질이고, **D-0103의 선택이 무엇을 대가로 냈는지가 그것이다.** 곡을 줄
세우는 데 쓰면 안 된다 (D-0083의 순위상관과 같은 지위다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services import chord_rhythm
from hathor.domain.services.transition_prior import transition_prior

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

STRETCHES: tuple[int, ...] = (1, 2, 3, 4)
"""늘이는 배수. **1이 원본이며 같은 표에 둔다** — 원본이 없으면 비교가 아니다 (O-25)."""

INVARIANCE_CEILING = 1e-12
"""«안 움직였다»의 천장. **0이 아니라 부동소수 잡음이다** — 되풀이는 정수 셈을 키우고
나눗셈만 한 번 더 타므로 실제로는 자릿수 오차조차 안 나는 것이 보통이다."""


@dataclass(frozen=True, slots=True)
class StretchLine:
    """한 배수의 결과. **두 자를 나란히 든다.**"""

    factor: int
    dropped: tuple[float, ...]
    """`drop_diagonal=True`에서 원본과의 거리. 곡별."""
    kept: tuple[float, ...]
    """`drop_diagonal=False`에서 원본과의 거리. 곡별."""

    @property
    def songs(self) -> int:
        return len(self.dropped)

    @property
    def dropped_max(self) -> float:
        """**최대를 든다.** 평균은 곡 하나가 무너진 것을 감춘다."""
        return max(self.dropped) if self.dropped else 0.0

    @property
    def kept_mean(self) -> float:
        return float(np.mean(self.kept)) if self.kept else 0.0

    @property
    def kept_max(self) -> float:
        return max(self.kept) if self.kept else 0.0

    @property
    def invariant(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0316).

        `drop_diagonal`이 든 자는 어느 곡에서도 천장을 안 넘어야 한다. **질 수 있다** —
        `transition_prior`가 창마다 최빈 도수 하나를 고르는 대신 분포를 외적해 더하면
        잡음 바닥이 유지 길이에 비례해 대각선 밖에 쌓이고 여기가 빨개진다 (D-0107).
        """
        return self.dropped_max <= INVARIANCE_CEILING


def distance(left: NDArray[np.float64], right: NDArray[np.float64]) -> float:
    """두 전이 사전의 전변동 거리. **판정에 쓰는 것과 같은 자다** (D-0102)."""
    return float(np.abs(np.asarray(left) - np.asarray(right)).sum()) / 2.0


def stretched(series: NDArray[np.float64], factor: int) -> NDArray[np.float64]:
    """창마다 `factor`번 되풀이한다. **진행은 그대로이고 길이만 배가 된다.**"""
    if factor < 1:
        raise ValueError("늘이는 배수는 1 이상이어야 한다")
    return np.asarray(np.repeat(np.asarray(series, dtype=np.float64), factor, axis=0))


def self_share(series: NDArray[np.float64]) -> float | None:
    """창 경계에서 도수가 **안 바뀌는** 비율. 전이가 없으면 `None`이다 (GR-0.5).

    **정본은 `chord_rhythm.self_transition_rate`다** (D-0317). D-0316이 이 식을 여기
    다시 썼고 **같은 저장소에 이미 있었다** — `event_scale`의 문서 문자열이 바로 위에서
    *"정본은 `chord_rhythm` 하나이고 여기서 베끼지 않는다"*고 적어 둔 그 자리다.

    여기 남은 것은 **`None` 처리뿐이다.** 정본은 창이 둘 미만이면 `0.0`을 내고 그것은
    «자기 전이가 없다»로 읽힌다 — 판정에 안 쓰는 진단값이라 정본에서는 문제가 아니지만,
    **표에 찍으면 거짓이 된다** (GR-0.5). 그래서 **부르기 전에 걸러낸다.**
    """
    stacked = np.asarray(series, dtype=np.float64)
    if stacked.ndim != 2 or stacked.shape[0] < 2:
        return None
    return chord_rhythm.self_transition_rate(stacked)


def line(songs: Sequence[NDArray[np.float64]], factor: int) -> StretchLine:
    """한 배수 전체. **두 자를 같은 곡 집합에서 낸다.**"""
    dropped: list[float] = []
    kept: list[float] = []
    for series in songs:
        taken = np.asarray(series, dtype=np.float64)
        if taken.ndim != 2 or taken.shape[0] < 2:
            continue
        longer = stretched(taken, factor)
        dropped.append(distance(transition_prior(taken), transition_prior(longer)))
        kept.append(
            distance(
                transition_prior(taken, drop_diagonal=False),
                transition_prior(longer, drop_diagonal=False),
            )
        )
    return StretchLine(factor=factor, dropped=tuple(dropped), kept=tuple(kept))


def sweep(
    songs: Sequence[NDArray[np.float64]], factors: Sequence[int] = STRETCHES
) -> tuple[StretchLine, ...]:
    return tuple(line(songs, factor) for factor in factors)


def shares(songs: Sequence[NDArray[np.float64]]) -> tuple[float, ...]:
    """곡별 자기 전이 몫. **못 재는 곡은 빠진다.**"""
    found = [self_share(np.asarray(series, dtype=np.float64)) for series in songs]
    return tuple(value for value in found if value is not None)
