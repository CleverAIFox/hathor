"""화성 도수 사전 비교의 단위 테스트.

**양성 대조와 음성 대조를 둘 다 둔다.** 하네스가 "정보 있음"을 낼 수 있다는 것만
확인하면 늘 통과하는 하네스와 구분되지 않는다. D-0061이 남긴 교훈이 정확히 그것이다 —
이길 수 없는 비교는 비교가 아니다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services.harmony_prior import (
    DEGREE_COUNT,
    HalfChroma,
    PriorCondition,
    _derangement,
    _leave_one_out_mean,
    compare_priors,
    cross_entropy,
    rotate_to_degrees,
    smooth,
)


def _observations(
    heads: np.ndarray, tails: np.ndarray, *, margin: float = 0.2, tonic: int = 0
) -> list[HalfChroma]:
    return [
        HalfChroma(
            source_key=f"곡{index:03d}.flac",
            tonic_pitch_class=tonic,
            margin=margin,
            head=tuple(float(value) for value in head),
            tail=tuple(float(value) for value in tail),
        )
        for index, (head, tail) in enumerate(zip(heads, tails, strict=True))
    ]


def _dirichlet(rng: np.random.Generator, count: int, concentration: float) -> np.ndarray:
    return rng.dirichlet(np.full(DEGREE_COUNT, concentration), size=count)


# --------------------------------------------------------------------- 회전


def test_회전은_으뜸음을_0번_인덱스로_옮긴다():
    chroma = np.zeros(DEGREE_COUNT)
    chroma[7] = 1.0  # G
    rotated = rotate_to_degrees(chroma, 7)
    assert rotated[0] == pytest.approx(1.0)


def test_회전은_원형이며_에너지를_보존한다():
    chroma = np.arange(DEGREE_COUNT, dtype=np.float64)
    rotated = rotate_to_degrees(chroma, 5)
    assert rotated.sum() == pytest.approx(chroma.sum())
    assert rotated[7] == pytest.approx(chroma[0])


def test_회전은_12차원이_아니면_거부한다():
    with pytest.raises(ValueError, match="12차원"):
        rotate_to_degrees(np.zeros(11), 0)


def test_회전은_범위_밖_으뜸음을_거부한다():
    with pytest.raises(ValueError, match="0~11"):
        rotate_to_degrees(np.zeros(DEGREE_COUNT), 12)


# ----------------------------------------------------------------- 교차 엔트로피


def test_균등_예측의_교차_엔트로피는_log12이다():
    rng = np.random.default_rng(0)
    targets = _dirichlet(rng, 5, 1.0)
    predictions = np.full_like(targets, 1.0 / DEGREE_COUNT)
    assert cross_entropy(targets, predictions) == pytest.approx(np.log(DEGREE_COUNT))


def test_자기_자신을_예측하면_교차_엔트로피가_가장_낮다():
    rng = np.random.default_rng(1)
    targets = _dirichlet(rng, 20, 0.5)
    other = _dirichlet(rng, 20, 0.5)
    assert np.all(cross_entropy(targets, targets) <= cross_entropy(targets, other))


def test_모양이_다르면_거부한다():
    with pytest.raises(ValueError, match="모양이 다르다"):
        cross_entropy(np.zeros((2, DEGREE_COUNT)), np.zeros((3, DEGREE_COUNT)))


def test_평활은_0을_없애고_합을_보존한다():
    distribution = np.zeros((1, DEGREE_COUNT))
    distribution[0, 0] = 1.0
    smoothed = smooth(distribution, PriorCondition(smoothing=0.1))
    assert float(smoothed.sum()) == pytest.approx(1.0)
    assert float(smoothed.min()) > 0.0


# --------------------------------------------------------------- 누수 방지 장치


def test_코퍼스_평균은_자기_자신을_뺀다():
    heads = np.eye(3, DEGREE_COUNT)
    mean = _leave_one_out_mean(heads)
    # 0번 곡의 예측에 0번 성분이 없어야 한다.
    assert mean[0, 0] == pytest.approx(0.0)
    assert mean[0, 1] == pytest.approx(0.5)


def test_코퍼스_평균은_한_곡으로는_계산되지_않는다():
    with pytest.raises(ValueError, match="2개 이상"):
        _leave_one_out_mean(np.zeros((1, DEGREE_COUNT)))


def test_짝짓기에_고정점이_없다():
    for count in (2, 3, 17, 100):
        pairing = _derangement(count, PriorCondition())
        assert not np.any(pairing == np.arange(count))
        assert sorted(pairing.tolist()) == list(range(count))


# ------------------------------------------------------------------- 조건 객체


def test_조건은_평활_범위를_검사한다():
    with pytest.raises(ValueError, match="smoothing"):
        PriorCondition(smoothing=1.0)


def test_조건은_음수_배음_감산을_거부한다():
    with pytest.raises(ValueError, match="harmonic"):
        PriorCondition(harmonic=-0.1)


def test_조건은_람다_격자를_검사한다():
    with pytest.raises(ValueError, match="blend_steps"):
        PriorCondition(blend_steps=1)


def test_배음_감산은_네_선_전부에_적용된다():
    """조건을 바꾸면 귀무선까지 따라 움직여야 한다 (O-25).

    코퍼스만 감산하고 베이스라인을 그대로 두는 것이 D-0059 · D-0060의 결함이었다.
    """
    rng = np.random.default_rng(7)
    latent = _dirichlet(rng, 40, 0.6)
    heads = latent + _dirichlet(rng, 40, 3.0) * 0.3
    tails = latent + _dirichlet(rng, 40, 3.0) * 0.3
    observations = _observations(heads, tails)

    plain = compare_priors(observations, PriorCondition(harmonic=0.0))
    reduced = compare_priors(observations, PriorCondition(harmonic=0.5))
    assert plain.other_score != pytest.approx(reduced.other_score)
    assert plain.corpus_score != pytest.approx(reduced.corpus_score)


# ----------------------------------------------------------------- 곡선 정합성


def test_람다_양_끝은_코퍼스선과_자기선이다():
    rng = np.random.default_rng(11)
    observations = _observations(_dirichlet(rng, 30, 0.8), _dirichlet(rng, 30, 0.8))
    result = compare_priors(observations)
    assert result.lambdas[0] == pytest.approx(0.0)
    assert result.lambdas[-1] == pytest.approx(1.0)
    assert result.self_curve[0] == pytest.approx(result.corpus_score)
    assert result.self_curve[-1] == pytest.approx(result.self_score)
    assert result.other_curve[0] == pytest.approx(result.corpus_score)


def test_코퍼스_공통_구조가_있어야_균등을_넘는다():
    """**균등은 천장이 아니다.**

    코퍼스에 공통 구조가 있으면 코퍼스 평균이 균등을 넘고, 없으면 균등이 최적이라
    코퍼스 평균은 그것의 잡음 섞인 추정치라 진다. 두 경우를 다 고정한다.
    """
    rng = np.random.default_rng(13)
    shared = rng.dirichlet(np.full(DEGREE_COUNT, 0.3))
    structured = 0.7 * shared + 0.3 * _dirichlet(rng, 60, 5.0)
    with_structure = compare_priors(_observations(structured, structured))
    assert with_structure.corpus_score < with_structure.uniform_score

    # 공통 구조가 없으면 균등이 최적이므로 코퍼스 평균의 이득이 사라진다.
    # **중앙값이라 균등을 밑돌 수도 있다** — 부호를 고정하지 않고 격차만 본다.
    flat = _dirichlet(rng, 60, 0.5)
    without_structure = compare_priors(_observations(flat, flat))
    structured_gain = with_structure.uniform_score - with_structure.corpus_score
    flat_gain = without_structure.uniform_score - without_structure.corpus_score
    assert structured_gain > flat_gain


# ------------------------------------------------------------------- 양성 대조


def test_곡_고유_신호가_있으면_정보가_있다고_판정한다():
    """곡마다 다른 잠재 분포를 두고 앞뒤 반쪽을 그것에서 뽑는다."""
    rng = np.random.default_rng(20260819)
    latent = _dirichlet(rng, 120, 0.4)
    noise_head = _dirichlet(rng, 120, 5.0)
    noise_tail = _dirichlet(rng, 120, 5.0)
    heads = 0.75 * latent + 0.25 * noise_head
    tails = 0.75 * latent + 0.25 * noise_tail

    result = compare_priors(_observations(heads, tails))
    assert result.is_conditioning_informative
    assert result.best_lambda > 0.0
    assert result.self_win_rate > 0.5
    assert result.self_score < result.other_score


# ------------------------------------------------------------------- 음성 대조


def test_곡_고유_신호가_없으면_정보가_없다고_판정한다():
    """모든 곡이 같은 잠재 분포를 공유하면 자기 반쪽은 잡음일 뿐이다.

    **이 검사가 통과해야 하네스가 판정 장치다.** 늘 "정보 있음"을 내는 하네스는
    이길 수 없는 지표와 같다.
    """
    rng = np.random.default_rng(20260820)
    shared = rng.dirichlet(np.full(DEGREE_COUNT, 0.4))
    heads = 0.2 * shared + 0.8 * _dirichlet(rng, 120, 5.0)
    tails = 0.2 * shared + 0.8 * _dirichlet(rng, 120, 5.0)

    result = compare_priors(_observations(heads, tails))
    assert not result.is_conditioning_informative
    assert result.best_lambda == pytest.approx(0.0)


def test_귀무선의_최적_람다는_0이다():
    """틀린 곡을 섞는 것이 도움이 되면 지표가 고장 난 것이다."""
    rng = np.random.default_rng(20260821)
    latent = _dirichlet(rng, 120, 0.4)
    heads = 0.75 * latent + 0.25 * _dirichlet(rng, 120, 5.0)
    tails = 0.75 * latent + 0.25 * _dirichlet(rng, 120, 5.0)
    result = compare_priors(_observations(heads, tails))
    assert result.null_lambda == pytest.approx(0.0)


# ------------------------------------------------------------------ 애매한 곡


def test_애매한_곡을_세고_걸러낸다():
    rng = np.random.default_rng(31)
    heads = _dirichlet(rng, 20, 0.8)
    tails = _dirichlet(rng, 20, 0.8)
    observations = _observations(heads, tails, margin=0.2)
    observations[:6] = [
        HalfChroma(
            source_key=item.source_key,
            tonic_pitch_class=item.tonic_pitch_class,
            margin=0.01,
            head=item.head,
            tail=item.tail,
        )
        for item in observations[:6]
    ]
    everything = compare_priors(observations, PriorCondition())
    confident = compare_priors(observations, PriorCondition(confident_only=True))
    assert everything.ambiguous_count == 6
    assert everything.song_count == 20
    assert confident.song_count == 14


def test_회전이_다른_으뜸음에도_정보를_보존한다():
    """으뜸음이 곡마다 달라도 도수 공간에서는 정렬돼야 한다."""
    rng = np.random.default_rng(41)
    latent = _dirichlet(rng, 80, 0.4)
    heads = 0.8 * latent + 0.2 * _dirichlet(rng, 80, 5.0)
    tails = 0.8 * latent + 0.2 * _dirichlet(rng, 80, 5.0)
    tonics = rng.integers(0, DEGREE_COUNT, size=80)
    observations = [
        HalfChroma(
            source_key=f"곡{index}.flac",
            tonic_pitch_class=int(tonic),
            margin=0.2,
            # 도수 공간의 잠재값을 피치클래스 공간으로 되돌려 저장한다.
            head=tuple(float(value) for value in np.roll(heads[index], int(tonic))),
            tail=tuple(float(value) for value in np.roll(tails[index], int(tonic))),
        )
        for index, tonic in enumerate(tonics)
    ]
    result = compare_priors(observations)
    assert result.is_conditioning_informative


def test_곡이_둘_미만이면_거부한다():
    rng = np.random.default_rng(51)
    with pytest.raises(ValueError, match="2개 이상"):
        compare_priors(_observations(_dirichlet(rng, 1, 1.0), _dirichlet(rng, 1, 1.0)))


def test_관측은_차원과_으뜸음을_검사한다():
    with pytest.raises(ValueError, match="12차원"):
        HalfChroma(source_key="a", tonic_pitch_class=0, margin=0.1, head=(1.0,), tail=(1.0,) * 12)
    with pytest.raises(ValueError, match="0~11"):
        HalfChroma(
            source_key="a", tonic_pitch_class=99, margin=0.1, head=(1.0,) * 12, tail=(1.0,) * 12
        )
