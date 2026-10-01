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
준다. 그때는 차이가 음수로 나오고 D-0064의 (b)는 기각된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.application.compare_output import PairedGap, gap_of
from hathor.domain.services.harmony_prior import (
    DegreeMatrix,
    cross_entropy,
    rotate_to_degrees,
    smooth,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hathor.domain.services.harmony_prior import HalfChroma, PriorCondition


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
    def widens(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0337).

        폭이 넓어졌고 짝지은 `t`가 문턱을 넘는다. 문턱은 `PAIRED_T_FLOOR`이며
        **이 판에서 고르지 않았다** — D-0327이 합성 양방향으로 정한 값이다.
        """
        return self.paired_gap.beats


def song_widths(observations: Sequence[HalfChroma], condition: PriorCondition) -> dict[str, float]:
    """곡별 달성 가능 폭 `CE(tail, uniform) - CE(tail, smooth(tail))`.

    **중앙값을 내기 전 벡터다.** `compare_priors`가 같은 두 양을 쓰고 중앙값으로
    접는다 — 여기서는 접지 않고 곡 이름에 붙여 낸다.
    """
    kept = [item for item in observations if item.is_confident]
    if not kept:
        return {}
    rotated = [
        rotate_to_degrees(np.asarray(item.tail, dtype=np.float64), item.tonic_pitch_class)
        for item in kept
    ]
    tails: DegreeMatrix = np.stack(rotated)
    uniform: DegreeMatrix = np.full_like(tails, 1.0 / tails.shape[1])
    gap = cross_entropy(tails, uniform) - cross_entropy(tails, smooth(tails, condition))
    return {item.source_key: float(value) for item, value in zip(kept, gap, strict=True)}


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
