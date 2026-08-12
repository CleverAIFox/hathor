"""Demucs 기반 스템 분리. StemSeparator 포트의 구현이다.

D-0018 실측: peak VRAM 549MB, 세그먼트 처리라 곡 길이와 무관하다.
19~21배속이며 64.1시간 코퍼스 기준 배치 약 3.4시간.

입력은 44.1kHz 스테레오다 (D-0021). 정규화하지 않으므로 값이 ±1을
넘을 수 있고 출력도 마찬가지다. 실측 스템 최대 1.28.
파일로 저장하지 않고 특징만 뽑으므로 float32로 다루는 한 문제가 없다.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hathor.domain.ports.audio_analysis import StereoWaveform

DEFAULT_MODEL = "htdemucs"
DEFAULT_DEVICE = "cuda"


class DemucsStemSeparator:
    """모델을 한 번 적재하고 재사용한다.

    1004곡 배치에서 곡마다 적재하면 8초씩 1004번을 버린다.

    torch와 demucs는 메서드 안에서 임포트한다. GPU가 없는 기계에서
    이 모듈을 임포트만 해도 2GB 라이브러리를 요구하면 안 된다.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = DEFAULT_DEVICE) -> None:
        from demucs.pretrained import get_model

        self._model: Any = get_model(model_name)
        self._model.eval()
        self._device = device
        self._sources: tuple[str, ...] = tuple(self._model.sources)

    @property
    def sources(self) -> tuple[str, ...]:
        """스템 이름. htdemucs는 drums / bass / other / vocals다."""
        return self._sources

    def separate(self, waveform: StereoWaveform) -> dict[str, StereoWaveform]:
        import torch
        from demucs.apply import apply_model

        tensor = torch.from_numpy(np.ascontiguousarray(waveform))[None]
        with torch.no_grad():
            stems = apply_model(self._model, tensor, device=self._device)
        return {
            name: np.asarray(stems[0, index].cpu().numpy(), dtype=np.float32)
            for index, name in enumerate(self._sources)
        }
