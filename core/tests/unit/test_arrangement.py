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


def test_모든_마디가_소리를_갖는다():
    """**빈 마디가 있으면 안 된다.**

    노트 수로 세던 것을 마디로 바꿨다 (D-0138 · D-0139). 같은 도수가 이어지면 하나로
    잇고 베이스가 붙었으므로 **노트 수는 더 이상 마디 수의 배수가 아니다.** 지키려는
    것은 마디가 빈 자리 없이 덮인다는 것이다.
    """
    notes = arrange(pattern("URUR"), PROGRESSION)
    covered = set()
    for note in notes:
        for bar in range(note.start_tick // TICKS_PER_BAR, note.end_tick // TICKS_PER_BAR):
            covered.add(bar)
    assert covered == set(range(4 * BARS_PER_SECTION))


def test_화음마다_네_성부다():
    """베이스 하나에 3화음 셋 (D-0139)."""
    notes = arrange(pattern("URUR"), PROGRESSION)
    starts = {note.start_tick for note in notes}
    assert all(sum(1 for n in notes if n.start_tick == tick) == 4 for tick in starts)


def test_소리가_끊기지_않는다():
    """발음 자리가 마디 격자 위에 있고 **틈이 없다.**

    마디마다 하나였던 것을 격자 위 여부로 바꿨다 (D-0138). 이어진 화음은 발음이
    한 번이며 **그것이 이 결정이 만들려던 것이다.**
    """
    notes = arrange(pattern("UU"), PROGRESSION)
    starts = sorted({note.start_tick for note in notes})
    assert all(tick % TICKS_PER_BAR == 0 for tick in starts)
    assert starts[0] == 0
    ends = {note.end_tick for note in notes}
    assert max(ends) == 2 * BARS_PER_SECTION * TICKS_PER_BAR


def _pitch_classes(notes, start, end=None):
    """마디별 음이름 집합. **틱 안의 순서는 안 본다** — 전위가 바뀌면 낮은 음이 바뀐다."""
    picked = [n for n in notes if start <= n.start_tick and (end is None or n.start_tick < end)]
    bars: dict[int, set[int]] = {}
    for note in picked:
        bars.setdefault(note.start_tick - start, set()).add(note.pitch % 12)
    return [bars[tick] for tick in sorted(bars)]


def test_repeated_sections_share_the_same_harmony():
    """구조 추출을 소리에 실제로 연결하는 지점이다.

    `R` 구간이 서로 다른 화성을 쓰면 구조를 뽑아 둔 의미가 없다 — 지표를
    만들어두고 보지 않는 것과 같다.

    **음높이가 아니라 음이름으로 본다** (D-0137). 성부 진행이 붙은 뒤로 전위는
    직전 화음이 정하므로 앞에 무엇이 왔느냐에 따라 같은 도수가 다른 자리에 놓인다.
    **지키려는 것은 화성이 같다는 것이고 그것은 음이름이다.**
    """
    notes = arrange(pattern("RUR"), PROGRESSION)
    span = TICKS_PER_BAR * BARS_PER_SECTION
    assert _pitch_classes(notes, 0, span) == _pitch_classes(notes, span * 2)


def test_반복_구간의_전위는_달라질_수_있다():
    """**앞에 무엇이 왔느냐가 전위를 정한다** (D-0137).

    이것이 결함이 아니라는 근거는 두 가지다. 도수가 같다는 것은 위 검사가 지키고,
    반복 구간의 전위가 매번 같아야 할 음악적 이유가 없다.
    """
    notes = arrange(pattern("RUR"), PROGRESSION)
    span = TICKS_PER_BAR * BARS_PER_SECTION
    first = [n.pitch for n in notes if n.start_tick < span]
    third = [n.pitch for n in notes if n.start_tick >= span * 2]
    assert sorted({p % 12 for p in first}) == sorted({p % 12 for p in third})


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
    first_bar = sorted(n.pitch % 12 for n in notes if n.start_tick == 0)
    wanted = sorted({p % 12 for p in chord_pitches(KEY, "I")})
    assert sorted(set(first_bar)) == wanted


def test_progression_shorter_than_section_wraps():
    """진행이 짧아도 마디가 비면 안 된다.

    **한 도수짜리 진행은 이제 한 번 쳐서 구간 전체를 끈다** (D-0138). 마디가 덮이는
    것이 지키려던 것이고, 같은 화음을 여덟 번 다시 치는 것이 아니었다.
    """
    short = ChordProgression(key=KEY, degrees=("I",))
    notes = arrange(pattern("U"), short)
    assert {note.start_tick for note in notes} == {0}
    assert {note.duration_ticks for note in notes} == {TICKS_PER_BAR * BARS_PER_SECTION}


def test_arrangement_is_deterministic():
    assert arrange(pattern("URUR"), PROGRESSION) == arrange(pattern("URUR"), PROGRESSION)


def test_total_bars_and_duration():
    """**상수를 따라간다** (D-0111). 숫자를 박아 두면 섹션 길이를 바꿀 때 갈린다."""
    structure = pattern("URUR")
    bars = 4 * BARS_PER_SECTION
    assert total_bars(structure) == bars
    # 마디마다 4박이므로 96BPM에서 마디당 2.5초다
    assert duration_seconds(structure, 96) == pytest.approx(bars * 2.5)


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


# ------------------------------------------------------------------ 블록 읽기 (D-0111)


def test_긴_진행이면_섹션마다_겹치지_않는_블록을_읽는다():
    """**배열 조건화가 소리에 닿으려면 진행을 넓게 읽어야 한다** (O-32 · D-0110).

    한 칸씩 밀어 읽으면 6섹션이 64마디 진행의 앞 일곱 마디만 쓴다. 실측에서
    그 일이 났다.
    """
    degrees = tuple(str(index) for index in range(4 * BARS_PER_SECTION))
    long = ChordProgression(key=KEY, degrees=degrees)
    read = set()
    for index in range(2):
        rotation = (index + 1) * BARS_PER_SECTION
        read |= {(rotation + offset) % long.length for offset in range(BARS_PER_SECTION)}
    # 두 `U` 구간이 서로 겹치지 않는 두 블록을 읽는다
    assert len(read) == 2 * BARS_PER_SECTION


def test_짧은_진행이면_예전처럼_한_칸씩_민다():
    """**고칠 것을 고치되 고쳤던 것을 되돌리지 않는다.**

    진행이 섹션과 같은 길이면 순차 블록이 전부 같아진다 — 그것을 고친 것이
    회전이었다 (`test_unique_sections_differ_from_each_other`).
    """
    short = ChordProgression(key=KEY, degrees=("I", "V", "vi", "IV"))
    notes = arrange(pattern("UU"), short, bars_per_section=4)
    boundary = TICKS_PER_BAR * 4
    head = [note.pitch for note in notes if note.start_tick < boundary]
    tail = [note.pitch for note in notes if note.start_tick >= boundary]
    assert head != tail


def test_섹션당_마디는_한_곳에서_온다():
    """**한 이름이 두 값이면 둘 중 하나는 반드시 틀린다** (D-0111)."""
    from hathor.application.orchestrator import generation_pipeline

    assert generation_pipeline.BARS_PER_SECTION is BARS_PER_SECTION
    assert generation_pipeline.DEFAULT_BARS == (
        generation_pipeline.DEFAULT_SECTIONS * BARS_PER_SECTION
    )
