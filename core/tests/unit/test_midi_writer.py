"""MIDI 인코딩 테스트. 외부 라이브러리를 쓰지 않는 이유가 여기서 검증된다.

**바이트를 직접 검사한다.** D-0009가 "같은 입력이면 산출물이 바이트 단위로 같다"를
요구하므로, 라이브러리에 맡기면 그 라이브러리 버전이 계약의 일부가 된다.
"""

import pytest

from hathor.domain.services.midi_writer import (
    DRUM_CHANNEL,
    MAJOR_SCALE,
    TICKS_PER_BEAT,
    VOICES,
    Note,
    _variable_length,
    chord_pitches,
    render_smf,
)
from hathor.domain.value_objects.key import Key, Mode

C_MAJOR = Key(tonic="C", mode=Mode.MAJOR)
A_MINOR = Key(tonic="A", mode=Mode.MINOR)


# --- 화성 이론 ---


def test_tonic_triad_in_c_major():
    """C장조 I화음은 도미솔이다. 여기가 틀리면 나머지는 볼 필요가 없다."""
    assert chord_pitches(C_MAJOR, "I") == (60, 64, 67)


def test_dominant_triad_wraps_octave():
    """V화음은 음계를 넘어간다. 옥타브를 올리지 않으면 3화음이 뒤집힌다."""
    assert chord_pitches(C_MAJOR, "V") == (67, 71, 74)


def test_minor_key_uses_minor_scale():
    """A단조 i화음은 라도미다."""
    assert chord_pitches(A_MINOR, "i") == (69, 72, 76)


def test_case_does_not_change_pitches():
    """대소문자는 화음 품질의 표기일 뿐 음계가 결정한다.

    대소문자로 품질을 따로 계산하면 두 진실 공급원이 생긴다.
    """
    assert chord_pitches(C_MAJOR, "ii") == chord_pitches(C_MAJOR, "II")


def test_every_degree_is_diatonic():
    """모든 도수가 조성 음계 안에 있어야 한다."""
    allowed = {(60 + step) % 12 for step in MAJOR_SCALE}
    for degree in ("I", "ii", "iii", "IV", "V", "vi", "vii"):
        for pitch in chord_pitches(C_MAJOR, degree):
            assert pitch % 12 in allowed, f"{degree} → {pitch}"


def test_unknown_degree_is_rejected():
    with pytest.raises(ValueError):
        chord_pitches(C_MAJOR, "IX")


# --- 가변 길이 수량 ---


def test_variable_length_matches_smf_spec():
    """SMF 규격의 예시 값. 여기가 틀리면 파일이 통째로 깨진다."""
    assert _variable_length(0) == b"\x00"
    assert _variable_length(127) == b"\x7f"
    assert _variable_length(128) == b"\x81\x00"
    assert _variable_length(8192) == b"\xc0\x00"
    assert _variable_length(0x0FFFFFFF) == b"\xff\xff\xff\x7f"


def test_variable_length_rejects_negative():
    with pytest.raises(ValueError):
        _variable_length(-1)


# --- 파일 구조 ---


def test_header_is_well_formed():
    data = render_smf([Note(60, 0, 480)])
    assert data[:4] == b"MThd"
    assert data[4:8] == (6).to_bytes(4, "big")
    assert data[8:10] == b"\x00\x00"  # 포맷 0
    assert data[10:12] == b"\x00\x01"  # 트랙 1개
    assert int.from_bytes(data[12:14], "big") == TICKS_PER_BEAT
    assert data[14:18] == b"MTrk"


def test_track_length_matches_actual_body():
    """길이 필드가 틀리면 재생기가 파일을 거부한다."""
    data = render_smf([Note(60, 0, 480), Note(64, 480, 480)])
    declared = int.from_bytes(data[18:22], "big")
    assert declared == len(data) - 22


def test_track_ends_with_end_of_track_meta():
    assert render_smf([Note(60, 0, 480)]).endswith(b"\x00\xff\x2f\x00")


def test_tempo_is_encoded_as_microseconds_per_beat():
    data = render_smf([Note(60, 0, 480)], tempo_bpm=120)
    marker = data.index(b"\xff\x51\x03")
    assert int.from_bytes(data[marker + 3 : marker + 6], "big") == 500_000


# --- 결정성 ---


def test_input_order_does_not_change_bytes():
    """같은 노트 집합이면 순서가 달라도 같은 파일이어야 한다 (D-0009).

    정렬하지 않으면 배치 순서나 딕셔너리 순회가 바이트에 새어 나온다.
    """
    notes = [Note(60, 0, 480), Note(64, 0, 480), Note(67, 480, 480)]
    assert render_smf(notes) == render_smf(list(reversed(notes)))


def test_repeated_render_is_identical():
    notes = [Note(60, 0, 480), Note(67, 240, 960)]
    assert render_smf(notes) == render_smf(notes)


def test_note_off_precedes_note_on_at_same_tick():
    """같은 틱에서 오프가 먼저여야 이어지는 같은 음이 잘리지 않는다."""
    data = render_smf([Note(60, 0, 480), Note(60, 480, 480)])
    body = data[22:]
    assert body.index(b"\x80\x3c") < body.index(b"\x90\x3c", body.index(b"\x80\x3c"))


def test_empty_note_list_still_makes_a_valid_file():
    data = render_smf([])
    assert data[:4] == b"MThd"
    assert data.endswith(b"\x00\xff\x2f\x00")


# --- 입력 검증 ---


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pitch": -1, "start_tick": 0, "duration_ticks": 480},
        {"pitch": 128, "start_tick": 0, "duration_ticks": 480},
        {"pitch": 60, "start_tick": -1, "duration_ticks": 480},
        {"pitch": 60, "start_tick": 0, "duration_ticks": 0},
        {"pitch": 60, "start_tick": 0, "duration_ticks": 480, "velocity": 0},
        {"pitch": 60, "start_tick": 0, "duration_ticks": 480, "velocity": 128},
    ],
)
def test_invalid_notes_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Note(**kwargs)


def test_invalid_tempo_is_rejected():
    with pytest.raises(ValueError):
        render_smf([Note(60, 0, 480)], tempo_bpm=0)


# ------------------------------------ 층마다 악기 (D-0405 · O-51)
#
# **세 층은 코드에 이미 있었다** — 전경(D-0141) · 배경(D-0137) · 받침(D-0139). 그런데
# `program_change`를 안 써서 재생기 기본값으로 **셋 다 피아노로 났고**, 사람이 세 번
# 물었다: *«베이스가 내가 아는 그 콘트라베이스?»* **층이 안 갈리면 귀가 판정을 못 한다.**


def test_쓰는_층에만_악기를_준다():
    """**안 쓰는 채널까지 적으면 바이트가 늘고 아무 소리도 안 낸다.**"""
    data = render_smf(
        [
            Note(pitch=60, start_tick=0, duration_ticks=480),
            Note(pitch=48, start_tick=0, duration_ticks=480, channel=2),
        ]
    )

    programs = [
        data[index : index + 2]
        for index in range(len(data) - 1)
        if data[index] in (0xC0, 0xC1, 0xC2)
    ]

    assert bytes((0xC0, VOICES[0][1])) in data
    assert bytes((0xC2, VOICES[2][1])) in data
    assert bytes((0xC1, VOICES[1][1])) not in data, "안 쓴 층에 악기를 줬다"
    assert len(programs) == 2


def test_음이_제_채널로_난다():
    """`0x90 | channel`. **채널을 안 실으면 셋이 한 악기로 겹친다.**"""
    data = render_smf([Note(pitch=60, start_tick=0, duration_ticks=480, channel=2)])

    assert bytes((0x92, 60)) in data
    assert bytes((0x82, 60, 0)) in data


def test_타악_채널은_막는다():
    """GM 9번은 북이다. **거기에 피아노를 넣으면 화음이 북으로 난다.**"""
    with pytest.raises(ValueError, match="타악"):
        Note(pitch=60, start_tick=0, duration_ticks=480, channel=DRUM_CHANNEL)


def test_층마다_악기가_다르다():
    """**같은 번호를 둘에 주면 갈라 들을 수 없다** — 이 판의 목적이 그것이다."""
    assert len({program for _, program in VOICES.values()}) == len(VOICES)
    assert set(VOICES) == {0, 1, 2}
    assert all(0 <= program <= 127 for _, program in VOICES.values())
