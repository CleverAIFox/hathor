"""코퍼스가 박 안 어디에 발음하나 — O-46의 비교선 (D-0399).

**실측은 그의 기기에서만 된다** (D-0015). 여기서 보는 것은 **가르는 법**이다 — 합성
포락선이라 정답을 알고, 1004곡의 수는 `make measure`가 낸다.

### 두 읽기가 정말 다른가

D-0206은 *«마디 4등분»*이라 적었는데 그 수를 낸 도구는 **박**을 4등분했다. 우리 출력은
마디 머리에만 치므로 어느 쪽이든 100%였고 **그때는 갈릴 일이 없었다.** 아래
`test_메트로놈은_박에_몰리고_마디엔_고르다`가 **둘이 다른 것을 잰다**는 것을 보인다 —
그래서 정본이 둘 다 든다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.corpus_rhythm import BEATS_PER_BAR, FLAT, phase_spread
from hathor.domain.services.onset import PHASE_BINS

HOP = 0.01
BPM = 120.0
BEAT_FRAMES = round(60.0 / BPM / HOP)


def _metronome(seconds: float = 30.0, *, accent: float = 1.0) -> np.ndarray:
    """박마다 똑같이 치는 포락선. `accent`를 주면 **마디 첫 박만** 더 세게 친다."""
    frames = int(seconds / HOP)
    envelope = np.zeros(frames, dtype=np.float64)
    for index in range(0, frames, BEAT_FRAMES):
        beat = index // BEAT_FRAMES
        envelope[index] = accent if beat % BEATS_PER_BAR == 0 else 1.0
    return envelope


def _noise(seconds: float = 30.0, seed: int = 11) -> np.ndarray:
    """봉우리가 없는 포락선. **박이 안 읽히거나 고르게 나온다.**"""
    return np.random.default_rng(seed).random(int(seconds / HOP))


def test_메트로놈은_박에_몰리고_마디엔_고르다() -> None:
    """**둘이 다른 것을 잰다** (D-0399).

    박마다 똑같이 치면 **박 안**에서는 한 칸에 전부 몰리고(≈1.0), **마디 안**에서는
    네 칸이 같아 균등(≈0.25)이다. 이 둘을 섞어 적으면 비교선이 거짓이 된다.
    """
    verdict = phase_spread([(_metronome(), HOP)] * 4)

    assert min(verdict.beat_top) > 0.8
    assert max(verdict.bar_top) == pytest.approx(1.0 / PHASE_BINS, abs=0.05)


def test_마디_첫_박을_세게_치면_마디에도_몰린다() -> None:
    """**마디 읽기가 주기를 박 넷으로 본다는 증거다.** 안 그러면 센 박이 안 보인다."""
    plain = phase_spread([(_metronome(), HOP)] * 4)
    accented = phase_spread([(_metronome(accent=6.0), HOP)] * 4)

    assert max(accented.bar_top) > max(plain.bar_top) + 0.1


def test_박을_못_읽은_곡은_차이로_든다() -> None:
    """**0으로 안 센다** (GR-0.5). 물어본 수와 읽은 수를 둘 다 든다."""
    verdict = phase_spread([(_metronome(), HOP), (np.zeros(2000, dtype=np.float64), HOP)])

    assert (verdict.read, verdict.asked) == (1, 2)


def test_고른_곡을_센다() -> None:
    """**봉우리가 없는 곡은 반주 리듬을 못 준다.** 그 수를 든다."""
    verdict = phase_spread([(_noise(seed=index), HOP) for index in range(6)])

    assert verdict.flat == sum(1 for value in verdict.beat_top if value < FLAT)
    assert verdict.flat > 0, "노이즈가 전부 몰렸다 — 자가 이상하다"


def test_네_곡_미만이면_사분위를_안_낸다() -> None:
    """**없는 수를 지어내지 않는다** (GR-0.5)."""
    verdict = phase_spread([(_metronome(), HOP)] * 3)

    with pytest.raises(LookupError):
        verdict.spread(verdict.beat_top)


def test_사분위가_중앙을_감싼다() -> None:
    envelopes = [(_metronome(), HOP)] * 3 + [(_noise(), HOP)] * 3
    verdict = phase_spread(envelopes)

    low, mid, high, top = verdict.spread(verdict.beat_top)

    assert low <= mid <= high <= top
    assert top == max(verdict.beat_top)


def test_고름의_선을_옮겨_적지_않았다() -> None:
    """`probe_onsets`가 D-0160부터 쓴 선과 **같은 수여야 한다** (GR-0.7 · D-0043)."""
    assert pytest.approx(1.5 / PHASE_BINS) == FLAT
