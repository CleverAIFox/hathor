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


@dataclass(frozen=True, slots=True)
class ConsistencyScore:
    """자기일관성 한 회의 결과. top-1과 **실패의 성격**을 함께 낸다.

    top-1만 남기면 `0.8983`이 무슨 실패인지 알 수 없다. 실패한 10%가 순위 2에
    몰려 있으면 표현은 멀쩡하고 top-1이라는 관문이 가혹한 것이고, 순위 400에
    흩어져 있으면 그 곡들은 표현이 실제로 없는 것이다. **두 진단의 처방이
    정반대인데 현재 하네스는 둘을 구분하지 못한다.**

    비용은 0이다. 이미 만든 유사도 행렬에서 순위를 세기만 하면 된다.
    """

    queries: int
    top1: float
    mrr: float
    recall_at_5: float
    recall_at_10: float
    miss_median_rank: float
    """실패 쿼리(순위 2 이상)의 정답 순위 중앙값. 실패가 없으면 0.0이다."""

    def as_record(self) -> dict[str, object]:
        return {
            "queries": self.queries,
            "top1_accuracy": round(self.top1, 6),
            "mrr": round(self.mrr, 6),
            "recall_at_5": round(self.recall_at_5, 6),
            "recall_at_10": round(self.recall_at_10, 6),
            "miss_median_rank": round(self.miss_median_rank, 3),
        }


def diagonal_ranks(similarity: Matrix) -> np.ndarray[tuple[int], np.dtype[np.int64]]:
    """행 i에서 열 i가 몇 등인지. 1등이 정답이다 (M0).

    동점 처리를 `top1_accuracy`의 argmax 규약과 **정확히** 맞춘다. 인덱스가
    작은 쪽이 이기므로, 자기보다 점수가 높은 후보 수에 더해 **동점이면서
    인덱스가 앞선 후보**를 함께 센다. 두 함수가 다른 규약을 쓰면
    `top1 = mean(rank == 1)`이 성립하지 않아 진단이 조용히 어긋난다.
    """
    if similarity.shape[0] != similarity.shape[1]:
        raise ValueError(f"정사각 행렬이어야 한다: {similarity.shape}")
    size = similarity.shape[0]
    if size == 0:
        return np.zeros(0, dtype=np.int64)
    own = np.diagonal(similarity).reshape(-1, 1)
    greater = similarity > own
    index = np.arange(size)
    earlier_tie = (similarity == own) & (index.reshape(1, -1) < index.reshape(-1, 1))
    return np.asarray(
        1 + greater.sum(axis=1, dtype=np.int64) + earlier_tie.sum(axis=1, dtype=np.int64),
        dtype=np.int64,
    )


def score_consistency(similarity: Matrix) -> ConsistencyScore:
    """대각선이 정답인 정사각 유사도에서 순위 진단을 낸다."""
    ranks = diagonal_ranks(similarity)
    if ranks.size == 0:
        return ConsistencyScore(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    misses = ranks[ranks > 1]
    return ConsistencyScore(
        queries=int(ranks.size),
        top1=float(np.mean(ranks == 1)),
        mrr=float(np.mean(1.0 / ranks)),
        recall_at_5=float(np.mean(ranks <= 5)),
        recall_at_10=float(np.mean(ranks <= 10)),
        miss_median_rank=float(np.median(misses)) if misses.size else 0.0,
    )


@dataclass(frozen=True, slots=True)
class PerQuery:
    """평균을 내기 **전** 단계의 쿼리별 점수 (D-0300).

    `score_retrieval`이 평균만 내주면 표본 흔들림을 잴 길이 없다. D-0284가 *"1인
    1004곡 규모에서 취향 벡터의 안정성"*을 재야 할 것으로 적었는데, `--split-repeats`는
    M0 자기일관성만 반복하고 M1/M2는 반복하지 않는다 — 직접 잴 장치가 없었다.

    `rows`를 같이 든다. 실측과 무작위 베이스라인은 **같은 쿼리 집합**에서 나와야
    하고(건너뛰기 조건이 마스크에만 의존하므로 그래야 맞다), `bootstrap_pair`가
    그것을 확인한다.
    """

    rows: tuple[int, ...]
    precision: tuple[float, ...]
    average_precision: tuple[float, ...]

    def mean(self) -> RetrievalScore:
        if not self.precision:
            return RetrievalScore(queries=0, precision_at_k=0.0, map_at_k=0.0)
        return RetrievalScore(
            queries=len(self.precision),
            precision_at_k=float(np.mean(self.precision)),
            map_at_k=float(np.mean(self.average_precision)),
        )


@dataclass(frozen=True, slots=True)
class Interval:
    """부트스트랩 구간. **표본평균의 정밀도이며 다른 사람 서고로의 일반화가 아니다.**

    쿼리를 복원추출로 다시 뽑아 평균을 `repeats`번 다시 낸다. 나오는 것은 *"이 1004곡에서
    이 평균이 얼마나 흔들리는가"*다. *"다른 사람 서고에서도 이 수가 나오는가"*는 서고가
    하나뿐이라 이 장치로 답이 안 나온다 — 그 구분을 지우면 D-0284가 경계한 과대해석이 된다.
    """

    mean: float
    std: float
    low: float
    high: float
    repeats: int

    def as_record(self) -> dict[str, object]:
        return {
            "mean": round(self.mean, 6),
            "std": round(self.std, 6),
            "low": round(self.low, 6),
            "high": round(self.high, 6),
            "repeats": self.repeats,
        }


BOOTSTRAP_FLOOR = 2
"""부트스트랩에 필요한 최소 쿼리 수. 하나면 어떻게 뽑아도 같은 값이라 표준편차가 0이다."""

BOOTSTRAP_PERCENTILES = (2.5, 97.5)
"""백분위 구간. 95%이며 **정규 가정을 쓰지 않는다** — P@k는 0과 1에서 잘린 분포다."""


def bootstrap_pair(
    measured: PerQuery, baseline: PerQuery, *, repeats: int, seed: int
) -> tuple[tuple[Interval, Interval], tuple[Interval, Interval]] | None:
    """실측과 베이스라인을 **같은 추출로** 부트스트랩한다.

    같은 쿼리 색인을 둘 다에 쓴다. 따로 뽑으면 둘의 차가 추출 잡음까지 타서
    "실측이 베이스라인보다 높다"의 구간이 실제보다 넓어진다.

    쿼리가 `BOOTSTRAP_FLOOR` 미만이거나 `repeats`가 0이면 `None`을 낸다 —
    **표준편차 0.0을 내지 않는다.** 0.0은 "흔들리지 않는다"로 읽히고 그것이 거짓이다.
    """
    if measured.rows != baseline.rows:
        raise ValueError("실측과 베이스라인의 쿼리 집합이 다르다")
    size = len(measured.rows)
    if repeats <= 0 or size < BOOTSTRAP_FLOOR:
        return None
    generator = np.random.default_rng(seed)
    draws = generator.integers(0, size, size=(repeats, size))
    return (
        _interval(measured.precision, draws, repeats),
        _interval(measured.average_precision, draws, repeats),
    ), (
        _interval(baseline.precision, draws, repeats),
        _interval(baseline.average_precision, draws, repeats),
    )


def _interval(
    values: tuple[float, ...], draws: np.ndarray[tuple[int, int], np.dtype[np.int64]], repeats: int
) -> Interval:
    sample = np.asarray(values, dtype=np.float64)[draws].mean(axis=1)
    low, high = np.percentile(sample, BOOTSTRAP_PERCENTILES)
    return Interval(
        mean=float(sample.mean()),
        std=float(sample.std(ddof=1)),
        low=float(low),
        high=float(high),
        repeats=repeats,
    )


def score_per_query(
    similarity: Matrix,
    relevant: BoolMatrix,
    excluded: BoolMatrix,
    k: int,
) -> PerQuery:
    """P@k와 MAP@k를 **쿼리별로** 낸다. `score_retrieval`이 이것의 평균이다.

    `excluded`가 True인 후보는 순위에서 아예 빠진다. 점수를 -inf로 낮추는
    방식이 아니라 실제로 제외한다. 유효 후보가 k개보다 적을 때 제외 대상이
    top-k를 채워 P@k를 조용히 떨어뜨리는 것을 막는다.

    정답이 하나도 없는 쿼리는 평균에서 뺀다. 그런 쿼리의 AP는 정의상 0이며,
    남겨두면 "정답이 존재하지 않는 곡이 많은 코퍼스"가 낮은 점수로 보인다.
    측정 대상은 코퍼스 구성이 아니라 임베딩이다.
    """
    if k <= 0:
        raise ValueError("k는 1 이상이어야 한다")

    rows: list[int] = []
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
        rows.append(row)
        precisions.append(float(np.count_nonzero(hits)) / float(k))

        running = np.cumsum(hits)
        ranks = np.arange(1, hits.size + 1)
        gained = (running / ranks) * hits
        average_precisions.append(float(gained.sum()) / float(min(hits_available, k)))

    return PerQuery(
        rows=tuple(rows),
        precision=tuple(precisions),
        average_precision=tuple(average_precisions),
    )


def score_retrieval(
    similarity: Matrix,
    relevant: BoolMatrix,
    excluded: BoolMatrix,
    k: int,
) -> RetrievalScore:
    """P@k와 MAP@k의 쿼리 평균. 쿼리별 값이 필요하면 `score_per_query`를 쓴다."""
    return score_per_query(similarity, relevant, excluded, k).mean()


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
