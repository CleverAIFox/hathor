"""BGE-M3 기반 가사 구간 인코더. `LyricsEncoder` 포트의 구현이다.

### 왜 다국어 모델인가 (D-0045)

코퍼스 실측: 한글 문자 55.0% · 라틴 45.0%, **혼재 곡 40.0%**.
파이프라인은 **구간 단위**로 인코딩하므로 같은 곡의 절이 한국어, 후렴이 영어인
경우가 실제로 존재한다. **조각이 다른 언어면 문자 n-gram은 원리적으로 매칭이 0이다**
— 겹치는 문자열이 없다. 한국어 특화 모델도 이 40%에서 무너진다.

BGE-M3는 언어 간 정렬이 학습 목표라 이 구간을 같은 공간에 놓는다.

### 왜 e5가 아닌가

`multilingual-e5-large`는 `query:` / `passage:` 접두사를 요구하는 **비대칭** 모델이다.
**M0는 구간↔구간 대칭 비교**이므로 어느 쪽에 무엇을 붙일지가 자의적 선택이 되고,
그 선택이 결과에 섞인다. BGE-M3는 접두사가 없다.

### dense만 쓴다

BGE-M3는 sparse·ColBERT 출력도 낸다. **한 번에 하나만 바꾼다**(GR-6.5).
dense 1024차원은 기본·345·nospace·damp 조건과 차원이 같아 **인코더 효과만 분리된다.**

### 결정론

`torch.no_grad` + `eval` + 정렬된 입력 순서. 배치 경계가 결과를 바꾸지 않도록
**패딩을 마스크로 배제**한다. 재현 검사는 `verify_deterministic`이 한다 (D-0009).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hathor.domain.ports.audio_analysis import Embedding

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DEVICE = "cuda"
DEFAULT_BATCH = 16
MAX_TOKENS = 512
FEATURE_DIM = 1024
"""해시 조건과 같은 차원. 차원을 고정해야 인코더 효과만 남는다."""


class BgeM3LyricsEncoder:
    """모델을 한 번 적재하고 구간 목록을 배치로 인코딩한다.

    구간은 짧다(가사 한 절). 512토큰이면 잘리는 경우가 드물지만, 잘림이
    일어나면 조용히 정보가 사라지므로 `truncated` 카운터로 드러낸다.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = DEFAULT_DEVICE,
        batch_size: int = DEFAULT_BATCH,
        use_fp16: bool = True,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer: Any = AutoTokenizer.from_pretrained(model_name)
        model: Any = AutoModel.from_pretrained(model_name)
        if use_fp16 and device.startswith("cuda"):
            # 4.8GB 실가용에서 fp32 568M은 여유가 없다. 추론 전용이라 손실이 없다.
            model = model.half()
        self._model = model.to(device).eval()
        self._device = device
        self._batch_size = max(1, batch_size)
        self._torch = torch
        self.truncated = 0
        """512토큰을 넘어 잘린 구간 수. 0이 아니면 기록에 남긴다."""

    @property
    def dimension(self) -> int:
        return int(self._model.config.hidden_size)

    def extract(self, segments: list[str]) -> Embedding:
        """구간 목록을 (구간 수, 1024) 행렬로 만든다.

        BGE-M3의 dense 표현은 **CLS 토큰**이다. 평균 풀링이 아니다 —
        학습 목표가 CLS에 문장 표현을 모으도록 되어 있어, 평균을 쓰면
        모델이 최적화된 지점과 다른 곳을 읽게 된다.
        """
        if not segments:
            return np.zeros((0, self.dimension), dtype=np.float32)

        rows: list[Any] = []
        with self._torch.no_grad():
            for start in range(0, len(segments), self._batch_size):
                batch = segments[start : start + self._batch_size]
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                )
                # 길이가 아니라 **마스크 합**으로 센다. `padding=True`는 배치 안의
                # 가장 긴 것에 맞춰 모두를 늘리므로, 긴 구간 하나가 섞이면 길이
                # 기준으로는 그 배치 전체가 잘린 것으로 잡힌다. 실제 토큰 수는
                # 마스크가 1인 칸의 개수다.
                self.truncated += int(
                    sum(1 for row in encoded["attention_mask"] if int(row.sum()) >= MAX_TOKENS)
                )
                inputs = {key: value.to(self._device) for key, value in encoded.items()}
                output = self._model(**inputs)
                cls = output.last_hidden_state[:, 0]
                rows.append(cls.float().cpu().numpy())

        matrix = np.concatenate(rows, axis=0)
        return np.asarray(matrix, dtype=np.float32)


def verify_deterministic(encoder: BgeM3LyricsEncoder, segments: list[str]) -> float:
    """같은 입력을 두 번 인코딩해 최대 절대 편차를 낸다 (D-0009 재현성 계층 1).

    GPU fp16 추론은 커널 선택에 따라 비결정적일 수 있다. **0이 아니면 산출물이
    기기·실행마다 달라지므로 결정 기록에 남기고 대책을 세운다.** 조용히 넘어가면
    "2대 노트북 산출물이 바이트 단위로 같다"는 전제가 깨진 채 남는다.
    """
    first = encoder.extract(segments)
    second = encoder.extract(segments)
    if first.shape != second.shape:
        raise ValueError(f"형상이 다르다: {first.shape} vs {second.shape}")
    return float(np.max(np.abs(first - second))) if first.size else 0.0
