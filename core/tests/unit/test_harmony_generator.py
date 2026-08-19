"""화성 생성기 단위 테스트."""

import pytest

from hathor.engines.compose.harmony_generator import generate_harmony

# ------------------------------------------------- 참조곡 조건화 (O-21 · D-0063)


def _prior(peaks: dict[int, float]) -> list[float]:
    """지정한 도수만 높은 12차원 사전."""
    vector = [1.0] * 12
    for index, value in peaks.items():
        vector[index] = value
    total = sum(vector)
    return [value / total for value in vector]


def test_사전을_주지_않으면_이전과_완전히_같다():
    """**기존 산출물이 바뀌지 않는다.** 조건화는 순수 추가다."""
    from hathor.domain.value_objects.key import Key, Mode

    for seed in (0, 7, 42, 20260819):
        for key in (Key(tonic="C", mode=Mode.MAJOR), Key(tonic="F#", mode=Mode.MINOR)):
            assert (
                generate_harmony(seed, key, bar_count=8).degrees
                == generate_harmony(seed, key, bar_count=8, prior=None).degrees
            )


def test_사전이_치우치면_그_도수가_많이_뽑힌다():
    from hathor.domain.value_objects.key import Key, Mode

    key = Key(tonic="C", mode=Mode.MAJOR)
    # V의 근음은 으뜸음 위 7반음이다.
    dominant = generate_harmony(1, key, bar_count=64, prior=_prior({7: 200.0}))
    assert dominant.degrees.count("V") > 50


def test_다른_사전은_다른_진행을_낸다():
    """같은 시드에서도 참조곡이 다르면 갈려야 한다 — O-21의 본문이다."""
    from hathor.domain.value_objects.key import Key, Mode

    key = Key(tonic="C", mode=Mode.MAJOR)
    first = generate_harmony(7, key, bar_count=16, prior=_prior({0: 60.0}))
    second = generate_harmony(7, key, bar_count=16, prior=_prior({9: 60.0}))
    assert first.degrees != second.degrees


def test_같은_사전은_같은_진행을_낸다():
    from hathor.domain.value_objects.key import Key, Mode

    key = Key(tonic="A", mode=Mode.MINOR)
    prior = _prior({3: 20.0, 7: 8.0})
    assert (
        generate_harmony(3, key, bar_count=12, prior=prior).degrees
        == generate_harmony(3, key, bar_count=12, prior=prior).degrees
    )


def test_가중치는_다이어토닉_6도수만_남기고_정규화한다():
    from hathor.domain.value_objects.key import Mode
    from hathor.engines.compose.harmony_generator import degree_weights

    weights = degree_weights(_prior({1: 500.0}), Mode.MAJOR)
    # 1반음은 장조 다이어토닉 근음이 아니므로 버려지고 6칸은 균등해야 한다.
    assert len(weights) == 6
    assert sum(weights) == pytest.approx(1.0)
    assert max(weights) == pytest.approx(min(weights))


def test_가중치가_전부_0이면_균등으로_되돌린다():
    from hathor.domain.value_objects.key import Mode
    from hathor.engines.compose.harmony_generator import degree_weights

    weights = degree_weights([0.0] * 12, Mode.MINOR)
    assert sum(weights) == pytest.approx(1.0)
    assert max(weights) == pytest.approx(min(weights))


def test_사전이_12차원이_아니면_거부한다():
    from hathor.domain.value_objects.key import Mode
    from hathor.engines.compose.harmony_generator import degree_weights

    with pytest.raises(ValueError, match="12차원"):
        degree_weights([0.1] * 11, Mode.MAJOR)
