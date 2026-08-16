"""청크 임베딩을 곡 벡터로 접는 규칙. 순수 함수이며 파일도 모델도 모른다.

추출기는 곡 하나를 (청크, 차원) 행렬로 낸다. 곡 간 유사도를 재려면 이를
벡터 하나로 접어야 하고, 혼합·스템 4종이 있으므로 무엇을 어떻게 합칠지도
정해야 한다. 어느 조합이 나은지는 실측 문제다. 따라서 여기서는 선택지를
열어두고 고르지 않는다. 고르는 것은 평가 하네스의 일이다.

`chunk_l2`가 시간축 풀링 **전에** 적용된다는 점이 중요하다. 코사인 유사도는
마지막 단계에서 다시 정규화하므로 곡 벡터에 L2를 거는 것은 아무 효과가 없다.
실제로 결과를 바꾸는 것은 청크별 정규화이며, 이것은 에너지가 큰 구간(후렴,
빌드업)이 곡 벡터를 얼마나 지배할지를 정하는 선택이다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

import numpy as np

from hathor.domain.ports.audio_analysis import Embedding

type Vector = np.ndarray[tuple[int], np.dtype[np.float32]]
"""곡 하나를 대표하는 1차원 float32 벡터."""

type Matrix = np.ndarray[tuple[int, int], np.dtype[np.float32]]
"""(곡, 차원) 행렬. 행 하나가 곡 하나다."""

EPSILON = 1e-12


class PoolMode(StrEnum):
    """시간축을 접는 방법."""

    MEAN = "mean"
    """청크 평균. 곡의 평균적 성격만 남고 변동은 사라진다."""

    MEAN_STD = "mean-std"
    """평균과 표준편차를 이어붙인다. 차원이 2배가 되며 시간축 변동을 담는다."""


class CombineMode(StrEnum):
    """혼합·스템 여러 종을 하나의 뷰로 합치는 방법."""

    CONCAT = "concat"
    """이어붙인다. 정보를 잃지 않으나 차원이 종 수만큼 늘어난다."""

    AVERAGE = "average"
    """평균낸다. 차원이 유지되나 종별 구분이 사라진다."""


def l2_normalize(matrix: Embedding) -> Embedding:
    """행 단위로 L2 정규화한다. 영벡터 행은 그대로 둔다.

    영벡터를 0으로 나누면 NaN이 되고, NaN 하나가 유사도 행렬 전체를
    조용히 오염시킨다. 무음 스템에서 실제로 나올 수 있는 값이다.
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe = np.where(norms < EPSILON, 1.0, norms)
    return np.asarray(matrix / safe, dtype=np.float32)


def pool(embedding: Embedding, mode: PoolMode = PoolMode.MEAN, *, chunk_l2: bool = False) -> Vector:
    """(청크, 차원) 임베딩을 벡터 하나로 접는다.

    청크가 없으면 실패한다. 조용히 영벡터를 내면 그 곡이 유사도 행렬에
    남아 모든 지표를 미세하게 틀어놓는다. 걸러내는 것은 호출자의 책임이다.
    """
    if embedding.ndim != 2 or embedding.shape[0] == 0:
        raise ValueError(f"청크가 없는 임베딩은 풀링할 수 없다: shape={embedding.shape}")

    source = l2_normalize(embedding) if chunk_l2 else embedding
    mean = source.mean(axis=0)
    if mode is PoolMode.MEAN:
        return np.asarray(mean, dtype=np.float32)
    # 청크가 1개면 표준편차가 전부 0이다. 오류는 아니며 정보가 없을 뿐이다.
    deviation = source.std(axis=0)
    return np.asarray(np.concatenate([mean, deviation]), dtype=np.float32)


def split_odd_even(embedding: Embedding) -> tuple[Embedding, Embedding]:
    """청크를 홀수·짝수 인덱스로 나눈다 (M0 자기일관성용).

    앞뒤 절반으로 자르지 않는다. 곡의 앞부분과 뒷부분은 구성이 다르므로
    (인트로 대 아웃트로) 그 대조는 임베딩 품질이 아니라 곡 구조를 잰다.
    홀짝은 두 쪽 모두 곡 전체에 고르게 퍼지므로 같은 곡이라는 사실 외의
    차이를 최소화한다.
    """
    if embedding.shape[0] < 2:
        raise ValueError("청크가 2개 미만이면 나눌 수 없다")
    return embedding[0::2], embedding[1::2]


def build_view(
    embeddings: Mapping[str, Embedding],
    keys: Sequence[str],
    *,
    combine: CombineMode = CombineMode.CONCAT,
    mode: PoolMode = PoolMode.MEAN,
    chunk_l2: bool = False,
) -> Vector:
    """선택한 키들을 각각 풀링한 뒤 하나의 뷰 벡터로 합친다.

    `AVERAGE`는 키별 차원이 같아야 한다. 혼합과 스템은 같은 모델을 거치므로
    현재는 항상 같지만, 다른 추출기를 섞으면 깨진다. 그때 조용히 브로드캐스트
    되지 않도록 명시적으로 막는다.
    """
    if not keys:
        raise ValueError("뷰에 쓸 키를 최소 하나 지정해야 한다")

    missing = [key for key in keys if key not in embeddings]
    if missing:
        raise KeyError(f"임베딩에 없는 키: {', '.join(sorted(missing))}")

    parts = [pool(embeddings[key], mode, chunk_l2=chunk_l2) for key in keys]
    if combine is CombineMode.CONCAT:
        return np.asarray(np.concatenate(parts), dtype=np.float32)

    dims = {part.shape[0] for part in parts}
    if len(dims) > 1:
        raise ValueError(f"AVERAGE는 차원이 같아야 한다: {sorted(dims)}")
    return np.asarray(np.mean(parts, axis=0), dtype=np.float32)
