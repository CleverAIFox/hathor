"""MFCC 베이스라인 특징 추출. FeatureExtractor 포트의 두 번째 구현이다.

MERT 점수 하나만으로는 아무것도 말할 수 없다. `MAP 0.41`이 좋은 수치인지
나쁜 수치인지는 무작위(하한)와 고전 특징(비교선) 사이 어디에 있는지로만
판정된다. 무작위 대비 20배여도 1990년대 MFCC와 같다면 GPU 6시간의 근거가
없다. 이 모듈은 그 비교선을 만든다.

**의존성을 늘리지 않는다.** librosa도 torchaudio도 쓰지 않고 numpy만 쓴다.
베이스라인 하나 때문에 라이브러리를 들이면 그 버전이 재현성 논의에 끼어든다.
librosa와 계수가 소수점 아래에서 다를 수 있으나 상관없다. 비교 대상은
librosa가 아니라 MERT다.

**44.1kHz 그대로 쓴다.** MERT 경로는 24kHz로 리샘플하지만 그것은 모델
요구사항이고, MFCC에는 리샘플러가 필요 없다. scipy를 끌어들이지 않아
GPU 없는 기기에서 추가 설치 없이 돈다.

**0차 계수를 버린다.** c0는 프레임 전체 에너지, 즉 마스터링 볼륨이다.
D-0021이 정규화를 도입한 이유와 같은 이유로 취향 비교에 섞이면 안 된다.
"""

from __future__ import annotations

import numpy as np

from hathor.domain.ports.audio_analysis import (
    CHUNK_SECONDS,
    SOURCE_SAMPLE_RATE,
    Embedding,
    StereoWaveform,
    Waveform,
)

FFT_SIZE = 2048
HOP_SIZE = 512
MEL_FILTERS = 40
MEL_FMIN_HZ = 0.0
MEL_FMAX_HZ = 8000.0
COEFFICIENTS = 20
"""c1~c20을 쓴다. c0는 에너지이므로 버린다."""

CHUNK_SAMPLES = CHUNK_SECONDS * SOURCE_SAMPLE_RATE
MIN_CHUNK_SAMPLES = SOURCE_SAMPLE_RATE
LOG_FLOOR = 1e-10
FEATURE_DIM = COEFFICIENTS * 2
"""청크별 평균과 표준편차를 이어붙인다."""


def hz_to_mel(hz: float) -> float:
    return 2595.0 * float(np.log10(1.0 + hz / 700.0))


def mel_to_hz(
    mel: np.ndarray[tuple[int], np.dtype[np.float64]],
) -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    return np.asarray(700.0 * (10.0 ** (mel / 2595.0) - 1.0), dtype=np.float64)


def mel_filterbank(
    sample_rate: int = SOURCE_SAMPLE_RATE,
) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
    """(멜 필터, 주파수 빈) 삼각 필터뱅크. 호출마다 같은 값이 나온다."""
    edges_mel = np.linspace(hz_to_mel(MEL_FMIN_HZ), hz_to_mel(MEL_FMAX_HZ), MEL_FILTERS + 2)
    edges_hz = mel_to_hz(edges_mel)
    bins = np.floor((FFT_SIZE + 1) * edges_hz / sample_rate).astype(np.int64)
    bank = np.zeros((MEL_FILTERS, FFT_SIZE // 2 + 1), dtype=np.float32)
    for index in range(MEL_FILTERS):
        left, center, right = int(bins[index]), int(bins[index + 1]), int(bins[index + 2])
        for position in range(left, min(center, bank.shape[1])):
            if center > left:
                bank[index, position] = (position - left) / (center - left)
        for position in range(center, min(right, bank.shape[1])):
            if right > center:
                bank[index, position] = (right - position) / (right - center)
    return bank


def dct_matrix() -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
    """직교 DCT-II 행렬 중 c1~cN 행만. c0는 만들지 않는다."""
    orders = np.arange(1, COEFFICIENTS + 1).reshape(-1, 1)
    positions = np.arange(MEL_FILTERS).reshape(1, -1)
    basis = np.cos(np.pi * orders * (2 * positions + 1) / (2 * MEL_FILTERS))
    return np.asarray(basis * np.sqrt(2.0 / MEL_FILTERS), dtype=np.float32)


def to_mono(stereo: StereoWaveform) -> Waveform:
    """산술 평균 다운믹스. MERT 경로와 같은 규약이다 (D-0021)."""
    mono = stereo.mean(axis=0) if stereo.ndim > 1 else stereo
    return np.asarray(mono, dtype=np.float32)


def split_chunks(waveform: Waveform) -> list[Waveform]:
    """10초 단위로 자르고 1초 미만 자투리는 버린다.

    MERT 경로와 같은 시간 격자를 쓴다. 청크 경계가 다르면 M0 자기일관성
    비교에서 청크 분할 방식의 차이가 임베딩 차이로 보인다.
    """
    chunks = [
        waveform[start : start + CHUNK_SAMPLES] for start in range(0, len(waveform), CHUNK_SAMPLES)
    ]
    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_SAMPLES]


class MfccFeatureExtractor:
    """청크당 (평균 20 + 표준편차 20) = 40차원을 낸다.

    프레임을 그대로 남기지 않는다. 218초 곡이면 프레임 18,000개가 되어
    곡당 1.4MB, 코퍼스 전체 1.4GB다. MERT npz 347MB보다 큰 베이스라인은
    말이 안 된다. 청크 단위로 접으면 MERT 산출물과 같은 (청크, 차원) 규격이
    되어 평가 하네스가 구분 없이 읽는다.
    """

    def __init__(self, sample_rate: int = SOURCE_SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._bank = mel_filterbank(sample_rate)
        self._dct = dct_matrix()
        self._window = np.hanning(FFT_SIZE).astype(np.float32)

    def extract(self, waveform: StereoWaveform) -> Embedding:
        chunks = split_chunks(to_mono(waveform))
        if not chunks:
            return np.zeros((0, FEATURE_DIM), dtype=np.float32)
        rows = [self._chunk_vector(chunk) for chunk in chunks]
        return np.asarray(np.stack(rows), dtype=np.float32)

    def _chunk_vector(self, chunk: Waveform) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
        coefficients = self._mfcc(chunk)
        if coefficients.shape[0] == 0:
            return np.zeros(FEATURE_DIM, dtype=np.float32)
        pooled = np.concatenate([coefficients.mean(axis=0), coefficients.std(axis=0)])
        return np.asarray(pooled, dtype=np.float32)

    def _mfcc(self, chunk: Waveform) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
        frames = self._frame(chunk)
        if frames.shape[0] == 0:
            return np.zeros((0, COEFFICIENTS), dtype=np.float32)
        spectrum = np.fft.rfft(frames * self._window, n=FFT_SIZE, axis=1)
        power = np.asarray(np.abs(spectrum) ** 2, dtype=np.float32)
        energies = power @ self._bank.T
        return np.asarray(np.log(energies + LOG_FLOOR) @ self._dct.T, dtype=np.float32)

    @staticmethod
    def _frame(chunk: Waveform) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
        """겹치는 프레임을 뷰로 만든다. 복사하지 않는다."""
        count = 1 + (len(chunk) - FFT_SIZE) // HOP_SIZE if len(chunk) >= FFT_SIZE else 0
        if count <= 0:
            return np.zeros((0, FFT_SIZE), dtype=np.float32)
        strides = (chunk.strides[0] * HOP_SIZE, chunk.strides[0])
        view = np.lib.stride_tricks.as_strided(chunk, shape=(count, FFT_SIZE), strides=strides)
        return np.asarray(view, dtype=np.float32)
