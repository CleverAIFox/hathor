#!/usr/bin/env python3
"""사전 쌍에서 **출력 거리만** 뽑는다 (D-0463).

`EvaluateHarmonyOutput.run()`은 비교선 **일곱 개**를 돈다. 그것이 옳다 — 판정에는
귀무선이 있어야 한다 (D-0078 · D-0230). 그런데 **문턱을 재는 탐침은 `paired`
하나만 읽는다.** 나머지 여섯의 생성과 전이 행렬이 통째로 버려진다.

### 왜 따로 사나

`probe_layout`이 이 고리를 **손으로 베껴** 들고 있었다 (D-0462). 그래서 같은
질문을 재는 두 탐침이 **다른 코드**로 돌았고, 한쪽을 고쳐도 다른 쪽은 안 움직였다
— D-0043이 「두 곳에 적으면 어긋난다」로 적은 바로 그 꼴이고, D-0446에서 거절
표본을 베껴 적다 `seen`을 빠뜨린 것과 같은 부류다.

**여기 있는 것이 그 한자리다.** `evaluate_harmony_output`에 두면 그 파일이 상한
600줄에 3줄까지 붙는다 — 못은 올리는 게 아니라 쪼갠다 (D-0117).

### 무엇을 보증하나

이 함수는 `run().line("paired").distances`와 **비트까지 같은 수**를 낸다. 쌍도
시드도 호출자가 넘기므로 어긋날 자리는 **호출자 하나**이고,
`EvaluateHarmonyOutput.paired_distances`가 자기 조건에서 직접 꺼내 넘긴다.
그 동일성을 `test_빠른_길이_느린_길과_비트까지_같다`가 건다.

**그 동일성이 규약인 까닭**: 느린 길로 모은 판과 빠른 길로 모은 판을 **같이 세기**
때문이다. 같은 수가 아니면 섞어 센 평균에 뜻이 없다 (GR-0.5).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import numpy as np

from hathor.application.progression_distance import (
    DegreePrior,
    Histogram,
    degree_histogram,
    total_variation,
)
from hathor.engines.compose.harmony_generator import Vocabulary, generate_harmony

if TYPE_CHECKING:
    from hathor.domain.value_objects.key import Key


def output_distances(
    priors: Sequence[DegreePrior],
    pairs: Sequence[tuple[int, int]],
    *,
    seeds: Iterable[int],
    key: Key,
    vocabulary: Vocabulary = Vocabulary.BASE,
    bar_count: int = 8,
) -> tuple[float, ...]:
    """쌍마다 **시드 평균 전변동 거리**. 쌍 순서대로 낸다.

    **짝지은 두 곡이 같은 시드 흐름을 쓴다** — `generate_harmony`가 시드에서만
    난수를 만들므로 사전이 같으면 거리가 **정확히** 0이고, 바닥이 표집 잡음에
    안 흔들린다 (D-0078).

    `seeds`를 한 번만 도는 것이 아니라 **곡마다 다시 돈다.** 그래서 꼬리가
    소진되는 반복자를 받으면 두 번째 곡부터 빈 묶음이 된다 — 튜플로 굳혀 둔다.

    생성은 곡 단위로 **한 번만** 한다(`cache`). 쌍이 곡을 여러 번 집으므로
    이것이 없으면 비용이 쌍 수에 비례한다.
    """
    frozen = tuple(seeds)
    if not frozen:
        raise ValueError("시드가 없다 — 거리 0이 아니라 잴 것이 없는 것이다")
    cache: dict[int, tuple[Histogram, ...]] = {}

    def histograms(index: int) -> tuple[Histogram, ...]:
        if index not in cache:
            cache[index] = tuple(
                degree_histogram(
                    generate_harmony(
                        seed,
                        key,
                        bar_count=bar_count,
                        prior=priors[index],
                        vocabulary=vocabulary,
                    ).degrees,
                    key.mode,
                    vocabulary,
                )
                for seed in frozen
            )
        return cache[index]

    return tuple(
        float(
            np.mean(
                [
                    total_variation(left, right)
                    for left, right in zip(histograms(one), histograms(other), strict=True)
                ]
            )
        )
        for one, other in pairs
    )
