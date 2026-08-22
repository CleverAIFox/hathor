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
| `shuffled` | 12칸 **전체 치환** | D-0083의 귀무선. **질량 교란이 있다** — 아래 |
| `within` | 다이어토닉·비음계 **조 안에서만 치환** | **질량이 보존되는 귀무선** (D-0084) |

### 전체 치환은 질량까지 바꾼다 (D-0084)

D-0083은 `shuffled`만 두고 "뾰족함이 정확히 같고 칸 정체성만 사라진다"고 적었다.
**틀렸다.** 12칸을 통째로 뒤섞으면 비음계 칸이 붙드는 **질량이 달라진다.**

1004곡 실측에서 비음계 질량이 실측 0.4047 대 전체 치환 0.5097이었다. 전변동 기여는
질량에 대략 비례하므로 **몫 차이 -0.0813의 대부분을 질량 차이 -0.1050이 만들었다.**
질량으로 기대되는 몫은 0.4105인데 실측이 0.4357로 **오히려 높았다.**

**D-0062가 경고한 부류에 다시 빠진 것이다** — 이겼을 때 정보 때문인지 다른 것
때문인지 갈리지 않는 귀무선이었다.

`within`은 다이어토닉 6칸 안에서, 비음계 6칸 안에서 **각각** 치환한다. 조별 질량이
정확히 보존되고 **어느 칸인지만** 사라진다. 남는 차이는 순수하게 **"두 곡이 같은
비음계 자리를 강조하는가"**다.

탐색에서 비음계 질량을 0.35와 0.50으로 바꿔 보면 `shuffled` 차이는 -0.159에서
-0.000까지 흔들리는데 `within` 차이는 **0 교차점이 질량과 무관하다.**

실측 몫이 `within`보다 **작으면** 곡들이 같은 비음계 자리에서 닮았다는 뜻이고
버려도 곡 정체성을 잃지 않는다. **크거나 같으면 버리는 칸이 곡을 가른다.**

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

SCALE_SEMITONES: dict[Mode, tuple[int, ...]] = {
    Mode.MAJOR: (0, 2, 4, 5, 7, 9, 11),
    Mode.MINOR: (0, 2, 3, 5, 7, 8, 10),
}
"""온음계 음. **근음 집합이 아니다** (D-0085).

`DIATONIC_ROOT_SEMITONES`는 **화음 근음** 6개이고 이것은 **음계 음** 7개다. 장조에서
둘의 차이는 반음 11 — C장조의 B, 이끔음이다. 감화음(vii°)을 코드 풀에서 뺐다는
이유로 **음 자체가 버려지고 있었다.** 단조에서는 반음 2(ii°의 근음)가 같은 처지다.
"""


def off_scale_indices(mode: Mode) -> tuple[int, ...]:
    """버려지는 칸. **선법마다 다르다** — 장조 기준으로 박으면 단조에서 틀린다."""
    roots = set(DIATONIC_ROOT_SEMITONES[mode])
    return tuple(index for index in range(DEGREE_COUNT) if index not in roots)


def scale_but_discarded(mode: Mode) -> tuple[int, ...]:
    """버려지는 칸 중 **온음계 음.** 장조는 반음 11(이끔음), 단조는 반음 2다."""
    scale = set(SCALE_SEMITONES[mode])
    return tuple(index for index in off_scale_indices(mode) if index in scale)


def chromatic_indices(mode: Mode) -> tuple[int, ...]:
    """버려지는 칸 중 **진짜 반음계 음** 5개."""
    scale = set(SCALE_SEMITONES[mode])
    return tuple(index for index in off_scale_indices(mode) if index not in scale)


def cell_share(left: Histogram, right: Histogram, cells: Sequence[int]) -> float:
    """두 사전의 전변동 중 **지정한 칸들이 차지하는 몫.**

    전변동은 칸별 절댓값의 합이므로 나눗셈 하나로 정확히 갈린다. 거리가 0이면
    나눌 것이 없으므로 0을 낸다.
    """
    gap = np.abs(left - right)
    total = float(gap.sum())
    if total <= 0.0:
        return 0.0
    return float(gap[list(cells)].sum() / total)


def off_scale_share(left: Histogram, right: Histogram, mode: Mode) -> float:
    """버려지는 칸 전체의 몫."""
    return cell_share(left, right, off_scale_indices(mode))


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

    scale_shares: tuple[float, ...] = ()
    """버려지는 칸 중 **온음계 음**이 낸 몫 (D-0085)."""
    chromatic_shares: tuple[float, ...] = ()
    """버려지는 칸 중 **진짜 반음계 음**이 낸 몫."""

    @property
    def mean_scale_share(self) -> float:
        return float(np.mean(self.scale_shares)) if self.scale_shares else 0.0

    @property
    def mean_chromatic_share(self) -> float:
        return float(np.mean(self.chromatic_shares)) if self.chromatic_shares else 0.0

    @property
    def share_per_mass(self) -> float:
        """몫을 질량으로 나눈 값. **1 근처면 질량에 비례해 갈린다는 뜻이다.**

        질량 교란을 눈으로 잡는 자리다 (D-0084). 실측이 귀무보다 크면 비음계 칸이
        질량 대비 **더** 갈린다.
        """
        mass = self.mean_mass
        return self.mean_share / mass if mass > 0 else 0.0

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

    def _gap(self, null: str) -> float:
        return self.line("observed").mean_share - self.line(null).mean_share

    def _win_rate(self, null: str) -> float:
        observed = np.asarray(self.line("observed").shares)
        other = np.asarray(self.line(null).shares)
        if observed.size == 0 or observed.size != other.size:
            return 0.0
        return float(np.mean(observed < other))

    @property
    def gap(self) -> float:
        """실측 몫에서 **전체 치환** 귀무 몫을 뺀 값 (D-0083).

        **이 값만 보면 안 된다** — 질량 교란이 있다 (D-0084).
        """
        return self._gap("shuffled")

    @property
    def win_rate(self) -> float:
        """쌍마다 실측 몫이 전체 치환보다 작았는가 (D-0083)."""
        return self._win_rate("shuffled")

    @property
    def mass_matched_gap(self) -> float:
        """실측 몫에서 **조 내 치환** 귀무 몫을 뺀 값. 질량이 보존된다 (D-0084)."""
        return self._gap("within")

    @property
    def mass_matched_win_rate(self) -> float:
        return self._win_rate("within")

    @property
    def off_scale_is_shared(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0084 · GR-6.5). 결과를 보고 고치지 않는다.

        1. 실측 비음계 몫이 **조 내 치환** 귀무선보다 작다.
        2. **쌍 과반에서** 그렇다.

        둘 다 넘으면 곡들이 **같은 비음계 자리에서 닮았다**는 뜻이고, 버려도 곡
        정체성을 잃지 않는다 — D-0063의 판단이 옳았던 것이다. 넘지 못하면 **버리는
        칸이 곡을 가르며**, 순서(O-32)를 건드리기 전에 어휘 표현부터 고쳐야 한다.

        **질 수 있다.** 탐색에서 비음계 칸의 곡 고유 성분을 올리자 차이가 0을 지나
        부호가 바뀌었고, **그 교차점이 질량과 무관했다.**
        """
        return self.mass_matched_gap < 0.0 and self.mass_matched_win_rate > 0.5

    @property
    def restriction_is_sound(self) -> bool:
        """D-0083이 사전 등록한 규칙. **질량 교란이 있어 단독으로 읽지 않는다** (D-0084).

        결과를 보고 고치지 않는다 — 통과했다는 사실은 그대로 두고 새 규칙을 옆에 둔다.

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

        on = [index for index in range(DEGREE_COUNT) if index not in set(off)]
        generator = np.random.default_rng(settings.seed)
        shuffled: list[Histogram] = [generator.permutation(vector) for vector in priors]
        within: list[Histogram] = []
        for vector in priors:
            moved = vector.copy()
            moved[on] = generator.permutation(vector[on])
            moved[off] = generator.permutation(vector[off])
            within.append(moved)

        scale_cells = scale_but_discarded(mode)
        chromatic_cells = chromatic_indices(mode)

        def measure(name: str, table: list[Histogram]) -> RestrictionLine:
            shares, full, restricted, masses = [], [], [], []
            scale_shares, chromatic_shares = [], []
            for left, right in pairs:
                a, b = table[left], table[right]
                shares.append(off_scale_share(a, b, mode))
                scale_shares.append(cell_share(a, b, scale_cells))
                chromatic_shares.append(cell_share(a, b, chromatic_cells))
                full.append(total_variation(a, b))
                restricted.append(total_variation(_weights(a, mode), _weights(b, mode)))
                masses.append(float(a[off].sum()))
            return RestrictionLine(
                name=name,
                shares=tuple(shares),
                distances_full=tuple(full),
                distances_restricted=tuple(restricted),
                masses=tuple(masses),
                scale_shares=tuple(scale_shares),
                chromatic_shares=tuple(chromatic_shares),
            )

        return RestrictionReport(
            label=label,
            condition=settings,
            reference_count=len(references),
            lines=(
                measure("observed", priors),
                measure("shuffled", shuffled),
                measure("within", within),
            ),
        )
