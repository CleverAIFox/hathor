"""가사 문자 n-gram 해싱 벡터. 가사축의 베이스라인이다.

MFCC가 오디오축에서 한 역할을 여기서 한다. **신경망 인코더를 붙이기 전에
값싼 기준선을 세운다.** 오디오축에서 MFCC가 MERT를 이겼던 일이 있으므로,
비싼 쪽이 나을 것이라는 가정을 두지 않는다.

### 문자 n-gram을 쓰는 이유

한국어는 교착어라 어미가 계속 붙는다(`사랑해`·`사랑했어`·`사랑하니까`).
띄어쓰기 단위로 자르면 이들이 전부 다른 항목이 되고, 형태소 분석기를 쓰면
의존성이 하나 늘고 그 성능이 결과에 섞인다. **문자 n-gram은 어미 변화를
자동으로 흡수하고 의존성이 0이다.**

### 해싱을 쓰는 이유

어휘 사전을 만들면 코퍼스 전체를 먼저 훑어야 하고, 곡이 추가될 때마다
차원이 변한다. 해싱은 차원을 고정하므로 곡 하나만 있어도 벡터가 나온다.
충돌이 생기지만 1024차원에 곡당 수백 n-gram이면 영향이 작다 **(실측 필요)**.

### IDF를 쓰지 않는 이유

흔한 조사·어미가 벡터를 지배하는 문제는 IDF로 푸는 것이 정석이다.
그러나 IDF는 코퍼스 통계라 곡이 추가되면 값이 변하고, 재현하려면 함께 저장해야 한다.
**같은 문제를 중심화(D-0030)가 이미 해결한다** — 모든 곡이 공유하는 성분을 빼는 것이
곧 흔한 항목의 가중치를 낮추는 것이다. 평가 하네스가 중심화를 기본으로 켜므로
여기서 IDF를 중복으로 넣지 않는다. **효과는 M1/M2로 판정한다.**
"""

from __future__ import annotations

import hashlib

import numpy as np

from hathor.domain.ports.audio_analysis import Embedding

FEATURE_DIM = 1024
NGRAM_SIZES = (2, 3, 4)
LYRICS_KEY = "lyrics"
EPSILON = 1e-12


def hash_index(token: str, dim: int = FEATURE_DIM) -> int:
    """n-gram을 차원 인덱스로. 파이썬 `hash`를 쓰지 않는다.

    내장 `hash`는 문자열에 대해 프로세스마다 시드가 달라(PYTHONHASHSEED)
    실행할 때마다 다른 벡터가 나온다. **재현성 계층 1을 조용히 깨뜨린다**(D-0009).
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dim


def char_ngrams(text: str, sizes: tuple[int, ...] = NGRAM_SIZES) -> list[str]:
    """공백을 하나로 줄인 뒤 문자 n-gram을 뽑는다.

    줄바꿈·연속 공백이 n-gram에 섞이면 같은 가사가 서식 차이로 달라진다.
    """
    normalized = " ".join(text.split())
    grams: list[str] = []
    for size in sizes:
        if len(normalized) < size:
            continue
        grams.extend(
            normalized[start : start + size] for start in range(len(normalized) - size + 1)
        )
    return grams


class HashedLyricsExtractor:
    """가사 구간 목록을 (구간, 차원) 행렬로 만든다.

    산출물 규격이 오디오 경로와 같으므로 **같은 저장소와 같은 평가 하네스가
    구분 없이 읽는다.** 가사축 전용 지표를 새로 만들 필요가 없다.
    """

    def __init__(self, dim: int = FEATURE_DIM, sizes: tuple[int, ...] = NGRAM_SIZES) -> None:
        self._dim = dim
        self._sizes = sizes

    @property
    def dim(self) -> int:
        return self._dim

    def extract(self, segments: list[str]) -> Embedding:
        if not segments:
            return np.zeros((0, self._dim), dtype=np.float32)
        rows = [self._vector(segment) for segment in segments]
        return np.asarray(np.stack(rows), dtype=np.float32)

    def _vector(self, segment: str) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
        counts = np.zeros(self._dim, dtype=np.float32)
        for gram in char_ngrams(segment, self._sizes):
            counts[hash_index(gram, self._dim)] += 1.0
        if not counts.any():
            return counts
        # 하위선형 스케일. 한 단어가 반복되는 후렴이 구간을 지배하는 것을 막는다.
        scaled = np.log1p(counts)
        return np.asarray(scaled / np.linalg.norm(scaled), dtype=np.float32)
