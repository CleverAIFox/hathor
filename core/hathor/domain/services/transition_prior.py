"""창별 크로마 시계열에서 **전이 사전**을 만든다 (O-32 · D-0107).

### 무엇을 만드는가

`ingest keys --series`가 남긴 창별 크로마를 읽어 **12x12 전이 행렬**을 낸다.
`(i, j)`는 "도수 `i` 다음에 `j`가 온다"의 무게다.

도수 사전(D-0063)이 **어휘**를 담았다면 이것은 **배열**을 담는다. 도수 히스토그램은
순서에 눈이 없어 `I V vi IV`와 `IV vi V I`의 거리가 0이다 (D-0102).

### 창마다 최빈 도수 하나를 고른다 — 부드러운 집계를 써 보고 뒤집었다

창의 도수 분포를 그대로 외적해 더하는 방법이 **재현 정확도는 조금 낫다.**

| 창 잡음 | `argmax` | 외적 합 |
|---|---|---|
| 0.3 | 0.1811 | 0.1634 |
| 0.8 | 0.1821 | 0.1668 |
| 1.5 | 0.1916 | 0.1942 |

**그런데 창 길이 불변을 깬다.** 같은 화음을 세 창 끌면 잡음 바닥끼리의 외적이
유지 길이에 비례해 대각선 밖에 쌓인다. 대각선만 버려서는 안 빠진다.

**불변이 정확도보다 중요하다** — D-0103이 박자 추정을 지운 근거가 통째로 그것이고,
불변이 없으면 창 길이를 다시 골라야 한다 (D-0104도 무너진다).

`argmax`는 같은 화음이 이어질 때 **자기 전이만 만들고 그것은 버려진다.** 불변이
정확하다. 대신 **두 도수가 비슷한 창에서 하나를 임의로 집는다** — 그 자의성은
남는다.

### 대각선을 버린다

**자기 전이는 창 길이가 정한다** (D-0103). 잘게 자르면 같은 화음이 여러 창에 걸쳐
대각선이 부풀고, 크게 자르면 화음이 섞인다. 실측에서 구간당 화음을 1에서 8로
바꾸자 전체 거리가 0.6122에서 0.2855로 반토막 났고 **대각선을 뺀 값은 0.6063으로
한 자리도 안 움직였다.**

그래서 이 사전이 답하는 것은 **"바뀐다면 어디로"**다. 화음을 얼마나 오래 끄는가는
**여기서 못 재고 O-37이다.**

### 회전은 밖에서 한다

들어오는 시계열은 **이미 으뜸음으로 회전돼 있어야 한다.** 회전 기준은 곡의 조성
추정이고 그것은 `keys.jsonl`에 있다 — **한 곳에서 읽어 한 번 회전한다** (D-0073).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from hathor.domain.services.harmony_prior import DEGREE_COUNT

TransitionMatrix = np.ndarray[tuple[int, int], np.dtype[np.float64]]


def transition_prior(
    series: Sequence[Sequence[float]] | TransitionMatrix, *, drop_diagonal: bool = True
) -> TransitionMatrix:
    """창별 크로마 시계열을 12x12 전이 사전으로 (D-0107).

    창이 둘 미만이면 전이가 없으므로 **0 행렬을 낸다** — 균등으로 되돌리지 않는다.
    없는 것을 있는 척하면 쓰는 쪽이 그것을 정보로 읽는다 (GR-0.5).
    """
    stacked = np.asarray(series, dtype=np.float64)
    if stacked.size == 0:
        return np.zeros((DEGREE_COUNT, DEGREE_COUNT), dtype=np.float64)
    if stacked.ndim != 2 or stacked.shape[1] != DEGREE_COUNT:
        raise ValueError(f"시계열은 (창 수, 12)이어야 한다: {stacked.shape}")
    if len(stacked) < 2:
        return np.zeros((DEGREE_COUNT, DEGREE_COUNT), dtype=np.float64)

    picked = np.argmax(stacked, axis=1)
    matrix: TransitionMatrix = np.zeros((DEGREE_COUNT, DEGREE_COUNT), dtype=np.float64)
    for left, right in pairwise(picked):
        matrix[left, right] += 1.0
    if drop_diagonal:
        np.fill_diagonal(matrix, 0.0)
    total = float(matrix.sum())
    return matrix / total if total > 0 else matrix


def is_empty(matrix: Sequence[Sequence[float]] | TransitionMatrix) -> bool:
    """전이가 없는 사전인가. **없는 것을 조건으로 쓰지 않는다.**"""
    return float(np.asarray(matrix).sum()) <= 0.0


def transition_row(
    matrix: Sequence[Sequence[float]] | TransitionMatrix,
    current: int,
    roots: Sequence[int],
) -> tuple[float, ...]:
    """지금 도수에서 다음으로 갈 무게. **코드 풀의 근음만 남긴다.**

    행이 비면 **열 합**으로 되돌린다 — 그 도수가 참조곡에 안 나왔다는 뜻이므로
    곡 전체의 도착 빈도를 쓴다. 그것도 비면 균등이다.
    """
    stacked = np.asarray(matrix, dtype=np.float64)
    picked = np.maximum(stacked[current, list(roots)], 0.0)
    if picked.sum() <= 0.0:
        picked = np.maximum(stacked[:, list(roots)].sum(axis=0), 0.0)
    total = float(picked.sum())
    if total <= 0.0:
        return tuple([1.0 / len(roots)] * len(roots))
    return tuple(float(value) for value in picked / total)
