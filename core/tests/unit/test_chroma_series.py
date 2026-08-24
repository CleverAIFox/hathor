"""크로마 시계열의 단위 검사 (O-32 · D-0105).

**D-0104의 전제가 여기 걸려 있다** — 묶은 것과 처음부터 그 길이로 뽑은 것이 같아야
"짧게 뽑아 두고 묶는다"가 성립한다. **그것이 이 파일의 첫 검사다.**
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services.key_estimation import (
    SOURCE_SAMPLE_RATE,
    chroma_series,
    group_series,
)

SR = SOURCE_SAMPLE_RATE


def _chord(seconds: float, roots: tuple[float, ...], seed: int = 3):
    """화음이 `seconds`마다 바뀌는 합성 파형."""
    rng = np.random.default_rng(seed)
    parts = []
    for root in roots:
        count = int(seconds * SR)
        time = np.arange(count) / SR
        wave = sum(np.sin(2 * np.pi * root * 2 ** (k / 12) * time) for k in (0, 4, 7))
        parts.append((wave / np.abs(wave).max()).astype(np.float32))
    made = np.concatenate(parts)
    return (made + rng.standard_normal(made.size).astype(np.float32) * 0.01).astype(np.float32)


# ------------------------------------------------------------------ 묶기


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_묶은_것과_직접_뽑은_것이_같다(factor):
    """**D-0104의 전제다.** 다르면 "짧게 뽑아 두고 묶는다"가 무너진다.

    정확히 0은 아니다 — `cq_chroma`가 대역마다 다른 창을 쓰고 프레임 수로 나눈다.
    실측 전변동 거리가 2초 0.0001 · 8초 0.0117이고 **지표 규모(0.2~0.6)에 비해
    무시할 수준이다.**
    """
    wave = _chord(4.0, (220.0, 261.6, 196.0, 293.7, 246.9, 174.6))
    grouped = group_series(chroma_series(wave, window_seconds=1.0), factor)
    direct = chroma_series(wave, window_seconds=float(factor))
    count = min(len(grouped), len(direct))
    assert count > 0
    gaps = [0.5 * float(np.abs(grouped[i] - direct[i]).sum()) for i in range(count)]
    assert max(gaps) < 0.02, f"묶기가 어긋난다: {max(gaps):.4f}"


def test_묶으면_창이_그만큼_준다():
    series = chroma_series(_chord(1.0, (220.0,) * 12), window_seconds=1.0)
    assert len(group_series(series, 3)) == len(series) // 3


def test_묶은_창도_합이_1이다():
    series = chroma_series(_chord(1.0, (220.0,) * 8), window_seconds=1.0)
    grouped = group_series(series, 4)
    assert grouped.sum(axis=1) == pytest.approx(np.ones(len(grouped)), abs=1e-6)


def test_묶는_수가_0이면_거부한다():
    with pytest.raises(ValueError, match="1 이상"):
        group_series(np.zeros((4, 12), dtype=np.float32), 0)


def test_창보다_크게_묶으면_비운다():
    """**부분 창은 길이가 달라 평균에 다른 무게를 준다.** 남는 꼬리는 버린다."""
    assert len(group_series(np.zeros((3, 12), dtype=np.float32), 8)) == 0


# ------------------------------------------------------------------ 시계열


def test_창마다_합이_1이다():
    series = chroma_series(_chord(1.0, (220.0,) * 6), window_seconds=1.0)
    assert len(series) == 6
    assert series.sum(axis=1) == pytest.approx(np.ones(len(series)), abs=1e-6)


def test_화음이_바뀌면_창이_달라진다():
    """**시간 축이 살아 있어야 한다.** 전곡 평균은 그것을 지운다."""
    wave = _chord(2.0, (220.0, 311.1))
    series = chroma_series(wave, window_seconds=1.0)
    early = series[0]
    late = series[-1]
    assert 0.5 * float(np.abs(early - late).sum()) > 0.2


def test_짧은_파형은_빈_시계열이다():
    """**길이가 다른 창을 섞지 않는다.** 짧은 꼬리는 프레임이 적어 통계가 다르다."""
    tiny = np.zeros(int(0.1 * SR), dtype=np.float32)
    assert chroma_series(tiny, window_seconds=1.0).shape == (0, 12)


def test_꼬리를_버린다():
    """창 하나에 못 미치는 꼬리는 버린다. `group_series`와 같은 규칙이다."""
    wave = _chord(1.0, (220.0,) * 5)
    padded = np.concatenate([wave, np.zeros(int(0.4 * SR), dtype=np.float32)])
    assert len(chroma_series(padded, window_seconds=1.0)) == 5


def test_같은_파형은_같은_시계열을_낸다():
    wave = _chord(1.0, (220.0,) * 5)
    assert chroma_series(wave, window_seconds=1.0) == pytest.approx(
        chroma_series(wave, window_seconds=1.0)
    )
