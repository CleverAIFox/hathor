"""시간 축 게이트의 단위 검사 (O-32 · D-0098).

**곡별 변화·잡음·코퍼스 공통 변화를 따로 돌린다.** 셋을 섞어 두면 무엇이 통계를
움직였는지 갈리지 않고, 그것이 D-0083부터 D-0086까지 귀무선을 세 번 틀리게 만든
형태다 (O-25 (5)).
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_time_drift import (
    GATE_T,
    DriftObservation,
    EvaluateTimeDrift,
    drift_vector,
)

DEGREES = 12
KRUMHANSL = np.asarray([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
FAST = {"bootstrap": 20, "null_repeats": 8}


def _corpus(count: int, *, drift: float, noise: float, common: float = 0.0, seed: int = 7):
    """`drift`=곡마다 다른 변화 · `noise`=반쪽 추정 잡음 · `common`=코퍼스 공통 변화."""
    rng = np.random.default_rng(seed)
    shape = KRUMHANSL / KRUMHANSL.sum()
    shared = np.exp(common * np.arange(DEGREES) / DEGREES)
    made: list[DriftObservation] = []
    for index in range(count):
        base = shape * rng.lognormal(0.0, 0.30, DEGREES)
        base = base / base.sum()
        step = np.exp(rng.normal(0.0, drift, DEGREES)) if drift > 0 else np.ones(DEGREES)
        sides = []
        for _ in range(2):
            head = base * np.exp(rng.normal(0.0, noise, DEGREES))
            tail = base * step * shared * np.exp(rng.normal(0.0, noise, DEGREES))
            sides.append(drift_vector(head / head.sum(), tail / tail.sum()))
        made.append(DriftObservation(f"곡{index:04d}.flac", sides[0], sides[1]))
    return made


# ------------------------------------------------------------------ 변화 벡터


def test_전체_세기가_바뀌어도_변화_벡터는_같다():
    """**로그를 쓰는 이유다.** 반쪽마다 세기가 달라도 화성이 아니다."""
    head = np.asarray([0.1, 0.2, 0.3, 0.4] + [0.0] * 8) + 1e-6
    tail = head * 3.0
    assert drift_vector(head, tail) == pytest.approx((0.0,) * DEGREES, abs=1e-9)


def test_한_칸만_오르면_그_칸이_양수다():
    head = np.full(DEGREES, 1.0 / DEGREES)
    tail = head.copy()
    tail[5] *= 2.0
    changed = drift_vector(head, tail)
    assert changed[5] == max(changed)
    assert changed[5] > 0


def test_변화_벡터가_12차원이_아니면_거부한다():
    with pytest.raises(ValueError, match="12차원"):
        DriftObservation("곡.flac", (0.0,) * 11, (0.0,) * 12)


# ------------------------------------------------------------------ 판정


def test_곡별_변화가_없으면_게이트가_멈춘다():
    """**음성 대조.** 잡음이 있어도 안 속아야 한다 — 버린 설계는 여기서 0.448이었다."""
    report = EvaluateTimeDrift(**FAST).run(_corpus(200, drift=0.0, noise=0.20), "test")
    assert not report.time_drift_is_song_specific
    assert report.t_statistic < GATE_T


def test_곡별_변화가_있으면_게이트가_통과한다():
    report = EvaluateTimeDrift(**FAST).run(_corpus(200, drift=0.15, noise=0.20), "test")
    assert report.time_drift_is_song_specific
    assert report.cell_share > 0.5


def test_코퍼스_공통_변화는_통과시키지_않는다():
    """**모든 곡이 똑같이 변하면 참조곡을 볼 이유가 없다.** 귀무선이 그 몫을 먹는다."""
    report = EvaluateTimeDrift(**FAST).run(_corpus(200, drift=0.0, noise=0.20, common=1.0), "test")
    assert not report.time_drift_is_song_specific


def test_곡별_변화를_키우면_초과분이_단조로_커진다():
    values = [
        EvaluateTimeDrift(**FAST).run(_corpus(200, drift=level, noise=0.20), "test").excess
        for level in (0.0, 0.15, 0.30)
    ]
    assert values[0] < values[1] < values[2]


def test_문턱이_관측_문턱보다_높다():
    """**승인 문턱은 관측 문턱보다 높아야 한다** (D-0095 이후의 규율)."""
    assert GATE_T > 2.0


# ------------------------------------------------------------------ 곁가지


def test_같은_시드는_같은_수를_낸다():
    made = _corpus(120, drift=0.15, noise=0.20)
    first = EvaluateTimeDrift(**FAST).run(made, "a")
    second = EvaluateTimeDrift(**FAST).run(made, "b")
    assert first.excess == second.excess


def test_곡이_열_개_미만이면_거부한다():
    with pytest.raises(ValueError, match="10개 이상"):
        EvaluateTimeDrift(**FAST).run(_corpus(5, drift=0.1, noise=0.1), "test")


def test_반복_수가_0이면_거부한다():
    with pytest.raises(ValueError, match="반복 수"):
        EvaluateTimeDrift(bootstrap=0)
