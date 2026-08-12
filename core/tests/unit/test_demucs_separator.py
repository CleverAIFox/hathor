"""Demucs 스템 분리 테스트 (유닛 #4).

모델 적재와 분리는 GPU와 2GB 라이브러리를 요구하므로 조건부로 돈다.
광인사(GPU 없음)에서는 스킵되고 리전에서 검증된다.
"""

import importlib.util

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE

DEMUCS_AVAILABLE = importlib.util.find_spec("demucs") is not None


def _cuda_available() -> bool:
    if importlib.util.find_spec("torch") is None:
        return False
    import torch

    return bool(torch.cuda.is_available())


requires_gpu = pytest.mark.skipif(
    not (DEMUCS_AVAILABLE and _cuda_available()),
    reason="demucs 또는 CUDA 없음",
)


@requires_gpu
def test_스템_4종을_돌려준다():
    from hathor.infrastructure.demucs_separator import DemucsStemSeparator

    sep = DemucsStemSeparator()
    assert set(sep.sources) == {"drums", "bass", "other", "vocals"}


@requires_gpu
def test_분리_결과가_입력과_같은_모양이다():
    from hathor.infrastructure.demucs_separator import DemucsStemSeparator

    rng = np.random.default_rng(42)
    wave = rng.standard_normal((2, SOURCE_SAMPLE_RATE * 3), dtype=np.float32) * 0.1
    stems = DemucsStemSeparator().separate(wave)

    assert set(stems) == {"drums", "bass", "other", "vocals"}
    for stem in stems.values():
        assert stem.shape == wave.shape
        assert stem.dtype == np.float32
        assert np.isfinite(stem).all()
