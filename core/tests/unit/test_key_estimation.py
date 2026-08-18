"""조성 추정 테스트. 합성 화음으로 검증하며 음원 파일을 쓰지 않는다."""

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.domain.services.key_estimation import (
    CHROMA_CQ,
    CHROMA_LINEAR,
    KRUMHANSL_MAJOR,
    KRUMHANSL_MINOR,
    SEMITONE_BINS,
    chroma,
    cq_filterbank,
    estimate_key,
    estimate_key_from_waveform,
    pitch_class_map,
    semitone_hz,
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
    result = chroma(tone(midi_hz(60), 2.0), mode=CHROMA_CQ)
    assert int(np.argmax(result)) == 0


def test_chroma_is_octave_invariant():
    """한 옥타브 위 C도 같은 피치클래스다. 이것이 크로마의 정의다."""
    low = chroma(tone(midi_hz(48), 2.0), mode=CHROMA_CQ)
    high = chroma(tone(midi_hz(72), 2.0), mode=CHROMA_CQ)
    assert int(np.argmax(low)) == int(np.argmax(high)) == 0


def test_chroma_sums_to_one():
    result = chroma(chord([60, 64, 67], 2.0), mode=CHROMA_CQ)
    assert float(result.sum()) == pytest.approx(1.0, abs=1e-5)


def test_chroma_of_silence_is_zero():
    assert float(chroma(np.zeros(65536, dtype=np.float32), mode=CHROMA_CQ).sum()) == 0.0


def test_chroma_of_too_short_signal_is_zero():
    assert chroma(np.ones(100, dtype=np.float32), mode=CHROMA_CQ).shape == (12,)


def test_linear_chroma_rejects_invalid_sizes():
    from hathor.domain.services.key_estimation import linear_chroma

    with pytest.raises(ValueError):
        linear_chroma(np.zeros(8192, dtype=np.float32), fft_size=1)


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


# --- 나란한조와 베이스라인 (D-0055) ---


def test_relative_key_round_trips():
    from hathor.domain.services.key_estimation import relative_key

    for tonic in ("C", "G", "F#", "A#"):
        for mode in (Mode.MAJOR, Mode.MINOR):
            key = Key(tonic=tonic, mode=mode)
            assert relative_key(relative_key(key)) == key


def test_relative_key_pairs_are_the_known_ones():
    from hathor.domain.services.key_estimation import relative_key

    assert relative_key(Key(tonic="C", mode=Mode.MAJOR)) == Key(tonic="A", mode=Mode.MINOR)
    assert relative_key(Key(tonic="G", mode=Mode.MAJOR)) == Key(tonic="E", mode=Mode.MINOR)
    assert relative_key(Key(tonic="A", mode=Mode.MINOR)) == Key(tonic="C", mode=Mode.MAJOR)


def test_random_baseline_is_reproducible():
    from hathor.domain.services.key_estimation import random_baseline

    first = random_baseline(50, seed=1)
    second = random_baseline(50, seed=1)
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])


def test_random_correlation_is_high_enough_to_be_misleading():
    """**무작위 크로마도 상관이 높다.** 절대값만 보면 늘 좋아 보인다 (D-0055).

    24개 프로파일이 서로 닮아 아무 벡터나 넣어도 그중 하나와는 꽤 맞는다.
    이 사실을 고정해 두지 않으면 "상관 0.87"을 좋은 수치로 오독하게 된다.
    """
    from hathor.domain.services.key_estimation import random_baseline

    correlations, _ = random_baseline(300, seed=7)
    assert float(np.median(correlations)) > 0.5


def test_random_margin_often_exceeds_the_ambiguity_floor():
    """격차 임계 0.05는 무작위도 대부분 넘는다. 기준이 헐겁다는 증거다."""
    from hathor.domain.services.key_estimation import random_baseline

    _, margins = random_baseline(300, seed=7)
    assert float((margins >= 0.05).mean()) > 0.5


# --- 반음 격자 크로마 (D-0056) ---


def scale_tone(note: int) -> np.ndarray:
    return tone(midi_hz(note), 1.5)


def test_semitone_grid_starts_at_c2():
    assert semitone_hz(0) == pytest.approx(65.41, abs=0.01)
    assert semitone_hz(12) == pytest.approx(130.82, abs=0.02)
    assert semitone_hz(SEMITONE_BINS - 1) == pytest.approx(1975.5, abs=1.0)


def test_filterbank_peaks_at_semitone_centres():
    """반음 중심에서 1이고 인접 중심에서 0이어야 한다."""
    bank = cq_filterbank(8192, 2)
    frequencies = np.fft.rfftfreq(8192, d=1.0 / SOURCE_SAMPLE_RATE)
    for pitch in range(12):
        center = semitone_hz(2 * 12 + pitch)
        # 빈 격자가 반음 중심에 정확히 놓이지 않으므로 최댓값 빈이 중심에서
        # 한 칸 어긋날 수 있다. **중심 근처인지**를 보고 값이 1에 가까운지 본다.
        peak = int(np.argmax(bank[pitch]))
        assert abs(frequencies[peak] - center) < (frequencies[1] - frequencies[0])
        assert bank[pitch, peak] > 0.8, f"{pitch}번 반음 봉우리가 낮다"


def test_filterbank_rows_do_not_overlap_beyond_neighbours():
    """한 반음 필터는 인접 반음 밖으로 새면 안 된다."""
    bank = cq_filterbank(8192, 2)
    frequencies = np.fft.rfftfreq(8192, d=1.0 / SOURCE_SAMPLE_RATE)
    for pitch in range(12):
        index = 2 * 12 + pitch
        active = frequencies[bank[pitch] > 0]
        if active.size:
            assert active.min() >= semitone_hz(index - 1) - 1.0
            assert active.max() <= semitone_hz(index + 1) + 1.0


@pytest.mark.parametrize("octave_start", [36, 48, 60, 72, 84])
def test_cq_identifies_every_semitone_in_five_octaves(octave_start):
    """**핵심 회귀 테스트.** 60음 전부 맞아야 한다 (D-0056).

    선형 방식은 저역(C2~B2)에서 7/12를 틀렸다. 빈 간격 10.77Hz가 65Hz에서
    2.65반음을 덮어 C2·C#2·D#2가 전부 D로 뭉쳤기 때문이다. 코퍼스에서 D가
    29%로 1위였던 것이 이 결함이다.
    """
    for note in range(octave_start, octave_start + 12):
        result = chroma(scale_tone(note), mode=CHROMA_CQ)
        assert int(np.argmax(result)) == note % 12, (
            f"{note}번 음이 {int(np.argmax(result))}로 잡혔다"
        )


def test_linear_still_fails_in_the_low_register():
    """베이스라인이 여전히 틀리는 것을 고정한다.

    베이스라인이 조용히 좋아지면 개선폭을 잘못 읽는다. `linear`는 D-0056 이전
    상태를 그대로 보존해야 비교선 구실을 한다.
    """
    wrong = sum(
        1
        for note in range(36, 48)
        if int(np.argmax(chroma(scale_tone(note), mode=CHROMA_LINEAR))) != note % 12
    )
    assert wrong >= 5, "베이스라인이 바뀌었다면 비교가 성립하지 않는다"


def test_cq_fixes_a_key_the_linear_method_got_wrong():
    """G장조 I-IV-V-I을 선형은 D장조로 틀렸다. 코퍼스 D 편중의 실물이다."""
    signal = np.concatenate(
        [chord([55, 59, 62]), chord([60, 64, 67]), chord([62, 66, 69]), chord([55, 59, 62])]
    )
    assert estimate_key(chroma(signal, mode=CHROMA_LINEAR)).key != Key(tonic="G", mode=Mode.MAJOR)
    assert estimate_key(chroma(signal, mode=CHROMA_CQ)).key == Key(tonic="G", mode=Mode.MAJOR)


def test_cq_raises_margin_on_ambiguous_progressions():
    """나란한조 혼동은 남되 격차가 커진다.

    선형에서 A단조 진행의 격차가 0.004로 사실상 동전 던지기였다.
    """
    signal = np.concatenate(
        [chord([57, 60, 64]), chord([53, 57, 60]), chord([48, 52, 55]), chord([55, 59, 62])]
    )
    linear = estimate_key(chroma(signal, mode=CHROMA_LINEAR))
    cq = estimate_key(chroma(signal, mode=CHROMA_CQ))
    assert cq.margin > linear.margin


def test_chroma_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode"):
        chroma(np.zeros(65536, dtype=np.float32), mode="nonsense")


def test_cq_is_deterministic():
    signal = chord([60, 64, 67], 1.5)
    assert np.array_equal(chroma(signal, mode=CHROMA_CQ), chroma(signal, mode=CHROMA_CQ))


def test_waveform_entry_point_passes_mode_through():
    mono = chord([55, 59, 62], 1.5)
    stereo = np.stack([mono, mono])
    assert (
        estimate_key_from_waveform(stereo, mode=CHROMA_CQ).key
        == estimate_key(chroma(mono, mode=CHROMA_CQ)).key
    )


# --- 조율 편차 (D-0057) ---


def detuned(note: int, cents: float, seconds: float = 1.0) -> np.ndarray:
    return tone(midi_hz(note) * 2 ** (cents / 1200), seconds)


def progression(cents: float) -> np.ndarray:
    return np.concatenate([detuned(note, cents) for note in (60, 64, 67, 72, 55, 59, 62)])


@pytest.mark.parametrize("cents", [-32.0, -16.0, 0.0, 16.0, 32.0])
def test_tuning_deviation_is_recovered(cents):
    """일부러 틀어 넣은 조율을 되찾아야 한다 (D-0057).

    **반음 격자로 바꾸고 나서야 보이게 된 문제다.** 선형 방식은 저역이 뭉개져
    조율 편차를 감췄다. 이제 반음을 정확히 가르므로 음원이 반음의 절반 이상
    벗어나면 이웃 반음으로 통째로 넘어간다.
    """
    from hathor.domain.services.key_estimation import estimate_tuning_cents

    assert estimate_tuning_cents(progression(cents)) == pytest.approx(cents, abs=6.0)


def test_tuning_search_stays_inside_the_semitone():
    """±50센트는 이웃 반음까지의 거리라 어느 쪽으로 붙여도 같다.

    끝값이 나오면 순환이 일어나 -40이 +50으로 보고된다. 탐색 범위를 좁혀
    그 모호함을 없앤다 — 실측으로 겪은 결함이다.
    """
    from hathor.domain.services.key_estimation import TUNING_RANGE_CENTS, estimate_tuning_cents

    for cents in (-40.0, 40.0):
        assert abs(estimate_tuning_cents(progression(cents))) < TUNING_RANGE_CENTS


def test_sharpness_uses_square_sum_not_peak():
    """제곱합은 12개 전체가 얼마나 몰렸는지 재고, 최댓값은 한 음만 본다.

    화음에서는 최댓값이 흔들려 조율 추정이 어긋난다. 격자가 맞을 때 제곱합이
    최대가 되는지를 직접 고정한다.
    """
    from hathor.domain.services.key_estimation import cq_chroma

    signal = progression(0.0)
    aligned = float(np.square(cq_chroma(signal, tuning_cents=0.0)).sum())
    for offset in (-30.0, -15.0, 15.0, 30.0):
        assert aligned > float(np.square(cq_chroma(signal, tuning_cents=offset)).sum())


def test_tuning_shift_moves_the_filterbank():
    """양의 센트는 필터 중심을 위로 민다."""
    from hathor.domain.services.key_estimation import cq_filterbank

    base = cq_filterbank(8192, 2, SOURCE_SAMPLE_RATE, 0.0)
    shifted = cq_filterbank(8192, 2, SOURCE_SAMPLE_RATE, 50.0)
    frequencies = np.fft.rfftfreq(8192, d=1.0 / SOURCE_SAMPLE_RATE)
    assert frequencies[int(np.argmax(shifted[0]))] > frequencies[int(np.argmax(base[0]))]


def test_tuning_does_not_change_a_correctly_tuned_signal():
    from hathor.domain.services.key_estimation import cq_chroma

    signal = progression(0.0)
    assert np.array_equal(cq_chroma(signal), cq_chroma(signal, tuning_cents=0.0))


# --- 로그 압축과 프로파일 (D-0058) ---


def test_uniform_component_does_not_change_the_estimate():
    """**핵심 반증.** 피어슨 상관은 평균을 빼므로 균등 성분에 불변이다 (D-0058).

    "드럼이 크로마를 평평하게 만들어 조가 흩어진다"는 가설을 세웠고, 로그 압축을
    처방으로 골랐다. **가설이 틀렸다.** 균등 성분을 90% 섞어 엔트로피를 균등에
    가깝게 올려도 상관과 판정이 그대로다. 평평함은 증상이지 원인이 아니다.
    """
    base = np.asarray([0.20, 0.02, 0.10, 0.02, 0.15, 0.08, 0.02, 0.18, 0.02, 0.10, 0.03, 0.08])
    reference = estimate_key(np.asarray(base / base.sum(), dtype=np.float32))
    for weight in (0.3, 0.6, 0.9):
        mixed = (1 - weight) * base + weight / 12
        estimate = estimate_key(np.asarray(mixed / mixed.sum(), dtype=np.float32))
        assert estimate.key == reference.key
        assert estimate.correlation == pytest.approx(reference.correlation, abs=1e-6)


def test_log_compression_defaults_to_off():
    """실측이 도움 없음을 보였으므로 기본은 0이다. 구현은 반증 기록과 함께 남긴다."""
    from hathor.domain.services.key_estimation import LOG_GAMMA

    assert LOG_GAMMA == 0.0


def test_log_compression_lowers_contrast():
    """로그는 큰 값을 눌러 대비를 줄인다. 상관이 오히려 내려간다."""
    from hathor.domain.services.key_estimation import cq_chroma

    signal = np.concatenate(
        [chord([60, 64, 67]), chord([67, 71, 74]), chord([69, 72, 76]), chord([65, 69, 72])]
    )
    plain = estimate_key(cq_chroma(signal, gamma=0.0))
    compressed = estimate_key(cq_chroma(signal, gamma=100.0))
    assert plain.key == compressed.key
    assert compressed.correlation < plain.correlation


def test_compression_normalizes_before_and_after():
    """압축 전에 정규화한다. 곡의 절대 음량이 압축 강도를 바꾸면 안 된다."""
    from hathor.domain.services.key_estimation import cq_chroma

    quiet = chord([60, 64, 67], 1.5) * 0.01
    loud = chord([60, 64, 67], 1.5) * 4.0
    assert np.allclose(cq_chroma(quiet, gamma=100.0), cq_chroma(loud, gamma=100.0), atol=1e-5)


def test_negative_gamma_is_rejected():
    from hathor.domain.services.key_estimation import cq_chroma

    with pytest.raises(ValueError):
        cq_chroma(chord([60, 64, 67], 1.5), gamma=-1.0)


def test_profiles_are_selectable_and_differ():
    """프로파일 교체가 실제로 다른 판정을 낼 수 있어야 선택의 의미가 있다."""
    from hathor.domain.services.key_estimation import (
        PROFILE_KRUMHANSL,
        PROFILE_TEMPERLEY,
        cq_chroma,
    )

    signal = np.concatenate(
        [chord([52, 55, 59]), chord([57, 60, 64]), chord([59, 62, 66]), chord([52, 55, 59])]
    )
    vector = cq_chroma(signal)
    krumhansl = estimate_key(vector, profile=PROFILE_KRUMHANSL)
    temperley = estimate_key(vector, profile=PROFILE_TEMPERLEY)
    assert krumhansl.correlation != temperley.correlation


def test_temperley_recovers_its_own_profile():
    from hathor.domain.services.key_estimation import (
        PROFILE_TEMPERLEY,
        TEMPERLEY_MAJOR,
        TEMPERLEY_MINOR,
    )

    major = np.asarray(TEMPERLEY_MAJOR, dtype=np.float32)
    estimate = estimate_key(major / major.sum(), profile=PROFILE_TEMPERLEY)
    assert estimate.key == Key(tonic="C", mode=Mode.MAJOR)
    assert estimate.correlation == pytest.approx(1.0, abs=1e-6)

    minor = np.asarray(TEMPERLEY_MINOR, dtype=np.float32)
    assert estimate_key(minor / minor.sum(), profile=PROFILE_TEMPERLEY).key == Key(
        tonic="C", mode=Mode.MINOR
    )


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="profile"):
        estimate_key(np.full(12, 1 / 12, dtype=np.float32), profile="nonsense")


def test_default_profile_is_the_baseline():
    """기본이 바뀌면 D-0054~D-0057의 수치와 비교할 수 없다."""
    from hathor.domain.services.key_estimation import PROFILE_KRUMHANSL

    vector = np.asarray(KRUMHANSL_MAJOR, dtype=np.float32)
    vector = vector / vector.sum()
    assert estimate_key(vector).correlation == pytest.approx(
        estimate_key(vector, profile=PROFILE_KRUMHANSL).correlation
    )
