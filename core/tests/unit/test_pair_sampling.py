"""쌍대비교 라벨 수집 테스트."""

import numpy as np
import pytest

from hathor.domain.entities.preference_comparison import PreferenceComparison, Side, agreement
from hathor.domain.services.pair_sampling import (
    canonical,
    presentation_order,
    sample_index_pairs,
    sample_pairs,
    with_repeats,
)

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


# ------------------------------------------------- 되묻기 · 판정자의 천장 (D-0421)


ANSWERED = [canonical(f"곡{i:02d}.mp3", f"곡{i + 1:02d}.mp3") for i in range(0, 10, 2)]


def _asked(count=20, answered=ANSWERED, *, seed=3, **kwargs):
    fresh = sample_pairs(KEYS, count, seed=seed, exclude=answered)
    return with_repeats(fresh, answered, seed=seed, **kwargs), fresh


def test_되묻기가_몫만큼_섞인다():
    """**천장을 재려면 같은 쌍을 다시 물어야 한다** (D-0421).

    10%면 20문항에 2번이다. 더 키우면 새 라벨이 줄고, 새 라벨이 모형을 만든다.
    """
    asked, fresh = _asked(20)

    assert sum(1 for _, again in asked if again) == 2
    assert len(asked) == len(fresh) + 2


def test_되묻기는_이미_답한_쌍에서만_나온다():
    """**새 쌍을 되묻기라 적으면 천장이 아니라 잡음을 잰다.**"""
    asked, _ = _asked(20)

    assert [pair for pair, again in asked if again] and all(
        pair in ANSWERED for pair, again in asked if again
    )


def test_새_문항은_하나도_안_빠진다():
    """되묻기를 섞느라 **새 라벨을 잃으면 안 된다.**"""
    asked, fresh = _asked(20)

    assert sorted(pair for pair, again in asked if not again) == sorted(fresh)


def test_되묻기가_끝에_안_몰린다():
    """**몰리면 사람이 알아챈다** — 알아챈 순간부터 답이 달라져 천장이 아니다."""
    asked, _ = _asked(60)

    places = [index for index, (_, again) in enumerate(asked) if again]
    assert places, "되묻기가 없다 — 이 검사가 빈 그물이다 (D-0230)"
    assert min(places) < len(asked) // 2, f"전부 뒷절반에 있다: {places}"


def test_답한_것이_없으면_안_되묻는다():
    """첫 세션에는 되물을 것이 없다. **지어내지 않는다** (GR-0.5)."""
    asked, fresh = _asked(20, [])

    assert [pair for pair, _ in asked] and len(asked) == len(fresh)
    assert not any(again for _, again in asked)


def test_몫이_1이상이면_거부한다():
    with pytest.raises(ValueError, match="되묻는 몫"):
        _asked(20, share=1.0)


def _said(*rows):
    return [
        PreferenceComparison(left=left, right=right, winner=winner, recorded_at="t")
        for left, right, winner in rows
    ]


def test_자기일치는_같은_쌍의_두_답을_견준다():
    said = _said(
        ("가", "나", Side.LEFT),
        ("가", "나", Side.LEFT),
        ("다", "라", Side.LEFT),
        ("다", "라", Side.RIGHT),
    )

    assert agreement(said) == (2, 1)


def test_한_번만_물은_쌍은_안_센다():
    """**천장은 되물은 쌍에서만 나온다.** 한 번짜리를 세면 분모가 부풀어 100%가 된다."""
    assert agreement(_said(("가", "나", Side.LEFT))) == (0, 0)


def test_건너뛴_것은_일치의_증거가_아니다():
    """판단을 안 한 것은 **일관된 것이 아니다.**"""
    said = _said(("가", "나", None), ("가", "나", None), ("가", "나", Side.LEFT))

    assert agreement(said) == (0, 0)


def test_세_번_물으면_언제나_첫_답과_견준다():
    """**학습 집합에 들어가는 라벨이 첫 답이다** — 모형이 맞혀야 하는 것이 그것이다.

    연달아 견주면 `A·B·A`가 0/2가 된다. 첫 답 기준이면 1/2이다. 둘 다 말이 되므로
    **정해 두지 않으면 나중에 조용히 바뀐다** (D-0043).
    """
    said = _said(("가", "나", Side.LEFT), ("가", "나", Side.RIGHT), ("가", "나", Side.LEFT))

    assert agreement(said) == (2, 1)


# ------------------------------------------------- 자리 번호 쌍 (D-0446)


def test_자리_번호_쌍은_겹치지_않는다():
    """**`evaluate_harmony_output`이 여기 있던 것을 제 안에 다시 짰다** (D-0424).

    베끼면서 `seen`/`continue`가 빠져 매 바퀴 무조건 담았고, 그래서 `limit`과
    `raise`가 **닿지 않는 코드**가 돼 있었다.
    """
    pairs = sample_index_pairs(12, 20, generator=np.random.default_rng([7, 0]))
    keyed = [tuple(sorted(pair)) for pair in pairs]

    assert len(pairs) == 20
    assert len(keyed) == len(set(keyed))
    assert all(left != right for left, right in pairs)


def test_자리_번호_쌍은_시드가_같으면_같다():
    first = sample_index_pairs(30, 15, generator=np.random.default_rng([3, 0]))
    again = sample_index_pairs(30, 15, generator=np.random.default_rng([3, 0]))

    assert first == again


def test_쌍이_모자라면_조용히_덜_내지_않는다():
    """**풀이 마르면 운다** (D-0230). 덜 내면 적은 표본으로 잰 것이 되고 수만 작아진다."""
    # 곡 넷이면 가능한 쌍이 여섯뿐이다.
    with pytest.raises(ValueError, match="겹치지 않는 쌍 20개를 못 만들었다"):
        sample_index_pairs(4, 20, generator=np.random.default_rng([1, 0]))


def test_곡이_하나면_쌍이_없다():
    with pytest.raises(ValueError, match="둘 이상"):
        sample_index_pairs(1, 5, generator=np.random.default_rng([1, 0]))
