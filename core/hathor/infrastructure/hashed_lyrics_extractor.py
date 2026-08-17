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


def char_ngrams(
    text: str,
    sizes: tuple[int, ...] = NGRAM_SIZES,
    *,
    collapse_space: bool = False,
) -> list[str]:
    """공백을 정리한 뒤 문자 n-gram을 뽑는다.

    줄바꿈·연속 공백이 n-gram에 섞이면 같은 가사가 서식 차이로 달라진다.

    `collapse_space`는 공백을 **아예 제거**한다. 한국어 가사에서 띄어쓰기는
    태그마다 제각각이라(`보고싶어` 대 `보고 싶어`) 같은 문구가 다른 n-gram을
    만드는 일이 잦다. 다만 어절 경계 정보가 사라지므로 **실측으로 판정한다.**
    """
    normalized = "".join(text.split()) if collapse_space else " ".join(text.split())
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

    def __init__(
        self,
        dim: int = FEATURE_DIM,
        sizes: tuple[int, ...] = NGRAM_SIZES,
        *,
        collapse_space: bool = False,
        repeat_damping: float = 0.0,
    ) -> None:
        self._dim = dim
        self._sizes = sizes
        self._collapse_space = collapse_space
        self._repeat_damping = repeat_damping
        """곡 안에서 여러 구간에 반복 등장하는 n-gram의 가중치를 낮춘다.

        후렴 문구는 홀·짝 양쪽에 모두 들어가므로 **곡의 절반으로 나머지 절반을
        찾는 데 전혀 기여하지 않는다.** 그런데 반복되는 만큼 벡터에서 큰 자리를
        차지해, 흔한 후렴 문구를 쓰는 다른 곡과 구분이 흐려진다.

        구간 중복률(실측 8.2%)은 이것을 잡지 못한다. **구간이 통째로 같지 않아도
        문구는 반복되기 때문이다.**

        0이면 감쇠 없음, 1이면 곡 내 문서빈도의 역수로 나눈다.
        """

    @property
    def dim(self) -> int:
        return self._dim

    def extract(self, segments: list[str]) -> Embedding:
        if not segments:
            return np.zeros((0, self._dim), dtype=np.float32)
        counts = np.asarray([self._counts(segment) for segment in segments], dtype=np.float32)
        if self._repeat_damping > 0.0:
            counts = self._damp_repeats(counts)
        scaled = np.log1p(counts)
        norms = np.linalg.norm(scaled, axis=1, keepdims=True)
        return np.asarray(scaled / np.where(norms < EPSILON, 1.0, norms), dtype=np.float32)

    def _counts(self, segment: str) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
        counts = np.zeros(self._dim, dtype=np.float32)
        for gram in char_ngrams(segment, self._sizes, collapse_space=self._collapse_space):
            counts[hash_index(gram, self._dim)] += 1.0
        return counts

    def _damp_repeats(
        self, counts: np.ndarray[tuple[int, int], np.dtype[np.float32]]
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
        """곡 내 문서빈도로 나눈다. 곡 **안에서만** 계산하므로 코퍼스에 의존하지 않는다.

        IDF와 형태는 같지만 대상이 다르다. IDF는 코퍼스 전체에서 흔한 항목을
        누르고(그 역할은 중심화가 한다, D-0036), 이것은 **이 곡의 모든 구간에
        나오는 항목**을 누른다. 후렴이 정확히 그것이다.
        """
        present = (counts > 0).sum(axis=0, dtype=np.float32)
        weight = np.where(present > 0, 1.0 / np.maximum(present, 1.0) ** self._repeat_damping, 0.0)
        return np.asarray(counts * weight.reshape(1, -1), dtype=np.float32)
