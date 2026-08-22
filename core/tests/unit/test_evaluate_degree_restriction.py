"""도수 제한 손실 측정의 단위 검사 (O-31 · D-0083).

**양성 대조와 음성 대조를 둘 다 둔다.** 비음계 칸에 곡 고유 성분을 넣고 빼면서
판정이 뒤집히는지 본다 — 뒤집히지 않으면 늘 통과하는 하네스다 (GR-0.9).
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_degree_restriction import (
    EvaluateDegreeRestriction,
    cell_share,
    chromatic_indices,
    off_scale_indices,
    off_scale_share,
    scale_but_discarded,
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


# ------------------------------------------------------------------ 질량 보존 귀무선


def _split_references(
    count: int, *, off_signal: float, off_mass: float, seed: int = 9
) -> list[ReferencePrior]:
    """**비음계 질량과 곡 고유 성분을 따로 돌린다.** 둘을 갈라야 교란이 보인다 (D-0084)."""
    off = list(off_scale_indices(Mode.MAJOR))
    on = [index for index in range(DEGREES) if index not in off]
    rng = np.random.default_rng(seed)
    shared = rng.dirichlet(np.full(len(off), 2.0))
    made: list[ReferencePrior] = []
    for index in range(count):
        vector = np.zeros(DEGREES)
        vector[on] = rng.dirichlet(np.full(len(on), 0.8)) * (1.0 - off_mass)
        raw = rng.dirichlet(np.full(len(off), 0.8))
        mixed = (1.0 - off_signal) * shared + off_signal * raw
        vector[off] = mixed / mixed.sum() * off_mass
        made.append(
            ReferencePrior(f"곡{index:03d}.flac", tuple(float(v) for v in vector / vector.sum()))
        )
    return made


def test_전체_치환은_질량을_바꾼다():
    """**D-0083의 결함이다.** 12칸을 뒤섞으면 비음계 칸이 붙드는 질량이 달라진다."""
    made = _split_references(60, off_signal=0.5, off_mass=0.35)
    report = EvaluateDegreeRestriction(FAST).run(made, "test")
    assert report.line("observed").mean_mass == pytest.approx(0.35, abs=0.02)
    assert report.line("shuffled").mean_mass > report.line("observed").mean_mass + 0.05


def test_조_내_치환은_질량을_보존한다():
    made = _split_references(60, off_signal=0.5, off_mass=0.35)
    report = EvaluateDegreeRestriction(FAST).run(made, "test")
    assert report.line("within").mean_mass == pytest.approx(
        report.line("observed").mean_mass, abs=1e-9
    )


@pytest.mark.parametrize("mass", [0.35, 0.50])
def test_조_내_치환_판정은_질량과_무관하다(mass):
    """**전체 치환 차이는 질량에 따라 흔들리는데 조 내 치환은 0 교차점이 고정이다.**"""
    shared = EvaluateDegreeRestriction(FAST).run(
        _split_references(60, off_signal=0.0, off_mass=mass), "test"
    )
    specific = EvaluateDegreeRestriction(FAST).run(
        _split_references(60, off_signal=1.0, off_mass=mass), "test"
    )
    assert shared.off_scale_is_shared
    assert not specific.off_scale_is_shared


def test_곡_고유_성분을_올리면_질량_보존_차이가_단조로_커진다():
    gaps = [
        EvaluateDegreeRestriction(FAST)
        .run(_split_references(60, off_signal=signal, off_mass=0.4), "test")
        .mass_matched_gap
        for signal in (0.0, 0.5, 1.0)
    ]
    assert gaps[0] < gaps[1] < gaps[2]


def test_몫_질량_비를_낸다():
    """질량 교란을 눈으로 잡는 자리다 (D-0084)."""
    report = EvaluateDegreeRestriction(FAST).run(_references(40, off_signal=0.0), "test")
    assert report.line("observed").share_per_mass > 0.0


# ------------------------------------------------------------------ 칸 쪼개기 (D-0085)


@pytest.mark.parametrize(
    "mode,scale,chromatic",
    [(Mode.MAJOR, (11,), (1, 3, 6, 8, 10)), (Mode.MINOR, (2,), (1, 4, 6, 9, 11))],
)
def test_버리는_칸_중_하나는_온음계_음이다(mode, scale, chromatic):
    """**반음계음이 아니다.** 감화음을 코드 풀에서 뺐다는 이유로 음 자체가 버려진다.

    장조의 반음 11은 C장조의 B, 이끔음이며 V화음 구성음이다.
    """
    assert scale_but_discarded(mode) == scale
    assert chromatic_indices(mode) == chromatic
    assert set(scale) | set(chromatic) == set(off_scale_indices(mode))


def test_온음계_몫과_반음계_몫을_더하면_전체_몫이다():
    """**쪼개도 합이 보존돼야 한다.** 전변동은 칸별 절댓값의 합이다."""
    report = EvaluateDegreeRestriction(FAST).run(_references(40, off_signal=0.5), "test")
    line = report.line("observed")
    assert line.mean_scale_share + line.mean_chromatic_share == pytest.approx(
        line.mean_share, abs=1e-9
    )


def test_이끔음만_다르면_온음계_몫이_1이다():
    left = np.full(DEGREES, 1.0 / DEGREES)
    right = left.copy()
    right[11] += 0.1
    assert cell_share(left, right, scale_but_discarded(Mode.MAJOR)) == pytest.approx(1.0)
    assert cell_share(left, right, chromatic_indices(Mode.MAJOR)) == pytest.approx(0.0)


# ------------------------------------------------------------------ 등가선 (D-0086)

KRUMHANSL = np.asarray([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])


def _tonal_references(count: int, *, off_jitter: float, on_jitter: float = 0.25, seed=4):
    """**코퍼스가 공유하는 조성 모양을 넣는다** (D-0086).

    이 구조가 없으면 통계가 실제 자료와 다르게 움직이고, **그것이 D-0083부터 D-0085까지
    귀무선을 세 번 틀리게 만든 원인이다.** 합성 귀무 자료는 실측에서 확인된 구조를
    재현해야 한다 (O-25 (5)).
    """
    off = list(off_scale_indices(Mode.MAJOR))
    on = [index for index in range(DEGREES) if index not in off]
    rng = np.random.default_rng(seed)
    shape = KRUMHANSL / KRUMHANSL.sum()
    made = []
    for index in range(count):
        vector = shape.copy()
        vector[on] = vector[on] * rng.lognormal(0.0, on_jitter, len(on))
        vector[off] = vector[off] * rng.lognormal(0.0, off_jitter, len(off))
        made.append(
            ReferencePrior(f"곡{index:03d}.flac", tuple(float(v) for v in vector / vector.sum()))
        )
    return made


def test_등가선은_두_조가_같을_때_0이_된다():
    """**눈금이 자료에서 나온다.** 모형 가정이 없다."""
    made = _tonal_references(200, off_jitter=0.25, on_jitter=0.25)
    report = EvaluateDegreeRestriction(OutputCondition(pair_count=200)).run(made, "test")
    assert report.specificity_gap == pytest.approx(0.0, abs=0.02)


def test_비음계_성분이_작으면_등가선보다_아래다():
    made = _tonal_references(200, off_jitter=0.02, on_jitter=0.25)
    report = EvaluateDegreeRestriction(OutputCondition(pair_count=200)).run(made, "test")
    assert report.specificity_gap < 0.0
    assert not report.off_scale_exceeds_matched


def test_비음계_성분이_크면_등가선보다_위다():
    made = _tonal_references(200, off_jitter=0.7, on_jitter=0.25)
    report = EvaluateDegreeRestriction(OutputCondition(pair_count=200)).run(made, "test")
    assert report.specificity_gap > 0.0
    assert report.off_scale_exceeds_matched


def test_조_내_치환의_0점은_0이_아니다():
    """**D-0085가 부호만 보고 읽은 자리다.** 두 조를 똑같이 맞춰도 양수가 나온다."""
    made = _tonal_references(200, off_jitter=0.25, on_jitter=0.25)
    report = EvaluateDegreeRestriction(OutputCondition(pair_count=200)).run(made, "test")
    assert report.mass_matched_gap > 0.02


def test_등가선은_조별_질량을_보존한다():
    made = _tonal_references(100, off_jitter=0.3)
    report = EvaluateDegreeRestriction(OutputCondition(pair_count=50)).run(made, "test")
    assert report.line("matched").mean_mass == pytest.approx(
        report.line("observed").mean_mass, abs=1e-9
    )
