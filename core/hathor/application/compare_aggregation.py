"""**평균 추출과 중앙값 추출을 맞댄다** — D-0064가 물은 것 (O-27 (b)).

### 왜 이 파일이 있나

D-0064가 *"창별 추출 후 중앙값"*을 채택하고 판정 지표까지 정해 뒀다.

> 곡 내 홀드아웃의 달성 가능 폭(`uniform` → `oracle`)이 **0.0187에서 오르는가.**

**추출은 이미 있다** — `ingest keys --aggregate median --window-seconds 10`이고 D-0064가
적은 「10초 창마다」 그대로다. **없던 것은 두 산출물을 견주는 자리 하나다.**

### 눈으로 견주면 안 된다

`eval harmony-prior --replay`가 폭을 **한 수**로 찍는다. 두 번 돌려 눈으로 빼면
**오차가 없다** — D-0327이 그 부류로 오경보율 50%짜리 판정을 돌리고 있었다.

폭은 **곡별로 쪼개진다.** `uniform_score`와 `oracle_score`는 곡별 교차 엔트로피의
중앙값이고, 중앙값을 내기 전 벡터가 곡별 폭이다. **같은 코퍼스를 다르게 뽑은 것이므로
곡으로 짝지을 수 있다** — 그러면 곡 사이 변동이 차이에서 지워진다 (D-0311).

**판정은 `PairedGap`이 한다** (D-0327). 차이·오차·`t`의 정본은 하나이고 여기서
베끼지 않는다 — 같은 식이 다섯 곳에 생기는 것이 이 저장소가 되풀이해 맞은 부류다.

### 무엇이 오르면 좋은 것인가

폭은 **클수록** 좋다. `uniform`(아무것도 모름)과 `oracle`(뒷반쪽으로 뒷반쪽을 맞힘)
사이가 넓다는 것은 **곡 고유 정보가 들어갈 자리가 넓다**는 뜻이다. 그래서 「중앙값이
평균보다 낫다」는 **폭의 차이가 양수이고 `t`가 문턱을 넘는 것**이다.

**질 수 있다** (O-25 (2)) — 중앙값이 창별 잡음을 깎으면서 **신호도 같이 깎으면** 폭이
준다.

### (b)는 이미 기각됐다 — 이 자가 그것을 뒤집으면 안 된다

**D-0337이 이 파일을 지을 때 그것을 몰랐다.** D-0065가 **272판 전에** 같은 200곡을
다시 뽑아 쟀고 폭이 0.0187 → **0.0198**이었다. D-0064가 등록한 기준은 **0.031**(K-K
장조 폭 0.0616의 절반)이고 **3분의 2에도 못 미쳐 (b)를 기각했다.**

그래서 짝지은 `t`만 보면 안 된다. **1004곡이면 +0.0011짜리 차이도 `t`를 넘길 수
있고**, 그러면 이 자가 「넓어졌다」고 찍어 **닫힌 판정을 느슨한 자로 되살린다.**
문턱을 결과에 맞춰 고르는 것이 D-0058이라면, 이쪽은 **사전 등록된 문턱이 있는데 다른
문턱을 들이대는 것**이다 — 같은 병의 다른 얼굴이다.

판정은 **둘을 다 넘어야** 한다 (D-0338).

1. 짝지은 차이가 잡음을 넘는다 (`PairedGap.beats`) — D-0065가 **못 한 것**이다.
   그쪽은 0.0187 대 0.0198을 **단일 수로** 비교했고 그 차이의 오차를 안 쟀다.
2. 폭 자체가 **사전 등록 기준 `ACHIEVABLE_FLOOR`를 넘는다** — D-0064가 등록했다.

### 그래서 이 파일은 무엇에 쓰나

**(b)를 다시 묻는 자가 아니다.** 남은 쓸모는 둘이다.

- **D-0065를 1004곡에서 재현한다.** 그 판은 *"그때의 산출물이 안 남았다"*(D-0253)고
  적었다 — **재현이 없는 판정이다.** 산출물 둘이 지금 남아 있다.
- **(a) 타악 분리의 기준선을 짝지은 오차와 함께 세운다.** D-0065가 *"(a)의 기준선은
  mean 쪽 0.0187이다"*라 적었고 **(a)의 사전 등록 기준은 착수할 때 정한다**고 미뤘다.
  그 기준을 정할 때 **차이의 오차가 얼마인지 알고 정해야 한다.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.application.compare_output import PairedGap, gap_of
from hathor.domain.services.harmony_prior import achievable_widths

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hathor.domain.services.harmony_prior import HalfChroma, PriorCondition

ACHIEVABLE_FLOOR = 0.031
"""D-0064가 착수 전에 등록한 문턱. **판정에 쓰지 않는다 — 참조선이다** (D-0338).

    달성 가능 폭이 0.0187 → 0.031 미만이면 (b)를 기각한다.
    0.031은 K-K 장조 폭(0.0616)의 절반이다.

**그 문턱은 이 표본에 못 쓴다.** 1004곡 **평균** 집계의 폭이 이미 **0.0471**이고
(K-K 폭의 76.5%) 중앙값을 넣기 전에 넘는다. 판정 조건으로 걸면 **아무것도 안
막는다** — 더 나쁘게는 **자료가 적을 때만 막는 자**가 되고 그것은 거꾸로다 (GR-0.8).

D-0338이 이것을 `widens`에서 뺐다. 화면에는 **찍는다** — 두 수가 2.5배 다른 것
자체가 봐야 할 사실이고, D-0063의 0.0187이 지금 수인 것처럼 읽히면 안 된다.
"""

REFERENCE_WIDTH = 0.0187
"""D-0063이 **200곡**에서 잰 달성 가능 폭 (전체 믹스 · 배음 0).

1004곡 전수에서 **0.0471**이 나왔다. 조건 표기는 같은데 2.5배다 — `oracle`이
2.4662에서 2.4378로 내려갔고, 그것은 **1004곡의 크로마가 더 뾰족하다**는 뜻이다.

**표본 요동인지 그 200곡이 코퍼스를 안 대표했는지 모른다.** D-0065가 *"그때의
산출물이 안 남았다"*(D-0253)고 적어서 **직접 맞댈 수가 없다.** `width_draws()`가
1004곡에서 200곡씩 뽑아 **이 수가 그 분포 안에 드는지** 묻는다.
"""


@dataclass(frozen=True, slots=True)
class AggregationComparison:
    """두 추출의 곡별 폭과 그 차이. **앞이 중앙값, 뒤가 평균이다.**"""

    median_widths: tuple[float, ...]
    mean_widths: tuple[float, ...]
    songs: tuple[str, ...]

    @property
    def paired_gap(self) -> PairedGap:
        """**정본은 `compare_output`에 하나다** (D-0327)."""
        return gap_of(self.median_widths, self.mean_widths)

    @property
    def median_width(self) -> float | None:
        """중앙값 추출의 폭. **없는 것을 0이라 하지 않는다** (GR-0.5)."""
        return float(np.median(self.median_widths)) if self.median_widths else None

    @property
    def mean_width(self) -> float | None:
        return float(np.median(self.mean_widths)) if self.mean_widths else None

    @property
    def clears_floor(self) -> bool:
        """앞쪽 폭이 **D-0064가 등록한 절대 기준**을 넘나 (D-0338).

        **짝지은 차이만으로는 모자란다.** 1004곡이면 +0.0011짜리 차이도 `t`를 넘길 수
        있고, 그러면 D-0065가 기각한 (b)가 느슨한 자로 되살아난다.
        """
        return self.median_width is not None and self.median_width >= ACHIEVABLE_FLOOR

    @property
    def widens(self) -> bool:
        """짝지은 차이가 잡음을 넘나. 문턱은 `PAIRED_T_FLOOR`다 (D-0327).

        **이것이 이 자가 재는 것 전부다** (D-0338). `ACHIEVABLE_FLOOR`를 여기 걸었다가
        뺐다 — 1004곡 평균이 이미 그 문턱을 넘어서 **걸면 아무것도 안 막고**, 자료가
        적을 때만 막는 거꾸로 된 자가 된다.

        **(b)를 판정하지 않는다.** D-0065가 272판 전에 기각했다.
        """
        return self.paired_gap.beats


def song_widths(observations: Sequence[HalfChroma], condition: PriorCondition) -> dict[str, float]:
    """곡별 달성 가능 폭. **식은 도메인에 하나다** (`achievable_widths` · D-0339).

    여기 식을 베꼈더니 `_stack`의 전처리 셋이 전부 빠졌고 **손잡이 셋이 동시에 안
    걸렸다** — `--harmonic`을 0에서 1.0까지 돌려도 소수점 넷째 자리까지 같았다.
    """
    return achievable_widths(observations, condition)


@dataclass(frozen=True, slots=True)
class WidthDraws:
    """작은 표본에서 폭이 얼마나 흔들리나 (D-0338).

    **수는 전부 여기서 낸다.** 처음에 분위와 구간을 CLI에서 냈고 계약 검사가 잡았다 —
    *"표시 계층이 계산하지 않는다"*. 화면은 꼴만 입힌다.
    """

    widths: tuple[float, ...]
    size: int
    target: float
    whole: float

    @property
    def median(self) -> float:
        """뽑기들의 폭 중앙값. **`whole`과 크게 다르면 그것부터 본다.**"""
        return float(np.median(np.asarray(self.widths, dtype=np.float64)))

    @property
    def interval(self) -> tuple[float, float]:
        """뽑기 폭의 95% 구간."""
        low, high = np.quantile(np.asarray(self.widths, dtype=np.float64), [0.025, 0.975])
        return float(low), float(high)

    @property
    def quantile(self) -> float:
        """`target`보다 작은 뽑기의 비율. **0이나 1이면 분포 밖이다.**"""
        below = sum(1 for value in self.widths if value < self.target)
        return below / len(self.widths)

    @property
    def inside(self) -> bool:
        """**`target`이 뽑기 분포 안에 드나.** 양쪽 2.5%를 밖으로 본다."""
        return 0.025 <= self.quantile <= 0.975

    def reading(self) -> str:
        """**이 판에서 고른 해석이 아니다** — 분포 밖이면 요동으로 설명이 안 된다."""
        if self.inside:
            return f"**표본 요동이다.** {self.target:.4f}가 {self.size}곡 뽑기 분포 안에 든다"
        return (
            f"**요동으로 설명이 안 된다.** {self.target:.4f}가 {self.size}곡 뽑기의 "
            f"{self.quantile:.1%} 분위이며 분포 밖이다 — 표본이 달랐거나 코드가 달랐다"
        )


def width_draws(
    observations: Sequence[HalfChroma],
    condition: PriorCondition,
    *,
    size: int,
    draws: int,
    target: float = REFERENCE_WIDTH,
    seed: int = 0,
) -> WidthDraws | None:
    """전수에서 `size`곡씩 `draws`번 뽑아 **달성 가능 폭의 분포**를 낸다.

    ### 왜 이것이 필요했나

    D-0063이 200곡에서 0.0187을, 1004곡 전수가 **0.0471**을 냈다. 조건 표기가 같은데
    2.5배다. **두 수를 직접 맞댈 수 없다** — 그때의 산출물이 안 남았다 (D-0253).

    맞댈 수 없으면 **지금 자료 안에서 재현**한다. 200곡 뽑기의 폭이 0.0187 근처까지
    흔들리면 그것은 요동이고, 안 흔들리면 **D-0063의 표본이 코퍼스를 안 대표했거나
    그 사이 코드가 바뀐 것**이다. 어느 쪽이든 **0.031 문턱을 못 쓴다**는 결론은 같고,
    바뀌는 것은 D-0063의 수를 어디까지 인용할 수 있는가다.

    **복원 없이 뽑는다.** D-0063은 200곡을 한 번 골랐고 같은 곡을 두 번 안 넣었다.
    """
    widths = song_widths(observations, condition)
    if len(widths) < size:
        return None
    values = np.asarray(list(widths.values()), dtype=np.float64)
    rng = np.random.default_rng(seed)
    drawn = [
        float(np.median(values[rng.choice(values.size, size=size, replace=False)]))
        for _ in range(draws)
    ]
    return WidthDraws(widths=tuple(drawn), size=size, target=target, whole=float(np.median(values)))


def compare(
    median: Sequence[HalfChroma],
    mean: Sequence[HalfChroma],
    condition: PriorCondition,
) -> AggregationComparison:
    """**곡으로 짝짓는다.** 한쪽에만 있는 곡은 뺀다 — 짝이 아니면 짝지은 차이가 아니다."""
    left = song_widths(median, condition)
    right = song_widths(mean, condition)
    shared = sorted(set(left) & set(right))
    return AggregationComparison(
        median_widths=tuple(left[name] for name in shared),
        mean_widths=tuple(right[name] for name in shared),
        songs=tuple(shared),
    )
