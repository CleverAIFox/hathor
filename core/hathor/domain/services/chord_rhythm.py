"""화성 리듬 — 곡이 화음을 얼마나 오래 끄는가 (O-37 · D-0123).

### 무엇을 재는가

크로마 시계열을 `k`창씩 묶으면 뾰족함이 떨어진다. **참 화음 길이를 넘는 순간
급락한다** — D-0104가 창 길이 기준 (3)을 기각하다가 관측한 것이고, 그 꺾임점이
곡마다 다르다(발라드와 댄스곡).

`반감점`은 뾰족함이 `k=1`에서 **극한까지 절반 내려오는 묶음 길이**다. 로그 격자에서
보간하므로 **연속값이다** — 격자 위 정수로 뭉치지 않는다.

### 자기 전이율을 쓰지 않는 이유

`argmax` 열의 자기 전이율이 더 싸다. 그러나 **창 길이가 그 값을 정한다** — D-0103이
대각선을 버린 근거가 통째로 그것이고, 1초 창을 0.5초로 다시 뽑으면 전부 오른다.
반감점은 **곡의 성질이지 격자의 성질이 아니다.**

### 실측 (1002곡 · `other` 스템 · 1초 창)

| | 반감점(초) |
|---|---|
| 실측 | 5% 2.21 · 25% 3.03 · **중앙 3.87** · 75% 4.82 · 95% 7.52 |
| 창 순서 뒤섞음 | 중앙 **2.32** |

`실측 - 뒤섞음 +1.982초 · t 21.43 · 곡 승률 95.1%`. **시간 순서에서 온다.**

합성 대조에서 화음이 안 이어지면(참 길이 1창) `t = -12.9`로 **진다** — 하네스가
고장이 아니라는 뜻이다 (O-25 (2)).

### 왜 손잡이가 아닌가

D-0109가 `self_transition`을 **진단 전용**으로 막으면서 이렇게 적었다 — *"고정 확률로
유지하는 안은 손잡이가 하나 늘고 그것을 실험으로 고르면 D-0058이라 기각했다."*

**그 기각은 유효하고 여기서 뒤집지 않는다.** 기각된 것은 *하나의 값을 코퍼스 전체에
실험으로 고르는 것*이다. `hold_probability`는 **참조곡 자신의 시계열에서 나온다** —
`prior`·`transition`과 같은 부류이고, 고를 값이 없다.

**자유 매개변수가 하나도 없다는 것이 그 증거다.** 아래 식의 두 항이 모두 같은 곡의
같은 자료에서 나온다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise

import numpy as np

Series = Sequence[Sequence[float]] | np.ndarray
"""창별 크로마. `(창 수, 12)`이며 **이미 으뜸음으로 회전돼 있다** (D-0105)."""

BUNDLES: tuple[int, ...] = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64)
"""묶음 길이(창 수). **촘촘한 격자다.**

`1,2,4,8`처럼 성기면 반감점이 네 값 중 하나로 뭉쳐 곡이 안 갈리고, 보간을 써도
격자 오차가 신호보다 커진다.
"""

SHUFFLE_SEED = 7
"""뒤섞기 시드. **고정한다** — 같은 곡이 매번 같은 바닥을 갖게 한다."""


def spikiness(series: Series) -> float:
    """창별 크로마의 **뾰족함 평균.** 균등이면 1/12, 한 음이면 1."""
    stacked = np.asarray(series, dtype=np.float64)
    if stacked.size == 0:
        return 0.0
    totals = stacked.sum(axis=1, keepdims=True)
    safe = np.where(totals > 0.0, totals, 1.0)
    return float((stacked / safe).max(axis=1).mean())


def bundle(series: Series, size: int) -> np.ndarray:
    """짧은 창 `size`개를 평균해 `size`배 긴 창으로 (D-0104).

    **크로마는 시간 평균이므로 정확히 `size`배 긴 창이다.** 남는 꼬리는 버린다 —
    길이가 다른 창을 섞으면 뾰족함이 창 길이만으로 달라진다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    usable = len(stacked) // size * size
    if usable < size:
        return stacked[:0]
    grouped = stacked[:usable].reshape(-1, size, stacked.shape[1]).mean(axis=1)
    return np.asarray(grouped, dtype=np.float64)


def limit_spikiness(series: Series) -> float:
    """`k`를 무한히 늘렸을 때의 뾰족함. **곡 전체를 한 창으로 본 값이다.**

    묶을수록 곡의 평균 크로마로 수렴하므로 이것이 바닥이고 **닫힌 꼴로 구한다.**

    **격자의 마지막 점을 바닥으로 쓰면 안 된다.** 화음이 격자보다 길면 거기서 아직
    안 내려왔고 반감점이 눌린다 — 합성에서 16창짜리가 8창보다 낮게 나왔다.
    D-0079의 *"극한 열이 상한이다"*와 같은 자리다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    if stacked.size == 0:
        return 0.0
    return spikiness(stacked.mean(axis=0, keepdims=True))


def curve(series: Series, bundles: Sequence[int] = BUNDLES) -> list[tuple[int, float]]:
    """묶음 길이별 뾰족함. 창이 모자라 빈 묶음은 뺀다."""
    points: list[tuple[int, float]] = []
    for size in bundles:
        grouped = bundle(series, size)
        if len(grouped) < 2:
            break
        points.append((size, spikiness(grouped)))
    return points


def half_fall(points: Sequence[tuple[int, float]], floor: float) -> float | None:
    """뾰족함이 **극한까지 절반 내려오는 묶음 길이.** 로그 격자에서 보간한다.

    격자 안에서 반을 안 지나면 `None`이다 — **없는 것을 있는 척하지 않는다** (GR-0.5).
    """
    if len(points) < 3:
        return None
    top = points[0][1]
    if top - floor <= 1e-9:
        return None
    target = floor + (top - floor) / 2.0
    for (left_k, left_v), (right_k, right_v) in pairwise(points):
        if left_v >= target > right_v:
            if left_v - right_v <= 1e-12:
                return float(left_k)
            share = (left_v - target) / (left_v - right_v)
            span = math.log(right_k) - math.log(left_k)
            return float(math.exp(math.log(left_k) + share * span))
    return None


def measure(series: Series) -> float | None:
    """그 곡의 반감점. 창 단위다."""
    stacked = np.asarray(series, dtype=np.float64)
    return half_fall(curve(stacked), limit_spikiness(stacked))


def shuffled(series: Series, seed: int = SHUFFLE_SEED) -> np.ndarray:
    """창 **순서만** 뒤섞는다 (D-0099 계열).

    창 하나하나는 그대로이므로 크로마 분포·잡음·곡 고유 어휘가 전부 남고
    **시간 구조만 죽는다.** 그래서 초과분만 화음 지속이다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    rng = np.random.default_rng(seed)
    return stacked[rng.permutation(len(stacked))]


def hold_probability(series: Series, seed: int = SHUFFLE_SEED) -> float:
    """그 곡의 **화음 유지 확률.** `[0, 1)`이며 자유 매개변수가 없다.

        p = 1 - 반감점(뒤섞음) / 반감점(실측)

    ### 왜 이 식인가

    묶음을 바 하나로 보면 평균 유지 길이 `R`은 기하분포로 `R = 1 / (1 - p)`이고,
    따라서 `p = 1 - 1/R`이다. `R`을 **그 곡의 뒤섞음 바닥에 대한 비**로 읽는다.

    **바닥을 상수로 박지 않는다.** 곡마다 잡음 수준이 다르고 그것이 반감점을
    통째로 밀어 올린다 — 상수를 쓰면 그것이 손잡이가 된다 (O-25).

    ### 무엇을 안 하는가

    **절대 화음 길이로 환산하지 않는다.** 반감점은 참 길이에 단조지만(합성 로그 상관
    0.9994) **눈금이 아니다** — 합성의 비 1.67배가 참 길이 2창 근처에 오는 것은
    합성 잡음을 0.25로 **임의로 고른 결과**다. 템포를 곱해 초로 바꾸는 것도 하지
    않는다. 그것은 O-26이 남긴 자리다.

    뒤섞음보다 낮은 곡은 `0.0`이다 — 실측에서 **49곡(4.9%)**이 그랬다. 그 곡들은
    지금까지와 똑같이 **매 마디 바뀐다.**
    """
    stacked = np.asarray(series, dtype=np.float64)
    real = measure(stacked)
    floor = measure(shuffled(stacked, seed))
    if real is None or floor is None or real <= 0.0:
        return 0.0
    return float(min(max(1.0 - floor / real, 0.0), 0.99))


def self_transition_rate(series: Series) -> float:
    """`argmax` 열이 이어지는 비율. **진단이다. 판정에 쓰지 않는다.**

    창 길이가 이 값을 정하므로 곡의 성질이 아니다 (D-0103). 실측에서 참 화음 길이
    8창의 0.317이 16창에서 0.305로 **내려갔다** — 단조도 아니다.
    D-0083의 순위상관과 같은 지위다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    if len(stacked) < 2:
        return 0.0
    picked = np.argmax(stacked, axis=1)
    return float((picked[:-1] == picked[1:]).mean())
