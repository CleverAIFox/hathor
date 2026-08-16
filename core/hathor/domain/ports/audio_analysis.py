"""오디오 분석 포트. 구현은 infrastructure가 담당한다 (DIP).

D-0021에 따라 디코더 출력은 24kHz 모노 float32이며 정규화하지 않는다.
정규화는 MERT 특징 추출기가 담당한다. 취향 벡터는 곡 간 비교가 목적이므로
마스터링 볼륨이 벡터에 섞이면 안 된다.

세 포트를 나눈 이유는 실행 환경이 다르기 때문이다. 디코딩은 CPU에서
돌지만 스템 분리와 특징 추출은 GPU가 필요하다. 포트로 갈라두면
GPU가 없는 기계에서도 테스트가 돈다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

type Waveform = np.ndarray[tuple[int], np.dtype[np.float32]]
"""모노 float32 파형. 정규화하지 않은 원본 샘플이다."""

type StereoWaveform = np.ndarray[tuple[int, int], np.dtype[np.float32]]
"""(채널, 샘플) 44.1kHz 스테레오 float32. Demucs 입력 규격이다."""

type Embedding = np.ndarray[tuple[int, int], np.dtype[np.float32]]
"""(청크 수, 특징 차원) 임베딩. MERT-v1-95M은 768차원이다."""

# Demucs는 44.1kHz 스테레오, MERT는 24kHz 모노를 기대한다.
# 디코더는 원본에 가까운 전자를 내고 MERT용은 파생시킨다 (D-0021 정정).
SOURCE_SAMPLE_RATE = 44100
FEATURE_SAMPLE_RATE = 24000
CHUNK_SECONDS = 10


class AudioDecoder(Protocol):
    """음원 파일을 분석용 파형으로 디코딩한다.

    반환은 44.1kHz 스테레오 float32다. 원본에 가장 가까운 형태이며
    MERT용 24kHz 모노는 여기서 파생시킨다.

    mp3 인터샘플 피크로 값이 ±1을 넘을 수 있으며 디코더는 보정하지 않는다.
    실측 최대 1.12. 스템을 파일로 저장하면 잘리지만 특징만 뽑고 버리므로
    float32 그대로 다루면 문제가 없다.
    """

    def decode(self, path: Path) -> StereoWaveform: ...


class StemSeparator(Protocol):
    """파형을 악기별 스템으로 분리한다 (Demucs).

    D-0018 실측: peak VRAM 549MB이며 세그먼트 처리라 곡 길이와 무관하다.
    19~21배속, 64.1시간 코퍼스 기준 배치 약 3.4시간.

    디코더가 정규화하지 않으므로 입력이 ±1을 넘을 수 있다.
    클리핑 여부는 구현체가 확인한다.
    """

    def separate(self, waveform: StereoWaveform) -> dict[str, StereoWaveform]: ...


class FeatureExtractor(Protocol):
    """파형에서 시간축 임베딩을 뽑는다 (MERT).

    D-0018 실측: 전곡 단위 추론은 불가능하다. 408초 곡이 8062MB로 물리
    VRAM을 초과해 통합 메모리로 넘어가며 449초가 걸린다.
    10초 청크 분할이 요구사항이며 선택 사항이 아니다.
    청크 10초에서 peak VRAM 557MB, 408초 곡 순수 추론 3.39초다.

    입력은 44.1kHz 스테레오다. 24kHz 모노 파생은 구현체가 담당한다.
    디코더 출력과 Demucs 스템이 같은 규격이므로 양쪽을 그대로 받는다.

    구현체는 모델의 특징 추출기를 반드시 거쳐야 한다 (D-0021).
    건너뛰면 마스터링 볼륨이 벡터에 섞인다.
    청크가 10초보다 짧으면 패딩이 들어가므로 어텐션 마스크를 적용해
    평균해야 한다. 그러지 않으면 패딩 구간이 벡터를 오염시킨다.
    """

    def extract(self, waveform: StereoWaveform) -> Embedding: ...
