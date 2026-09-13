"""박·온셋의 단위 검사 (O-46 · D-0143).

**합성에서 참값을 회복하지 못하면 실측에 걸지 않는다** — D-0123이 반감점에서 쓴
순서와 같다. 이 파일이 그 관문이다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services.onset import (
    PHASE_BINS,
    TEMPO_RANGE,
    beat_period,
    phase_profile,
    tempo_bpm,
)

HOP = 0.01


def synth(bpm, pattern=None, *, noise=0.0, seed=1, bars=32):
    """참 박이 있는 온셋 포락선. **참값을 아는 자료로 먼저 본다.**"""
    pattern = pattern or {0.0: 1.0}
    rng = np.random.default_rng(seed)
    period = 60.0 / bpm
    size = int(bars * 4 * period / HOP)
    found = np.zeros(size)
    for beat in range(int(size * HOP / period)):
        for phase, amplitude in pattern.items():
            index = int((beat + phase) * period / HOP)
            if index < size:
                found[index] = amplitude
    smeared = np.convolve(found, np.hanning(7), mode="same")
    return smeared + rng.normal(0.0, noise, size)


# ------------------------------------------------------------------ 박


@pytest.mark.parametrize("bpm", [72, 96, 120, 140])
def test_참_빠르기를_회복한다(bpm):
    """**격자 아래로 보간한다.** 안 하면 96을 96.77로 읽는다 (D-0143 실측)."""
    found = beat_period(synth(bpm), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - bpm) < 0.5


@pytest.mark.parametrize("bpm", [72, 96, 140])
def test_잡음에도_회복한다(bpm):
    found = beat_period(synth(bpm, noise=0.3), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - bpm) < 1.0


def test_배수_오류를_스스로_신고한다():
    """**배수 모호성은 결함이 아니라 성질이다** (D-0054와 같은 근거).

    120BPM에 잡음 0.3이면 절반을 고른다. 사람도 그렇게 짚을 수 있으며 **그 사실이
    사라지면 안 된다** — `octave_margin`이 낮게 나온다.
    """
    found = beat_period(synth(120, noise=0.3), HOP)
    assert found is not None
    assert found.octave_margin < 0.20


def test_길이로_나누지_않는다():
    """나누면 긴 지연이 밀려 올라간다 — 120BPM·잡음 0.1에서 60을 골랐다."""
    found = beat_period(synth(120, noise=0.1), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - 120) < 1.0


def test_무음이면_못_고른다():
    """**없는 것을 지어내지 않는다** (GR-0.5)."""
    assert beat_period(np.zeros(500), HOP) is None


def test_탐색_범위는_맞추는_값이_아니다():
    """좁히면 결과가 좋아 보이게 만들 수 있고 그것이 D-0058이다."""
    assert TEMPO_RANGE == (50.0, 200.0)


def test_너무_짧으면_거부한다():
    with pytest.raises(ValueError, match="너무 짧다"):
        beat_period([1.0, 0.0], HOP)


def test_홉이_양수여야_한다():
    with pytest.raises(ValueError, match="홉 길이"):
        beat_period(synth(96), 0.0)


def test_빠르기_환산():
    assert tempo_bpm(0.5) == 120.0
    with pytest.raises(ValueError, match="박 주기"):
        tempo_bpm(0.0)


# ------------------------------------------------------------------ 위상


def test_정박만_있으면_한_칸에_몰린다():
    found = beat_period(synth(96), HOP)
    assert found is not None
    profile = phase_profile(synth(96), found.period_seconds, HOP)
    assert max(profile) > 0.5
    assert sum(1 for value in profile if value == 0.0) >= 2


def test_뒤박이_섞이면_퍼진다():
    """**이 차이가 반주 리듬의 재료다.**"""
    envelope = synth(96, {0.0: 1.0, 0.5: 0.7})
    found = beat_period(envelope, HOP)
    assert found is not None
    profile = phase_profile(envelope, found.period_seconds, HOP)
    assert max(profile) < 0.5


def test_합이_1이다():
    found = beat_period(synth(96), HOP)
    assert found is not None
    assert sum(phase_profile(synth(96), found.period_seconds, HOP)) == pytest.approx(1.0)


def test_칸수는_박의_4분할이다():
    """`TICKS_PER_BEAT`가 이미 480으로 4분할을 담는다. **새 격자가 아니다.**"""
    assert PHASE_BINS == 4


def test_에너지가_없으면_균등이다():
    assert phase_profile(np.zeros(500), 0.5, HOP) == tuple([0.25] * 4)


def test_칸이_0이면_거부한다():
    with pytest.raises(ValueError, match="칸은 1 이상"):
        phase_profile(synth(96), 0.5, HOP, bins=0)
