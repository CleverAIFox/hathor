"""반음계 질량 정체 측정의 단위 검사 (O-33 · D-0089).

**합성 코퍼스에 조성 공유 모양을 넣는다** (O-25 (5)). 그 구조가 빠지면 통계가 실제
자료와 다르게 움직이고, **그것이 D-0083부터 D-0086까지 귀무선을 세 번 틀리게 만든
원인이다.**
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_chromatic_origin import (
    ROTATION_ERRORS,
    SUBSTITUTION_PAIRS,
    EvaluateChromaticOrigin,
    OriginCondition,
    substitution_correlation,
)
from hathor.application.evaluate_harmony_output import ReferencePrior
from hathor.domain.value_objects.key import Mode

DEGREES = 12
KRUMHANSL = np.asarray([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
FAST = OriginCondition(bootstrap=15, null_repeats=5)
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)


def _corpus(count: int, *, borrow: float, error: float, seed: int = 7):
    """**조성 공유 모양 위에서** 차용(첨가)과 오차(치환)를 따로 돌린다."""
    rng = np.random.default_rng(seed)
    shape = KRUMHANSL / KRUMHANSL.sum()
    made: list[ReferencePrior] = []
    for index in range(count):
        vector = shape * rng.lognormal(0.0, 0.25, DEGREES)
        if borrow > 0:
            picked = rng.choice([1, 3, 6, 8, 10], size=int(rng.integers(1, 3)), replace=False)
            vector[picked] = vector[picked] * (1 + borrow * rng.uniform(1, 4, len(picked)))
        vector = vector / vector.sum()
        if rng.random() < error:
            vector = np.roll(vector, -int(rng.choice(ROTATION_ERRORS)))
        made.append(
            ReferencePrior(f"곡{index:04d}.flac", tuple(float(v) for v in vector / vector.sum()))
        )
    return made


# ------------------------------------------------------------------ 치환 짝


@pytest.mark.parametrize("mode", [Mode.MAJOR, Mode.MINOR])
def test_치환_짝은_선법마다_다르고_반음_차이다(mode):
    """각 반음계 칸은 **짝 온음계 칸의 반음 변화**다. 그것이 조성 오차의 치환 관계이기도 하다."""
    pairs = SUBSTITUTION_PAIRS[mode]
    assert len(pairs) == 5
    for chromatic, scale in pairs:
        assert abs(chromatic - scale) == 1


def test_장조_짝은_음계_음을_가리킨다():
    for _, scale in SUBSTITUTION_PAIRS[Mode.MAJOR]:
        assert scale in MAJOR_SCALE


def test_5도_오차는_이끔음을_지우고_b7을_올린다():
    """**오차의 서명이다.** 이 관계가 도구 전체의 근거다."""
    rotated = {(pitch - 7) % DEGREES for pitch in MAJOR_SCALE}
    assert rotated - set(MAJOR_SCALE) == {10}
    assert set(MAJOR_SCALE) - rotated == {11}


# ------------------------------------------------------------------ 판정


def test_조성_오차가_있으면_치환으로_잡는다():
    """**강한 방향.** 합성에서 t = -8까지 내려간다."""
    report = EvaluateChromaticOrigin(FAST).run(_corpus(500, borrow=0.0, error=0.35), "test")
    assert report.excess < 0.0
    assert report.t_statistic < -2.0
    assert report.chromatic_is_substitution


def test_차용화음만_있으면_치환으로_안_잡는다():
    """**음성 대조.** 첨가는 음수로 안 간다."""
    report = EvaluateChromaticOrigin(FAST).run(_corpus(500, borrow=1.0, error=0.0), "test")
    assert report.excess > 0.0
    assert not report.chromatic_is_substitution


def test_둘_다_없으면_0_근처다():
    report = EvaluateChromaticOrigin(FAST).run(_corpus(800, borrow=0.0, error=0.0), "test")
    assert abs(report.excess) < 0.06


def test_오차를_늘리면_초과분이_단조로_내려간다():
    values = [
        EvaluateChromaticOrigin(FAST).run(_corpus(500, borrow=0.0, error=rate), "test").excess
        for rate in (0.0, 0.2, 0.4)
    ]
    assert values[0] > values[1] > values[2]


# ------------------------------------------------------------------ 눈금선


def test_눈금선은_회전을_넣은_값이다():
    """**실측 코퍼스로 만든 자다.** 합성이 아니다."""
    report = EvaluateChromaticOrigin(FAST).run(_corpus(500, borrow=0.0, error=0.0), "test")
    assert report.rotated_excess < report.excess


def test_회전_비율이_0이나_1이면_거부한다():
    for share in (0.0, 1.0):
        with pytest.raises(ValueError, match="회전 비율"):
            OriginCondition(rotated_share=share)


def test_반복_수가_0이면_거부한다():
    with pytest.raises(ValueError, match="반복 수"):
        OriginCondition(bootstrap=0)


# ------------------------------------------------------------------ 곁가지


def test_공유_모양만_있으면_상관이_구조를_안_만든다():
    """곡별 흔들림이 없으면 편차가 0이라 상관을 못 낸다. **0으로 나누지 않는다.**"""
    shape = KRUMHANSL / KRUMHANSL.sum()
    table = [np.asarray(shape) for _ in range(10)]
    assert substitution_correlation(table, Mode.MAJOR) == 0.0


def test_같은_시드는_같은_수를_낸다():
    made = _corpus(300, borrow=0.5, error=0.2)
    first = EvaluateChromaticOrigin(FAST).run(made, "a")
    second = EvaluateChromaticOrigin(FAST).run(made, "b")
    assert first.excess == second.excess
    assert first.standard_error == second.standard_error


def test_참조곡이_셋_미만이면_거부한다():
    with pytest.raises(ValueError, match="3개 이상"):
        EvaluateChromaticOrigin(FAST).run(_corpus(2, borrow=0.0, error=0.0), "test")


def test_온음계_질량을_함께_낸다():
    report = EvaluateChromaticOrigin(FAST).run(_corpus(300, borrow=0.0, error=0.0), "test")
    assert 0.5 < report.scale_mass < 1.0
