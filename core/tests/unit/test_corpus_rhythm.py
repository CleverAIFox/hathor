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

from hathor.application.corpus_rhythm import (
    BEATS_PER_BAR,
    FLAT,
    peaked,
    phase_spread,
    split_half,
)
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


def _voiced(
    offsets: tuple[int, ...], seconds: float = 40.0, seed: int = 0, start: int = 0
) -> np.ndarray:
    """**그 곡만의 박 안 자리**에 치는 포락선. `offsets`는 박을 넷으로 나눈 칸.

    **칸 한가운데를 친다** (`MIDDLE`). 칸 경계에 치면 주기 보간의 0.0x칸 차이로
    같은 자리가 이웃 칸에 떨어져 **잡음 씨앗만 바꿔도 분포가 돈다** — 실제로 그렇게
    물렸다 (D-0406).
    """
    frames = int(seconds / HOP)
    envelope = np.random.default_rng(seed).random(frames) * 0.02
    for head in range(start, frames - BEAT_FRAMES, BEAT_FRAMES):
        for one in offsets:
            envelope[head + round((one + 0.5) * BEAT_FRAMES / PHASE_BINS)] += 1.0
    return envelope


PLACES = ((0,), (0, 2), (0, 1), (0, 3), (1, 3), (0,))
"""여섯 곡의 **서로 다른 발음 자리.** 둘은 일부러 겹친다 — 전부 달라야 신호가 나는
자가 아니라, **섞여 있어도 나는 자**라야 코퍼스에서 뜻이 있다."""


def _songs(seconds: float = 40.0) -> list[tuple[np.ndarray, float]]:
    return [(_voiced(one, seconds, seed=index), HOP) for index, one in enumerate(PLACES)]


def test_곡마다_자리가_다르면_신호가_난다() -> None:
    """**이 자가 신호를 볼 수 있나.** 못 보는 자로 「없다」고 하면 그게 거짓 음성이다."""
    verdict = split_half(_songs())

    assert verdict.signal is not None
    assert verdict.signal > 0.3, f"고유한 리듬을 심었는데 신호가 {verdict.signal}이다"


def test_전부_같은_자리면_신호가_0이다() -> None:
    """**귀무.** 곡마다 다른 것이 없으면 같은 곡도 다른 곡도 똑같이 가깝다."""
    same = [(_voiced((0, 2), seed=index), HOP) for index in range(6)]

    verdict = split_half(same)

    assert verdict.signal == pytest.approx(0.0, abs=0.05)


def test_자르는_자리가_박_배수가_아니어도_같다() -> None:
    """**심은 결함** (D-0069 · D-0406).

    `phase_profile`은 받은 배열의 0번 칸을 박의 머리로 본다. 한가운데서 그냥 자르면
    뒤 절반의 위상이 `중간 % 주기`만큼 돌아가 **리듬이 같은 곡도 남남이 됐다** —
    40.0초에서 0.003, 40.25초에서 0.992였다. 길이 하나로 신호가 사라진다.
    """
    aligned = split_half(_songs(seconds=40.0))
    odd = split_half(_songs(seconds=40.25))

    assert aligned.signal is not None
    assert odd.signal is not None
    assert odd.signal == pytest.approx(aligned.signal, abs=0.05)


APART = ((0,), (1,), (2,), (0, 2), (1, 2), (1, 3))
"""**서로 가장 먼** 여섯 자리 (교차 거리 바닥 0.483). `PLACES`는 둘이 겹치게 심어
뒀고, 겹친 쌍은 제 짝과 구별이 안 돼 이 시험에서는 못 쓴다."""

SEEDS = range(12)
"""짝 고르기를 **시드로 쓴다.** 한 시드만 보면 제 짝이 안 뽑힌 판을 통과로 읽는다 —
곡이 몇이든 「아무도 제 짝이 아닐」 확률이 1/e쯤이라 한 판으로는 못 가른다."""


def test_제_짝을_안_고른다() -> None:
    """**자기 자신과 견주면 귀무가 신호를 베낀다** — 그 곡의 차가 0이 된다.

    심은 결함이 **가끔만** 드러나는 꼴이라 시드를 쓸어 본다 (D-0069 · D-0082).
    """
    songs = [(_voiced(one, seed=index), HOP) for index, one in enumerate(APART)]
    verdicts = [split_half(songs, seed=seed) for seed in SEEDS]

    # **전제를 시험이 스스로 확인한다.** 서로 다른 자리로 심어도 봉우리 잡기가 둘을
    # 같은 칸에 넣으면 그 쌍의 거리가 0이 되고, 그러면 아래 단언이 **제 짝을 골라서**
    # 운 것인지 **자리가 겹쳐서** 운 것인지 못 가른다.
    assert min(one for verdict in verdicts for one in verdict.same) < 0.05
    for seed, verdict in zip(SEEDS, verdicts, strict=True):
        assert min(verdict.other) > 0.1, f"시드 {seed}에서 제 짝을 골랐다"


def test_두_곡_미만이면_신호를_안_낸다() -> None:
    """**없는 수를 지어내지 않는다** (GR-0.5). 짝지을 다른 곡이 없다."""
    verdict = split_half([(_voiced((0,)), HOP)])

    assert verdict.read == 1
    assert verdict.signal is None


def test_박을_못_읽은_곡은_빼고_센다() -> None:
    """**0으로 안 센다** (GR-0.5). 읽은 곡 수를 든다."""
    verdict = split_half([*_songs(), (np.zeros(2000, dtype=np.float64), HOP)])

    assert verdict.read == len(PLACES)


def test_같은_시드는_같은_수를_낸다() -> None:
    """짝이 무작위면 **같은 코퍼스에서 판마다 다른 수**가 나온다 (GR-6.5 · D-0082)."""
    songs = _songs()

    assert split_half(songs, seed=7).other == split_half(songs, seed=7).other


def test_거리가_1을_안_넘는다() -> None:
    """**총변동거리다** — L1의 절반이라 0~1이고, 겹치는 곳이 없으면 1이다.

    눈금이 두 배면 정본의 천분율이 전부 두 배가 되고 **거울이 100%를 넘겨 찍는다.**
    """
    disjoint = [(_voiced((0,), seed=1), HOP), (_voiced((2,), seed=2), HOP)]

    verdict = split_half(disjoint)

    assert max(verdict.other) == pytest.approx(1.0, abs=0.05)


def test_앞뒤가_다른_곡은_같은_곡_거리가_크다() -> None:
    """**앞과 뒤를 둘 다 읽는다는 증거** (D-0406).

    둘 다 앞 절반을 읽으면 같은 곡 거리가 **언제나 0**이 되고, 신호가 저절로 생긴다 —
    거짓 양성이며 「곡마다 고유한 리듬이 있다」로 읽힌다 (GR-0.8).
    """
    frames = int(40.0 / HOP)
    turning = np.random.default_rng(3).random(frames) * 0.02
    for start in range(0, frames - BEAT_FRAMES, BEAT_FRAMES):
        place = 0 if start < frames // 2 else 2
        turning[start + round((place + 0.5) * BEAT_FRAMES / PHASE_BINS)] += 1.0

    verdict = split_half([(turning, HOP), (_voiced((1,), seed=4), HOP)])

    assert verdict.same[0] > 0.8, "앞뒤가 다른 곡인데 거리가 0에 가깝다"


def test_모양은_같고_시작만_다르면_돌린_신호가_0이다() -> None:
    """**이 자의 요점이다** (D-0407).

    곡마다 녹음이 시작한 자리가 다르면 **리듬이 똑같아도** 분포가 통째로 돌아간다 —
    돌리지 않은 귀무는 그것을 「곡마다 다른 리듬」으로 읽는다. 생성이 베끼는 것은
    모양이지 원점이 아니므로(어차피 우리 격자 머리에 맞춘다) **판정은 돌린 쪽이다.**
    """
    turned = [
        (_voiced((0, 2), seed=index, start=(index % PHASE_BINS) * 12), HOP) for index in range(6)
    ]

    verdict = split_half(turned)

    assert verdict.signal is not None
    assert verdict.signal > 0.3, "원점만 다른데 돌리지 않은 신호가 안 났다 — 자가 이상하다"
    assert verdict.turned_signal == pytest.approx(0.0, abs=0.05)


def test_모양이_진짜_다르면_돌려도_남는다() -> None:
    """**돌리기가 신호를 다 먹으면 쓸 수 없는 자다.** 거짓 음성이 된다 (GR-0.8)."""
    shapes = ((0,), (0, 1), (0, 1, 2), (0, 2), (1, 2), (0, 1, 3))
    songs = [(_voiced(one, seed=index), HOP) for index, one in enumerate(shapes)]

    verdict = split_half(songs)

    assert verdict.turned_signal is not None
    assert verdict.turned_signal > 0.2


def test_돌린_거리가_안_돌린_것보다_크지_않다() -> None:
    """**돌리기는 귀무를 가깝게만 만든다.** 커지면 최솟값을 안 고른 것이다."""
    songs = _songs()

    verdict = split_half(songs)

    assert all(turn <= raw + 1e-9 for turn, raw in zip(verdict.turned, verdict.other, strict=True))


def test_고른_곡을_거른다() -> None:
    """**봉우리가 없는 곡은 베낄 리듬이 없다** (D-0401의 45.9%).

    섞여 들면 같은 곡도 다른 곡도 거리가 0에 가까워 **양쪽을 똑같이 끌어내린다.**
    """
    noise = [(_noise(seed=200 + index), HOP) for index in range(6)]

    assert len(peaked(noise + _songs())) == len(PLACES)
