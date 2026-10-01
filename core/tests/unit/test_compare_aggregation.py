"""평균 추출과 중앙값 추출을 맞대는 자 (D-0064 · D-0337).

D-0064가 판정 지표를 **착수 전에** 정해 뒀다 — *"곡 내 홀드아웃의 달성 가능 폭
(`uniform` → `oracle`)이 0.0187에서 오르는가."* 추출은 이미 있었고 **견주는 자리가
없었다.**

**눈으로 빼면 안 된다.** `eval harmony-prior --replay`는 폭을 한 수로 찍고, 두 번 돌려
빼면 오차가 없다 — D-0327이 그 부류로 오경보율 50%짜리 판정을 돌렸다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.compare_aggregation import compare, song_widths
from hathor.domain.services.harmony_prior import HalfChroma, PriorCondition

DEGREES = 12
CONDITION = PriorCondition()


def _songs(count: int, *, sharpness: float, seed: int) -> list[HalfChroma]:
    """`sharpness`가 클수록 뒷반쪽이 뾰족하다 — **폭이 넓어진다.**"""
    rng = np.random.default_rng(seed)
    made: list[HalfChroma] = []
    for index in range(count):
        shape = rng.dirichlet(np.full(DEGREES, 1.0 / max(sharpness, 1e-6)))
        flat = np.full(DEGREES, 1.0 / DEGREES)
        made.append(
            HalfChroma(
                source_key=f"곡{index:03d}",
                tonic_pitch_class=0,
                margin=1.0,
                head=tuple(float(v) for v in flat),
                tail=tuple(float(v) for v in shape),
            )
        )
    return made


def test_뾰족하면_폭이_넓다() -> None:
    """**자의 방향을 먼저 고정한다.** 폭은 클수록 좋다 — 곡 고유 정보가 들어갈 자리다."""
    flat = song_widths(_songs(60, sharpness=0.2, seed=1), CONDITION)
    sharp = song_widths(_songs(60, sharpness=5.0, seed=1), CONDITION)

    assert np.median(list(sharp.values())) > np.median(list(flat.values()))


def test_신뢰도_낮은_곡은_뺀다() -> None:
    """`is_confident`가 거짓인 곡은 안 센다 — **조성이 틀렸으면 회전이 틀렸다.**"""
    songs = _songs(10, sharpness=2.0, seed=3)
    songs[0] = HalfChroma(
        source_key=songs[0].source_key,
        tonic_pitch_class=0,
        margin=-1.0,
        head=songs[0].head,
        tail=songs[0].tail,
    )
    assert songs[0].source_key not in song_widths(songs, CONDITION)
    assert len(song_widths(songs, CONDITION)) == 9


def test_한쪽에만_있는_곡은_뺀다() -> None:
    """**짝이 아니면 짝지은 차이가 아니다** (D-0311)."""
    median = _songs(10, sharpness=2.0, seed=5)
    mean = _songs(7, sharpness=2.0, seed=5)

    found = compare(median, mean, CONDITION)
    assert len(found.songs) == 7
    assert len(found.median_widths) == len(found.mean_widths) == 7


def test_같은_자료면_차이가_0이다() -> None:
    """**음성 대조다.** 같은 것을 두 번 넣으면 폭 차이가 정확히 0이어야 한다."""
    songs = _songs(40, sharpness=2.0, seed=7)
    found = compare(songs, songs, CONDITION)

    assert found.paired_gap.gain == pytest.approx(0.0, abs=1e-12)
    assert found.widens is False


def test_넓어지면_잡는다() -> None:
    """중앙값 쪽이 더 뾰족하면 **폭이 넓어지고 통과한다.**"""
    found = compare(
        _songs(80, sharpness=5.0, seed=11), _songs(80, sharpness=1.0, seed=11), CONDITION
    )
    assert found.paired_gap.gain > 0.0
    assert found.widens is True


def test_좁아지면_진다() -> None:
    """**질 수 있는 자여야 한다** (O-25 (2)).

    중앙값이 창별 잡음을 깎으면서 **신호도 같이 깎으면** 폭이 준다. D-0064의 (b)는
    그때 기각된다 — 자가 그것을 말할 수 있어야 한다.
    """
    found = compare(
        _songs(80, sharpness=1.0, seed=11), _songs(80, sharpness=5.0, seed=11), CONDITION
    )
    assert found.paired_gap.gain < 0.0
    assert found.widens is False


def test_곡이_없으면_없다고_말한다() -> None:
    """**없는 것을 0이라 하지 않는다** (GR-0.5). 폭 0은 「정보가 없다」로 읽힌다."""
    empty = compare([], [], CONDITION)

    assert empty.median_width is None
    assert empty.mean_width is None
    assert empty.widens is False
