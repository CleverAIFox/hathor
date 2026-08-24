"""버려지는 반음계 칸이 **차용화음인지 조성 추정 오차인지** 가른다 (O-33 · D-0089).

### 왜 상관으로는 안 되는가

D-0088에서 버려지는 칸의 곡 고유성이 다이어토닉과 대등하고, **초과분이 전부 진짜
반음계 5칸(♭2·♭3·♯4·♭6·♭7)에서 나온다**는 것이 나왔다. 그 3%가 음악인지 잡음인지가
남았다.

`margin`(조성 추정 신뢰도)과 반음계 질량의 상관을 보고 싶어진다. **안 된다** —
**역인과가 있다.** 차용화음이 많은 곡은 조성 추정도 어려워지므로 두 방향이 같은
상관을 만든다.

### 오차는 치환이고 차용은 첨가다

조성 추정이 틀리면 사전 전체가 잘못 회전한다. 그 결과는 **정확히 계산된다.**

| 참 조성이 추정보다 | 늘어난 칸 | 사라진 칸 |
|---|---|---|
| +7 (딸림조 혼동) | ♭7 | **이끔음** |
| +5 (버금딸림조) | ♯4 | **4** |
| +9 (관계단조) | ♭3 ♭6 ♭7 | **3 6 이끔음** |
| +2 | ♭3 ♭7 | **3 이끔음** |

**어느 오차든 온음계 음이 빠지면서 반음계 음이 든다 — 치환이다.**

진짜 믹솔리디안 차용은 다르다. ♭7이 오르되 **이끔음은 남는다** — 곡의 다른 곳에서
V화음을 쓰기 때문이다. **첨가다.**

그래서 **곡 안에서 반음계 칸과 그것이 변화시킨 온음계 칸이 함께 큰지**가 둘을
가른다. 역인과를 타지 않는다 — 인과의 방향이 아니라 **모양**을 보기 때문이다.

### 치환 상관

각 반음계 칸을 그것이 변화시킨 온음계 칸과 짝짓는다 (`SUBSTITUTION_PAIRS`).
**코퍼스 공유 모양을 로그로 나눠 없앤 뒤** 곡 간 상관을 재고 다섯 쌍을 평균한다.

- **음수** — 반음계 칸이 짝 온음계 칸을 **대체한다.** 조성 오차의 모양이다.
- **0 근처나 양수** — 함께 커진다. 첨가의 모양이다.

귀무선은 조 내 치환이다. **합이 1인 자료라 아무 상관이나 재도 음수가 나오므로**
그 몫을 빼야 한다 (D-0084 이후로 같은 규율이다).

### 검출력이 한쪽만 강하다 — 그래서 그 방향으로만 판정한다

합성 탐색(조성 공유 모양을 넣고, O-25 (5)):

| 차용 | 오차 | 실측 - 귀무 | t |
|---|---|---|---|
| 없음 | 없음 | -0.0038 | -0.23 |
| 없음 | 35% | **-0.1226** | **-8.19** |
| 있음 | 없음 | +0.0251 | +1.40 |
| 있음 | 35% | +0.0279 | +1.67 |

**오차는 t = -8로 잡히고 차용은 t = +1.4로 겨우 보인다.** 그러니 판정을 한쪽으로만
낸다 — **뚜렷한 음수면 오차가 지배한다**는 강한 결론이고, 그렇지 않으면
**오차로 설명되지 않는다**는 약한 결론이다.

**약한 쪽은 "음악이다"의 증명이 아니다.** 크로마 누설도 첨가의 모양을 흉내 낸다.
그것은 아래 **뭉침 대비**가 가른다.

### 차용은 뭉치고 누설은 고르게 번진다 (D-0091)

단조 차용은 화음 단위로 온다. `♭III`(♭3·5·♭7) · `iv`(4·♭6·1) · `♭VI`(♭6·1·♭3) ·
`♭VII`(♭7·2·4)가 **함께** 쓰이므로 **♭3·♭6·♭7이 한 곡에서 같이 오른다.**

크로마 누설은 다르다. 배음·비브라토는 이웃 반음으로 번지고 곡마다 그 양이 다르므로
**반음계 다섯 칸이 고르게 함께 오른다.** 특정 셋만 뭉치지 않는다.

그래서 **삼총사 세 쌍의 상관에서 나머지 일곱 쌍의 상관을 뺀다.**

| 차용 | 누설 | 대비 - 귀무 |
|---|---|---|
| 없음 | 없음 | -0.002 |
| 없음 | 있음 | **-0.032 ~ -0.016** |
| 있음 | 없음 | **+0.79 ~ +1.00** |
| 있음 | 있음 | **+0.50 ~ +0.96** |

**누설로는 안 나오는 값이다.** 차용이 있으면 두 자릿수 배로 벌어진다.

### 눈금은 자료에서 만든다

실제 곡의 일부를 일부러 5도·관계조만큼 회전시킨 `rotated` 선을 낸다. **"오차가
이만큼 있으면 값이 여기까지 내려간다"**를 합성이 아니라 실측 코퍼스로 보여 준다.
등가선(D-0086)과 같은 착상이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.application.evaluate_degree_restriction import (
    NULL_REPEATS,
    chromatic_indices,
    off_scale_indices,
)
from hathor.application.evaluate_harmony_output import Histogram, ReferencePrior
from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.domain.value_objects.key import Mode

SUBSTITUTION_PAIRS: dict[Mode, tuple[tuple[int, int], ...]] = {
    Mode.MAJOR: ((1, 2), (3, 4), (6, 5), (8, 9), (10, 11)),
    Mode.MINOR: ((1, 0), (4, 3), (6, 5), (9, 8), (11, 10)),
}
"""`(반음계 칸, 그것이 변화시킨 온음계 칸)`.

장조는 ♭2←2 · ♭3←3 · ♯4←4 · ♭6←6 · ♭7←이끔음이다. **음악적 변화 관계이자 조성
오차의 치환 관계**이며, 위 표에서 두 관계가 같은 짝을 가리킨다.
"""

MODAL_MIXTURE: dict[Mode, tuple[int, ...]] = {
    Mode.MAJOR: (3, 8, 10),
    Mode.MINOR: (4, 9, 11),
}
"""단조 차용 삼총사 (D-0091).

장조에서 ♭3·♭6·♭7이다. `♭III` · `iv` · `♭VI` · `♭VII`가 함께 쓰이므로 **한 곡에서
같이 오른다.** 단조에서는 반대로 장조 차용(피카르디 3도 계열)의 3·6·이끔음이다.
"""

ROTATION_ERRORS = (7, 5, 2, 9)
"""눈금선이 흉내 내는 조성 오차. **딸림조·버금딸림조·관계조 혼동**이 실제로 흔하다."""

DEFAULT_ROTATED_SHARE = 0.30
"""눈금선에서 일부러 회전시킬 곡의 비율. **자의적이다** — 오차가 이 정도일 때 값이
어디까지 내려가는지 보여 주는 자이지 실제 오차율의 추정이 아니다.
"""

DEFAULT_BOOTSTRAP = 40
"""부트스트랩 반복. 곡 단위로 다시 뽑는다."""


@dataclass(frozen=True, slots=True)
class OriginCondition:
    """실험 조건 한 묶음. **모든 선이 이 객체 하나를 받는다** (O-25)."""

    key_mode: Mode = Mode.MAJOR
    seed: int = 20260822
    null_repeats: int = NULL_REPEATS
    bootstrap: int = DEFAULT_BOOTSTRAP
    rotated_share: float = DEFAULT_ROTATED_SHARE

    def __post_init__(self) -> None:
        if not 0.0 < self.rotated_share < 1.0:
            raise ValueError(f"회전 비율은 0과 1 사이여야 한다: {self.rotated_share}")
        if self.null_repeats < 1 or self.bootstrap < 1:
            raise ValueError("반복 수는 1 이상이어야 한다")


def _deviations(priors: Sequence[Histogram]) -> Histogram:
    """**코퍼스 공유 모양을 로그로 나눠 없앤다.**

    없애지 않으면 모든 칸이 K-K 모양을 함께 갖고 있어 상관이 그 모양을 잰다 —
    D-0086이 등가선을 만든 것과 같은 이유다.
    """
    stacked = np.asarray(priors, dtype=np.float64)
    mean = stacked.mean(axis=0)
    deviation: Histogram = np.log(np.maximum(stacked, 1e-12)) - np.log(np.maximum(mean, 1e-12))
    return deviation


def substitution_correlation(priors: Sequence[Histogram], mode: Mode) -> float:
    """치환 상관. **음수면 반음계 칸이 짝 온음계 칸을 대체한다.**"""
    deviation = _deviations(priors)
    found: list[float] = []
    for chromatic, scale in SUBSTITUTION_PAIRS[mode]:
        left, right = deviation[:, chromatic], deviation[:, scale]
        if left.std() == 0.0 or right.std() == 0.0:
            continue
        found.append(float(np.corrcoef(left, right)[0, 1]))
    return float(np.mean(found)) if found else 0.0


def _pair_correlation(deviation: Histogram, pairs: Sequence[tuple[int, int]]) -> float:
    found: list[float] = []
    for left, right in pairs:
        if deviation[:, left].std() == 0.0 or deviation[:, right].std() == 0.0:
            continue
        found.append(float(np.corrcoef(deviation[:, left], deviation[:, right])[0, 1]))
    return float(np.mean(found)) if found else 0.0


def mixture_pairs(mode: Mode) -> tuple[tuple[int, int], ...]:
    """삼총사 세 쌍."""
    cells = MODAL_MIXTURE[mode]
    return tuple((cells[i], cells[j]) for i in range(len(cells)) for j in range(i + 1, len(cells)))


def other_chromatic_pairs(mode: Mode) -> tuple[tuple[int, int], ...]:
    """반음계 칸의 나머지 쌍. **삼총사 쌍과 겹치지 않는다** — 겹치면 대비가 희석된다.

    **온음계인데 버려지는 칸(장조 이끔음)은 뺀다** — 반음계가 아니다 (D-0085).
    """
    cells = chromatic_indices(mode)
    mixture = set(mixture_pairs(mode))
    return tuple(
        (cells[i], cells[j])
        for i in range(len(cells))
        for j in range(i + 1, len(cells))
        if (cells[i], cells[j]) not in mixture
    )


def mixture_contrast(priors: Sequence[Histogram], mode: Mode) -> float:
    """삼총사 뭉침에서 나머지 반음계 뭉침을 뺀다. **차용에서만 크게 양수다.**"""
    deviation = _deviations(priors)
    return _pair_correlation(deviation, mixture_pairs(mode)) - _pair_correlation(
        deviation, other_chromatic_pairs(mode)
    )


def _within_shuffled(
    priors: Sequence[Histogram], mode: Mode, generator: np.random.Generator
) -> list[Histogram]:
    off = list(off_scale_indices(mode))
    on = [index for index in range(DEGREE_COUNT) if index not in set(off)]
    built: list[Histogram] = []
    for vector in priors:
        moved = vector.copy()
        moved[on] = generator.permutation(vector[on])
        moved[off] = generator.permutation(vector[off])
        built.append(moved)
    return built


def _rotated(
    priors: Sequence[Histogram], share: float, generator: np.random.Generator
) -> list[Histogram]:
    """일부 곡을 일부러 잘못 회전시킨다. **눈금선이지 귀무선이 아니다.**"""
    built: list[Histogram] = []
    for vector in priors:
        if generator.random() < share:
            offset = int(generator.choice(ROTATION_ERRORS))
            built.append(np.roll(vector, -offset))
        else:
            built.append(vector.copy())
    return built


@dataclass(frozen=True, slots=True)
class OriginReport:
    label: str
    condition: OriginCondition
    reference_count: int
    observed: float
    null: float
    rotated: float
    rotated_null: float
    standard_error: float
    scale_mass: float
    mixture: float = 0.0
    """삼총사 대비 실측 (D-0091)."""
    mixture_null: float = 0.0
    mixture_standard_error: float = 0.0

    @property
    def excess(self) -> float:
        """실측에서 귀무선을 뺀 값. **합이 1인 자료의 몫을 걷어낸다.**"""
        return self.observed - self.null

    @property
    def rotated_excess(self) -> float:
        """눈금선. **오차가 조건에 적힌 만큼 있을 때의 값이다.**"""
        return self.rotated - self.rotated_null

    @property
    def t_statistic(self) -> float:
        return self.excess / self.standard_error if self.standard_error > 0 else 0.0

    @property
    def mixture_excess(self) -> float:
        """삼총사 대비에서 귀무선을 뺀 값 (D-0091)."""
        return self.mixture - self.mixture_null

    @property
    def mixture_t(self) -> float:
        if self.mixture_standard_error <= 0:
            return 0.0
        return self.mixture_excess / self.mixture_standard_error

    @property
    def modal_mixture_present(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0091 · GR-6.5). 결과를 보고 고치지 않는다.

        1. 삼총사 대비 초과분이 양수다.
        2. `t`가 2보다 크다.

        둘 다 넘으면 **♭3·♭6·♭7이 한 곡에서 함께 오른다** — 화음 단위로 오는 단조
        차용의 모양이며 **크로마 누설로는 만들어지지 않는다.** 합성에서 누설만
        있을 때 -0.032에서 -0.002 사이였고 차용이 있으면 +0.50을 넘었다.

        **질 수 있다.** 차용을 끄면 부호가 0 아래로 내려간다.
        """
        return self.mixture_excess > 0.0 and self.mixture_t > 2.0

    @property
    def chromatic_is_substitution(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0089 · GR-6.5). 결과를 보고 고치지 않는다.

        1. 초과분이 음수다.
        2. `t`가 -2보다 작다.

        둘 다 넘으면 **조성 추정 오차가 지배한다** — 반음계 질량은 회전이 틀린
        자국이며 어휘 확장의 근거가 아니다.

        **넘지 못하는 것은 "음악이다"의 증명이 아니다.** 오차로 설명되지 않는다는
        뜻뿐이며, 크로마 누설은 이 지문을 안 남긴다.

        `t < -2`는 자의적이다. **합성에서 오차 35%가 t = -8이었고 오차 0%가
        -0.23이었으므로 그 사이에 두었다.** 옮기면 여기서 드러난다.
        """
        return self.excess < 0.0 and self.t_statistic < -2.0


class EvaluateChromaticOrigin:
    """반음계 질량이 치환인지 첨가인지 잰다."""

    def __init__(self, condition: OriginCondition | None = None) -> None:
        self._condition = condition if condition is not None else OriginCondition()

    def run(self, references: Sequence[ReferencePrior], label: str) -> OriginReport:
        settings = self._condition
        if len(references) < 3:
            raise ValueError(f"참조곡이 3개 이상 필요하다: {len(references)}")
        mode = settings.key_mode
        priors: list[Histogram] = [np.asarray(item.prior, dtype=np.float64) for item in references]

        def stream(line: int, repeat: int = 0) -> np.random.Generator:
            """**선마다 흐름이 따로다** (D-0087)."""
            return np.random.default_rng([settings.seed, line, repeat])

        def null_of(table: Sequence[Histogram], line: int) -> float:
            drawn = [
                substitution_correlation(_within_shuffled(table, mode, stream(line, index)), mode)
                for index in range(settings.null_repeats)
            ]
            return float(np.mean(drawn))

        rotated = _rotated(priors, settings.rotated_share, stream(3))
        scale = [index for index in range(DEGREE_COUNT) if index not in off_scale_indices(mode)]
        scale = sorted({*scale, *(pair[1] for pair in SUBSTITUTION_PAIRS[mode])})

        def mixture_null_of(table: Sequence[Histogram], line: int) -> float:
            drawn = [
                mixture_contrast(_within_shuffled(table, mode, stream(line, index)), mode)
                for index in range(settings.null_repeats)
            ]
            return float(np.mean(drawn))

        resample = np.random.default_rng([settings.seed, 9])
        spread: list[float] = []
        mixture_spread: list[float] = []
        for _ in range(settings.bootstrap):
            picked = resample.integers(0, len(priors), len(priors))
            sample = [priors[int(index)] for index in picked]
            spread.append(substitution_correlation(sample, mode) - null_of(sample, 4))
            mixture_spread.append(mixture_contrast(sample, mode) - mixture_null_of(sample, 5))

        return OriginReport(
            label=label,
            condition=settings,
            reference_count=len(priors),
            observed=substitution_correlation(priors, mode),
            null=null_of(priors, 1),
            rotated=substitution_correlation(rotated, mode),
            rotated_null=null_of(rotated, 2),
            standard_error=float(np.std(spread, ddof=1)) if len(spread) > 1 else 0.0,
            scale_mass=float(np.mean([vector[scale].sum() for vector in priors])),
            mixture=mixture_contrast(priors, mode),
            mixture_null=mixture_null_of(priors, 6),
            mixture_standard_error=(
                float(np.std(mixture_spread, ddof=1)) if len(mixture_spread) > 1 else 0.0
            ),
        )
