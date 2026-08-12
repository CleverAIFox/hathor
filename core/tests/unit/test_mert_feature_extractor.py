"""MERT 특징 추출 테스트 (유닛 #4, D-0018 · D-0021).

리샘플링과 청크 분할은 GPU 없이 돈다. 모델 추론은 조건부다.
"""

import importlib.util

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import (
    CHUNK_SECONDS,
    FEATURE_SAMPLE_RATE,
    SOURCE_SAMPLE_RATE,
)
from hathor.infrastructure.mert_feature_extractor import (
    split_chunks,
    to_feature_waveform,
)


def test_스테레오를_24khz_모노로_만든다():
    stereo = np.zeros((2, SOURCE_SAMPLE_RATE * 4), dtype=np.float32)
    mono = to_feature_waveform(stereo)
    assert mono.ndim == 1
    assert mono.dtype == np.float32
    assert abs(len(mono) / FEATURE_SAMPLE_RATE - 4.0) < 0.01


def test_다운믹스는_산술평균이다():
    stereo = np.stack(
        [
            np.full(SOURCE_SAMPLE_RATE, 1.0, dtype=np.float32),
            np.full(SOURCE_SAMPLE_RATE, 0.0, dtype=np.float32),
        ]
    )
    mono = to_feature_waveform(stereo)
    # 에너지 보존(√2 나눗셈)이 아니라 산술 평균이므로 0.5다
    assert abs(float(mono[FEATURE_SAMPLE_RATE // 2]) - 0.5) < 0.01


def test_10초_단위로_자른다():
    wave = np.zeros(FEATURE_SAMPLE_RATE * 25, dtype=np.float32)
    chunks = split_chunks(wave)
    assert len(chunks) == 3
    assert len(chunks[0]) == CHUNK_SECONDS * FEATURE_SAMPLE_RATE
    assert len(chunks[2]) == CHUNK_SECONDS * FEATURE_SAMPLE_RATE // 2


def test_1초_미만_자투리는_버린다():
    # 자투리 임베딩은 의미가 없고 패딩 비율이 커져 벡터를 왜곡한다
    wave = np.zeros(FEATURE_SAMPLE_RATE * 20 + 1000, dtype=np.float32)
    assert len(split_chunks(wave)) == 2


def test_1초_이상_자투리는_남긴다():
    wave = np.zeros(FEATURE_SAMPLE_RATE * 21, dtype=np.float32)
    assert len(split_chunks(wave)) == 3


def _gpu_ready() -> bool:
    if importlib.util.find_spec("torch") is None:
        return False
    if importlib.util.find_spec("transformers") is None:
        return False
    import torch

    return bool(torch.cuda.is_available())


requires_gpu = pytest.mark.skipif(not _gpu_ready(), reason="transformers 또는 CUDA 없음")


@requires_gpu
def test_임베딩_모양이_청크_수와_맞는다():
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor

    rng = np.random.default_rng(42)
    wave = rng.standard_normal(FEATURE_SAMPLE_RATE * 25, dtype=np.float32) * 0.1
    embedding = MertFeatureExtractor().extract(wave)

    assert embedding.shape == (3, 768)
    assert embedding.dtype == np.float32
    assert np.isfinite(embedding).all()


@requires_gpu
def test_짧은_청크도_유한한_벡터를_낸다():
    # 마지막 청크가 10초보다 짧으면 패딩이 들어간다. 마스크가 없으면
    # 패딩 구간이 벡터를 오염시킨다 (D-0021).
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor

    rng = np.random.default_rng(7)
    wave = rng.standard_normal(FEATURE_SAMPLE_RATE * 12, dtype=np.float32) * 0.1
    embedding = MertFeatureExtractor().extract(wave)

    assert embedding.shape == (2, 768)
    assert np.isfinite(embedding).all()
    # 두 벡터가 완전히 같으면 마스크 처리가 무의미해진 것이다
    assert not np.allclose(embedding[0], embedding[1])


@requires_gpu
def test_빈_입력은_빈_임베딩():
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor

    empty = np.zeros(0, dtype=np.float32)
    assert MertFeatureExtractor().extract(empty).shape == (0, 768)
