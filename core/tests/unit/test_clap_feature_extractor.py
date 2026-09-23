"""CLAP 특징 추출 (O-68 · D-0231).

리샘플링과 청크 분할은 GPU 없이 돈다. 모델은 **가짜로 세운다** — 1.7GB를 받아야 도는 시험은
아무도 안 돌린다 (D-0061과 같은 이유).
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import CHUNK_SECONDS, SOURCE_SAMPLE_RATE
from hathor.infrastructure.clap_feature_extractor import (
    CLAP_SAMPLE_RATE,
    MIXTURE_OUTPUT_KEY,
    ClapFeatureExtractor,
    split_chunks,
    to_clap_waveform,
)

requires_scipy = pytest.mark.skipif(
    importlib.util.find_spec("scipy") is None,
    reason="리샘플러가 scipy에 의존한다. GPU 묶음 없는 기기에서는 건너뛴다",
)
DIMENSION = 512


@requires_scipy
def test_스테레오를_48khz_모노로_만든다() -> None:
    """**MERT는 24kHz, CLAP은 48kHz다** — 규격이 갈리면 임베딩이 조용히 나빠진다."""
    stereo = np.zeros((2, SOURCE_SAMPLE_RATE * 4), dtype=np.float32)
    mono = to_clap_waveform(stereo)
    assert mono.ndim == 1
    assert mono.dtype == np.float32
    assert abs(len(mono) / CLAP_SAMPLE_RATE - 4.0) < 0.01


@requires_scipy
def test_다운믹스는_산술평균이다() -> None:
    stereo = np.stack(
        [
            np.full(SOURCE_SAMPLE_RATE, 1.0, dtype=np.float32),
            np.full(SOURCE_SAMPLE_RATE, 0.0, dtype=np.float32),
        ]
    )
    mono = to_clap_waveform(stereo)
    assert abs(float(mono[CLAP_SAMPLE_RATE // 2]) - 0.5) < 0.01


def test_10초로_자르고_1초_미만은_버린다() -> None:
    chunks = split_chunks(np.zeros(CLAP_SAMPLE_RATE * 25, dtype=np.float32))
    assert [len(chunk) for chunk in chunks] == [
        CHUNK_SECONDS * CLAP_SAMPLE_RATE,
        CHUNK_SECONDS * CLAP_SAMPLE_RATE,
        CLAP_SAMPLE_RATE * 5,
    ]
    assert split_chunks(np.zeros(CLAP_SAMPLE_RATE // 2, dtype=np.float32)) == []


class _FakeTensor:
    def __init__(self, data: np.ndarray) -> None:
        self.data = data

    def to(self, device: str) -> _FakeTensor:
        return self

    def cpu(self) -> _FakeTensor:
        return self

    def numpy(self) -> np.ndarray:
        return self.data

    def __getitem__(self, index: int) -> _FakeTensor:
        return _FakeTensor(self.data[index])


def _fake_torch() -> ModuleType:
    torch = ModuleType("torch")

    class _NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    torch.no_grad = _NoGrad  # type: ignore[attr-defined]
    torch.stack = lambda values: _FakeTensor(  # type: ignore[attr-defined]
        np.stack([value.data for value in values])
    )
    return torch


def _extractor(monkeypatch: pytest.MonkeyPatch, seen: list[int]) -> ClapFeatureExtractor:
    """모델도 처리기도 가짜다. **여기서 보는 것은 청크 수와 모양이다.**"""
    transformers = ModuleType("transformers")

    class _Model:
        config = SimpleNamespace(projection_dim=DIMENSION)

        def to(self, device: str) -> _Model:
            return self

        def eval(self) -> _Model:
            return self

        def get_audio_features(self, **inputs: Any) -> _FakeTensor:
            seen.append(int(inputs["input_features"].data.shape[0]))
            return _FakeTensor(np.ones((1, DIMENSION), dtype=np.float32))

    transformers.ClapModel = SimpleNamespace(from_pretrained=lambda name: _Model())  # type: ignore[attr-defined]
    transformers.AutoProcessor = SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda name: (
            lambda audios, sampling_rate, return_tensors: {
                "input_features": _FakeTensor(np.asarray(audios).reshape(1, -1))
            }
        )
    )
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", _fake_torch())
    return ClapFeatureExtractor(device="cpu")


@requires_scipy
def test_청크마다_임베딩_하나를_쌓는다(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []
    extractor = _extractor(monkeypatch, seen)
    stereo = np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32)

    found = extractor.extract_layers(stereo)

    assert list(found) == [MIXTURE_OUTPUT_KEY], "스템도 레이어도 안 만든다 (D-0024)"
    assert found[MIXTURE_OUTPUT_KEY].shape == (3, DIMENSION)
    assert found[MIXTURE_OUTPUT_KEY].dtype == np.float32
    assert len(seen) == 3, "청크 수만큼 추론한다"


@requires_scipy
def test_1초_미만_곡은_빈_배열이다(monkeypatch: pytest.MonkeyPatch) -> None:
    """MERT와 같은 약속이다 — 저장소가 빈 곡을 그대로 받는다."""
    extractor = _extractor(monkeypatch, [])
    found = extractor.extract(np.zeros((2, SOURCE_SAMPLE_RATE // 2), dtype=np.float32))
    assert found.shape == (0, DIMENSION)


def test_레이어를_안_뽑는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """포트를 만족시키려고 둔 자리다. 비어 있어야 `ExtractLayerFeatures`가 그대로 돈다."""
    assert _extractor(monkeypatch, []).layers == ()
