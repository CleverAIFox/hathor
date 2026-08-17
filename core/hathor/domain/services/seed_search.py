"""시드곡 조합과 곡 내부 반복 구간. 순수 함수다.

D-0011은 생성 입력을 **시드곡 선택**으로 정했다. 형용사 체크박스가 아니라
"이 곡들 같은 느낌으로"다. 그러려면 곡 여러 개를 하나의 조건으로 접어야 하고,
그 조건이 임베딩 공간에서 의미 있는 지점을 가리키는지 확인할 수단이 필요하다.
이 모듈이 그 접기를 담당한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

import numpy as np

from hathor.domain.ports.audio_analysis import CHUNK_SECONDS, Embedding
from hathor.domain.services.embedding_pooling import Matrix, Vector, unit

EPSILON = 1e-12


class FusionMode(StrEnum):
    """시드 여러 개의 유사도를 하나의 점수로 접는 방법."""

    MEAN = "mean"
    """평균. 중점 벡터에 대한 코사인과 순위가 동일하다."""

    MIN = "min"
    """최솟값. 모든 시드와 가까워야 점수가 나온다."""

    PENALIZED = "penalized"
    """평균에서 시드 간 편차를 뺀다. 둘의 절충이다."""


def fuse(vectors: Sequence[Vector]) -> Vector:
    """시드곡 여러 개를 조건 벡터 하나로 접는다 (MEAN 전용).

    **각 곡을 단위 벡터로 만든 뒤 평균낸다.** 그냥 평균내면 노름이 큰 곡이
    조합을 지배해서 "A와 B의 퓨전"이 사실상 A가 된다. 노름은 음량·마스터링에
    따라 달라지는 값이지 취향의 강도가 아니다.

    MIN·PENALIZED는 **벡터로 표현할 수 없다.** 후보마다 시드별 유사도를 따로
    보고 결합해야 하므로 `fuse_scores`를 쓴다.
    """
    if not vectors:
        raise ValueError("시드가 최소 하나 필요하다")
    dims = {vector.shape[0] for vector in vectors}
    if len(dims) > 1:
        raise ValueError(f"시드 차원이 다르다: {sorted(dims)}")
    return np.asarray(np.mean([unit(vector) for vector in vectors], axis=0), dtype=np.float32)


def fuse_scores(
    similarities: Matrix,
    mode: FusionMode = FusionMode.MEAN,
    *,
    penalty: float = 1.0,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """(시드, 후보) 유사도 행렬을 후보별 점수로 접는다.

    **MEAN은 한쪽에 극단적으로 가까운 곡을 선호한다.** 시드 A와 0.9, B와 0.0인
    곡은 평균 0.45이고, 양쪽과 0.42인 곡은 0.42다. 전자가 이긴다. 실측에서
    `밤편지 + 뱅뱅뱅` 상위 10곡 중 4곡이 아이유였던 원인이다.

    **MIN은 모든 시드와 가까울 것을 요구한다.** 위 예에서 전자는 0.0이 되고
    후자는 0.42가 된다. 다만 시드가 서로 아주 멀면 전 후보의 최솟값이 낮아져
    순위가 잡음에 가까워질 수 있다.

    **PENALIZED**는 평균에서 시드 간 편차(최대-최소)를 `penalty`배 빼서 둘을 절충한다.
    `penalty=0`이면 MEAN, 아주 크면 MIN에 가까워진다.

    어느 쪽이 나은지는 코퍼스에 달렸으므로 **실측으로 정한다.**
    """
    if similarities.ndim != 2 or similarities.shape[0] == 0:
        raise ValueError("(시드, 후보) 행렬이 필요하다")
    if mode is FusionMode.MEAN:
        return np.asarray(similarities.mean(axis=0), dtype=np.float32)
    if mode is FusionMode.MIN:
        return np.asarray(similarities.min(axis=0), dtype=np.float32)
    spread = similarities.max(axis=0) - similarities.min(axis=0)
    return np.asarray(similarities.mean(axis=0) - penalty * spread, dtype=np.float32)


def representative_chunk(embedding: Embedding) -> int:
    """다른 청크들과 가장 비슷한 청크의 인덱스.

    후렴은 곡에서 여러 번 반복되므로 반복도가 높은 구간이 후렴일 가능성이
    크다는 발상이다. 청크 23개끼리 코사인 한 번이면 끝나므로 추가 추출도
    GPU도 필요 없다.

    **이것이 실제로 후렴에 떨어지는지는 미검증이다 (실측 필요).**
    따라서 "하이라이트"가 아니라 "반복도가 가장 높은 구간"으로 부른다.
    도입부·아웃트로가 조용한 곡에서는 중간 어딘가를 가리키는 정도만 보장된다.
    """
    if embedding.ndim != 2 or embedding.shape[0] == 0:
        raise ValueError("청크가 없는 임베딩에는 대표 구간이 없다")
    if embedding.shape[0] == 1:
        return 0

    norms = np.linalg.norm(embedding, axis=1, keepdims=True)
    units = embedding / np.where(norms < EPSILON, 1.0, norms)
    similarity = units @ units.T
    # 자기 자신과의 유사도(대각 1.0)를 빼야 청크 수에 따라 값이 흔들리지 않는다.
    np.fill_diagonal(similarity, 0.0)
    return int(np.argmax(similarity.sum(axis=1)))


def chunk_timestamp(index: int) -> str:
    """청크 인덱스를 `분:초`로. 청크 경계이므로 근사 위치다."""
    total = index * CHUNK_SECONDS
    return f"{total // 60}:{total % 60:02d}"
