"""가락의 단위 검사 (D-0141).

**손잡이가 사방에 있는 자리다.** 이 검사들이 지키는 것은 음악적 품질이 아니라
**새 값이 생기지 않았다는 것**이다.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from hathor.application.arrangement import BEATS_PER_BAR
from hathor.domain.services.melody import chord_positions, pitch_classes, sing
from hathor.domain.services.midi_writer import TICKS_PER_BEAT
from hathor.domain.value_objects.key import Key, Mode

KEY = Key(tonic="C", mode=Mode.MAJOR)
SPANS = [("I", 1), ("V", 2), ("vi", 1), ("IV", 1)]
TRIAD_CLASSES = pitch_classes(chord_positions("I"), KEY)
"""다장조 `I`화음의 **피치클래스** — C·E·G = 0·4·7. 손으로 안 적는다 (GR-0.7)."""


def _line(seed=7, **kwargs):
    return sing(seed, SPANS, KEY, ceiling=72, beats_per_bar=BEATS_PER_BAR, **kwargs)


# ------------------------------------------------------------------ 격자


def test_박마다_하나다():
    """**화음은 마디 격자를 쓰고 가락은 박 격자를 쓴다.** 둘 다 이미 있던 눈금이다."""
    bars = sum(repeats for _, repeats in SPANS)
    assert len(_line()) == bars * BEATS_PER_BAR


def test_발음이_박_격자_위에_있다():
    assert all(start % TICKS_PER_BEAT == 0 for start, _, _ in _line())


def test_화음이_끄는_동안에도_움직인다():
    """**그것이 전경과 배경의 차이다.** 2마디짜리 `V`에서도 박마다 발음한다."""
    line = _line()
    span = [note for note in line if TICKS_PER_BEAT * 4 <= note[0] < TICKS_PER_BEAT * 12]
    assert len(span) == 8


# ------------------------------------------------------------------ 고를 음


def test_화음_구성음만_짚는다():
    """**화음이 이미 정했다.** 가락이 화음 밖으로 나가면 새 규칙이 필요해진다."""
    scale = (0, 2, 4, 5, 7, 9, 11)
    for (degree, repeats), _ in zip(SPANS, SPANS, strict=True):
        wanted = {(scale[position]) % 12 for position in chord_positions(degree)}
        assert len(wanted) == 3
        assert repeats >= 1


def test_고른_음이_그_마디_화음_안에_있다():
    scale = (0, 2, 4, 5, 7, 9, 11)
    line = _line()
    beat = 0
    for degree, repeats in SPANS:
        wanted = {scale[position] % 12 for position in chord_positions(degree)}
        for _ in range(repeats * BEATS_PER_BAR):
            assert line[beat][2] % 12 in wanted
            beat += 1


def test_3화음은_세_자리다():
    assert len(chord_positions("ii")) == 3


def test_모르는_도수는_거부한다():
    with pytest.raises(ValueError, match="알 수 없는 도수"):
        chord_positions("ix")


# ------------------------------------------------------------------ 자리


def test_화음_위에_놓인다():
    """베이스가 아래인 것과 같은 근거다 (D-0139)."""
    assert all(pitch >= 72 for _, _, pitch in _line())


def test_한_옥타브_안에_있다():
    """`_place`가 기준 위 첫 자리를 잡으므로 **음역이 저절로 한 옥타브다.**"""
    pitches = [pitch for _, _, pitch in _line()]
    assert max(pitches) - min(pitches) < 12


# ------------------------------------------------------------------ 값이 없다


def test_시드가_같으면_같다():
    assert _line() == _line()


def test_시드가_다르면_다르다():
    assert _line(seed=7) != _line(seed=11)


def test_자료가_없으면_균등이다():
    """**지어내지 않는다** (GR-0.5). 사전도 전이도 없으면 구성음이 고르게 나온다."""
    line = sing(7, [("I", 32)], KEY, ceiling=72, beats_per_bar=BEATS_PER_BAR)
    found = {pitch for _, _, pitch in line}
    assert len(found) == 3


def _tonic_line(**kwargs):
    """`I`화음(C·E·G) 위에서 한 축만 세워 **어느 음이 나오는지** 본다."""
    return sing(7, [("I", 8)], KEY, ceiling=72, beats_per_bar=BEATS_PER_BAR, **kwargs)


@pytest.mark.parametrize("wanted", TRIAD_CLASSES)
def test_사전이_가리킨_피치클래스가_나온다(wanted):
    """**사전의 축은 피치클래스 12칸이다** (D-0063 · `DEGREE_COUNT`).

    음계 자리 0~6으로 찍으면 다장조에서 «미»(4)에 준 무게가 «솔»(7)로 간다.
    셋 다 거는 이유는 **상수 하나로는 안 걸리기 때문이다** — 으뜸음(0)은 두 축에서
    값이 같아 혼자서는 아무것도 못 잡는다 (D-0420).
    """
    prior = [0.0] * 12
    prior[wanted] = 1.0
    line = _tonic_line(prior=prior)

    assert {pitch % 12 for _, _, pitch in line} == {wanted}


def test_무게가_말없이_사라지지_않는다():
    """**«솔»에 준 무게는 안 읽혀 합이 0이 되고 균등으로 떨어졌다** (D-0420).

    틀린 음을 내는 것보다 나쁘다 — 참조곡 사전이 **아무 말 없이 버려진다.**
    """
    prior = [0.0] * 12
    prior[7] = 1.0
    line = _tonic_line(prior=prior)

    assert len({pitch % 12 for _, _, pitch in line}) == 1, "균등으로 떨어졌다"


def test_전이_행렬이_우선한다():
    """**직전에 무엇이 왔는가가 곡의 움직임이다.** 사전만 쓰면 점의 나열이다.

    **이 검사가 결함을 고정하고 있었다** (D-0420). `row[4]`(«미»)를 세워 놓고
    기대값을 `7`(«솔»)로 적었다 — 구현을 보고 쓴 수다. 뜻을 보고 쓰면 `4`다.
    """
    transition = [[0.0] * 12 for _ in range(12)]
    for row in transition:
        row[4] = 1.0
    line = _tonic_line(prior=[1.0] + [0.0] * 11, transition=transition)

    assert line[0][2] % 12 == 0, "첫 박은 사전이 정한다 — 전이에는 시작이 없다"
    assert {pitch % 12 for _, _, pitch in line[1:]} == {4}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"prior": [1.0] * 7}, "도수 사전은"),
        ({"prior": [1.0] * 12, "transition": [[1.0] * 7] * 7}, "전이 사전은"),
    ],
)
def test_차원이_다르면_죽는다(kwargs, message):
    """**`% len(...)`으로 감으면 아무 데서도 안 죽고 다른 칸을 읽는다** (D-0233).

    `degree_weights`는 같은 자리에서 터진다 — 가락만 안 터졌다.
    """
    with pytest.raises(ValueError, match=message):
        sing(7, [("I", 2)], KEY, ceiling=72, beats_per_bar=BEATS_PER_BAR, **kwargs)


def test_도약을_막지_않는다():
    """**도약 폭은 고르는 값이 아니라 재는 값이다** (O-45).

    막으면 문턱이 생긴다 — 몇 반음부터 큰가. D-0137이 병행 5도에서 내린 판단과 같다.
    """
    source = sing.__doc__ or ""
    assert "도약" not in source


def test_마디당_박이_0이면_거부한다():
    with pytest.raises(ValueError, match="박은 1 이상"):
        sing(7, SPANS, KEY, ceiling=72, beats_per_bar=0)


def test_가락_없이도_배치된다():
    """`seed`를 안 주면 D-0139까지의 소리 그대로다. **기본 경로가 안 바뀐다.**"""
    from hathor.application.arrangement import arrange
    from hathor.domain.services.song_structure import StructurePattern
    from hathor.domain.value_objects.chord_progression import ChordProgression

    pattern = StructurePattern(("U",), (0,))
    progression = ChordProgression(key=KEY, degrees=("I", "V"))
    assert arrange(pattern, progression) == arrange(pattern, progression, seed=None)


def test_도약_분포는_실측이다():
    """실측 평균 **3.79반음** · 같은 음 유지 **25%** (D-0141).

    **문턱이 아니라 기준선이다.** 판정은 귀가 하며, 거슬린다고 하면 그때 근거가
    생긴다 (O-45). 여기서는 **움직이기는 한다**만 고정한다.
    """
    line = sing(7, [("I", 8), ("V", 8)], KEY, ceiling=72, beats_per_bar=BEATS_PER_BAR)
    leaps = [abs(b[2] - a[2]) for a, b in pairwise(line)]
    assert 0 < sum(leaps) / len(leaps) < 6.0
    assert 0 < leaps.count(0) / len(leaps) < 0.6
