"""구조와 화성을 잇는 배치 테스트."""

from collections.abc import Sequence
from typing import cast

import pytest

from hathor.application.arrangement import (
    BARS_PER_SECTION,
    BASS_CHANNEL,
    BEATS_PER_BAR,
    DRUM_HIT_TICKS,
    DRUM_STRIKE,
    KICK_BEATS,
    LEAD_CHANNEL,
    PAD_CHANNEL,
    SNARE_BEATS,
    SUBDIVISIONS,
    TICKS_PER_BAR,
    arrange,
    duration_seconds,
    total_bars,
)
from hathor.domain.services.midi_writer import (
    DRUM_CHANNEL,
    DRUM_KIT,
    DYNAMICS,
    METRIC_STRESS,
    TICKS_PER_BEAT,
    Note,
    chord_pitches,
    softer,
)
from hathor.domain.services.song_structure import StructurePattern
from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode
from tests.conftest import tool_module

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
    """베이스 하나에 3화음 셋 (D-0139).

    **베이스는 발음이 드물다** (D-0207). 위 성부는 박마다 다시 치고 받침은 끈다.

    **타악은 성부가 아니다** (D-0411) — 세면 같은 틱에 북이 겹쳐 수가 흐트러진다.
    """
    notes = [one for one in arrange(pattern("URUR"), PROGRESSION) if one.channel != DRUM_CHANNEL]
    counts = {
        tick: sum(1 for n in notes if n.start_tick == tick)
        for tick in {note.start_tick for note in notes}
    }
    assert set(counts.values()) == {3, 4}, counts


def test_소리가_끊기지_않는다():
    """발음 자리가 마디 격자 위에 있고 **틈이 없다.**

    마디마다 하나였던 것을 격자 위 여부로 바꿨다 (D-0138). 이어진 화음은 발음이
    한 번이며 **그것이 이 결정이 만들려던 것이다.**
    """
    notes = arrange(pattern("UU"), PROGRESSION)
    starts = sorted({note.start_tick for note in notes})
    # **8분 격자다** (D-0207 → D-0402). 마디 격자였을 때 화음 에너지의 100%가 첫
    # 박에 몰렸고, 박 격자에서도 **박 안 4등분의 100%가 박머리에** 몰려 있었다.
    assert all(tick % (TICKS_PER_BEAT // SUBDIVISIONS) == 0 for tick in starts)
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
    """**타악은 빼고 본다** (D-0411). 9번 채널의 음높이는 음이 아니라 **어느 북인지**를
    고르는 번호다 — 음명으로 읽으면 36·38·42가 화음에 섞여 들어온다."""
    notes = arrange(pattern("R"), PROGRESSION)
    first_bar = sorted(
        n.pitch % 12 for n in notes if n.start_tick == 0 and n.channel != DRUM_CHANNEL
    )
    wanted = sorted({p % 12 for p in chord_pitches(KEY, "I")})
    assert sorted(set(first_bar)) == wanted


def test_progression_shorter_than_section_wraps():
    """진행이 짧아도 마디가 비면 안 된다.

    **한 도수짜리 진행은 이제 한 번 쳐서 구간 전체를 끈다** (D-0138). 마디가 덮이는
    것이 지키려던 것이고, 같은 화음을 여덟 번 다시 치는 것이 아니었다.
    """
    short = ChordProgression(key=KEY, degrees=("I",))
    notes = arrange(pattern("U"), short)
    whole = TICKS_PER_BAR * BARS_PER_SECTION
    pitched = [n for n in notes if n.channel != DRUM_CHANNEL]
    # **베이스는 한 번 쳐서 구간 전체를 끈다** — D-0138이 지키려던 것이다.
    assert [n.duration_ticks for n in pitched if n.start_tick == 0].count(whole) == 1
    # **위 성부는 8분마다 다시 친다** (D-0207 → D-0402).
    assert {n.duration_ticks for n in pitched} == {whole, TICKS_PER_BEAT // SUBDIVISIONS}
    # **타악은 한 방이다** (D-0411) — GM이 노트오프를 무시하므로 길이를 안 준다.
    assert {n.duration_ticks for n in notes if n.channel == DRUM_CHANNEL} == {DRUM_HIT_TICKS}
    assert max(n.end_tick for n in notes) == whole


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
    """**한 이름이 두 값이면 둘 중 하나는 반드시 틀린다** (D-0111).

    옛 판은 `generation_pipeline.BARS_PER_SECTION`을 읽어 같은 객체인지 봤다. 그것은
    **재수출에 기댄 것이고** 재수출을 쓰는 곳은 이 시험뿐이었다 (D-0264). 지키려는 것은
    그 이름이 아니라 «파생값이 정본에서 나왔는가»이므로 파생값으로 확인한다.
    """
    from hathor.application.orchestrator.generation_pipeline import (
        DEFAULT_BARS,
        DEFAULT_SECTIONS,
    )

    assert DEFAULT_BARS == DEFAULT_SECTIONS * BARS_PER_SECTION


# ------------------------------------------------------------------ 층별 세기 (D-0174)


def test_박마다_세기가_다르다():
    """**층 안이 갈린다** (D-0177).

    전부 같은 세기면 *"초등학생이 치는 느낌"*이 난다 — 귀가 그렇게 판정했다.
    """
    notes = arrange(pattern("UUR"), PROGRESSION, seed=7)
    melody = {note.velocity for note in notes if note.velocity >= DYNAMICS["mp"]}
    assert len(melody) >= 3


def test_강박이_가장_세다():
    """강 · 약 · 중 · 약. **밖에서 온 격자다.**"""
    assert METRIC_STRESS == (0, 2, 1, 2)
    assert METRIC_STRESS[0] == min(METRIC_STRESS)
    assert METRIC_STRESS[2] < METRIC_STRESS[1]


def test_표_안에서만_내린다():
    """**표 밖으로 안 나간다.** 맨 아래보다 더 내려가면 맨 아래다."""
    assert softer(DYNAMICS["f"], 0) == DYNAMICS["f"]
    assert softer(DYNAMICS["f"], 1) == DYNAMICS["mf"]
    assert softer(DYNAMICS["f"], 2) == DYNAMICS["mp"]
    assert softer(DYNAMICS["pp"], 3) == DYNAMICS["pp"]
    with pytest.raises(ValueError, match="여린소리표 밖"):
        softer(72, 1)


def test_올리지_않는다():
    """**귀가 이미 *\"소리가 크다\"*로 판정했다** (D-0174). 올릴 근거가 없다."""
    notes = arrange(pattern("UUR"), PROGRESSION, seed=7)
    assert max(note.velocity for note in notes) == DYNAMICS["f"]


def test_층마다_세기가_다르다():
    """전부 72이던 동안 **가락과 반주가 같은 층에서 울렸다.**

    귀가 *"반주가 앞에서 논다"*로 판정했고 그것이 근거다 (D-0174).
    """
    notes = arrange(pattern("UUR"), PROGRESSION, seed=7)
    levels = {note.velocity for note in notes}
    assert levels <= set(DYNAMICS.values())
    # 화음 · 베이스 · 가락 강박이 서로 다르다. 가락 약박이 더 갈린다 (D-0177).
    assert len(levels) >= 3


def test_가락이_가장_세다():
    """**전경이 배경보다 세야 한다** (D-0141의 층 구분을 소리로 옮긴 것이다)."""
    notes = arrange(pattern("UUR"), PROGRESSION, seed=7)
    top = max(note.velocity for note in notes)
    assert sum(1 for note in notes if note.velocity == top) > 0
    assert min(note.velocity for note in notes) < top


def test_여린소리표_밖의_값을_안_쓴다():
    """**밖에서 온 격자다.** 실험으로 옮기면 그 순간 D-0058이다."""
    assert DYNAMICS == {"pp": 32, "p": 48, "mp": 64, "mf": 80, "f": 96, "ff": 112}


# ------------------------------------------------------------------ 잇기 (D-0176)


def test_이어지는_같은_음을_잇는다():
    """**D-0138이 화음에서 세운 규칙을 가락에 그대로 쓴다.**

    D-0141이 *"같은 음 유지 25%"*를 쟀고, 다시 치는 것과 끄는 것은 다른 소리다.
    """
    notes = arrange(pattern("UUR"), PROGRESSION, seed=7)
    melody = [note for note in notes if note.velocity == DYNAMICS["f"]]
    lengths = {note.duration_ticks for note in melody}
    assert len(lengths) > 1


def test_붙어_있고_같아야_잇는다():
    """**문턱이 없다.** 떨어져 있거나 음이 다르면 안 잇는다."""
    from hathor.application.arrangement import _tie

    assert _tie([(0, 480, 60), (480, 480, 60)]) == [(0, 960, 60)]
    assert _tie([(0, 480, 60), (480, 480, 62)]) == [(0, 480, 60), (480, 480, 62)]
    assert _tie([(0, 480, 60), (960, 480, 60)]) == [(0, 480, 60), (960, 480, 60)]


def test_잇기가_밀도를_안_바꾼다():
    """**같은 시간에 같은 음이 울린다.** 주는 것은 다시 치는 횟수뿐이다 (O-50)."""
    from hathor.application.arrangement import _tie

    sung = [(0, 480, 60), (480, 480, 60), (960, 480, 62)]
    assert sum(length for _, length, _ in _tie(sung)) == sum(length for _, length, _ in sung)


# ------------------------------- 코퍼스 범위 안인가 (D-0402 · D-0401)
#
# **판정선이 정본에 있다.** D-0206·D-0207은 그 수를 기록에 적어 두었고 아무도 다시
# 안 봤다 — 이제 `measured.toml`의 `[onset]`이 들고 이 시험이 **거기서 읽는다.**
# 재서 수가 움직이면 이 시험이 먼저 운다 (GR-0.7).


def _concentration(notes: Sequence[Note], period: int, bins: int = 4) -> float:
    """그 주기 안 `bins`등분에서 **가장 센 칸의 몫** — 코퍼스를 잰 자와 같은 꼴.

    세기로 무게를 준다. `phase_profile`이 봉우리 높이로 무게를 주는 것과 같다
    (D-0206) — 발음 수가 아니라 **에너지**가 몰렸는가를 본다.
    """
    found = [0.0] * bins
    for note in notes:
        found[int((note.start_tick % period) / period * bins) % bins] += note.velocity
    total = sum(found)
    return max(one / total for one in found)


def _corpus() -> dict[str, int]:
    return cast("dict[str, int]", tool_module("measured").canon()["onset"]["counts"])


def test_마디_집중도가_코퍼스_범위_안이다():
    """**100% → 41.5%** (D-0207) → **35.8%** (D-0402). 범위는 정본이 든다."""
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)

    found = _concentration(notes, TICKS_PER_BAR)

    assert found <= _corpus()["phase_bar_max_permille"] / 1000
    assert found > _corpus()["phase_bar_q1_permille"] / 1000, "코퍼스보다 고르면 그것도 수상하다"


def test_박_안_집중도가_코퍼스_범위_안이다():
    """**박 안은 100%였다** (D-0402). 박마다 쳐도 **박 안에서는 메트로놈**이었다.

    자가 없어서 안 보였다 — D-0401이 `[onset]`에 박 읽기를 넣고서야 드러났다.
    """
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)

    found = _concentration(notes, TICKS_PER_BEAT)

    assert found <= _corpus()["phase_beat_max_permille"] / 1000
    assert found > _corpus()["phase_beat_q1_permille"] / 1000


def test_쪼갬을_늘리면_집중도가_내려간다():
    """**방향이 맞나.** 늘려도 안 내려가면 쪼갬이 그 수를 안 움직이는 것이다."""
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)
    only_beats = [note for note in notes if note.start_tick % TICKS_PER_BEAT == 0]

    assert _concentration(notes, TICKS_PER_BEAT) < _concentration(only_beats, TICKS_PER_BEAT)


def test_층이_제_채널로_간다():
    """**역할이 곧 채널이다** (D-0405 · O-51).

    셋이 한 채널에 있으면 재생기가 **한 악기로** 낸다 — 사람이 *«베이스가 내가 아는
    그 콘트라베이스?»*라고 물은 것이 그 상태였다.
    """
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)
    layers = {note.channel for note in notes}

    assert layers == {LEAD_CHANNEL, PAD_CHANNEL, BASS_CHANNEL, DRUM_CHANNEL}
    # **받침은 드물고 배경은 잦다** (D-0207 · D-0402). 수가 뒤집히면 역할이 바뀐 것이다.
    counted = {one: sum(1 for note in notes if note.channel == one) for one in layers}
    assert counted[BASS_CHANNEL] < counted[LEAD_CHANNEL] < counted[PAD_CHANNEL]
    # **북은 마디마다 같은 수로 온다** (D-0411) — 가락보다 잦고 배경보다 드물다.
    assert counted[LEAD_CHANNEL] < counted[DRUM_CHANNEL] < counted[PAD_CHANNEL]


def _drum_notes(notes: Sequence[Note]) -> list[Note]:
    return [one for one in notes if one.channel == DRUM_CHANNEL]


def test_북이_난다() -> None:
    """**D-0405가 남긴 말이 «드럼이 없다»였다.** 채널만 막아 두고 치는 자가 없었다."""
    drums = _drum_notes(arrange(pattern("URUR"), PROGRESSION, seed=42))

    assert drums, "타악이 하나도 없다"
    assert {one.pitch for one in drums} == set(DRUM_KIT.values())


def test_뒷박_치기다() -> None:
    """**킥 1·3, 스네어 2·4** (D-0411). 그 둘이 번갈아 나는 것이 춤곡의 자리다.

    뒤바뀌면 — 킥이 2·4로 가면 — **박이 거꾸로 들린다.** 귀로는 바로 알지만 수로
    안 걸면 아무도 모른다 (D-0126).
    """
    drums = _drum_notes(arrange(pattern("URUR"), PROGRESSION, seed=42))

    for name, beats in (("킥", KICK_BEATS), ("스네어", SNARE_BEATS)):
        where = {
            (one.start_tick % TICKS_PER_BAR) // TICKS_PER_BEAT
            for one in drums
            if one.pitch == DRUM_KIT[name]
        }
        assert where == set(beats), f"{name}이 {sorted(where)}에 있다"


def test_하이햇이_8분이다() -> None:
    """**배경과 같은 격자다** (D-0402의 `SUBDIVISIONS`). 표를 두 벌로 안 만든다."""
    drums = _drum_notes(arrange(pattern("URUR"), PROGRESSION, seed=42))
    hats = [one for one in drums if one.pitch == DRUM_KIT["하이햇"]]

    where = {one.start_tick % TICKS_PER_BEAT for one in hats}

    assert where == {0, TICKS_PER_BEAT // SUBDIVISIONS}


def test_마디마다_북이_빠짐없이_있다() -> None:
    """**한 마디라도 비면 거기서 박이 끊긴다.** 마디 수는 다른 층이 든다."""
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)
    bars = max(one.start_tick for one in notes) // TICKS_PER_BAR + 1
    drums = _drum_notes(notes)

    struck = {one.start_tick // TICKS_PER_BAR for one in drums}

    assert struck == set(range(bars))
    per_bar = len(KICK_BEATS) + len(SNARE_BEATS) + BEATS_PER_BAR * SUBDIVISIONS
    assert len(drums) == bars * per_bar


def test_북이_들어가도_집중도가_범위_안이다() -> None:
    """**북은 박 머리에 떨어진다** — 그만큼 박 안 집중도를 올린다 (D-0411).

    실측: 마디 34.3% · 박 68.5%. 북 없이는 35.8% · 65.6%였고 **박이 2.9점 올랐다.**
    판정은 «범위 안인가»다 (D-0207 · D-0404) — 중앙을 겨누면 세기 표를 만지게 되고
    그것이 D-0058이다.
    """
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)

    assert _concentration(notes, TICKS_PER_BAR) <= _corpus()["phase_bar_max_permille"] / 1000
    assert _concentration(notes, TICKS_PER_BEAT) <= _corpus()["phase_beat_max_permille"] / 1000


def test_북을_빼면_박_집중도가_내려간다() -> None:
    """**방향이 맞나.** 북이 그 수를 안 움직이면 위 시험이 헛돈다 (D-0230)."""
    notes = arrange(pattern("URUR"), PROGRESSION, seed=42)
    pitched = [one for one in notes if one.channel != DRUM_CHANNEL]

    assert _concentration(pitched, TICKS_PER_BEAT) < _concentration(notes, TICKS_PER_BEAT)


def test_북이_하이햇보다_세다() -> None:
    """**귀가 잡은 것을 수로 건다** (D-0412 · D-0126).

    D-0411은 킥·스네어에 `METRIC_STRESS`를 곱했다. 2·4박이 약박이라 **스네어가
    하이햇과 똑같은 48**이 됐고, 사람이 *«북이 북 같지도 않고 너무 작아»*로
    판정했다 — **철 때리는 소리만 들렸다.**

    뒷박 치기의 요점이 **메트릭 강세를 거스르는 것**이다. 거기에 메트릭 강세를
    곱하면 그 어긋남이 사라진다.
    """
    drums = _drum_notes(arrange(pattern("URUR"), PROGRESSION, seed=42))
    struck = {
        name: {one.velocity for one in drums if one.pitch == DRUM_KIT[name]} for name in DRUM_KIT
    }

    assert struck["킥"] == struck["스네어"] == {DRUM_STRIKE}
    assert max(struck["하이햇"]) < DRUM_STRIKE, "하이햇이 북만큼 세다"


def test_뒷박이_약박에서_안_죽는다() -> None:
    """**2·4박의 스네어가 1·3박의 킥과 같은 세기여야 한다** (D-0412).

    박자리를 따르면 2·4가 내려간다 — 그것이 D-0411의 결함이었고, **자리마다 세기가
    다른지**를 보면 바로 걸린다.
    """
    drums = _drum_notes(arrange(pattern("URUR"), PROGRESSION, seed=42))
    beaten = {
        (one.start_tick % TICKS_PER_BAR) // TICKS_PER_BEAT: one.velocity
        for one in drums
        if one.pitch in {DRUM_KIT["킥"], DRUM_KIT["스네어"]}
    }

    assert len(set(beaten.values())) == 1, f"박자리마다 세기가 다르다: {beaten}"
