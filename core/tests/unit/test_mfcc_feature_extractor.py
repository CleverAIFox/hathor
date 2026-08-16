"""MFCC 베이스라인 테스트. 합성 사인파만 쓴다."""

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.infrastructure.mfcc_feature_extractor import (
    FEATURE_DIM,
    MEL_FILTERS,
    MfccFeatureExtractor,
    dct_matrix,
    mel_filterbank,
    to_mono,
)


def tone(hz: float, seconds: float, amplitude: float = 0.5) -> np.ndarray:
    samples = np.arange(int(SOURCE_SAMPLE_RATE * seconds), dtype=np.float32)
    wave = amplitude * np.sin(2 * np.pi * hz * samples / SOURCE_SAMPLE_RATE)
    return np.asarray(np.stack([wave, wave]), dtype=np.float32)


def test_filterbank_shape_and_nonnegativity():
    bank = mel_filterbank()
    assert bank.shape[0] == MEL_FILTERS
    assert (bank >= 0).all()
    assert bank.sum() > 0


def test_dct_matrix_drops_zeroth_order():
    """c0(에너지)를 만들지 않는다. 각 기저의 합이 0에 가까우면 상수 성분이 없다."""
    matrix = dct_matrix()
    assert matrix.shape[1] == MEL_FILTERS
    assert np.allclose(matrix.sum(axis=1), 0.0, atol=1e-5)


def test_to_mono_averages_channels():
    stereo = np.asarray([[1.0, 3.0], [3.0, 1.0]], dtype=np.float32)
    assert np.allclose(to_mono(stereo), [2.0, 2.0])


def test_extract_returns_chunk_rows():
    extractor = MfccFeatureExtractor()
    result = extractor.extract(tone(440.0, 25.0))
    # 10 + 10 + 5초. 5초 자투리는 1초 이상이므로 남는다.
    assert result.shape == (3, FEATURE_DIM)
    assert np.isfinite(result).all()


def test_extract_drops_short_leftover():
    """10초 + 0.5초면 청크는 하나다. 1초 미만 자투리는 버린다."""
    assert MfccFeatureExtractor().extract(tone(440.0, 10.5)).shape[0] == 1


def test_extract_returns_empty_for_too_short_audio():
    assert MfccFeatureExtractor().extract(tone(440.0, 0.5)).shape == (0, FEATURE_DIM)


def test_extract_is_deterministic():
    extractor = MfccFeatureExtractor()
    waveform = tone(440.0, 11.0)
    assert np.array_equal(extractor.extract(waveform), extractor.extract(waveform))


def test_extract_is_invariant_to_gain():
    """c0를 버렸으므로 마스터링 볼륨이 벡터에 섞이지 않는다 (D-0021과 같은 이유).

    완전 불변은 아니다. 로그 바닥값(1e-10)이 조용한 신호의 저에너지 빈에서
    먼저 걸리기 때문이며, 10배 게인 차이에서 상대 오차 1% 미만이다.
    """
    extractor = MfccFeatureExtractor()
    quiet = extractor.extract(tone(440.0, 11.0, amplitude=0.05))
    loud = extractor.extract(tone(440.0, 11.0, amplitude=0.5))
    assert np.allclose(quiet, loud, rtol=0.01, atol=0.05)


def test_extract_separates_different_pitches():
    extractor = MfccFeatureExtractor()
    low = extractor.extract(tone(220.0, 11.0))
    high = extractor.extract(tone(3520.0, 11.0))
    assert not np.allclose(low, high, atol=1e-2)


def test_extract_handles_silence_without_nan():
    silent = np.zeros((2, SOURCE_SAMPLE_RATE * 11), dtype=np.float32)
    result = MfccFeatureExtractor().extract(silent)
    assert np.isfinite(result).all()


def test_extract_matches_mert_chunk_count():
    """MERT 경로와 같은 시간 격자를 쓴다. 청크 수가 어긋나면 M0 비교가 흔들린다."""
    from hathor.infrastructure.mert_feature_extractor import split_chunks as mert_chunks

    scipy = pytest.importorskip("scipy", reason="MERT 경로 리샘플러가 scipy에 의존한다")
    assert scipy is not None

    from hathor.infrastructure.mert_feature_extractor import to_feature_waveform

    waveform = tone(440.0, 47.0)
    mfcc_count = MfccFeatureExtractor().extract(waveform).shape[0]
    assert mfcc_count == len(mert_chunks(to_feature_waveform(waveform)))
