"""후렴 구간 찾기 (D-0430).

**합성 자료로 선을 긋는다.** 실물 1004곡에서 얼마나 맞는지는 사람이 들어야 알고,
그 수는 D-0430이 연 질문이다 — 여기서 재는 것은 **옮긴 셈이 논문대로 도는가**다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services.thumbnail import (
    LATEST_START_SHARE,
    Thumbnail,
    thumbnail,
    window_count,
)

RNG = np.random.default_rng(20261015)


def _noise(count: int) -> np.ndarray:
    return RNG.random((count, 12))


def _song(*, length: int, motif: int, at: tuple[int, ...]) -> np.ndarray:
    """`motif`창짜리 같은 무늬를 `at` 자리마다 심은 곡."""
    frames = _noise(length)
    block = _noise(motif)
    for start in at:
        frames[start : start + motif] = block
    return frames


# ------------------------------------------------------------------ 반복을 집는다


def test_반복되는_구간을_집는다() -> None:
    """**두 번 나오는 무늬가 후렴이다.** 이것이 논문의 전부다."""
    frames = _song(length=120, motif=12, at=(20, 80))

    found = thumbnail(frames, window=12)

    assert found is not None
    assert found.start == 20, "먼저 나온 쪽을 집는다"
    assert found.lag == 60
    assert found.score > 0.99, f"같은 무늬인데 {found.score:.3f}다"


def test_반복이_없으면_점수가_낮다() -> None:
    """**무엇을 집든 점수가 말한다** (D-0203). 사람이 먼저 들어 볼 곡을 고르는 자리다."""
    quiet = thumbnail(_noise(120), window=12)
    loud = thumbnail(_song(length=120, motif=12, at=(20, 80)), window=12)

    assert quiet is not None
    assert loud is not None
    assert quiet.score < loud.score - 0.1, "반복이 있는 곡과 구별이 안 된다"


# ------------------------------------------------------------------ 논문의 제약 둘


def test_바로_옆_창은_안_본다() -> None:
    """**지연 바닥이 없으면 «변화가 적은 곳»을 «후렴»이라 부른다.**

    대각선 바로 아래는 무엇이든 1에 가깝다 — 자기 자신과의 비교에 가깝기 때문이다.
    **곡 가운데에 둔다** — 뒤쪽에 두면 «3/4 이전» 제약이 먼저 걸러서 이 시험이 그쪽을
    재게 되고, 지연 바닥을 지워도 초록인 **빈 그물**이 된다 (D-0230).
    """
    frames = _song(length=120, motif=12, at=(20, 80))
    frames[40:58] = frames[40]  # 곡 가운데 박아 둔 «변화 없는» 구간

    found = thumbnail(frames, window=12)

    assert found is not None
    assert found.lag >= 12, f"곡 길이의 1/10보다 가까운 짝을 집었다: lag {found.lag}"


def test_곡의_뒤쪽은_시작점이_못_된다() -> None:
    """**아웃트로 반복을 집지 않는다** (논문의 제약).

    곡 끝에만 반복을 심어 둔다. 제약이 없으면 그것이 유일한 1.0이라 반드시 이긴다.
    """
    frames = _song(length=200, motif=10, at=(160, 185))

    found = thumbnail(frames, window=10)

    assert found is not None
    assert found.start <= int(200 * LATEST_START_SHARE), f"뒤쪽을 집었다: {found.start}"
    assert found.score < 0.99, "아웃트로 반복을 그대로 집었다"


# ------------------------------------------------------------------ 못 재면 0이 아니다


def test_짧으면_None이다() -> None:
    """**0번 창을 조용히 돌려주면 «곡 앞이 후렴»이라는 거짓 주장이다** (GR-0.5)."""
    assert thumbnail(_noise(10), window=9) is None


def test_차원이_다르면_죽는다() -> None:
    """D-0233. 조용히 이상한 수를 내는 대신 멈춘다."""
    with pytest.raises(ValueError, match="12"):
        thumbnail(RNG.random((50, 7)), window=5)


def test_창_길이가_0이면_죽는다() -> None:
    with pytest.raises(ValueError, match="1 이상"):
        thumbnail(_noise(50), window=0)


def test_무음이_섞여도_안_죽는다() -> None:
    """크로마가 전부 0인 창이 있다 — **0으로 나누지 않는다.**"""
    frames = _song(length=120, motif=12, at=(20, 80))
    frames[0:5] = 0.0

    found = thumbnail(frames, window=12)

    assert found is not None
    assert np.isfinite(found.score)


# ------------------------------------------------------------------ 초 -> 창


def test_창_수는_0이_안_된다() -> None:
    """**창이 요청한 길이보다 길면 1이다.** 0이면 `thumbnail`이 바로 죽는다."""
    assert window_count(23.0, series_seconds=60.0) == 1
    assert window_count(23.0, series_seconds=2.0) == 12


def test_창_길이가_0이면_수를_안_지어낸다() -> None:
    with pytest.raises(ValueError, match="0 이하"):
        window_count(23.0, series_seconds=0.0)


def test_고른_것이_자기를_설명한다() -> None:
    """`Thumbnail`의 칸 넷이 **왜 거기인지**에 답한다 (D-0203)."""
    found = thumbnail(_song(length=120, motif=12, at=(20, 80)), window=12)

    assert isinstance(found, Thumbnail)
    assert found.length == 12
    assert found.start + found.lag + found.length <= 120, "짝이 곡 밖에 있다"
