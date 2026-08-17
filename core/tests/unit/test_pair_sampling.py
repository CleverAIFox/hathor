"""쌍대비교 라벨 수집 테스트."""

import pytest

from hathor.domain.entities.preference_comparison import PreferenceComparison, Side
from hathor.domain.services.pair_sampling import canonical, presentation_order, sample_pairs

KEYS = [f"곡{index:02d}.mp3" for index in range(12)]


def test_canonical_ignores_order():
    assert canonical("나", "가") == canonical("가", "나") == ("가", "나")


def test_sample_pairs_is_deterministic():
    assert sample_pairs(KEYS, 5, seed=7) == sample_pairs(KEYS, 5, seed=7)


def test_sample_pairs_differs_by_seed():
    assert sample_pairs(KEYS, 5, seed=7) != sample_pairs(KEYS, 5, seed=8)


def test_sample_pairs_has_no_duplicates():
    pairs = sample_pairs(KEYS, 20, seed=1)
    assert len(pairs) == len(set(pairs))


def test_sample_pairs_never_pairs_a_track_with_itself():
    assert all(left != right for left, right in sample_pairs(KEYS, 20, seed=2))


def test_sample_pairs_returns_canonical_order():
    assert all(left <= right for left, right in sample_pairs(KEYS, 20, seed=3))


def test_sample_pairs_excludes_answered():
    """세션을 나눠 수집해도 같은 문항이 반복되면 그 쌍의 가중치만 커진다."""
    first = sample_pairs(KEYS, 10, seed=4)
    second = sample_pairs(KEYS, 10, seed=4, exclude=first)
    assert not set(first) & set(second)


def test_sample_pairs_exclude_ignores_given_order():
    first = sample_pairs(KEYS, 5, seed=5)
    flipped = [(right, left) for left, right in first]
    assert not set(sample_pairs(KEYS, 5, seed=5, exclude=flipped)) & set(first)


def test_sample_pairs_stops_when_exhausted():
    """가능한 쌍이 3개뿐인데 10개를 요구해도 무한 루프에 빠지지 않는다."""
    pairs = sample_pairs(["가", "나", "다"], 10, seed=6)
    assert len(pairs) == 3


def test_sample_pairs_rejects_zero_count():
    with pytest.raises(ValueError):
        sample_pairs(KEYS, 0, seed=1)


def test_sample_pairs_rejects_single_track():
    with pytest.raises(ValueError):
        sample_pairs(["가"], 1, seed=1)


def test_presentation_order_flips_for_some_seeds():
    """좌우 고정은 위치 편향을 라벨에 싣는다."""
    pair = ("가", "나")
    orders = {presentation_order(pair, seed=seed) for seed in range(20)}
    assert orders == {("가", "나"), ("나", "가")}


def test_presentation_order_is_deterministic():
    assert presentation_order(("가", "나"), seed=3) == presentation_order(("가", "나"), seed=3)


def test_comparison_rejects_non_canonical_order():
    with pytest.raises(ValueError):
        PreferenceComparison(left="나", right="가", winner=None, recorded_at="t")


def test_comparison_rejects_self_pair():
    with pytest.raises(ValueError):
        PreferenceComparison(left="가", right="가", winner=None, recorded_at="t")


def test_comparison_preferred_resolves_winner():
    left_wins = PreferenceComparison(left="가", right="나", winner=Side.LEFT, recorded_at="t")
    right_wins = PreferenceComparison(left="가", right="나", winner=Side.RIGHT, recorded_at="t")
    assert left_wins.preferred == "가"
    assert right_wins.preferred == "나"


def test_comparison_skip_is_preserved():
    """건너뛴 문항도 정보다. 지우면 그 쌍이 다시 출제된다."""
    skipped = PreferenceComparison(left="가", right="나", winner=None, recorded_at="t")
    assert skipped.skipped
    assert skipped.preferred is None
    assert skipped.as_record()["winner"] is None
