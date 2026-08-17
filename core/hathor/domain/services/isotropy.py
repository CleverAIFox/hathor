"""임베딩 공간의 등방화. 순수 함수다.

**문제**: 딥 임베딩은 좁은 원뿔 안에 뭉치는 경향이 있다(anisotropy).
HATHOR 코퍼스 실측에서 1004곡의 전체 쌍 평균 코사인이 **0.9476**이었다.
서로 다른 곡들이 평균 95% 유사한 셈이고, 이 상태에서는 두 가지가 망가진다.

1. **허브 곡이 생긴다.** 코퍼스 중심 방향에 가까운 곡이 어떤 질의에도 상위에
   올라온다. 실제로 시드 퓨전 1위가 코퍼스 중심 1위와 동일하게 나왔다.
2. **차이가 소수점 셋째 자리에 갇힌다.** 1위와 10위의 코사인 차이가 0.01이면
   순위가 사실상 잡음에 좌우된다.

**해법**: 전 곡의 평균 방향을 빼면 모든 곡이 공유하는 성분이 사라지고
곡을 구분하는 성분만 남는다. 이 보정은 임베딩 검색에서 널리 쓰이며 비용이
거의 없다. 다만 **효과는 코퍼스마다 다르므로 M1/M2로 판정한다.**

중심은 코퍼스 전체에서 구한다. 즉 **질의 시점의 코퍼스에 의존한다.** 곡이
추가되면 중심이 미세하게 움직이며, 그것이 이 기법의 대가다. 재현하려면
중심을 함께 기록해야 한다.
"""

from __future__ import annotations

import numpy as np

from hathor.domain.services.embedding_pooling import Matrix, Vector

EPSILON = 1e-12


def mean_direction(matrix: Matrix) -> Vector:
    """단위 벡터들의 평균 방향. 코퍼스가 공유하는 성분이다.

    노름을 그대로 두고 평균내면 음량이 큰 곡이 중심을 끌고 간다.
    중심은 방향의 문제이므로 먼저 단위화한다.
    """
    if matrix.shape[0] == 0:
        raise ValueError("빈 행렬에는 중심이 없다")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    units = matrix / np.where(norms < EPSILON, 1.0, norms)
    center = units.mean(axis=0)
    scale = float(np.linalg.norm(center))
    if scale < EPSILON:
        # 이미 등방이다. 뺄 공통 성분이 없다.
        return np.zeros(matrix.shape[1], dtype=np.float32)
    return np.asarray(center / scale, dtype=np.float32)


def center(matrix: Matrix, direction: Vector) -> Matrix:
    """각 행에서 공통 방향 성분을 제거한다 (사영 제거).

    단순히 `x - c`가 아니라 **`x`가 `c` 방향으로 갖는 성분만큼** 뺀다.
    노름이 제각각인 벡터에서 같은 상수를 빼면 노름이 작은 벡터가 반대편으로
    넘어가 버려서, 조용한 곡의 방향이 통째로 뒤집힌다.
    """
    if direction.shape[0] != matrix.shape[1]:
        raise ValueError(f"차원이 다르다: {matrix.shape[1]} != {direction.shape[0]}")
    if float(np.linalg.norm(direction)) < EPSILON:
        return matrix
    projection = (matrix @ direction).reshape(-1, 1) * direction.reshape(1, -1)
    return np.asarray(matrix - projection, dtype=np.float32)


def anisotropy(matrix: Matrix) -> float:
    """전체 쌍 평균 코사인. 1에 가까울수록 공간이 뭉쳐 있다.

    자기 자신과의 유사도(대각 1.0)를 제외한다. 포함하면 곡 수가 적을수록
    값이 커져 코퍼스 간 비교가 불가능해진다.
    """
    if matrix.shape[0] < 2:
        return 0.0
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    units = matrix / np.where(norms < EPSILON, 1.0, norms)
    similarity = units @ units.T
    count = similarity.shape[0]
    total = float(similarity.sum() - np.trace(similarity))
    return float(total / (count * (count - 1)))
