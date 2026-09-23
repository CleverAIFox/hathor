"""CLAP 특징 추출 (O-68 · D-0231).

리샘플링과 청크 분할은 GPU 없이 돈다. 모델은 **가짜로 세운다** — 1.7GB를 받아야 도는 시험은
아무도 안 돌린다 (D-0061과 같은 이유).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import CHUNK_SECONDS, SOURCE_SAMPLE_RATE
from hathor.infrastructure.clap_feature_extractor import (
    CLAP_SAMPLE_RATE,
    MIXTURE_OUTPUT_KEY,
    ClapFeatureExtractor,
    audio_vector,
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


class _FakeOutput:
    """transformers 5의 반환을 흉내 낸다 — **`[0]`은 임베딩이 아니다** (D-0233).

    `get_audio_features`는 `BaseModelOutputWithPooling`을 내고 그 첫 자리는
    `last_hidden_state`다. 가짜가 텐서를 내주면 내 실수가 또 초록이 된다.
    """

    def __init__(self, pooled: np.ndarray, hidden: np.ndarray) -> None:
        self.pooler_output = _FakeTensor(pooled)
        self.last_hidden_state = _FakeTensor(hidden)

    def __getitem__(self, index: int) -> _FakeTensor:
        return (self.last_hidden_state, self.pooler_output)[index]


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


def _extractor(
    monkeypatch: pytest.MonkeyPatch, seen: list[int], dimension: int = DIMENSION
) -> ClapFeatureExtractor:
    """모델도 처리기도 가짜다. **여기서 보는 것은 청크 수와 모양이다.**"""
    transformers = ModuleType("transformers")

    class _Model:
        config = SimpleNamespace(projection_dim=DIMENSION)

        def to(self, device: str) -> _Model:
            return self

        def eval(self) -> _Model:
            return self

        def get_audio_features(self, **inputs: Any) -> _FakeOutput:
            seen.append(int(inputs["input_features"].data.shape[0]))
            # 은닉 상태는 **미끼다.** 이것을 집어 쌓은 것이 6GB였다 (D-0233).
            return _FakeOutput(
                np.ones((1, dimension), dtype=np.float32),
                np.zeros((1, 768, 2, 32), dtype=np.float32),
            )

    transformers.ClapModel = SimpleNamespace(from_pretrained=lambda name: _Model())  # type: ignore[attr-defined]
    # **가짜의 서명이 실물과 같아야 한다** (D-0232). 첫 판은 `audios`를 받게 만들어
    # 놓고 그 이름으로 불렀고, 시험은 초록이었는데 1004곡이 전부 떨어졌다.
    transformers.AutoProcessor = SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda name: (
            lambda audio, sampling_rate, return_tensors: {
                "input_features": _FakeTensor(np.asarray(audio).reshape(1, -1))
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


def test_처리기_인자_이름을_실물에서_확인한다() -> None:
    """**D-0232의 강제자.** 가짜만 보면 내가 틀린 이름으로 부른 것을 못 잡는다.

    `audios`는 transformers 5에서 죽었다. 깔린 판의 서명을 직접 읽어 우리가 쓰는 이름이
    거기 있는지 본다 — 상류가 또 바꾸면 **배치가 아니라 여기가 먼저 빨개진다.**
    """
    transformers = pytest.importorskip("transformers", reason="GPU 묶음에만 있다")
    import inspect

    from hathor.infrastructure import clap_feature_extractor as module

    names = set(inspect.signature(transformers.ClapProcessor.__call__).parameters)
    assert "audio" in names, f"처리기 인자가 바뀌었다: {sorted(names)}"
    wanted = set(inspect.signature(transformers.ClapModel.get_audio_features).parameters)
    assert "input_features" in wanted, f"모델 인자가 바뀌었다: {sorted(wanted)}"
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "audio=chunk" in source and "audios=" not in source


@requires_scipy
def test_은닉_상태가_아니라_임베딩을_쌓는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**D-0233의 강제자.** transformers 5는 텐서가 아니라 출력 객체를 낸다.

    `[0]`을 집으면 `last_hidden_state`(청크당 (768, 2, 32))가 쌓인다. 1004곡이 그 상태로
    **6GB**가 됐고, 배치는 초록으로 끝났다 — 아무도 모양을 안 봤기 때문이다.
    """
    extractor = _extractor(monkeypatch, [])
    found = extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32))
    assert found[MIXTURE_OUTPUT_KEY].shape == (3, DIMENSION), "은닉 상태를 쌓았다"


@requires_scipy
def test_모양이_다르면_첫_곡에서_죽는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """상류가 또 바꿔도 **70분과 6GB 뒤가 아니라 첫 곡에서** 안다."""
    extractor = _extractor(monkeypatch, [], dimension=7)
    with pytest.raises(ValueError, match="청크"):
        extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32))


def test_반환_모양을_실물에서_확인한다() -> None:
    """서명만으로는 부족했다 — **반환 타입이 바뀐 것**이 이번 결함이다 (D-0233).

    깔린 판이 무엇을 내는지 직접 만들어 보고, 우리가 그중 어느 자리를 집는지 확인한다.
    """
    pytest.importorskip("transformers", reason="GPU 묶음에만 있다")
    import inspect

    import torch
    from transformers import ClapModel
    from transformers.modeling_outputs import BaseModelOutputWithPooling

    annotation = str(inspect.signature(ClapModel.get_audio_features).return_annotation)
    assert "BaseModelOutputWithPooling" in annotation, f"반환이 바뀌었다: {annotation}"

    # `cast`는 스텁이 `FloatTensor`를 요구해서다. 실물이 내는 것은 그냥 텐서다.
    found = BaseModelOutputWithPooling(
        last_hidden_state=cast("Any", torch.zeros(1, 768, 2, 32)),
        pooler_output=cast("Any", torch.ones(1, DIMENSION)),
    )
    assert tuple(audio_vector(found).shape) == (1, DIMENSION)
    assert tuple(found[0].shape) != (1, DIMENSION), "`[0]`은 임베딩이 아니다"


def test_transformers_4의_텐서도_받는다() -> None:
    """4는 텐서를 그대로 냈다. 둘 다 받아야 판을 내려도 안 죽는다."""
    tensor = _FakeTensor(np.ones((1, DIMENSION), dtype=np.float32))
    assert audio_vector(tensor) is tensor
