"""출력의 배열이 **그 참조곡의** 배열을 닮았는지 잰다 (O-32 · D-0112).

### 왜 쌍 거리로는 안 되는가

D-0102의 `전이초과`는 **두 출력이 순서에서 얼마나 다른가**를 잰다. 전이 사전을
주기만 하면 그 값이 오른다 — 곡 짝을 뒤섞은 사전을 줘도 오른다.

**"쓰이고 있다"와 "맞는 것을 쓴다"는 다르다.** 어휘를 넓히기만 해도 거리가 +0.054
공짜로 오른 것과 같은 함정이다 (D-0094).

### self 대 other

D-0062가 화성 어휘에서 쓴 구조를 그대로 쓴다.

- `self` — 출력의 전이 행렬과 **그 곡의** 전이 사전의 거리
- `other` — 출력의 전이 행렬과 **다른 곡의** 전이 사전의 거리

`self`가 `other`보다 작으면 출력이 그 곡의 배열을 담은 것이다. **전이 사전을 안 주면
둘이 같아야 한다** — 그것이 음성 대조다.

| 전이 사전 | 마디 | self | other | other - self |
|---|---|---|---|---|
| 없음 | 16 | 0.7607 | 0.7541 | **-0.0066** |
| 없음 | 64 | 0.6080 | 0.6007 | **-0.0074** |
| 있음 | 16 | 0.5327 | 0.7417 | **+0.2090** |
| 있음 | 64 | 0.3763 | 0.6345 | **+0.2582** |

### 자리를 맞춘다

전이 사전은 12x12이고 출력의 전이 행렬은 코드 풀 크기다. **사전을 코드 풀 근음으로
좁혀 같은 자리에 놓는다** — `degree_weights`가 도수 사전에 하는 일과 같다 (D-0063).

대각선은 둘 다 없다 (D-0103). **자기 전이는 창 길이가 정하므로 비교에 쓸 수 없다.**

### `other`를 한 곡만 쓰지 않는다

곡마다 **다음 곡**을 짝지으면 코퍼스 순서에 값이 달린다. 곡마다 `other`를
`OTHER_SAMPLES`번 뽑아 평균한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.application.evaluate_harmony_output import (
    Grid,
    OutputCondition,
    ReferencePrior,
    bigram_matrix,
    total_variation,
)
from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.engines.compose.harmony_generator import generate_harmony, vocabulary_roots

OTHER_SAMPLES = 4
"""곡마다 `other`를 몇 번 뽑을 것인가. **한 곡만 쓰면 코퍼스 순서에 값이 달린다.**"""


@dataclass(frozen=True, slots=True)
class OrderReference:
    """참조곡 하나의 도수 사전과 전이 사전."""

    source_key: str
    prior: tuple[float, ...]
    transition: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if len(self.prior) != DEGREE_COUNT:
            raise ValueError(f"도수 사전은 12차원이어야 한다: {len(self.prior)}")
        if len(self.transition) != DEGREE_COUNT:
            raise ValueError(f"전이 사전은 12x12여야 한다: {len(self.transition)}")


def restrict_transition(transition: Sequence[Sequence[float]], roots: Sequence[int]) -> Grid:
    """전이 사전을 코드 풀 근음으로 좁힌다. **출력 전이와 같은 자리에 놓는다.**"""
    picked = np.asarray(transition, dtype=np.float64)[np.ix_(list(roots), list(roots))]
    np.fill_diagonal(picked, 0.0)
    total = float(picked.sum())
    result: Grid = picked / total if total > 0 else picked
    return result


@dataclass(frozen=True, slots=True)
class OrderReport:
    condition: OutputCondition
    reference_count: int
    self_distances: tuple[float, ...]
    other_distances: tuple[float, ...]

    @property
    def mean_self(self) -> float:
        return float(np.mean(self.self_distances)) if self.self_distances else 0.0

    @property
    def mean_other(self) -> float:
        return float(np.mean(self.other_distances)) if self.other_distances else 0.0

    @property
    def gap(self) -> float:
        """`other - self`. **양수면 출력이 그 곡의 배열을 담았다.**"""
        return self.mean_other - self.mean_self

    @property
    def standard_error(self) -> float:
        """**짝지은 차이의 표준오차** (D-0087). 곡마다 둘을 같은 출력에서 잰다."""
        if len(self.self_distances) < 2:
            return 0.0
        gap = np.asarray(self.other_distances) - np.asarray(self.self_distances)
        return float(np.std(gap, ddof=1) / np.sqrt(gap.size))

    @property
    def t_statistic(self) -> float:
        return self.gap / self.standard_error if self.standard_error > 0 else 0.0

    @property
    def win_rate(self) -> float:
        """곡 단위 승률. **평균 한 점의 우연이 아님을 본다** (D-0062)."""
        if not self.self_distances:
            return 0.0
        return float(np.mean(np.asarray(self.other_distances) > np.asarray(self.self_distances)))

    @property
    def carries_reference_order(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0112 · GR-6.5).

        1. `other`가 `self`보다 크다.
        2. `t > 3` — **승인 문턱이다.** 이 판정이 O-32를 닫는다 (D-0098의 규율).
        3. **곡 과반**에서 그렇다.

        **질 수 있다.** 전이 사전을 안 주면 `other - self`가 -0.007로 음수다.
        """
        return self.gap > 0.0 and self.t_statistic > 3.0 and self.win_rate > 0.5


class EvaluateOrderConditioning:
    """출력의 배열이 그 참조곡의 배열을 닮았는지 잰다."""

    def __init__(self, condition: OutputCondition | None = None) -> None:
        self._condition = condition if condition is not None else OutputCondition()

    def run(
        self, references: Sequence[OrderReference], *, use_transition: bool = True
    ) -> OrderReport:
        settings = self._condition
        if len(references) < 2:
            raise ValueError(f"참조곡이 2개 이상 필요하다: {len(references)}")
        roots = vocabulary_roots(settings.key.mode, settings.vocabulary)
        restricted: list[Grid] = [
            restrict_transition(item.transition, roots) for item in references
        ]
        generator = np.random.default_rng([settings.seed, 5])

        mine: list[float] = []
        theirs: list[float] = []
        for index, item in enumerate(references):
            others = [
                int(value)
                for value in generator.choice(
                    [pick for pick in range(len(references)) if pick != index],
                    size=min(OTHER_SAMPLES, len(references) - 1),
                    replace=False,
                )
            ]
            for seed in settings.seeds:
                degrees = generate_harmony(
                    seed,
                    settings.key,
                    bar_count=settings.bar_count,
                    prior=item.prior,
                    vocabulary=settings.vocabulary,
                    transition=item.transition if use_transition else None,
                ).degrees
                observed = bigram_matrix(
                    degrees, settings.key.mode, settings.vocabulary, drop_diagonal=True
                )
                mine.append(total_variation(observed, restricted[index]))
                theirs.append(
                    float(np.mean([total_variation(observed, restricted[pick]) for pick in others]))
                )
        return OrderReport(
            condition=settings,
            reference_count=len(references),
            self_distances=tuple(mine),
            other_distances=tuple(theirs),
        )


def references_from(
    priors: Sequence[ReferencePrior], transitions: dict[str, tuple[tuple[float, ...], ...]]
) -> list[OrderReference]:
    """도수 사전과 전이 사전을 곡 단위로 맞춘다. **둘 다 있는 곡만 남긴다.**"""
    return [
        OrderReference(
            source_key=item.source_key,
            prior=item.prior,
            transition=transitions[item.source_key],
        )
        for item in priors
        if item.source_key in transitions
    ]
