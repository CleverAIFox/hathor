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
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = DEFAULT_DEVICE) -> None:
        from transformers import AutoFeatureExtractor, AutoModel

        self._model: Any = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self._model = self._model.to(device).eval()
        self._processor: Any = AutoFeatureExtractor.from_pretrained(  # type: ignore[no-untyped-call]
            model_name, trust_remote_code=True
        )
        self._device = device

    def extract(self, waveform: Waveform) -> Embedding:
        import torch

        chunks = split_chunks(waveform)
        if not chunks:
            return np.zeros((0, self._model.config.hidden_size), dtype=np.float32)

        vectors: list[Any] = []
        with torch.no_grad():
            for chunk in chunks:
                inputs = self._processor(
                    chunk,
                    sampling_rate=FEATURE_SAMPLE_RATE,
                    return_tensors="pt",
                    return_attention_mask=True,
                )
                values = inputs["input_values"].to(self._device)
                hidden = self._model(values).last_hidden_state[0]
                vectors.append(self._masked_mean(hidden, inputs.get("attention_mask")))
        stacked = torch.stack(vectors).cpu().numpy()
        return np.asarray(stacked, dtype=np.float32)

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
