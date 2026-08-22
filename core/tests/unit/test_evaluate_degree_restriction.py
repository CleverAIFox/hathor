"""도수 제한 손실 측정의 단위 검사 (O-31 · D-0083).

**양성 대조와 음성 대조를 둘 다 둔다.** 비음계 칸에 곡 고유 성분을 넣고 빼면서
판정이 뒤집히는지 본다 — 뒤집히지 않으면 늘 통과하는 하네스다 (GR-0.9).
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_degree_restriction import (
    EvaluateDegreeRestriction,
    off_scale_indices,
    off_scale_share,
)
from hathor.application.evaluate_harmony_output import OutputCondition, ReferencePrior
from hathor.domain.value_objects.key import Key, Mode

DEGREES = 12
FAST = OutputCondition(pair_count=40)


def _references(count: int, *, off_signal: float, seed: int = 5) -> list[ReferencePrior]:
    """`off_signal`이 비음계 칸에 곡 고유 성분을 얼마나 남길지 정한다.

    0이면 비음계 칸은 곡마다 같고(균등 성분), 1이면 다이어토닉 칸만큼 곡 고유하다.
    **이 손잡이가 있어야 판정이 질 수 있는지 확인된다.**
    """
    off = list(off_scale_indices(Mode.MAJOR))
    rng = np.random.default_rng(seed)
    shared = rng.dirichlet(np.full(len(off), 2.0))
    made: list[ReferencePrior] = []
    for index in range(count):
        vector = rng.dirichlet(np.full(DEGREES, 0.8))
        mass = float(vector[off].sum())
        vector[off] = (1.0 - off_signal) * shared * mass + off_signal * vector[off]
        made.append(
            ReferencePrior(f"곡{index:03d}.flac", tuple(float(v) for v in vector / vector.sum()))
        )
    return made


# ------------------------------------------------------------------ 칸 나누기


@pytest.mark.parametrize(
    "mode,expected", [(Mode.MAJOR, (1, 3, 6, 8, 10, 11)), (Mode.MINOR, (1, 2, 4, 6, 9, 11))]
)
def test_버리는_칸은_선법마다_다르다(mode, expected):
    """**장조 기준으로 박으면 단조에서 틀린다.**"""
    assert off_scale_indices(mode) == expected


def test_다이어토닉만_다르면_비음계_몫이_0이다():
    left = np.full(DEGREES, 1.0 / DEGREES)
    right = left.copy()
    right[0] += 0.1  # 으뜸음은 다이어토닉이다
    assert off_scale_share(left, right, Mode.MAJOR) == pytest.approx(0.0)


def test_비음계만_다르면_몫이_1이다():
    left = np.full(DEGREES, 1.0 / DEGREES)
    right = left.copy()
    right[1] += 0.1  # 단2도는 장조 다이어토닉이 아니다
    assert off_scale_share(left, right, Mode.MAJOR) == pytest.approx(1.0)


def test_같은_사전이면_몫이_0이다():
    """거리가 0이면 나눌 것이 없다. **0으로 나누지 않는다.**"""
    left = np.full(DEGREES, 1.0 / DEGREES)
    assert off_scale_share(left, left, Mode.MAJOR) == 0.0


# ------------------------------------------------------------------ 판정


def test_비음계_칸이_균등_성분이면_제한이_옳다():
    """**양성 대조.** D-0063이 가정한 상황이다."""
    report = EvaluateDegreeRestriction(FAST).run(_references(60, off_signal=0.0), "test")
    assert report.gap < 0.0
    assert report.win_rate > 0.5
    assert report.restriction_is_sound


def test_비음계_칸이_곡_고유하면_제한이_정보를_버린다():
    """**음성 대조.** 이것이 안 뒤집히면 판정 규칙이 이길 수만 있는 규칙이다."""
    report = EvaluateDegreeRestriction(FAST).run(_references(60, off_signal=1.0), "test")
    assert not report.restriction_is_sound


def test_곡_고유_성분을_올리면_차이가_단조로_줄어든다():
    """탐색에서 -0.208에서 +0.003까지 올라온 것을 검사로 고정한다."""
    gaps = [
        EvaluateDegreeRestriction(FAST).run(_references(60, off_signal=signal), "test").gap
        for signal in (0.0, 0.5, 1.0)
    ]
    assert gaps[0] < gaps[1] < gaps[2]


def test_치환_귀무선은_칸_수_비율_근처다():
    """칸 정체성을 지우면 6/12에 가까워진다. **그러나 그것이 기준선은 아니다** —

    사전 질량이 다이어토닉에 몰리면 실측 몫은 자연히 낮아지므로, 질량을 그대로 둔
    치환선과 견줘야 한다.
    """
    report = EvaluateDegreeRestriction(FAST).run(_references(60, off_signal=0.0), "test")
    assert report.line("shuffled").mean_share == pytest.approx(0.5, abs=0.08)


# ------------------------------------------------------------------ 곁가지


def test_제한_후_거리와_질량을_함께_낸다():
    report = EvaluateDegreeRestriction(FAST).run(_references(40, off_signal=0.0), "test")
    observed = report.line("observed")
    assert 0.0 < observed.mean_mass < 1.0
    assert observed.survival > 0.0
    assert -1.0 <= observed.rank_agreement <= 1.0


def test_같은_시드는_같은_수를_낸다():
    made = _references(40, off_signal=0.3)
    first = EvaluateDegreeRestriction(FAST).run(made, "a")
    second = EvaluateDegreeRestriction(FAST).run(made, "b")
    assert first.gap == second.gap


def test_단조에서도_돈다():
    from dataclasses import replace

    condition = replace(FAST, key=Key(tonic="A", mode=Mode.MINOR))
    report = EvaluateDegreeRestriction(condition).run(_references(40, off_signal=0.0), "test")
    assert report.line("observed").mean_share > 0.0


def test_참조곡이_둘_미만이면_거부한다():
    with pytest.raises(ValueError, match="2개 이상"):
        EvaluateDegreeRestriction(FAST).run(_references(1, off_signal=0.0), "test")


def test_없는_비교선을_찾으면_거부한다():
    report = EvaluateDegreeRestriction(FAST).run(_references(40, off_signal=0.0), "test")
    with pytest.raises(KeyError):
        report.line("없는선")
