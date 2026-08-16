"""MERT 기반 특징 추출. FeatureExtractor 포트의 구현이다.

D-0018 실측: 전곡 단위 추론은 불가능하다. 408초 곡이 8062MB로 물리
VRAM을 초과해 통합 메모리로 넘어가며 449초가 걸린다. 10초 청크 분할은
요구사항이며 선택 사항이 아니다. 청크 10초에서 peak VRAM 557MB,
408초 곡 순수 추론 3.39초다.

입력은 44.1kHz 스테레오이며 여기서 24kHz 모노로 파생시킨다 (D-0021).
모델의 특징 추출기를 반드시 거친다. 건너뛰면 마스터링 볼륨이 벡터에
섞이고, 취향 벡터는 곡 간 비교가 목적이므로 그것은 원하는 신호가 아니다.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hathor.domain.ports.audio_analysis import (
    CHUNK_SECONDS,
    FEATURE_SAMPLE_RATE,
    SOURCE_SAMPLE_RATE,
    Embedding,
    StereoWaveform,
    Waveform,
)

DEFAULT_MODEL = "m-a-p/MERT-v1-95M"
DEFAULT_DEVICE = "cuda"
CHUNK_SAMPLES = CHUNK_SECONDS * FEATURE_SAMPLE_RATE
MIN_CHUNK_SAMPLES = FEATURE_SAMPLE_RATE
LAYER_KEY_PREFIX = "layer"
MIXTURE_OUTPUT_KEY = "mixture"


def layer_key(index: int) -> str:
    """레이어 임베딩의 npz 키. 0은 트랜스포머 블록 이전 특징이다."""
    return f"{LAYER_KEY_PREFIX}{index:02d}"


def to_feature_waveform(stereo: StereoWaveform) -> Waveform:
    """44.1kHz 스테레오를 24kHz 모노로 만든다.

    다운믹스는 산술 평균이다. ffmpeg 기본 -ac 1은 에너지 보존을 위해
    √2로 나누지만 특징 추출기가 분산을 맞추므로 계수는 무의미하다.
    명시적으로 두어 버전 변화에 흔들리지 않게 한다.
    """
    from scipy.signal import resample_poly

    mono = stereo.mean(axis=0) if stereo.ndim > 1 else stereo
    resampled = resample_poly(mono, FEATURE_SAMPLE_RATE, SOURCE_SAMPLE_RATE)
    return np.asarray(resampled, dtype=np.float32)


def split_chunks(waveform: Waveform) -> list[Waveform]:
    """10초 단위로 자른다. 1초 미만 자투리는 버린다.

    자투리 임베딩은 의미가 없고 패딩 비율이 커져 벡터를 왜곡한다.
    """
    chunks = [
        waveform[start : start + CHUNK_SAMPLES] for start in range(0, len(waveform), CHUNK_SAMPLES)
    ]
    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_SAMPLES]


class MertFeatureExtractor:
    """모델과 특징 추출기를 한 번 적재하고 재사용한다.

    청크를 하나씩 처리한다. 배치로 묶으면 짧은 청크에 패딩이 늘어
    마스크 처리가 복잡해지고 VRAM 이득도 크지 않다.

    `layers`를 주면 지정한 은닉 레이어들을 함께 낸다. 자기지도 음악·음성
    모델은 **마지막 레이어가 다운스트림 과제에서 가장 나쁜 경우가 흔하다.**
    사전학습 목표(마스킹 예측)에 특화되어 있기 때문이다 (D-0025, O-8).

    레이어별로 추출을 반복하지 않는다. 한 번의 forward에서 전 레이어가
    나오므로 필요한 것만 골라 담으면 되고, 반복하면 13배 시간이 든다.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = DEFAULT_DEVICE,
        layers: tuple[int, ...] = (),
    ) -> None:
        from transformers import AutoFeatureExtractor, AutoModel

        self._model: Any = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self._model = self._model.to(device).eval()
        self._processor: Any = AutoFeatureExtractor.from_pretrained(  # type: ignore[no-untyped-call]
            model_name, trust_remote_code=True
        )
        self._device = device
        self._layers = tuple(sorted(set(layers)))

    @property
    def layers(self) -> tuple[int, ...]:
        return self._layers

    @property
    def layer_count(self) -> int:
        """임베딩 출력을 포함한 은닉 상태 개수. 95M은 13(=1+12)이다."""
        return int(self._model.config.num_hidden_layers) + 1

    def extract(self, waveform: StereoWaveform) -> Embedding:
        """기본 경로. `last_hidden_state` 하나만 낸다 (기존 산출물과 동일)."""
        return self.extract_layers(waveform)[MIXTURE_OUTPUT_KEY]

    def extract_layers(self, waveform: StereoWaveform) -> dict[str, Embedding]:
        """혼합 임베딩과 선택한 레이어 임베딩을 함께 낸다.

        반환 키는 `mixture`(마지막 레이어)와 `layerNN`이다. 저장소가 키를
        그대로 npz에 담으므로 평가 하네스가 `--keys layer06`으로 읽는다.
        """
        import torch

        chunks = split_chunks(to_feature_waveform(waveform))
        wanted = (MIXTURE_OUTPUT_KEY, *(layer_key(index) for index in self._layers))
        if not chunks:
            empty = np.zeros((0, self._model.config.hidden_size), dtype=np.float32)
            return dict.fromkeys(wanted, empty)

        collected: dict[str, list[Any]] = {key: [] for key in wanted}
        with torch.no_grad():
            for chunk in chunks:
                inputs = self._processor(
                    chunk,
                    sampling_rate=FEATURE_SAMPLE_RATE,
                    return_tensors="pt",
                    return_attention_mask=True,
                )
                values = inputs["input_values"].to(self._device)
                mask = inputs.get("attention_mask")
                output = self._model(values, output_hidden_states=bool(self._layers))
                collected[MIXTURE_OUTPUT_KEY].append(
                    self._masked_mean(output.last_hidden_state[0], mask)
                )
                for index in self._layers:
                    hidden = output.hidden_states[index][0]
                    collected[layer_key(index)].append(self._masked_mean(hidden, mask))
        return {
            key: np.asarray(torch.stack(values).cpu().numpy(), dtype=np.float32)
            for key, values in collected.items()
        }

    @staticmethod
    def _masked_mean(hidden: Any, attention_mask: Any) -> Any:
        """유효 구간만 평균한다.

        마스크 없이 평균하면 패딩 구간이 벡터를 오염시킨다 (D-0021).
        마지막 청크가 10초보다 짧을 때 실제로 발생한다.

        모델이 시간축을 다운샘플링하므로 마스크 길이와 은닉 상태 길이가
        다르다. 비율로 유효 프레임 수를 환산한다.
        """
        import torch

        frames = hidden.shape[0]
        if attention_mask is None:
            return hidden.mean(dim=0)

        mask = attention_mask[0]
        valid_ratio = float(mask.sum()) / float(len(mask))
        valid_frames = max(1, min(frames, round(frames * valid_ratio)))
        if valid_frames == frames:
            return hidden.mean(dim=0)
        return torch.mean(hidden[:valid_frames], dim=0)
