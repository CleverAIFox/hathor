"""**같은 쌍을 빼서 만든 차이 하나** — 두 판정의 정본 (D-0311 · D-0327).

### 왜 이 파일이 있나

`evaluate_harmony_output`에 판정이 셋 있었고 **하나만 오차를 봤다.**

| 판정 | 규칙 | 오경보율 |
|---|---|---|
| `carries_order` | `초과 > 0` **and `t > 2`** | — |
| `transmits_prior_contrast` | `이득 > 0` and `승률 > 0.5` | **50%** |
| 어휘 비교 (CLI에 박혀 있었다) | `이득 > 0` and `승률 > 0.5` | **50%** |

**승률 0.5는 문턱이 아니라 동전의 중앙값이다.** 진짜 차이가 0이면 이득의 부호가
반반이고 승률도 반반이며, 둘은 같은 방향으로 움직이므로 **둘을 곱해도 반이다.**

D-0095가 이미 *"승률 문턱이 없어 잡음으로도 통과한다. 실측 51.0%는 동전 던지기다"*
라고 진단해 놓고 **동전의 중앙값을 문턱으로 삼았다.** 그 뒤 실물에서 승률 52.0%로
또 통과했다 (D-0327).

### 문턱 2.0은 고른 것이 아니다

실물 퍼짐을 재현한 합성 코퍼스 둘에서 1000곡 24회씩 쟀다 (O-25 (4)·(5)·(6)).

| 문턱 | 음성 통과 | 양성 통과 |
|---|---|---|
| 이득 > 0 and 승률 > 0.5 | **50%** | 100% |
| `t >= 1.5` | 8% | 100% |
| **`t >= 2.0`** | **4%** | **100%** |
| `t >= 2.5` | 0% | 92% |
| `t >= 3.0` | 0% | 62% |

2.0은 **`carries_order`가 이미 쓰던 값이다.** 잘 나오는 값을 찾아 돌린 것이 아니라
같은 파일에 이미 서 있던 문턱에 나머지 둘을 맞췄다 (D-0058).
### 판정 셋이 한 자리에 산다

`SourceComparison`(O-29 닫힘 D-0082) · `VocabularyComparison`(O-36 닫힘 D-0097)이
여기 있다. **흩어져 있어서
같은 결함이 둘에 따로 살았다** — 한 곳만 고쳐지는 날이 온다 (D-0317 · D-0323 · D-0326).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hathor.application.evaluate_harmony_output import OutputReport

PAIRED_T_FLOOR = 2.0
"""짝지은 차이가 오차로 설명되지 않는다고 말할 문턱 (D-0327).

**`carries_order`가 이미 쓰던 값이다** (D-0102). 새로 고르면 그것이 D-0058이다.
"""


@dataclass(frozen=True, slots=True)
class PairedGap:
    """같은 쌍·같은 시드로 잰 두 줄의 차이.

    **선별 표준오차를 따로 내서 빼지 않는다** (D-0311). 두 줄은 같은 쌍에서 나왔으므로
    곡 사이 변동이 차이에서 지워진다 — 따로 재면 그 변동이 두 번 들어가 오차가 부풀고,
    부푼 오차는 **있는 신호를 없다고 말한다.**
    """

    target: tuple[float, ...]
    baseline: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.target) != len(self.baseline):
            raise ValueError(
                f"쌍 수가 다르면 짝지은 차이가 아니다: {len(self.target)} vs {len(self.baseline)}"
            )

    @property
    def differences(self) -> tuple[float, ...]:
        return tuple(float(value) for value in np.asarray(self.target) - np.asarray(self.baseline))

    @property
    def gain(self) -> float:
        values = self.differences
        return float(np.mean(values)) if values else 0.0

    @property
    def standard_error(self) -> float:
        """**둘 이하면 0을 낸다** — 오차를 못 잰 것이지 0인 것이 아니다 (GR-0.5)."""
        values = self.differences
        if len(values) < 2:
            return 0.0
        return float(np.std(values, ddof=1) / np.sqrt(len(values)))

    @property
    def t(self) -> float:
        """**오차를 못 재면 0이다.** 0으로 나누지 않고, 판정도 통과시키지 않는다."""
        error = self.standard_error
        return self.gain / error if error > 0.0 else 0.0

    @property
    def win_rate(self) -> float:
        """쌍마다 목표가 더 컸는가. **판정이 아니라 진단이다** (D-0327)."""
        values = self.differences
        return float(np.mean([value > 0.0 for value in values])) if values else 0.0

    @property
    def beats(self) -> bool:
        """**사전 등록한 판정 규칙이다.** 이득이 양수이고 `t >= 2`다.

        승률은 안 본다 — 진짜 차이가 0일 때 승률이 과반일 확률이 **절반**이라
        규칙을 조이지 못하면서 읽는 사람에게는 근거가 하나 더 있는 것처럼 보인다.
        """
        return self.gain > 0.0 and self.t >= PAIRED_T_FLOOR


def gap_of(target: Sequence[float], baseline: Sequence[float]) -> PairedGap:
    """순서를 틀리기 쉬워 이름으로 못 박는다 — **앞이 목표, 뒤가 기준이다.**"""
    return PairedGap(target=tuple(target), baseline=tuple(baseline))


@dataclass(frozen=True, slots=True)
class SourceComparison:
    """두 사전 출처를 **같은 쌍·같은 시드로** 견준다. O-29의 본문이다 (닫힘 D-0082)."""

    baseline: OutputReport
    target: OutputReport

    def __post_init__(self) -> None:
        # **같은 쌍·같은 시드가 아니면 짝지은 비교가 아니다.** 곡 목록이 다르면
        # 쌍 추첨이 서로 다른 곡을 가리키고, 그러면 출처 차이인지 쌍 차이인지
        # 갈리지 않는다 — D-0033이 "쌍을 한 번 뽑아 모든 모드에 쓴다"고 정한 자리다.
        if self.baseline.reference_count != self.target.reference_count:
            raise ValueError(
                "두 출처의 참조곡 수가 다르다: "
                f"{self.baseline.reference_count} vs {self.target.reference_count}. "
                "같은 곡 집합으로 맞춰야 짝지은 비교가 성립한다"
            )
        if self.baseline.condition != self.target.condition:
            raise ValueError("두 출처의 조건이 다르다. 같은 조건 객체를 써야 한다")

    @property
    def paired_gap(self) -> PairedGap:
        """**차이·오차·t의 정본은 여기 하나다** (D-0327)."""
        return gap_of(self.target.line("paired").distances, self.baseline.line("paired").distances)

    @property
    def gain(self) -> float:
        return self.paired_gap.gain

    @property
    def limit_gain(self) -> float:
        return self.target.line("paired").mean_limit - self.baseline.line("paired").mean_limit

    @property
    def win_rate(self) -> float:
        """쌍마다 목표 출처가 더 갈렸는가. **진단이다** — 판정은 `t`가 한다 (D-0327)."""
        return self.paired_gap.win_rate

    @property
    def standard_error(self) -> float:
        return self.paired_gap.standard_error

    @property
    def t(self) -> float:
        return self.paired_gap.t

    @property
    def transmits_prior_contrast(self) -> bool:
        """**사전 등록한 판정 규칙이다.** 사전 대비가 커지면 출력 차이도 커지는가.

        이득이 양수이고 **짝지은 차이의 `t`가 2 이상**이다 (D-0327).

        **예전에는 «승률 과반»이었고 그것은 문턱이 아니었다** — 진짜 차이가 0인 합성
        코퍼스에서 **50%가 통과했다.** 같은 규칙을 쓰던 어휘 비교가 실물에서 이득
        +0.0011 · 승률 52.0%로 통과하는 것을 보고 잡았다.

        넘지 못하면 **문턱 추출이 사전 대비를 삼킨 것이며**, 사전을 더 뾰족하게
        만드는 축(O-27 · D-0074)은 출력에 닿지 않는다.
        """
        return self.paired_gap.beats


@dataclass(frozen=True, slots=True)
class VocabularyComparison:
    """세 어휘를 **같은 쌍·같은 시드로** 견준다. O-36의 본문이다 (D-0094 · D-0327).

    **CLI에 박혀 있었다.** 그래서 오차가 붙지 않았고, `paired` 선 옆에 표준오차가
    있는데도 어휘 표에는 한 칸도 없었다. 판정이 화면 쪽에 있으면 검사를 못 붙인다.
    """

    base: OutputReport
    control: OutputReport
    mixture: OutputReport

    @property
    def free_gain(self) -> float:
        """**칸이 늘어 공짜로 오른 몫.** 차용이 전혀 없어도 오른다 (D-0094)."""
        return self.control.line("paired").mean_distance - self.base.line("paired").mean_distance

    @property
    def paired_gap(self) -> PairedGap:
        """차용이 번 몫. **`base`가 아니라 `control`에서 뺀다** — 칸 수를 맞춘다."""
        return gap_of(self.mixture.line("paired").distances, self.control.line("paired").distances)

    @property
    def gain(self) -> float:
        return self.paired_gap.gain

    @property
    def win_rate(self) -> float:
        return self.paired_gap.win_rate

    @property
    def standard_error(self) -> float:
        return self.paired_gap.standard_error

    @property
    def t(self) -> float:
        return self.paired_gap.t

    @property
    def beats_control(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0327). 이득이 양수이고 `t >= 2`다.

        **질 수 있다** (O-25 (2)) — 실물 1004곡에서 이득 +0.0011 · 승률 52.0%로
        졌고, 그것이 이 규칙을 고치게 만든 자료다.
        """
        return self.paired_gap.beats
