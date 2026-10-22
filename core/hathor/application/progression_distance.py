#!/usr/bin/env python3
"""진행과 사전 사이의 **거리** — 셋이 함께 쓰는 순수 함수 (D-0461).

`evaluate_harmony_output` 안에 살았고 `evaluate_degree_restriction` ·
`evaluate_order_conditioning`이 **거기서 가져다 썼다.** 응용 하나가 다른 응용 둘의
연장을 들고 있는 꼴이라 **그 파일을 쪼갤 때마다 둘이 같이 흔들렸다** (D-0127이
`tables.py`에서 본 자리와 같다).

**도메인으로는 못 간다** — `vocabulary_degrees` · `degree_weights`가
`engines.compose.harmony_generator`에 있고 「도메인은 외부를 모른다」가 그것을 막는다.
그래서 **같은 층의 공유 자리**다.

여기 있는 것은 전부 **상태가 없다.** 진행 하나, 사전 하나를 받아 수를 낸다.
"""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from typing import TYPE_CHECKING

import numpy as np

from hathor.engines.compose.harmony_generator import (
    Vocabulary,
    degree_weights,
    vocabulary_degrees,
)

if TYPE_CHECKING:
    from hathor.domain.value_objects.key import Mode

DegreePrior = tuple[float, ...]
Progression = tuple[str, ...]

Histogram = np.ndarray[tuple[int], np.dtype[np.float64]]
"""창 하나의 12칸 또는 도수 히스토그램. **1차원이다.**"""

Grid = np.ndarray[tuple[int, int], np.dtype[np.float64]]
"""전이 행렬 같은 2차원.

**1차원 별칭을 2차원에 쓰다가 `make check`가 리전에서만 빨갛게 뜬 적이 있다**
(D-0108). 기기마다 넘파이 판이 달라 한쪽에서만 통과한다 — **이름이 맞으면 판이
관대하든 아니든 잡는다.**
"""


def degree_histogram(
    progression: Progression, mode: Mode, vocabulary: Vocabulary = Vocabulary.BASE
) -> Histogram:
    """진행을 코드 풀의 도수 히스토그램으로. 합이 1이다.

    **칸 수가 어휘마다 다르다.** 칸이 늘면 두 진행이 겹칠 확률이 낮아져 거리가
    기계적으로 오르므로 **같은 칸 수의 대조군과만 견준다** (D-0094).
    """
    counts = Counter(progression)
    pool = vocabulary_degrees(mode, vocabulary)
    vector = np.asarray([counts.get(name, 0) for name in pool], dtype=np.float64)
    total = float(vector.sum())
    return vector / total if total > 0 else vector


def bigram_matrix(
    progression: Progression,
    mode: Mode,
    vocabulary: Vocabulary = Vocabulary.BASE,
    *,
    drop_diagonal: bool = False,
) -> Grid:
    """이웃한 두 마디의 도수 쌍 분포 (O-32 · D-0102).

    **도수 히스토그램은 순서에 눈이 없다** — `I V vi IV`와 `IV vi V I`의 거리가 0이다.
    전이 행렬은 이웃 관계를 보므로 배열이 달라지면 값이 달라진다.
    """
    pool = vocabulary_degrees(mode, vocabulary)
    index = {name: position for position, name in enumerate(pool)}
    matrix = np.zeros((len(pool), len(pool)), dtype=np.float64)
    for left, right in pairwise(progression):
        matrix[index[left], index[right]] += 1.0
    if drop_diagonal:
        # **자기 전이를 빼면 구간 길이에 불변이다** (D-0103). 같은 화음을 몇 구간
        # 유지하는지는 자르는 방식이 정하고, 그것이 대각선을 통째로 부풀린다.
        np.fill_diagonal(matrix, 0.0)
    total = float(matrix.sum())
    result: Grid = matrix / total if total > 0 else matrix
    return result


def total_variation(left: Histogram | Grid, right: Histogram | Grid) -> float:
    """전변동 거리. 0~1이며 **`TV * 마디 수`가 옮겨야 하는 마디 수다.**"""
    return 0.5 * float(np.abs(left - right).sum())


def weight_distance(
    left: DegreePrior,
    right: DegreePrior,
    mode: Mode,
    vocabulary: Vocabulary = Vocabulary.BASE,
) -> float:
    """두 사전의 **가중치 벡터** 거리. 마디 수를 늘렸을 때의 극한이다 (O-25 (3)).

    생성기가 실제로 쓰는 `degree_weights`를 그대로 부른다. 여기서 6도수 정규화를
    다시 구현하면 생성기와 어긋날 수 있고, **어긋나도 아무도 모른다.**
    """
    return total_variation(
        np.asarray(degree_weights(left, mode, vocabulary), dtype=np.float64),
        np.asarray(degree_weights(right, mode, vocabulary), dtype=np.float64),
    )
