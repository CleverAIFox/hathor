"""MusicFM 특징 추출 (O-68 · D-0248 · D-0413).

모델은 **가짜로 세운다** — 가중치를 받아야 도는 시험은 아무도 안 돌린다 (D-0061).
그리고 이 모델은 **pip로 안 깔려** 클론까지 해야 하므로 더 그렇다.

### 실물로는 한 번도 안 돌았다

가중치가 Hugging Face에 있고 **쓰는 쪽 컨테이너가 거기 못 나간다.** 그래서 이 파일이
보는 것은 **모양과 배선**이고, 실물 첫 실행은 그의 기기다 (D-0015 · D-0413).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import CHUNK_SECONDS, SOURCE_SAMPLE_RATE

# **키는 MERT 것을 그대로 쓴다** (D-0043) — 들여온 이름을 다시 내보내지 않으므로
# 시험도 **원래 자리에서** 가져온다.
from hathor.infrastructure.mert_feature_extractor import MIXTURE_OUTPUT_KEY
from hathor.infrastructure.musicfm_feature_extractor import (
    DEFAULT_CHECKPOINT,
    MUSICFM_COMMIT,
    MUSICFM_DIMENSION,
    MUSICFM_LAYERS,
    MUSICFM_SAMPLE_RATE,
    MusicFmFeatureExtractor,
    read_stats,
)

requires_scipy = pytest.mark.skipif(
    importlib.util.find_spec("scipy") is None,
    reason="리샘플러가 scipy에 의존한다. GPU 묶음 없는 기기에서는 건너뛴다",
)

FRAMES = 250
"""25Hz × 10초. 가짜가 내는 프레임 수이고 **평균이 그 축을 먹는다.**"""


class _FakeTensor:
    def __init__(self, data: np.ndarray) -> None:
        self.data = data

    def to(self, device: str) -> _FakeTensor:
        return self

    def cpu(self) -> _FakeTensor:
        return self

    def numpy(self) -> np.ndarray:
        return self.data

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(self.data.shape)

    def mean(self, dim: int) -> _FakeTensor:
        return _FakeTensor(self.data.mean(axis=dim))

    def __getitem__(self, index: Any) -> _FakeTensor:
        return _FakeTensor(self.data[index])


def _fake_torch() -> ModuleType:
    torch = ModuleType("torch")

    class _NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    class Tensor:
        """**실물에 있으니 가짜에도 있어야 한다** (D-0276 — `scipy`가 들여다본다)."""

    torch.Tensor = Tensor  # type: ignore[attr-defined]
    torch.no_grad = _NoGrad  # type: ignore[attr-defined]
    torch.from_numpy = lambda data: _FakeTensor(np.asarray(data))  # type: ignore[attr-defined]
    torch.stack = lambda values: _FakeTensor(  # type: ignore[attr-defined]
        np.stack([value.data for value in values])
    )
    return torch


def _clone(root: Path) -> Path:
    """클론한 모양만 흉내 낸다 — `_home`이 **파일 하나로 자리를 확인**한다."""
    model = root / "musicfm" / "model"
    model.mkdir(parents=True, exist_ok=True)
    (model / "musicfm_25hz.py").write_text("# 가짜\n", encoding="utf-8")
    data = root / "musicfm" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "fma_stats.json").write_text('{"mean": 0.0, "std": 1.0}', encoding="utf-8")
    # **가중치도 있어야 한다** (D-0414). 첫 실물 실행에서 1.22GB가 절반에서 끊겼고,
    # 그 뒤로 **모델을 올리기 전에** 파일 둘을 본다.
    (data / "pretrained_fma.pt").write_bytes(b"\x00")
    return root


def _extractor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    seen: list[int],
    *,
    layers: tuple[int, ...] = (),
    depth: int = MUSICFM_LAYERS,
    dimension: int = MUSICFM_DIMENSION,
) -> MusicFmFeatureExtractor:
    """**가짜를 심기 전에 게으른 임포트를 데운다** (D-0276).

    `to_feature_waveform`이 함수 안에서 `scipy`를 들이는데, 그것이 **가짜 `torch`가
    심긴 동안** 일어나면 `scipy`가 `sys.modules["torch"]`를 보다 죽는다.
    """
    if importlib.util.find_spec("scipy") is not None:
        import scipy.signal  # noqa: F401  데우기 전용

    class _Layer:
        """컨포머 층 하나. **훅이 걸리는 자리**이고 그것이 이 가짜의 전부다."""

        def __init__(self) -> None:
            self._hooks: list[Any] = []

        def register_forward_pre_hook(self, hook: Any) -> Any:
            self._hooks.append(hook)
            return SimpleNamespace(remove=lambda: self._hooks.remove(hook))

        def fire(self, given: _FakeTensor) -> None:
            for hook in list(self._hooks):
                hook(self, (given,))

        @property
        def hooked(self) -> int:
            return len(self._hooks)

    class _Conformer:
        def __init__(self) -> None:
            self.layers = [_Layer() for _ in range(depth - 1)]

        def __call__(self, entering: _FakeTensor) -> dict[str, _FakeTensor]:
            # **프레임마다 값을 흔든다** (D-0400 · D-0413). 층 번호로 꽉 채웠더니
            # *«평균 대신 첫 프레임을 쓴다»*는 변이가 **안 물렸다** — 가짜가 그 축을
            # 안 보면 그 축의 배선이 안 보인다. 0을 중심으로 대칭이라 **평균은
            # 정확히 층 번호**이고 첫 프레임은 아니다.
            swing = np.linspace(-1.0, 1.0, FRAMES, dtype=np.float32)[None, :, None]
            for index, layer in enumerate(self.layers):
                layer.fire(
                    _FakeTensor(
                        np.full((1, FRAMES, dimension), float(index), dtype=np.float32) + swing
                    )
                )
            last = np.full((1, FRAMES, dimension), float(depth - 1), dtype=np.float32) + swing
            return {"last_hidden_state": _FakeTensor(last)}

    class _Model:
        def __init__(self) -> None:
            self.conformer = _Conformer()

        def to(self, device: str) -> _Model:
            return self

        def eval(self) -> _Model:
            return self

        def preprocessing(self, values: _FakeTensor, features: list[str]) -> dict[str, Any]:
            # **가짜가 인자를 본다** (D-0400). 안 보면 청크 배선이 끊겨도 안 운다.
            seen.append(int(values.shape[-1]))
            return {one: values for one in features}

        def normalize(self, given: dict[str, Any]) -> dict[str, Any]:
            return given

        def conv(self, given: _FakeTensor) -> _FakeTensor:
            return given

    package = ModuleType("musicfm")
    package.__path__ = []  # type: ignore[attr-defined]
    inner = ModuleType("musicfm.model")
    inner.__path__ = []  # type: ignore[attr-defined]
    leaf = ModuleType("musicfm.model.musicfm_25hz")
    leaf.MusicFM25Hz = lambda **kwargs: _Model()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "musicfm", package)
    monkeypatch.setitem(sys.modules, "musicfm.model", inner)
    monkeypatch.setitem(sys.modules, "musicfm.model.musicfm_25hz", leaf)
    monkeypatch.setitem(sys.modules, "torch", _fake_torch())
    return MusicFmFeatureExtractor(home=_clone(tmp_path), device="cpu", layers=layers)


def test_입력_규격이_MERT와_같다() -> None:
    """**24kHz를 두 벌로 안 만든다** (D-0043). 값이 갈리면 임베딩이 조용히 나빠진다."""
    from hathor.infrastructure.mert_feature_extractor import CHUNK_SAMPLES

    assert MUSICFM_SAMPLE_RATE == 24000
    assert CHUNK_SAMPLES == CHUNK_SECONDS * MUSICFM_SAMPLE_RATE


def test_코드가_없으면_무엇을_할지_말한다(tmp_path: Path) -> None:
    """**「임포트 실패」만 던지면 사람이 pip를 친다** — 이 모델은 pip로 안 깔린다."""
    with pytest.raises(ValueError, match="pip로 안 깔린다"):
        MusicFmFeatureExtractor(home=None)

    with pytest.raises(ValueError, match="부모"):
        MusicFmFeatureExtractor(home=tmp_path)


def test_가중치가_없으면_모델을_올리기_전에_죽는다(tmp_path: Path) -> None:
    """**받다 만 파일은 `torch.load`가 알아듣기 힘든 말로 죽는다** (D-0414).

    실물 첫 실행에서 1.22GB 받기가 절반에서 끊겼다(`curl: (92)`). 모델을 올린 뒤에
    죽으면 **무엇을 해야 하는지가 안 보인다** — 이어받기를 오류가 직접 적는다.
    """
    root = _clone(tmp_path)
    (root / "musicfm" / "data" / "pretrained_fma.pt").unlink()

    with pytest.raises(ValueError, match="curl -LC -"):
        MusicFmFeatureExtractor(home=root)


def test_들여온_코드의_의존성이_없으면_말해_준다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**우리가 안 부르는 의존성이라 시험이 초록이었다** (D-0414).

    저자 코드가 `torchaudio`를 들이는데 우리 코드는 그것을 안 쓴다. 가짜를 심은
    시험에서는 영원히 안 난다 — **실물 첫 실행에서야 났다.** 여기서 보는 것은
    **잡는 자리**이고, 무엇이 없었는지가 아니다.
    """
    root = _clone(tmp_path)
    # **잎을 안 심는다.** 그러면 `from musicfm.model.musicfm_25hz import …`가 실물과
    # 같은 `ModuleNotFoundError`로 떨어진다 — 실물에서는 그 안쪽의 `torchaudio`가
    # 없어서 났고, 여기서는 잎 자체가 없어서 난다. **잡는 자리는 같다.**
    package = ModuleType("musicfm")
    package.__path__ = []  # type: ignore[attr-defined]
    inner = ModuleType("musicfm.model")
    inner.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "musicfm", package)
    monkeypatch.setitem(sys.modules, "musicfm.model", inner)
    monkeypatch.delitem(sys.modules, "musicfm.model.musicfm_25hz", raising=False)

    with pytest.raises(ValueError, match="make sync"):
        MusicFmFeatureExtractor(home=root)


@requires_scipy
def test_청크마다_벡터_하나를_쌓는다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """25초면 10·10·5초 셋이다 (D-0018). **프레임 축은 평균이 먹는다.**"""
    seen: list[int] = []
    extractor = _extractor(monkeypatch, tmp_path, seen)

    found = extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32))

    assert len(seen) == 3, "청크마다 한 번씩 안 돌았다"
    assert found[MIXTURE_OUTPUT_KEY].shape == (3, MUSICFM_DIMENSION)


@requires_scipy
def test_층을_한_번의_forward에서_다_뽑는다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**저자의 `get_latent`은 층마다 다시 돈다** (D-0413).

    층 셋을 달라 해도 `get_predictions`는 **청크당 한 번**이어야 한다. 다시 돌면
    D-0025가 MERT에서 피한 13배가 그대로 돌아온다.
    """
    seen: list[int] = []
    extractor = _extractor(monkeypatch, tmp_path, seen, layers=(3, 7))

    found = extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32))

    assert len(seen) == 3, f"청크 3개에 forward가 {len(seen)}번이다"
    assert set(found) == {MIXTURE_OUTPUT_KEY, "layer03", "layer07"}


@requires_scipy
def test_혼합은_마지막_층이다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**MERT와 같은 약속이다.** 가짜가 층 번호를 값으로 내므로 바로 갈린다."""
    extractor = _extractor(monkeypatch, tmp_path, [], layers=(3,))

    found = extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 11), dtype=np.float32))

    # **실수 먼지를 받는다** — 가짜가 프레임을 흔들므로 평균이 정확히 안 떨어진다.
    assert float(found[MIXTURE_OUTPUT_KEY][0][0]) == pytest.approx(MUSICFM_LAYERS - 1, abs=1e-4)
    assert float(found["layer03"][0][0]) == pytest.approx(3.0, abs=1e-4)


def test_층_수가_다르면_올릴_때_죽는다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**조용히 다른 수를 쌓으면 MERT와 나란히 못 놓는데 산출물은 그럴듯하다** (D-0233).

    훅으로 모으므로 **모을 수가 컨포머 층 수로 정해진다** — 그래서 배치를 돌리기
    전에, 모델을 올리는 자리에서 본다 (D-0416).
    """
    with pytest.raises(ValueError, match="컨포머 층"):
        _extractor(monkeypatch, tmp_path, [], depth=7)


@requires_scipy
def test_훅을_청크마다_떼_둔다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**안 떼면 다음 청크에서 스물여섯이 쌓인다** (D-0416).

    그때 층 수 검사가 울기는 하지만, 그전에 **핸들이 샌다** — 1004곡이면 그 수가
    이십만을 넘는다. 돌고 나서 남은 훅이 0이어야 한다.
    """
    extractor = _extractor(monkeypatch, tmp_path, [])

    extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 25), dtype=np.float32))

    layers = extractor._model.conformer.layers  # 가짜의 속을 본다
    assert [one.hooked for one in layers] == [0] * len(layers)


@requires_scipy
def test_차원이_다르면_죽는다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """체크포인트를 바꾸면 여기서 먼저 죽는다 (CLAP과 같은 규율 · D-0233)."""
    extractor = _extractor(monkeypatch, tmp_path, [], dimension=768)

    with pytest.raises(ValueError, match="차원"):
        extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE * 11), dtype=np.float32))


@requires_scipy
def test_소리가_짧으면_빈_배열을_낸다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**1초 미만은 버린다** — 0곡이 아니라 **0청크**이고 모양은 유지한다 (GR-0.5)."""
    extractor = _extractor(monkeypatch, tmp_path, [], layers=(3,))

    found = extractor.extract_layers(np.zeros((2, SOURCE_SAMPLE_RATE // 2), dtype=np.float32))

    assert found[MIXTURE_OUTPUT_KEY].shape == (0, MUSICFM_DIMENSION)
    assert set(found) == {MIXTURE_OUTPUT_KEY, "layer03"}


def test_통계를_먼저_읽는다(tmp_path: Path) -> None:
    """**모델은 없으면 늦게 죽는다** — 배치 한 시간을 돌리고 나서 죽으면 늦다."""
    assert read_stats(_clone(tmp_path)) == {"mean": 0.0, "std": 1.0}

    with pytest.raises(OSError, match="No such file"):
        read_stats(tmp_path, stats="msd_stats.json")


def test_잰_커밋을_박아_둔다() -> None:
    """**클론은 버전이 안 박힌다** (D-0009). 산출물 설명이 이 값을 싣는다.

    저자가 *«2024-02-13 이전 체크포인트는 틀렸다»*라고 적었고, 박아 둔 커밋은
    **그 다음 날**이다.
    """
    assert len(MUSICFM_COMMIT) == 40
    assert DEFAULT_CHECKPOINT.endswith("_fma.pt"), "기본이 FMA 판이 아니다 (D-0413)"


def test_명령이_등재돼_있다() -> None:
    """**배선을 빼먹어도 초록이면 안 된다** (D-0273)."""
    from hathor.interfaces.cli import eval_musicfm

    assert [one.name for one in eval_musicfm.COMMANDS] == ["musicfm"]
    assert eval_musicfm.DIRNAME == "musicfm"


def test_라이선스_대장이_가중치를_미확인으로_든다() -> None:
    """**코드 라이선스를 가중치에 넘겨 「된다」고 적으면 그것이 추측이다** (D-0217).

    D-0248이 *«MusicFM은 MIT다»*로 제목까지 달았고 그것은 **코드** 얘기다. `LICENSE`는
    듀얼이며 가중치 라이선스는 어디에도 없다 (D-0413).
    """
    from tests.conftest import tool_module

    table = tool_module("check_model_licenses").LICENSES
    license_text, commercial, _why = table["minzwon/MusicFM"]

    assert commercial == "unknown"
    assert "가중치 미명시" in license_text
