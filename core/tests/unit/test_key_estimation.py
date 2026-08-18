"""조성 추정 테스트. 합성 화음으로 검증하며 음원 파일을 쓰지 않는다."""

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.domain.services.key_estimation import (
    KRUMHANSL_MAJOR,
    KRUMHANSL_MINOR,
    chroma,
    estimate_key,
    estimate_key_from_waveform,
    pitch_class_map,
    to_mono,
)
from hathor.domain.value_objects.key import Key, Mode


def tone(frequency: float, seconds: float = 1.0) -> np.ndarray:
    """배음 3개까지 넣는다. 순음은 실제 악기와 너무 달라 검증이 무의미해진다."""
    time = np.arange(int(SOURCE_SAMPLE_RATE * seconds)) / SOURCE_SAMPLE_RATE
    stacked = sum(np.sin(2 * np.pi * frequency * partial * time) / partial for partial in (1, 2, 3))
    return np.asarray(stacked, dtype=np.float32)


def midi_hz(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def chord(notes: list[int], seconds: float = 1.0) -> np.ndarray:
    return np.asarray(sum(tone(midi_hz(note), seconds) for note in notes), dtype=np.float32)


# --- 빈 매핑 ---


def test_pitch_class_map_puts_a440_on_class_nine():
    """A4=440Hz는 피치클래스 9(A)여야 한다. 여기가 틀리면 전부 이조된다."""
    mapping = pitch_class_map()
    frequencies = np.fft.rfftfreq(4096, d=1.0 / SOURCE_SAMPLE_RATE)
    nearest = int(np.argmin(np.abs(frequencies - 440.0)))
    assert mapping[nearest] == 9


def test_pitch_class_map_excludes_out_of_range_bins():
    mapping = pitch_class_map()
    assert mapping[0] == -1  # DC
    assert mapping[-1] == -1  # 나이키스트
    assert set(np.unique(mapping[mapping >= 0])) == set(range(12))


# --- 크로마 ---


def test_chroma_peaks_on_the_played_pitch_class():
    """C를 울리면 C(0)가 가장 커야 한다."""
    result = chroma(tone(midi_hz(60), 2.0))
    assert int(np.argmax(result)) == 0


def test_chroma_is_octave_invariant():
    """한 옥타브 위 C도 같은 피치클래스다. 이것이 크로마의 정의다."""
    low = chroma(tone(midi_hz(48), 2.0))
    high = chroma(tone(midi_hz(72), 2.0))
    assert int(np.argmax(low)) == int(np.argmax(high)) == 0


def test_chroma_sums_to_one():
    result = chroma(chord([60, 64, 67], 2.0))
    assert float(result.sum()) == pytest.approx(1.0, abs=1e-5)


def test_chroma_of_silence_is_zero():
    assert float(chroma(np.zeros(8192, dtype=np.float32)).sum()) == 0.0


def test_chroma_of_too_short_signal_is_zero():
    assert chroma(np.ones(100, dtype=np.float32)).shape == (12,)


def test_chroma_rejects_invalid_sizes():
    with pytest.raises(ValueError):
        chroma(np.zeros(8192, dtype=np.float32), fft_size=1)


# --- 조성 추정 ---


def test_c_major_progression_is_identified():
    """C장조 I-V-vi-IV. 가장 흔한 진행이다."""
    signal = np.concatenate(
        [chord([60, 64, 67]), chord([67, 71, 74]), chord([69, 72, 76]), chord([65, 69, 72])]
    )
    assert estimate_key(chroma(signal)).key == Key(tonic="C", mode=Mode.MAJOR)


def test_transposition_moves_the_estimate():
    """전체를 5도 올리면 G장조가 나와야 한다. 이조에 따라가지 않으면 쓸모가 없다."""
    signal = np.concatenate(
        [chord([67, 71, 74]), chord([74, 78, 81]), chord([76, 79, 83]), chord([72, 76, 79])]
    )
    assert estimate_key(chroma(signal)).key == Key(tonic="G", mode=Mode.MAJOR)


def test_relative_minor_confusion_shows_up_as_small_margin():
    """나란한 장·단조 혼동은 K-S의 원리적 한계다 (D-0054).

    A단조 진행(i-VI-III-VII)을 C장조로 볼 수 있다. 구성음이 같기 때문이다.
    **고칠 수 없으므로 격차로 드러낸다.** 1등만 남기면 그 사실이 사라진다.
    """
    signal = np.concatenate(
        [chord([69, 72, 76]), chord([65, 69, 72]), chord([60, 64, 67]), chord([67, 71, 74])]
    )
    estimate = estimate_key(chroma(signal))
    assert {estimate.key, estimate.runner_up} == {
        Key(tonic="C", mode=Mode.MAJOR),
        Key(tonic="A", mode=Mode.MINOR),
    }
    assert estimate.margin < 0.15, "혼동인데 격차가 크면 애매함을 감지할 수 없다"


def test_clear_key_has_larger_margin_than_ambiguous_one():
    clear = estimate_key(np.asarray(KRUMHANSL_MAJOR, dtype=np.float32) / sum(KRUMHANSL_MAJOR))
    flat = estimate_key(np.full(12, 1 / 12, dtype=np.float32))
    assert clear.margin > flat.margin


def test_profiles_recover_their_own_key():
    """프로파일 자체를 넣으면 그 조성이 나와야 한다. 상관이 1에 가깝다."""
    major = estimate_key(np.asarray(KRUMHANSL_MAJOR, dtype=np.float32) / sum(KRUMHANSL_MAJOR))
    assert major.key == Key(tonic="C", mode=Mode.MAJOR)
    assert major.correlation == pytest.approx(1.0, abs=1e-6)

    minor = estimate_key(np.asarray(KRUMHANSL_MINOR, dtype=np.float32) / sum(KRUMHANSL_MINOR))
    assert minor.key == Key(tonic="C", mode=Mode.MINOR)


def test_estimate_is_deterministic():
    vector = chroma(chord([60, 64, 67], 2.0))
    assert estimate_key(vector).as_record() == estimate_key(vector).as_record()


def test_estimate_rejects_wrong_dimension():
    with pytest.raises(ValueError):
        estimate_key(np.zeros(11, dtype=np.float32))


# --- 파형 경로 ---


def test_stereo_is_downmixed():
    mono = tone(midi_hz(60), 1.0)
    stereo = np.stack([mono, mono])
    assert np.allclose(to_mono(stereo), mono)


def test_waveform_entry_point_matches_chroma_path():
    mono = chord([60, 64, 67], 2.0)
    stereo = np.stack([mono, mono])
    assert estimate_key_from_waveform(stereo).key == estimate_key(chroma(mono)).key
