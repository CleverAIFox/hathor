"""구조와 화성을 잇는 배치 테스트."""

import pytest

from hathor.application.arrangement import (
    BARS_PER_SECTION,
    TICKS_PER_BAR,
    arrange,
    duration_seconds,
    total_bars,
)
from hathor.domain.services.midi_writer import chord_pitches
from hathor.domain.services.song_structure import StructurePattern
from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode

KEY = Key(tonic="C", mode=Mode.MAJOR)
PROGRESSION = ChordProgression(key=KEY, degrees=("I", "V", "vi", "IV"))


def pattern(text: str) -> StructurePattern:
    return StructurePattern(
        labels=tuple(text),
        groups=tuple(0 if char == "R" else index for index, char in enumerate(text)),
    )


def test_every_bar_gets_a_triad():
    notes = arrange(pattern("URUR"), PROGRESSION)
    assert len(notes) == 4 * BARS_PER_SECTION * 3


def test_bars_are_laid_out_without_gaps():
    notes = arrange(pattern("UU"), PROGRESSION)
    starts = sorted({note.start_tick for note in notes})
    assert starts == [index * TICKS_PER_BAR for index in range(2 * BARS_PER_SECTION)]


def test_repeated_sections_share_the_same_harmony():
    """구조 추출을 소리에 실제로 연결하는 지점이다.

    `R` 구간이 서로 다른 화성을 쓰면 구조를 뽑아 둔 의미가 없다 — 지표를
    만들어두고 보지 않는 것과 같다.
    """
    notes = arrange(pattern("RUR"), PROGRESSION)
    first = [n.pitch for n in notes if n.start_tick < TICKS_PER_BAR * BARS_PER_SECTION]
    third_start = TICKS_PER_BAR * BARS_PER_SECTION * 2
    third = [n.pitch for n in notes if n.start_tick >= third_start]
    assert first == third


def test_unique_sections_differ_from_each_other():
    """`U` 구간은 서로 달라야 한다.

    **실측으로 잡은 결함이다.** 처음에는 진행을 순차로 잘라 썼는데, 진행 길이가
    섹션 마디 수의 배수이면(4마디 진행 · 4마디 섹션) 모든 `U` 구간이 똑같아졌다.
    진행 8마디처럼 흔한 조합에서도 걸린다. 회전으로 바꿔 고쳤다.
    """
    notes = arrange(pattern("UU"), PROGRESSION)
    boundary = TICKS_PER_BAR * BARS_PER_SECTION
    first = [n.pitch for n in notes if n.start_tick < boundary]
    second = [n.pitch for n in notes if n.start_tick >= boundary]
    assert first != second


def test_repeated_section_starts_at_progression_head():
    notes = arrange(pattern("R"), PROGRESSION)
    first_bar = sorted(n.pitch for n in notes if n.start_tick == 0)
    assert first_bar == sorted(chord_pitches(KEY, "I"))


def test_progression_shorter_than_section_wraps():
    """진행이 짧아도 마디가 비면 안 된다."""
    short = ChordProgression(key=KEY, degrees=("I",))
    notes = arrange(pattern("U"), short)
    assert len({note.start_tick for note in notes}) == BARS_PER_SECTION


def test_arrangement_is_deterministic():
    assert arrange(pattern("URUR"), PROGRESSION) == arrange(pattern("URUR"), PROGRESSION)


def test_total_bars_and_duration():
    structure = pattern("URUR")
    assert total_bars(structure) == 16
    # 16마디 × 4박 = 64박, 96BPM이면 40초
    assert duration_seconds(structure, 96) == pytest.approx(40.0)


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        arrange(pattern("U"), PROGRESSION, bars_per_section=0)
    with pytest.raises(ValueError):
        duration_seconds(pattern("U"), 0)


@pytest.mark.parametrize("degree_count", [2, 3, 4, 5, 6, 8, 12, 16])
def test_unique_sections_differ_for_every_progression_length(degree_count):
    """길이가 섹션 마디 수의 배수여도 성립해야 한다.

    순차 방식이 4·8·12·16에서 조용히 깨졌다. 배수를 포함해 훑는다.
    """
    degrees = tuple(
        ("I", "V", "vi", "IV", "ii", "iii", "I", "V")[index % 8] for index in range(degree_count)
    )
    progression = ChordProgression(key=KEY, degrees=degrees)
    notes = arrange(pattern("UU"), progression)
    boundary = TICKS_PER_BAR * BARS_PER_SECTION
    first = [n.pitch for n in notes if n.start_tick < boundary]
    second = [n.pitch for n in notes if n.start_tick >= boundary]
    assert first != second, f"진행 길이 {degree_count}에서 U 구간이 같다"
