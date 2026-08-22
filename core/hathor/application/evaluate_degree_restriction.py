"""다이어토닉 6도수 제한이 버리는 몫을 잰다 (O-31 · D-0083).

### 왜 필요한가

`degree_weights`는 12칸 사전에서 **선법의 다이어토닉 근음 6칸만 골라 다시
정규화한다.** 나머지 6칸은 버린다.

D-0063이 이 제한을 채택한 근거는 **버리는 쪽이 균등 성분이라 걷어내면 대비가
선명해진다**였다. 그때 재지 않은 것이 있다 — **버리는 6칸이 곡 고유 대비도 함께
담고 있는가.**

D-0082에서 그 자국이 나왔다. 조건화 이득 3.14배는 전변동 거리로 1.77배에
해당하는데 실측 극한 비는 **1.51배**였다. 차이가 여기서 나올 수 있다.

### 무엇을 재는가 — 전변동은 칸별로 정확히 쪼개진다

`TV = 0.5 * sum|p - q|`는 칸별 절댓값의 합이므로 **다이어토닉 6칸과 비음계 6칸의
기여로 정확히 나뉜다.** 모형이 필요 없다.

`비음계 몫 = sum_비음계|p - q| / sum_전체|p - q|`

칸 수로만 보면 6/12 = 0.5가 기준선이다. **그러나 그것은 기준선이 아니다** — 사전
질량이 다이어토닉 쪽에 몰려 있으면 몫도 자연히 낮아진다. 그래서 **뾰족함과 질량
분포를 그대로 두고 어느 칸인지만 지우는 치환 귀무선**이 필요하다.

| 선 | 사전 | 무엇을 재는가 |
|---|---|---|
| `observed` | 참조곡 A, B | 재려는 것 |
| `shuffled` | 같은 사전의 **도수를 치환** | **귀무선.** 질량 분포는 같고 칸 정체성만 없다 |

실측 몫이 귀무 몫보다 **작으면** 비음계 칸이 곡 고유 대비를 덜 담는다는 뜻이고,
**D-0063의 판단이 옳았던 것이다.** 같으면 버리는 것이 손실이다.

### 순위상관은 판정에 안 쓴다

`d12`(12칸 거리)와 `d6`(제한 후 거리)의 스피어만 상관을 함께 내지만 **진단이다.**
탐색에서 비음계 칸에 곡 고유 성분이 전혀 없을 때도 0.54였고 가득 있을 때도
0.50이었다 — **갈리지 않는 지표는 판정에 쓸 수 없다** (O-25 (2)).

### 쌍은 D-0082와 같은 것을 쓴다

`OutputCondition`의 쌍 추첨을 그대로 받는다. 같은 쌍이어야 D-0082의 극한값과
나란히 읽을 수 있다. **비교선을 새로 뽑으면 두 기록의 수를 이을 수 없다.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.application.evaluate_harmony_output import (
    EvaluateHarmonyOutput,
    Histogram,
    OutputCondition,
    ReferencePrior,
    total_variation,
)
from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.domain.value_objects.key import Mode
from hathor.engines.compose.harmony_generator import (
    DIATONIC_ROOT_SEMITONES,
    degree_weights,
)


def off_scale_indices(mode: Mode) -> tuple[int, ...]:
    """버려지는 칸. **선법마다 다르다** — 장조 기준으로 박으면 단조에서 틀린다."""
    roots = set(DIATONIC_ROOT_SEMITONES[mode])
    return tuple(index for index in range(DEGREE_COUNT) if index not in roots)


def off_scale_share(left: Histogram, right: Histogram, mode: Mode) -> float:
    """두 사전의 전변동 중 **비음계 칸이 차지하는 몫.**

    전변동은 칸별 절댓값의 합이므로 나눗셈 하나로 정확히 갈린다. 거리가 0이면
    나눌 것이 없으므로 0을 낸다.
    """
    gap = np.abs(left - right)
    total = float(gap.sum())
    if total <= 0.0:
        return 0.0
    return float(gap[list(off_scale_indices(mode))].sum() / total)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    """순위 상관. **`scipy`를 쓰지 않는다** — 광인사는 ML 추가 의존을 안 깐다."""
    if len(left) < 3:
        return 0.0
    ranks = [
        np.argsort(np.argsort(np.asarray(values))).astype(np.float64) for values in (left, right)
    ]
    if ranks[0].std() == 0 or ranks[1].std() == 0:
        return 0.0
    return float(np.corrcoef(ranks[0], ranks[1])[0, 1])


def _weights(prior: Histogram, mode: Mode) -> Histogram:
    return np.asarray(
        degree_weights(tuple(float(value) for value in prior), mode), dtype=np.float64
    )


@dataclass(frozen=True, slots=True)
class RestrictionLine:
    """비교선 하나. **쌍별 값을 들고 있다** — 짝지은 비교에 필요하다."""

    name: str
    shares: tuple[float, ...]
    distances_full: tuple[float, ...]
    distances_restricted: tuple[float, ...]
    masses: tuple[float, ...]

    @property
    def mean_share(self) -> float:
        return float(np.mean(self.shares)) if self.shares else 0.0

    @property
    def mean_mass(self) -> float:
        """비음계 칸이 사전 질량에서 차지하는 비율. **버리는 양 자체다.**"""
        return float(np.mean(self.masses)) if self.masses else 0.0

    @property
    def standard_error(self) -> float:
        if len(self.shares) < 2:
            return 0.0
        return float(np.std(self.shares, ddof=1) / np.sqrt(len(self.shares)))

    @property
    def survival(self) -> float:
        """제한 후 거리 / 제한 전 거리. 1보다 크면 정규화가 대비를 키운 것이다."""
        full = float(np.mean(self.distances_full)) if self.distances_full else 0.0
        if full <= 0.0:
            return 0.0
        return float(np.mean(self.distances_restricted)) / full

    @property
    def rank_agreement(self) -> float:
        """진단이다. **판정에 쓰지 않는다** — 갈리지 않는다."""
        return _spearman(self.distances_full, self.distances_restricted)


@dataclass(frozen=True, slots=True)
class RestrictionReport:
    label: str
    condition: OutputCondition
    reference_count: int
    lines: tuple[RestrictionLine, ...]

    def line(self, name: str) -> RestrictionLine:
        for item in self.lines:
            if item.name == name:
                return item
        raise KeyError(f"그런 비교선이 없다: {name}")

    @property
    def gap(self) -> float:
        """실측 몫에서 귀무 몫을 뺀 값. **음수면 제한이 옳다.**"""
        return self.line("observed").mean_share - self.line("shuffled").mean_share

    @property
    def win_rate(self) -> float:
        """쌍마다 실측 몫이 귀무보다 작았는가. 평균 한 점의 우연이 아님을 본다."""
        observed = np.asarray(self.line("observed").shares)
        null = np.asarray(self.line("shuffled").shares)
        if observed.size == 0 or observed.size != null.size:
            return 0.0
        return float(np.mean(observed < null))

    @property
    def restriction_is_sound(self) -> bool:
        """**사전 등록한 판정 규칙이다** (GR-6.5). 결과를 보고 고치지 않는다.

        1. 실측 비음계 몫이 치환 귀무선보다 **작다.**
        2. **쌍 과반에서** 그렇다.

        둘 다 넘으면 버리는 6칸이 곡 고유 대비를 덜 담는다는 뜻이고 **D-0063의
        판단이 옳았던 것이다.** 넘지 못하면 제한이 곡 정보를 함께 버리고 있으며,
        순서(O-32)를 건드리기 전에 어휘 표현부터 고쳐야 한다.

        **질 수 있다.** 탐색에서 비음계 칸에 곡 고유 성분을 채워 넣자 차이가
        -0.208에서 +0.003까지 단조로 올라왔다.
        """
        return self.gap < 0.0 and self.win_rate > 0.5


class EvaluateDegreeRestriction:
    """다이어토닉 제한이 버리는 몫을 잰다. **쌍은 D-0082와 같은 것을 쓴다.**"""

    def __init__(self, condition: OutputCondition | None = None) -> None:
        self._condition = condition if condition is not None else OutputCondition()

    def run(self, references: Sequence[ReferencePrior], label: str) -> RestrictionReport:
        settings = self._condition
        if len(references) < 2:
            raise ValueError(f"참조곡이 2개 이상 필요하다: {len(references)}")

        mode = settings.key.mode
        off = list(off_scale_indices(mode))
        pairs = EvaluateHarmonyOutput(settings).pair_indices(len(references))
        priors: list[Histogram] = [np.asarray(item.prior, dtype=np.float64) for item in references]

        generator = np.random.default_rng(settings.seed)
        shuffled: list[Histogram] = [generator.permutation(vector) for vector in priors]

        def measure(name: str, table: list[Histogram]) -> RestrictionLine:
            shares, full, restricted, masses = [], [], [], []
            for left, right in pairs:
                a, b = table[left], table[right]
                shares.append(off_scale_share(a, b, mode))
                full.append(total_variation(a, b))
                restricted.append(total_variation(_weights(a, mode), _weights(b, mode)))
                masses.append(float(a[off].sum()))
            return RestrictionLine(
                name=name,
                shares=tuple(shares),
                distances_full=tuple(full),
                distances_restricted=tuple(restricted),
                masses=tuple(masses),
            )

        return RestrictionReport(
            label=label,
            condition=settings,
            reference_count=len(references),
            lines=(measure("observed", priors), measure("shuffled", shuffled)),
        )
