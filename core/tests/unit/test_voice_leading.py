"""성부 진행의 단위 검사 (D-0137).

**실측이 기준선이다.** 근음 위치로만 쌓던 동안 63번 전환 중 57번(90.5%)이 병행
5도였고 공통음 유지가 9.5%였다.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

from hathor.domain.services.midi_writer import MIDDLE_C, chord_pitches
from hathor.domain.services.voice_leading import (
    bass,
    distance,
    lead,
    parallel_fifths,
    voicings,
)
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony

KEY = Key(tonic="C", mode=Mode.MAJOR)


# ------------------------------------------------------------------ 후보


def test_전위는_셋이다():
    """**더도 덜도 아니다.** 후보가 늘면 무엇을 고를지 정하는 값이 필요해진다."""
    assert len(voicings(chord_pitches(KEY, "I"), octave_base=MIDDLE_C)) == 3


def test_가장_낮은_음이_기준_옥타브_안에_있다():
    """전위는 화음의 성질이고 옥타브는 자리다. **자리를 고정해야 후보가 유한하다.**"""
    for option in voicings(chord_pitches(KEY, "vii"), octave_base=MIDDLE_C):
        assert MIDDLE_C <= option[0] < MIDDLE_C + 12


def test_후보는_같은_음이름을_갖는다():
    base = chord_pitches(KEY, "IV")
    wanted = sorted(pitch % 12 for pitch in base)
    for option in voicings(base, octave_base=MIDDLE_C):
        assert sorted(pitch % 12 for pitch in option) == wanted


def test_빈_화음은_거부한다():
    with pytest.raises(ValueError, match="빈 화음"):
        voicings((), octave_base=MIDDLE_C)


# ------------------------------------------------------------------ 고르기


def test_직전이_없으면_근음_위치다():
    assert lead(None, chord_pitches(KEY, "I"), octave_base=MIDDLE_C) == (60, 64, 67)


def test_가장_적게_움직이는_것을_고른다():
    before = (60, 64, 67)
    picked = lead(before, chord_pitches(KEY, "V"), octave_base=MIDDLE_C)
    others = [v for v in voicings(chord_pitches(KEY, "V"), octave_base=MIDDLE_C) if v != picked]
    assert all(distance(before, picked) <= distance(before, other) for other in others)


def test_같은_화음이면_안_움직인다():
    before = lead(None, chord_pitches(KEY, "ii"), octave_base=MIDDLE_C)
    assert lead(before, chord_pitches(KEY, "ii"), octave_base=MIDDLE_C) == before


def test_동점이면_사전순이다():
    """**결정성을 위한 것이며 음악적 선택이 아니다.**"""
    before = (60, 64, 67)
    picked = lead(before, chord_pitches(KEY, "I"), octave_base=MIDDLE_C)
    tied = [
        option
        for option in voicings(chord_pitches(KEY, "I"), octave_base=MIDDLE_C)
        if distance(before, option) == distance(before, picked)
    ]
    assert picked == min(tied)


def test_성부는_서로를_넘나들지_않는다():
    """낮은 음은 낮은 음으로 간다. **따라갈 수 없으면 성부가 아니다.**"""
    assert distance((60, 64, 67), (67, 64, 60)) == 0


# ------------------------------------------------------------------ 실측


def _walk(degrees):
    found, before = [], None
    for degree in degrees:
        before = lead(before, chord_pitches(KEY, degree), octave_base=MIDDLE_C)
        found.append(before)
    return found


def test_병행_5도가_크게_준다():
    """실측 기준선 **90.5%**. 0%는 아니다 — 예측이 틀렸고 그대로 적는다 (O-42)."""
    degrees = generate_harmony(seed=7, key=KEY, bar_count=64).degrees
    chords = _walk(degrees)
    found = sum(parallel_fifths(a, b) for a, b in pairwise(chords))
    assert found / (len(chords) - 1) < 0.30


def test_공통음_유지가_는다():
    """실측 기준선 **9.5%**."""
    degrees = generate_harmony(seed=7, key=KEY, bar_count=64).degrees
    chords = _walk(degrees)
    moves = [
        abs(x - y) for a, b in pairwise(chords) for x, y in zip(sorted(a), sorted(b), strict=True)
    ]
    assert moves.count(0) / len(moves) > 0.25


def test_평균_이동이_준다():
    """실측 기준선 **4.17반음**."""
    degrees = generate_harmony(seed=7, key=KEY, bar_count=64).degrees
    chords = _walk(degrees)
    moves = [
        abs(x - y) for a, b in pairwise(chords) for x, y in zip(sorted(a), sorted(b), strict=True)
    ]
    assert sum(moves) / len(moves) < 2.0


def test_병행을_세는_것과_고르는_것은_다르다():
    """**보게 하면 그 순간 문턱이 생긴다.** `lead`는 이 함수를 안 부른다."""
    root = Path(__file__).resolve().parents[3]
    path = root / "core" / "hathor" / "domain" / "services" / "voice_leading.py"
    body = path.read_text(encoding="utf-8").split("def lead(")[1].split("\ndef ")[0]
    assert "parallel_fifths" not in body


# ------------------------------------------------------------------ 베이스 (D-0139)


def test_베이스는_화음_아래_옥타브다():
    """**베이스가 화음과 겹치면 베이스가 아니다.**"""
    for degree in ("I", "ii", "iii", "IV", "V", "vi", "vii"):
        rooted = chord_pitches(KEY, degree)
        low = bass(rooted, octave_base=MIDDLE_C)
        assert MIDDLE_C - 12 <= low < MIDDLE_C


def test_베이스는_근음이다():
    for degree in ("I", "ii", "IV", "V"):
        rooted = chord_pitches(KEY, degree)
        assert bass(rooted, octave_base=MIDDLE_C) % 12 == min(rooted) % 12


def test_베이스는_전위를_안_따른다():
    """근음은 화음의 성질이고 전위는 자리다 (D-0139)."""
    rooted = chord_pitches(KEY, "V")
    low = bass(rooted, octave_base=MIDDLE_C)
    assert all(bass(rooted, octave_base=MIDDLE_C) == low for _ in range(3))


def test_빈_화음은_근음이_없다():
    with pytest.raises(ValueError, match="근음"):
        bass((), octave_base=MIDDLE_C)
