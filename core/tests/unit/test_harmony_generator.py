"""화성 생성기 단위 테스트."""

from itertools import pairwise

import pytest

from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony

MAJOR = Key(tonic="C", mode=Mode.MAJOR)

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
    # V의 근음은 으뜸음 위 7반음이다.
    dominant = generate_harmony(1, MAJOR, bar_count=64, prior=_prior({7: 200.0}))
    assert dominant.degrees.count("V") > 50


def test_다른_사전은_다른_진행을_낸다():
    """같은 시드에서도 참조곡이 다르면 갈려야 한다 — O-21의 본문이다."""
    first = generate_harmony(7, MAJOR, bar_count=16, prior=_prior({0: 60.0}))
    second = generate_harmony(7, MAJOR, bar_count=16, prior=_prior({9: 60.0}))
    assert first.degrees != second.degrees


def test_같은_사전은_같은_진행을_낸다():
    minor = Key(tonic="A", mode=Mode.MINOR)
    prior = _prior({3: 20.0, 7: 8.0})
    assert (
        generate_harmony(3, minor, bar_count=12, prior=prior).degrees
        == generate_harmony(3, minor, bar_count=12, prior=prior).degrees
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


# ------------------------------------------------------------------ 배열 조건화 (O-32 · D-0109)


def _transition(pairs: dict[tuple[int, int], float]) -> list[list[float]]:
    matrix = [[0.0] * 12 for _ in range(12)]
    for (left, right), weight in pairs.items():
        matrix[left][right] = weight
    return matrix


def test_전이_사전이_다음_마디를_정한다():
    """**그때까지 순서는 시드만 정했다** (D-0062)."""
    prior = [1.0] + [0.0] * 11  # 첫 마디는 I
    matrix = _transition({(0, 7): 1.0, (7, 5): 1.0, (5, 0): 1.0})
    degrees = generate_harmony(7, MAJOR, 6, prior=prior, transition=matrix).degrees
    assert degrees == ("I", "V", "IV", "I", "V", "IV")


def test_마디마다_반드시_바뀐다():
    """**전이 사전은 대각선을 버렸다** (D-0103). 안 바꿀 확률이 거기 없다.

    화음을 얼마나 오래 끄는가는 O-37이다. 고정 확률로 유지하는 안은 **손잡이가 하나
    늘고 그것을 실험으로 고르면 D-0058이라** 기각했다.
    """
    prior = [1.0] * 12
    matrix = _transition({(a, b): 1.0 for a in range(12) for b in range(12) if a != b})
    degrees = generate_harmony(3, MAJOR, 32, prior=prior, transition=matrix).degrees
    assert all(left != right for left, right in pairwise(degrees))


def test_전이가_없으면_기존_동작이다():
    """**기존 산출물이 안 바뀐다.**"""
    prior = [0.2, 0.05, 0.15, 0.05, 0.1, 0.12, 0.03, 0.14, 0.04, 0.06, 0.03, 0.03]
    assert (
        generate_harmony(11, MAJOR, 8, prior=prior).degrees
        == generate_harmony(11, MAJOR, 8, prior=prior, transition=None).degrees
    )


def test_빈_전이_사전이면_물러난다():
    """창이 둘 미만이거나 한 도수만 나온 곡이 그렇다 (D-0107).

    **없는 것을 조건으로 쓰지 않는다** — 균등으로 되돌리면 사전이 있는 척이 된다.
    """
    prior = [0.2, 0.05, 0.15, 0.05, 0.1, 0.12, 0.03, 0.14, 0.04, 0.06, 0.03, 0.03]
    empty = [[0.0] * 12 for _ in range(12)]
    assert (
        generate_harmony(11, MAJOR, 8, prior=prior, transition=empty).degrees
        == generate_harmony(11, MAJOR, 8, prior=prior).degrees
    )


def test_첫_마디는_사전이_정한다():
    """**전이 사전에는 시작이 없다.**"""
    matrix = _transition({(a, b): 1.0 for a in range(12) for b in range(12) if a != b})
    only_five = [0.0] * 12
    only_five[7] = 1.0
    assert generate_harmony(5, MAJOR, 4, prior=only_five, transition=matrix).degrees[0] == "V"


def test_행이_비어도_자기_자신으로_안_돌아온다():
    """행이 비면 열 합으로 되돌아오는데 **거기 자기 자신이 들어 있다** (D-0107)."""
    prior = [1.0] * 12
    # `V`(7)에서 나가는 행이 비어 있다
    matrix = _transition({(0, 7): 1.0, (2, 7): 1.0, (4, 7): 1.0})
    degrees = generate_harmony(9, MAJOR, 12, prior=prior, transition=matrix).degrees
    assert all(left != right for left, right in pairwise(degrees))


def test_자기_전이_기본값은_산출물을_안_바꾼다():
    """**진단 손잡이가 제품 경로를 건드리면 안 된다** (O-38).

    D-0109가 `transition` 기본값에 대해 건 것과 같은 검사다. 기본값에서는 아예
    다른 갈래를 지나므로 되튐 하나 없이 같아야 한다.
    """
    prior = [0.2, 0.05, 0.15, 0.05, 0.1, 0.12, 0.03, 0.14, 0.04, 0.06, 0.03, 0.03]
    matrix = _transition({(a, b): float(a + b + 1) for a in range(12) for b in range(12) if a != b})
    assert (
        generate_harmony(3, MAJOR, 32, prior=prior, transition=matrix, self_transition=0.0).degrees
        == generate_harmony(3, MAJOR, 32, prior=prior, transition=matrix).degrees
    )


def test_자기_전이가_실제로_결과를_바꾼다():
    """**새 인자가 결과를 바꾸는지 고정한다** (O-25 · D-0064).

    `chroma(harmonic=...)`가 조용히 무시되고 있던 자리가 정확히 이것이다.
    """
    prior = [1.0] * 12
    matrix = _transition({(a, b): 1.0 for a in range(12) for b in range(12) if a != b})
    kept = generate_harmony(3, MAJOR, 64, prior=prior, transition=matrix, self_transition=0.8)
    assert any(left == right for left, right in pairwise(kept.degrees))


def test_자기_전이가_1_이상이면_거부한다():
    """1.0이면 첫 마디에 갇힌다. **바꿀 수 없는 진행은 진행이 아니다.**"""
    prior = [1.0] * 12
    matrix = _transition({(a, b): 1.0 for a in range(12) for b in range(12) if a != b})
    for bad in (1.0, -0.1):
        with pytest.raises(ValueError, match=r"\[0, 1\)"):
            generate_harmony(3, MAJOR, 8, prior=prior, transition=matrix, self_transition=bad)
