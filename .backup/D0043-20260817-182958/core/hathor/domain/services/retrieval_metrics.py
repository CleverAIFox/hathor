"""검색 지표. 임베딩이 무엇인지, 라벨이 어디서 왔는지 모른다.

유사도 행렬과 불리언 마스크만 받는다. 그래야 MERT든 MFCC든 무작위든
같은 코드로 재고, 지표 정의가 특징 추출기에 딸려가지 않는다.

**MAP@k 정규화**: AP를 `min(R, k)`로 나눈다. R은 유효 후보 중 정답 수다.
R이 k보다 작을 때 R로 나누지 않고 k로 나누면 완벽한 순위도 1.0에 못 미쳐
"2곡짜리 앨범은 최대 0.2점"이 된다. 앨범당 곡 수가 제각각인 코퍼스에서는
지표가 앨범 크기 분포를 재게 된다. 정의를 바꾸면 수치가 통째로 달라지므로
비교 대상 수치가 같은 정의인지 항상 확인해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

type Matrix = np.ndarray[tuple[int, int], np.dtype[np.float32]]
type BoolMatrix = np.ndarray[tuple[int, int], np.dtype[np.bool_]]

EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class RetrievalScore:
    """지표 하나의 결과. 쿼리 수를 함께 들고 다닌다.

    쿼리 수 없이 평균값만 남기면 "MAP 0.41"이 12곡짜리인지 900곡짜리인지
    알 수 없게 된다.
    """

    queries: int
    precision_at_k: float
    map_at_k: float

    def as_record(self) -> dict[str, object]:
        return {
            "queries": self.queries,
            "precision_at_k": round(self.precision_at_k, 6),
            "map_at_k": round(self.map_at_k, 6),
        }


def cosine_similarity(queries: Matrix, candidates: Matrix) -> Matrix:
    """(쿼리, 후보) 코사인 유사도 행렬. 영벡터 행은 유사도 0이 된다."""
    if queries.shape[1] != candidates.shape[1]:
        raise ValueError(f"차원이 다르다: {queries.shape[1]} != {candidates.shape[1]}")
    left = _unit_rows(queries)
    right = _unit_rows(candidates)
    return np.asarray(left @ right.T, dtype=np.float32)


def _unit_rows(matrix: Matrix) -> Matrix:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe = np.where(norms < EPSILON, 1.0, norms)
    return np.asarray(matrix / safe, dtype=np.float32)


def top1_accuracy(similarity: Matrix) -> float:
    """행 i의 최대값이 열 i인 비율. 대각선이 정답이라는 전제다 (M0).

    동점은 인덱스가 작은 쪽이 이긴다(argmax 규약). 임베딩이 무너져 전 행이
    동일해지는 경우 정답률이 0에 수렴하므로 실패가 성공으로 보이지 않는다.
    """
    if similarity.shape[0] == 0:
        return 0.0
    if similarity.shape[0] != similarity.shape[1]:
        raise ValueError(f"정사각 행렬이어야 한다: {similarity.shape}")
    best = np.argmax(similarity, axis=1)
    return float(np.mean(best == np.arange(similarity.shape[0])))


def score_retrieval(
    similarity: Matrix,
    relevant: BoolMatrix,
    excluded: BoolMatrix,
    k: int,
) -> RetrievalScore:
    """P@k와 MAP@k를 잰다.

    `excluded`가 True인 후보는 순위에서 아예 빠진다. 점수를 -inf로 낮추는
    방식이 아니라 실제로 제외한다. 유효 후보가 k개보다 적을 때 제외 대상이
    top-k를 채워 P@k를 조용히 떨어뜨리는 것을 막는다.

    정답이 하나도 없는 쿼리는 평균에서 뺀다. 그런 쿼리의 AP는 정의상 0이며,
    남겨두면 "정답이 존재하지 않는 곡이 많은 코퍼스"가 낮은 점수로 보인다.
    측정 대상은 코퍼스 구성이 아니라 임베딩이다.
    """
    if k <= 0:
        raise ValueError("k는 1 이상이어야 한다")

    precisions: list[float] = []
    average_precisions: list[float] = []
    for row in range(similarity.shape[0]):
        valid = np.flatnonzero(~excluded[row])
        if valid.size == 0:
            continue
        hits_available = int(np.count_nonzero(relevant[row][valid]))
        if hits_available == 0:
            continue

        order = valid[np.argsort(-similarity[row][valid], kind="stable")][:k]
        hits = relevant[row][order]
        precisions.append(float(np.count_nonzero(hits)) / float(k))

        running = np.cumsum(hits)
        ranks = np.arange(1, hits.size + 1)
        gained = (running / ranks) * hits
        average_precisions.append(float(gained.sum()) / float(min(hits_available, k)))

    if not precisions:
        return RetrievalScore(queries=0, precision_at_k=0.0, map_at_k=0.0)
    return RetrievalScore(
        queries=len(precisions),
        precision_at_k=float(np.mean(precisions)),
        map_at_k=float(np.mean(average_precisions)),
    )


def expected_random_precision(relevant: BoolMatrix, excluded: BoolMatrix) -> float:
    """무작위 순위에서 기대되는 P@k. 경험적 무작위 베이스라인의 검산용이다.

    쿼리별 정답 비율(정답 수 / 유효 후보 수)의 평균이며 k와 무관하다.
    시드를 바꿔 뽑은 무작위 베이스라인이 이 값 근처에 오지 않으면
    마스크 구성이나 난수 처리에 결함이 있다는 뜻이다.
    """
    ratios: list[float] = []
    for row in range(relevant.shape[0]):
        valid = np.flatnonzero(~excluded[row])
        if valid.size == 0:
            continue
        hits = int(np.count_nonzero(relevant[row][valid]))
        if hits == 0:
            continue
        ratios.append(hits / float(valid.size))
    return float(np.mean(ratios)) if ratios else 0.0
