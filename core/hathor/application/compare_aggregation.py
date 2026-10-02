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

### 폭이 재는 것은 뾰족함이다 — 곡 고유성이 아니다 (D-0340)

D-0337이 여기 적었던 문장은 **거짓이었다.**

> `uniform`과 `oracle` 사이가 넓다는 것은 **곡 고유 정보가 들어갈 자리가 넓다**는
> 뜻이다.

반대 방향 합성 둘로 갈랐다 (O-25 여섯째 줄 · D-0303).

| 코퍼스 | 폭 중앙값 |
|---|---|
| **뾰족하고 곡끼리 완전히 똑같다** — 곡 고유성 0 | **0.7446** |
| 평평하고 곡끼리 다르다 — 고유성은 있다 | **0.0010** |
| 뾰족하고 곡끼리 다르다 | 0.8203 |

**곡 고유성을 0으로 만들어도 폭이 0.74다.** 전부 넣어야 10% 늘고, 뾰족함을 빼면
**700배 줄어든다.** `oracle`은 뒷반쪽으로 뒷반쪽을 맞히므로 **뾰족한 벡터는 자기
자신을 잘 맞힌다** — 그것은 정보가 아니다.

실물이 같은 말을 한다. `--harmonic`을 0 → 1.0으로 돌리면 폭이 **0.0471 → 0.4238**,
**9배**다. 코퍼스는 한 글자도 안 바뀌었다. **손잡이로 9배 움직이는 양은 「정보가
들어갈 자리」가 아니다.**

**그래서 절대 문턱을 안 둔다.** D-0064가 등록한 0.031과 D-0063의 0.0187을 상수로
들고 있었는데 **둘을 지웠다** — 전자는 뾰족함 문턱이라 배음 하나로 넘고, 후자는
**감산이 안 걸린 크로마**의 수라 지금 수 옆에 찍으면 거짓 비교다.

### 그러면 무엇이 안 깨지나

- **`self` 대 `corpus`는 다른 양이다.** 곡 고유성은 λ*와 낙폭이 재고, 그쪽은 귀무
  낙폭 0.0000이라는 **자기 대조를 갖는다** (D-0062 · 1004곡에서 λ*=0.90).
  **폭에는 그 대조가 없었고 그것이 이 판에서 드러난 구멍이다.**
- **D-0063의 「K-K 장조 폭 0.0616 대비」는 유효하다.** K-K 폭도 그 프로파일의
  뾰족함이므로 **뾰족함 대 뾰족함**이다. 이름이 틀렸고 비교는 맞다.
- **D-0065의 (b) 기각도 유효하다.** D-0064의 가설은 *"전곡 평균이 평평함의 근인"*
  이었고 폭은 바로 평평함을 잰다 — **그 질문에 대해서는 맞는 자였다.**

### 그래서 이 파일은 무엇에 쓰나

**두 집계의 뾰족함을 짝지어 맞댄다.** (b)는 D-0065가 기각했고 이 자가 그것을 안
뒤집는다. 보태는 것은 **차이의 오차**(그 판에 없었다)와 **1004곡 재현**이다
(그 판은 산출물이 안 남았다 · D-0253).
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
        """짝지은 차이가 잡음을 넘나. 문턱은 `PAIRED_T_FLOOR`다 (D-0327).

        **이것이 이 자가 재는 것 전부다.** D-0338이 D-0064의 0.031을 여기 걸었고
        D-0340이 **상수째로 지웠다** — 폭은 `--harmonic` 하나로 9배 움직이므로
        **절대 문턱을 걸 수 있는 양이 아니다.**

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
        """**해석을 고르지 않는다** — 분포 밖이면 요동으로 설명이 안 된다는 것뿐이다."""
        if self.inside:
            return f"**뽑기로 설명된다.** {self.target:.4f}가 {self.size}곡 뽑기 분포 안에 든다"
        return (
            f"**뽑기로 설명이 안 된다.** {self.target:.4f}가 {self.size}곡 뽑기의 "
            f"{self.quantile:.1%} 분위이며 분포 밖이다 — **조건이 달랐다는 뜻이다**"
        )


def width_draws(
    observations: Sequence[HalfChroma],
    condition: PriorCondition,
    *,
    size: int,
    draws: int,
    target: float | None = None,
    seed: int = 0,
) -> WidthDraws | None:
    """전수에서 `size`곡씩 `draws`번 뽑아 **폭의 분포**를 낸다.

    ### 기본 과녁이 전수 폭이다 (D-0340)

    D-0338은 과녁을 **D-0063의 0.0187로 박아** 뒀다. 그 수는 **배음 감산이 안 걸린
    크로마**의 것이고 지금 산출물은 **0.5가 걸린** 것이다 — 비교 대상이 아니었고,
    「분포 밖」이 **표본 얘기로 읽혔다.** 상수를 지웠다.

    과녁을 안 주면 **전수 폭**을 쓴다. 그러면 이 함수가 답하는 질문이
    *"작은 표본이 전수를 재현하나"*로 바뀌고, 그것은 조건에 안 묶인 질문이다.
    옛 수와 맞대려면 **그 수의 조건을 확인하고 `target`을 직접 준다.**

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
    whole = float(np.median(values))
    return WidthDraws(
        widths=tuple(drawn),
        size=size,
        target=whole if target is None else target,
        whole=whole,
    )


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
