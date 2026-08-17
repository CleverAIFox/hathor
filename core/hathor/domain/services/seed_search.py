"""시드곡 조합과 곡 내부 반복 구간. 순수 함수다.

D-0011은 생성 입력을 **시드곡 선택**으로 정했다. 형용사 체크박스가 아니라
"이 곡들 같은 느낌으로"다. 그러려면 곡 여러 개를 하나의 조건으로 접어야 하고,
그 조건이 임베딩 공간에서 의미 있는 지점을 가리키는지 확인할 수단이 필요하다.
이 모듈이 그 접기를 담당한다.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from hathor.domain.ports.audio_analysis import CHUNK_SECONDS, Embedding
from hathor.domain.services.embedding_pooling import Vector, unit

EPSILON = 1e-12


def fuse(vectors: Sequence[Vector]) -> Vector:
    """시드곡 여러 개를 조건 벡터 하나로 접는다.

    **각 곡을 단위 벡터로 만든 뒤 평균낸다.** 그냥 평균내면 노름이 큰 곡이
    조합을 지배해서 "A와 B의 퓨전"이 사실상 A가 된다. 노름은 음량·마스터링에
    따라 달라지는 값이지 취향의 강도가 아니다.

    가중치는 받지 않는다. "A를 70%, B를 30%"는 사용자가 의미를 부여할 수 없는
    수치이고, 실측으로 검증할 방법도 아직 없다. 필요해지면 그때 추가한다.
    """
    if not vectors:
        raise ValueError("시드가 최소 하나 필요하다")
    dims = {vector.shape[0] for vector in vectors}
    if len(dims) > 1:
        raise ValueError(f"시드 차원이 다르다: {sorted(dims)}")
    return np.asarray(np.mean([unit(vector) for vector in vectors], axis=0), dtype=np.float32)


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
