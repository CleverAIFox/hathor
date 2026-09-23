"""CLAP 기반 특징 추출 — 상업 가능한 취향 축 후보 (O-68 · D-0231).

### 왜 또 하나인가

검색 M1 20.4배(D-0027)와 화성 `layer03`(D-0181)이 **`m-a-p/MERT-v1-95M` 위에 서 있고 그것은
CC-BY-NC-4.0이다.** 제품 경로에 못 간다 (D-0217 · O-68). LAION CLAP(`larger_clap_music`)은
Apache-2.0이고 **같은 하네스로 잴 수 있다** — 같은 1004곡 · 같은 분할이라 비교가 이미 선다.

### MERT와 다른 것은 셋

| | MERT | CLAP |
|---|---|---|
| 입력 | 24kHz 모노 | **48kHz 모노** |
| 뽑는 것 | 은닉 레이어(마지막 = `mixture`) | **오디오 임베딩 하나** (텍스트와 같은 공간) |
| 차원 | 768 | 512 |

**10초 청크는 그대로다** (D-0018). 곡 하나가 (청크 수, 512)로 쌓이고 `NpzFeatureStore`가 키를
그대로 쓰므로 `eval retrieval --keys clap:mixture`가 바로 읽는다.

### 스템을 안 만든다

D-0024가 스템이 검색에 기여하지 않음을 확정했다. 혼합 하나만 뽑아 **배치가 1시간 안팎**이다.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hathor.domain.ports.audio_analysis import (
    CHUNK_SECONDS,
    SOURCE_SAMPLE_RATE,
    Embedding,
    StereoWaveform,
    Waveform,
)

DEFAULT_MODEL = "laion/larger_clap_music"
DEFAULT_DEVICE = "cuda"
CLAP_SAMPLE_RATE = 48000
"""CLAP의 입력 규격. **포트의 24kHz와 다르다** — 여기서만 쓰는 값이라 포트에 넣지 않는다."""

CHUNK_SAMPLES = CHUNK_SECONDS * CLAP_SAMPLE_RATE
MIN_CHUNK_SAMPLES = CLAP_SAMPLE_RATE
MIXTURE_OUTPUT_KEY = "mixture"


def to_clap_waveform(stereo: StereoWaveform) -> Waveform:
    """44.1kHz 스테레오를 48kHz 모노로. 다운믹스는 산술 평균이다 (D-0021과 같은 규칙)."""
    from scipy.signal import resample_poly

    mono = stereo.mean(axis=0) if stereo.ndim > 1 else stereo
    resampled = resample_poly(mono, CLAP_SAMPLE_RATE, SOURCE_SAMPLE_RATE)
    return np.asarray(resampled, dtype=np.float32)


def split_chunks(waveform: Waveform) -> list[Waveform]:
    """10초 단위. 1초 미만 자투리는 버린다 — 패딩 비율이 커져 벡터가 왜곡된다."""
    chunks = [
        waveform[start : start + CHUNK_SAMPLES] for start in range(0, len(waveform), CHUNK_SAMPLES)
    ]
    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_SAMPLES]


class ClapFeatureExtractor:
    """모델과 처리기를 한 번 적재하고 재사용한다.

    `extract_layers`를 두어 `LayeredFeatureExtractor` 포트를 만족시킨다 — 레이어를 안 뽑지만
    **`ExtractLayerFeatures`를 그대로 쓰기 위해서**다. 유스케이스를 새로 짜면 두 벌이 된다.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = DEFAULT_DEVICE) -> None:
        from transformers import AutoProcessor, ClapModel

        # MERT와 같은 모양이다 — 먼저 받고 나서 옮긴다. 이어 붙이면 타입이 `Any`를 벗어난다.
        model: Any = ClapModel.from_pretrained(model_name)
        self._model: Any = model.to(device).eval()
        self._processor: Any = AutoProcessor.from_pretrained(model_name)  # type: ignore[no-untyped-call]
        self._device = device

    @property
    def layers(self) -> tuple[int, ...]:
        """레이어를 안 뽑는다. 포트가 묻는 자리라 비워 둔다."""
        return ()

    @property
    def dimension(self) -> int:
        return int(self._model.config.projection_dim)

    def extract(self, waveform: StereoWaveform) -> Embedding:
        return self.extract_layers(waveform)[MIXTURE_OUTPUT_KEY]

    def extract_layers(self, waveform: StereoWaveform) -> dict[str, Embedding]:
        """(청크 수, 512). **곡이 1초 미만이면 빈 배열이다** — MERT와 같은 약속이다."""
        import torch

        chunks = split_chunks(to_clap_waveform(waveform))
        if not chunks:
            return {MIXTURE_OUTPUT_KEY: np.zeros((0, self.dimension), dtype=np.float32)}

        vectors: list[Any] = []
        with torch.no_grad():
            for chunk in chunks:
                inputs = self._processor(
                    audios=chunk, sampling_rate=CLAP_SAMPLE_RATE, return_tensors="pt"
                )
                moved = {key: value.to(self._device) for key, value in inputs.items()}
                vectors.append(self._model.get_audio_features(**moved)[0])
        stacked = torch.stack(vectors).cpu().numpy()
        return {MIXTURE_OUTPUT_KEY: np.asarray(stacked, dtype=np.float32)}
