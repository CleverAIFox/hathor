#!/usr/bin/env python3
"""문턱을 재는 **음성·양성 대조 코퍼스** (D-0460).

D-0327이 `t>=2`를 고르며 *«음성 4% · 양성 100%»*를 쟀다. **그 코퍼스를 짓는 코드가
커밋되지 않았다** — 기록의 `재현`은 실물 명령만 적는다. 그래서 D-0453이 쌍 수를
올렸을 때 그 문턱을 **다시 걸 수가 없었다**: 도구가 없으면 다시 재지 못하고,
다시 재지 못하면 **고른 적 있다는 사실만 남는다** (GR-0.7 · D-0449가 수에서 본 병이
여기서는 **자**에서 났다).

### 둘이 무엇을 다르게 만드나

**열두 칸이 교환가능하면 음성이다.** 어느 칸도 다른 칸보다 더 곡 고유하지 않으므로
*«차용 칸이 출력을 더 가른다»*가 참일 수 없다. **차용 칸만 곡 간에 흔들면 양성이다.**

`follows`는 셋째 모양이다 — 차용 칸이 **이웃 온음계 칸에 비례**한다. 흔들림은 있는데
`base` 6도수가 이미 아는 흔들림이라 **어휘를 넓혀도 새 정보가 없다** (D-0333).

### 질량을 맞춘다

D-0334가 *«합성이 퍼짐만 맞추고 무게를 안 맞췄다»*를 잡았다 — 그 코퍼스의 온음계
질량이 **0.4971**인데 실물은 **0.7237**이다. 낮은 가중치 도수는 잘 안 뽑히므로
어휘에 넣어도 히스토그램이 덜 움직인다.

**온음계 칸을 고정 배수 `k`로 민다.** 곡마다 다른 배수를 쓰면 **온음계 블록에
곡 고유한 공통 인자가 생겨** 음성 대조가 음성이 아니게 된다 — 고치려던 것을 만든다.
균등 디리클레에서 온음계와 나머지의 기대 질량이 반반이므로 `k = m / (1 - m)`이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from hathor.application.evaluate_harmony_output import ReferencePrior  # noqa: E402

DEGREE_COUNT = 12

DIATONIC = (0, 2, 4, 5, 7, 9)
"""장조 다이어토닉 **근음** 여섯 (D-0085). 화음 근음이라 이끔음 11은 안 든다."""

BORROWED = (3, 8, 10)
"""단조 차용 삼총사 ♭3 · ♭6 · ♭7 (D-0091 · D-0093). `harmony_generator`가 드는 그 칸이다."""

NEIGHBOUR = {3: 2, 8: 7, 10: 9}
"""차용 칸과 **이웃한 온음계 칸**. 누설이라면 이 비율로 따라온다 (D-0091 · D-0333)."""

SHAPE = 3.385
"""디리클레 농도. **실물 퍼짐을 재현한 값이다** (D-0327이 `CONC`으로 골랐다).

**여기서 새로 안 고른다** (D-0058). 퍼짐은 그 판이 맞췄고 이 판이 더하는 것은
**질량**이다 — 손잡이를 둘 돌리면 어느 쪽이 움직였는지 못 가른다.
"""

FOLLOW_SIGMA = 0.15
"""이웃 비례 모양에서 **비례를 얼마나 느슨하게** 둘 것인가 (D-0333).

**`sigma`와 다른 손잡이다.** 예전에는 0.15가 코드에 박혀 있어 `sigma`를 아무리
흔들어도 `follows` 코퍼스가 **바이트까지 같았다** — 인자를 받는 척만 했다 (D-0461).
"""

REAL_DIATONIC_MASS = 0.7237
"""실물 1004곡의 온음계 질량 (D-0334가 쟀다).

**기본값이지 고른 값이 아니다.** 「합성을 실물에 맞춘다」가 이 상수의 전부이고,
**맞춘 뒤 무엇이 나오는지는 모른다** — 알고 고르면 그것이 D-0058이다.
"""


def _jitter(sigma: float, noise: float) -> float:
    """**평균이 1인** 로그정규 흔들림 (D-0460).

    맨 `exp(sigma*z)`는 기댓값이 `exp(sigma^2/2)`다 — 0.9면 **1.50배**라 차용 칸이
    통째로 무거워지고 **양성 코퍼스의 온음계 질량이 음성보다 0.03 낮게 선다.**
    두 대조가 다른 자에서 나오면 견줄 수가 없다.

    실제로 그렇게 짰다가 질량을 재서 잡았다 — **목표만 적고 실측을 안 봤으면
    못 봤다** (GR-0.5). D-0334가 *«퍼짐만 맞추고 무게를 안 맞췄다»*로 잡은 것과
    같은 부류이고, 이번엔 **흔들림이 무게를 밀었다.**
    """
    return float(np.exp(sigma * noise - 0.5 * sigma * sigma))


def mass_factor(target: float) -> float:
    """온음계 칸에 곱할 **고정** 배수. 모든 곡에 같은 값이 간다.

    `k = m/(1-m)`은 **기댓값의 비**를 맞춘다. 실현 질량은 `E[kA/(kA+B)]`라 젠센
    몫만큼 비낀다 — 목표 0.7237에서 실측 **0.7194**로 0.004쯤 낮다 (D-0461).
    **맞추는 것이 아니라 가까이 두는 것**이고, 얼마나 가까운지는
    `diatonic_mass_of`가 **실측으로** 답한다 (GR-0.5).
    """
    if not 0.0 < target < 1.0:
        raise ValueError(f"온음계 질량은 0과 1 사이여야 한다: {target}")
    return target / (1.0 - target)


def build(
    count: int,
    *,
    seed: int,
    sigma: float,
    follows: bool = False,
    follow_sigma: float = FOLLOW_SIGMA,
    diatonic_mass: float = REAL_DIATONIC_MASS,
) -> list[ReferencePrior]:
    """대조 코퍼스 한 벌.

    `sigma == 0`이면 **음성**이다 — 열두 칸이 교환가능하다.
    `sigma > 0`이고 `follows`가 거짓이면 **양성** — 차용 칸만 곡 간에 흔들린다.
    `follows`가 참이면 차용 칸이 이웃 온음계 칸에 비례한다 (D-0333의 셋째 모양).
    """
    if count < 2:
        raise ValueError(f"곡이 둘 이상이어야 쌍을 만든다: {count}")
    if sigma < 0.0:
        raise ValueError(f"흔들림은 0 이상이어야 한다: {sigma}")
    if follows and sigma <= 0.0:
        raise ValueError("`follows`는 흔들림이 있어야 뜻이 있다")

    rng = np.random.default_rng(seed)
    push = mass_factor(diatonic_mass)
    diatonic = list(DIATONIC)
    made: list[ReferencePrior] = []
    for index in range(count):
        shape = rng.dirichlet(np.full(DEGREE_COUNT, SHAPE))
        if sigma > 0.0:
            for cell in BORROWED:
                noise = float(rng.standard_normal())
                if follows:
                    shape[cell] = shape[NEIGHBOUR[cell]] * _jitter(follow_sigma, noise)
                else:
                    shape[cell] *= _jitter(sigma, noise)
        # **고정 배수다.** 곡마다 다르게 밀면 온음계 블록에 곡 고유한 인자가 생긴다.
        shape[diatonic] *= push
        shape /= shape.sum()
        made.append(ReferencePrior(f"곡{index:04d}", tuple(float(value) for value in shape)))
    return made


def diatonic_mass_of(corpus: list[ReferencePrior]) -> float:
    """그 코퍼스가 **실제로** 낸 온음계 질량. **목표가 아니라 실측이다** (GR-0.5)."""
    stacked = np.asarray([item.prior for item in corpus], dtype=np.float64)
    return float(stacked[:, list(DIATONIC)].sum(axis=1).mean())
