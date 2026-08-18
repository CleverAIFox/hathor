"""BGE-M3 가사 인코더 테스트. **모델도 torch도 내려받지 않는다.**

토크나이저·모델·torch를 가짜로 주입하되 **`extract` 본체는 실제 코드가 돈다.**
가짜를 상속으로 덮으면 테스트가 테스트 자신을 검증하게 되므로 그렇게 하지 않는다.

여기서 고정하는 것은 둘이다. **배치 경계가 결과를 바꾸지 않는가**와
**결정론 검사가 편차를 잡는가.** 둘 다 어긋나면 1003곡 산출물이 통째로 버려진다.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np
import pytest

from hathor.infrastructure.bge_m3_lyrics_encoder import (
    MAX_TOKENS,
    POOL_CLS,
    POOL_MEAN,
    BgeM3LyricsEncoder,
    verify_deterministic,
)

DIM = 8


class _Tensor:
    """평균 풀링 경로가 쓰는 텐서 연산까지 흉내낸다.

    `unsqueeze` · `sum(dim=)` · `clamp` · 원소곱 · 나눗셈을 지원해야
    **평균 풀링 본체가 실제로 돌아간다.** 지원하지 않으면 그 경로는
    테스트를 통과해도 검증된 것이 아니다.
    """

    def __init__(self, array: np.ndarray) -> None:
        self.array = array

    @property
    def dtype(self) -> object:
        return self.array.dtype

    def to(self, _device_or_dtype: object) -> "_Tensor":
        return self

    def float(self) -> "_Tensor":
        return _Tensor(self.array.astype(np.float32))

    def cpu(self) -> "_Tensor":
        return self

    def numpy(self) -> np.ndarray:
        return self.array

    def unsqueeze(self, axis: int) -> "_Tensor":
        return _Tensor(np.expand_dims(self.array, axis))

    def sum(self, dim: int | None = None) -> "_Tensor":
        return _Tensor(self.array.sum(axis=dim) if dim is not None else self.array.sum())

    def clamp(self, *, min: float) -> "_Tensor":
        return _Tensor(np.clip(self.array, min, None))

    def __mul__(self, other: "_Tensor") -> "_Tensor":
        return _Tensor(self.array * other.array)

    def __truediv__(self, other: "_Tensor") -> "_Tensor":
        return _Tensor(self.array / other.array)

    def __getitem__(self, key: object) -> "_Tensor":
        return _Tensor(self.array[key])

    def __iter__(self):
        return iter(self.array)


def _fake_tokenizer(batch, *, padding, truncation, max_length, return_tensors):
    """토큰 수를 문자 수로 삼고 배치 최대 길이에 패딩한다. 실제 토크나이저의
    패딩 동작을 흉내내야 배치 경계 문제가 드러난다."""
    lengths = [min(len(text), max_length) for text in batch]
    width = max(lengths)
    ids = np.zeros((len(batch), width), dtype=np.int64)
    mask = np.zeros((len(batch), width), dtype=np.int64)
    for row, (text, length) in enumerate(zip(batch, lengths, strict=True)):
        ids[row, :length] = [ord(ch) % 1000 for ch in text[:length]]
        mask[row, :length] = 1
    return {"input_ids": _Tensor(ids), "attention_mask": _Tensor(mask)}


def _make_model(*, jitter: float = 0.0):
    """토큰마다 다른 은닉값을 낸다. **패딩 칸에 큰 값을 넣는다.**

    패딩에 0을 넣으면 마스크를 빼먹어도 평균이 대충 맞아 버그가 숨는다.
    큰 값을 넣어야 마스크 누락이 즉시 드러난다.
    """
    state = {"calls": 0}
    padding_value = 1000.0

    def forward(*, input_ids, attention_mask):
        ids = input_ids.array
        mask = attention_mask.array
        rows, cols = ids.shape
        hidden = np.full((rows, cols, DIM), padding_value, dtype=np.float32)
        for row in range(rows):
            content = ids[row][mask[row] == 1]
            # CLS 자리(0번)에는 구간 전체를 대표하는 값, 나머지는 토큰별 값
            hidden[row, 0] = float(content.sum() % 97)
            for col in range(1, cols):
                if mask[row, col]:
                    hidden[row, col] = float(ids[row, col] % 13)
        state["calls"] += 1
        hidden[:, 0] += jitter * state["calls"]
        return SimpleNamespace(last_hidden_state=_Tensor(hidden))

    return SimpleNamespace(
        __call__=forward, config=SimpleNamespace(hidden_size=DIM), _forward=forward
    )


def _encoder(
    *, batch_size: int = 2, jitter: float = 0.0, pooling: str = POOL_CLS
) -> BgeM3LyricsEncoder:
    """`__init__`을 건너뛰고 의존만 채운다. 모델 적재 없이 실제 extract를 돌린다."""
    encoder = object.__new__(BgeM3LyricsEncoder)
    model = _make_model(jitter=jitter)
    encoder._tokenizer = _fake_tokenizer
    encoder._model = _Callable(model._forward, model.config)
    encoder._device = "cpu"
    encoder._batch_size = batch_size
    encoder._pooling = pooling
    encoder._torch = SimpleNamespace(no_grad=_no_grad)
    encoder.truncated = 0
    return encoder


class _Callable:
    def __init__(self, forward, config) -> None:
        self._forward = forward
        self.config = config

    def __call__(self, **kwargs):
        return self._forward(**kwargs)


@contextmanager
def _no_grad():
    yield


def test_empty_segments_give_empty_matrix():
    """구간이 없어도 형상이 맞아야 한다. 저장소가 npz에 그대로 담는다."""
    result = _encoder().extract([])
    assert result.shape == (0, DIM)
    assert result.dtype == np.float32


def test_batch_boundary_does_not_change_result():
    """배치 크기를 바꿔도 같은 벡터가 나와야 한다.

    패딩이 마스크로 배제되지 않으면 배치 구성에 따라 값이 흔들린다.
    그 경우 `--batch-size`만 바꿔도 산출물이 달라져 재현성이 깨진다.
    길이가 제각각인 구간을 써야 패딩 폭이 배치마다 달라져 문제가 드러난다.
    """
    segments = ["짧다", "조금 더 긴 구간이다", "a", "훨씬 훨씬 더 긴 구간을 넣는다 길게", "mid len"]
    one = _encoder(batch_size=1).extract(segments)
    two = _encoder(batch_size=2).extract(segments)
    whole = _encoder(batch_size=99).extract(segments)
    assert np.array_equal(one, two)
    assert np.array_equal(one, whole)


def test_every_segment_gets_a_row_in_order():
    segments = [f"구간 {index}" for index in range(7)]
    result = _encoder(batch_size=3).extract(segments)
    assert result.shape == (7, DIM)
    single = _encoder(batch_size=1).extract(segments)
    assert np.array_equal(result, single)


def test_truncation_is_counted():
    """잘림은 조용히 정보를 버린다. 세지 않으면 드러나지 않는다."""
    encoder = _encoder(batch_size=1)
    encoder.extract(["짧다", "가" * (MAX_TOKENS + 50)])
    assert encoder.truncated == 1


def test_padding_is_not_counted_as_truncation():
    """긴 구간 하나가 배치에 섞여도 나머지가 잘린 것으로 잡히면 안 된다.

    `padding=True`는 배치 안 최대 길이에 모두를 맞춘다. 토큰 **길이**로 세면
    그 배치 전체가 잘린 것으로 보고된다. 실제로 겪은 오계수이며, 마스크 합으로
    세야 한다. 잘못 세면 "구간이 잘리고 있다"는 잘못된 신호로 설계를 바꾸게 된다.
    """
    encoder = _encoder(batch_size=4)
    encoder.extract(["짧다", "가" * (MAX_TOKENS + 50), "b", "조금 긴 구간"])
    assert encoder.truncated == 1


def test_verify_deterministic_reports_zero_when_stable():
    assert verify_deterministic(_encoder(), ["가", "na", "혼재 mix"]) == 0.0


def test_verify_deterministic_catches_drift():
    """비결정적 커널을 흉내낸다. 0이 아니면 추출 전에 잡혀야 한다."""
    drift = verify_deterministic(_encoder(jitter=0.25), ["가", "na"])
    assert drift == pytest.approx(0.25)


def test_verify_deterministic_rejects_shape_change():
    class _Unstable:
        def __init__(self) -> None:
            self.calls = 0

        def extract(self, segments):
            self.calls += 1
            return np.zeros((self.calls, DIM), dtype=np.float32)

    with pytest.raises(ValueError):
        verify_deterministic(_Unstable(), ["가"])


# --- 평균 풀링 (D-0046) ---


def test_mean_pooling_excludes_padding():
    """패딩이 평균에 섞이면 배치 구성마다 값이 달라진다.

    가짜 모델은 패딩 칸에 1000을 넣는다. 마스크를 빼먹으면 그 값이 평균을
    끌어올려 배치 크기에 따라 결과가 갈린다. **`--batch-size`만 바꿔도 산출물이
    변하는 상태이며, 재현성이 조용히 깨진다.**
    """
    segments = ["짧다", "훨씬 훨씬 더 긴 구간을 넣는다 아주 길게", "a"]
    one = _encoder(batch_size=1, pooling=POOL_MEAN).extract(segments)
    three = _encoder(batch_size=3, pooling=POOL_MEAN).extract(segments)
    assert np.array_equal(one, three)
    assert float(one.max()) < 1000.0


def test_mean_and_cls_differ():
    """두 풀링이 같은 값을 내면 선택이 무의미하다. 실제로 다른 것을 읽는지 본다."""
    segments = ["가사 구간 하나", "another segment here"]
    cls = _encoder(pooling=POOL_CLS).extract(segments)
    mean = _encoder(pooling=POOL_MEAN).extract(segments)
    assert not np.array_equal(cls, mean)


def test_mean_pooling_is_deterministic():
    assert verify_deterministic(_encoder(pooling=POOL_MEAN), ["가", "na", "혼재 mix"]) == 0.0


def test_unknown_pooling_is_rejected_before_model_load():
    """오타를 모델 적재 **전에** 잡는다.

    검증이 뒤에 있으면 2.3GB를 받고 GPU에 올린 뒤에야 터진다. CLI가 choices로
    막지만 라이브러리로 직접 쓸 때는 여기가 유일한 방어선이다.
    """
    with pytest.raises(ValueError, match="pooling"):
        BgeM3LyricsEncoder(pooling="nonsense", device="cpu")
