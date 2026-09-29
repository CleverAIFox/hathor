"""검색 지표 테스트.

손으로 계산할 수 있는 작은 행렬만 쓴다. 지표 정의가 바뀌면 여기가 깨져야 한다.
"""

import numpy as np
import pytest

from hathor.domain.services.retrieval_metrics import (
    PerQuery,
    bootstrap_pair,
    cosine_similarity,
    diagonal_ranks,
    expected_random_precision,
    score_consistency,
    score_per_query,
    score_retrieval,
    top1_accuracy,
)


def bool_matrix(rows: list[list[int]]) -> np.ndarray:
    return np.asarray(rows, dtype=np.bool_)


def test_cosine_similarity_is_scale_invariant():
    left = np.asarray([[1.0, 0.0]], dtype=np.float32)
    right = np.asarray([[5.0, 0.0], [0.0, 3.0]], dtype=np.float32)
    result = cosine_similarity(left, right)
    assert np.allclose(result, [[1.0, 0.0]])


def test_cosine_similarity_handles_zero_rows():
    left = np.zeros((1, 2), dtype=np.float32)
    right = np.asarray([[1.0, 0.0]], dtype=np.float32)
    assert np.isfinite(cosine_similarity(left, right)).all()


def test_cosine_similarity_rejects_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity(np.zeros((1, 2), np.float32), np.zeros((1, 3), np.float32))


def test_top1_accuracy_perfect_on_identity():
    assert top1_accuracy(np.eye(3, dtype=np.float32)) == 1.0


def test_top1_accuracy_counts_misses():
    similarity = np.asarray([[0.1, 0.9, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    assert top1_accuracy(similarity) == pytest.approx(2 / 3)


def test_top1_accuracy_rejects_non_square():
    with pytest.raises(ValueError):
        top1_accuracy(np.zeros((2, 3), dtype=np.float32))


def test_score_retrieval_perfect_ranking():
    """정답 2개가 상위 2위에 오면 MAP@k는 1.0이다 (min(R,k) 정규화)."""
    similarity = np.asarray([[0.0, 0.9, 0.8, 0.1]], dtype=np.float32)
    relevant = bool_matrix([[0, 1, 1, 0]])
    excluded = bool_matrix([[1, 0, 0, 0]])
    score = score_retrieval(similarity, relevant, excluded, k=3)
    assert score.map_at_k == pytest.approx(1.0)
    assert score.precision_at_k == pytest.approx(2 / 3)
    assert score.queries == 1


def test_score_retrieval_penalizes_bad_ranking():
    similarity = np.asarray([[0.0, 0.1, 0.2, 0.9]], dtype=np.float32)
    relevant = bool_matrix([[0, 1, 1, 0]])
    excluded = bool_matrix([[1, 0, 0, 0]])
    score = score_retrieval(similarity, relevant, excluded, k=3)
    # 순위 2,3위가 정답: (1/2 + 2/3) / 2
    assert score.map_at_k == pytest.approx((0.5 + 2 / 3) / 2)


def test_score_retrieval_skips_queries_without_answers():
    """정답이 없는 쿼리는 평균에서 뺀다. 남기면 코퍼스 구성을 재게 된다."""
    similarity = np.asarray([[0.0, 0.9], [0.9, 0.0]], dtype=np.float32)
    relevant = bool_matrix([[0, 1], [0, 0]])
    excluded = bool_matrix([[1, 0], [0, 1]])
    score = score_retrieval(similarity, relevant, excluded, k=1)
    assert score.queries == 1
    assert score.precision_at_k == 1.0


def test_score_retrieval_excluded_do_not_fill_topk():
    """유효 후보가 k보다 적어도 제외 대상이 순위에 들어오지 않는다."""
    similarity = np.asarray([[0.0, 0.9, 0.99, 0.99]], dtype=np.float32)
    relevant = bool_matrix([[0, 1, 0, 0]])
    excluded = bool_matrix([[1, 0, 1, 1]])
    score = score_retrieval(similarity, relevant, excluded, k=1)
    assert score.precision_at_k == 1.0


def test_score_retrieval_returns_empty_when_no_query_qualifies():
    similarity = np.zeros((1, 2), dtype=np.float32)
    score = score_retrieval(similarity, bool_matrix([[0, 0]]), bool_matrix([[1, 0]]), k=1)
    assert score.queries == 0
    assert score.map_at_k == 0.0


def test_score_retrieval_rejects_zero_k():
    with pytest.raises(ValueError):
        score_retrieval(np.zeros((1, 1), np.float32), bool_matrix([[1]]), bool_matrix([[0]]), k=0)


def test_score_retrieval_is_deterministic_on_ties():
    """전부 동점이어도 같은 순위가 나와야 한다. 무작위 베이스라인의 전제다."""
    similarity = np.zeros((1, 5), dtype=np.float32)
    relevant = bool_matrix([[0, 0, 1, 0, 0]])
    excluded = bool_matrix([[1, 0, 0, 0, 0]])
    first = score_retrieval(similarity, relevant, excluded, k=2)
    second = score_retrieval(similarity, relevant, excluded, k=2)
    assert first == second


def test_expected_random_precision_matches_prevalence():
    relevant = bool_matrix([[0, 1, 0, 0, 0]])
    excluded = bool_matrix([[1, 0, 0, 0, 0]])
    assert expected_random_precision(relevant, excluded) == pytest.approx(0.25)


def test_expected_random_precision_ignores_answerless_queries():
    relevant = bool_matrix([[0, 0], [1, 0]])
    excluded = bool_matrix([[1, 0], [0, 1]])
    assert expected_random_precision(relevant, excluded) == pytest.approx(1.0)


def test_diagonal_ranks_agree_with_top1_accuracy():
    """두 함수의 동점 규약이 같아야 한다.

    어긋나면 `top1 = mean(rank == 1)`이 깨지고, 순위 진단이 top-1과 다른 것을
    재게 된다. 진단이 조용히 어긋나는 것이 가장 나쁜 실패다.
    """
    generator = np.random.default_rng(4)
    for _ in range(20):
        similarity = np.asarray(generator.random((12, 12)), dtype=np.float32)
        ranks = diagonal_ranks(similarity)
        assert float(np.mean(ranks == 1)) == pytest.approx(top1_accuracy(similarity))


def test_diagonal_ranks_handle_ties_like_argmax():
    """전부 동점이면 인덱스가 작은 쪽이 이긴다 (argmax 규약)."""
    similarity = np.ones((4, 4), dtype=np.float32)
    assert list(diagonal_ranks(similarity)) == [1, 2, 3, 4]


def test_score_consistency_reports_near_misses():
    """대각선이 항상 2등인 행렬. top-1은 0이지만 표현은 멀쩡하다.

    현재 하네스는 이것과 '대각선이 꼴찌'를 같은 0.0으로 보고했다.
    처방이 정반대인 두 상황을 구분하는 것이 이 지표의 목적이다.
    """
    size = 6
    similarity = np.zeros((size, size), dtype=np.float32)
    for row in range(size):
        similarity[row, row] = 0.9
        similarity[row, (row + 1) % size] = 1.0
    score = score_consistency(similarity)
    assert score.top1 == pytest.approx(0.0)
    assert score.recall_at_5 == pytest.approx(1.0)
    assert score.miss_median_rank == pytest.approx(2.0)
    assert score.mrr == pytest.approx(0.5)


def test_score_consistency_perfect_matrix():
    similarity = np.eye(5, dtype=np.float32)
    score = score_consistency(similarity)
    assert score.top1 == pytest.approx(1.0)
    assert score.mrr == pytest.approx(1.0)
    assert score.miss_median_rank == pytest.approx(0.0)
    assert score.queries == 5


def test_score_consistency_record_is_serializable():
    import json

    record = score_consistency(np.eye(3, dtype=np.float32)).as_record()
    assert json.loads(json.dumps(record))["top1_accuracy"] == 1.0


def test_diagonal_ranks_rejects_non_square():
    with pytest.raises(ValueError):
        diagonal_ranks(np.zeros((2, 3), dtype=np.float32))


def test_쿼리별_점수의_평균이_전체_점수다() -> None:
    """`score_retrieval`이 `score_per_query().mean()`이다. **두 길이 갈리면 안 된다.**"""
    similarity = np.asarray(
        [[1.0, 0.9, 0.1, 0.2], [0.9, 1.0, 0.3, 0.1], [0.1, 0.3, 1.0, 0.8], [0.2, 0.1, 0.8, 1.0]],
        dtype=np.float32,
    )
    relevant = bool_matrix([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]])
    excluded = bool_matrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    per_query = score_per_query(similarity, relevant, excluded, 2)
    assert per_query.rows == (0, 1, 2, 3)
    assert per_query.mean() == score_retrieval(similarity, relevant, excluded, 2)


def test_정답_없는_쿼리는_쿼리별_목록에서도_빠진다() -> None:
    """`rows`가 어느 쿼리가 평균에 들었는지 말한다 — 베이스라인 짝맞춤이 여기 걸린다."""
    similarity = np.asarray([[1.0, 0.5], [0.5, 1.0]], dtype=np.float32)
    relevant = bool_matrix([[0, 1], [0, 0]])
    excluded = bool_matrix([[1, 0], [0, 1]])
    per_query = score_per_query(similarity, relevant, excluded, 1)
    assert per_query.rows == (0,)
    assert len(per_query.precision) == 1


def _paired(count: int) -> tuple[PerQuery, PerQuery]:
    rows = tuple(range(count))
    high = tuple(float(index % 3) / 2.0 for index in range(count))
    low = tuple(0.1 for _ in range(count))
    return (
        PerQuery(rows=rows, precision=high, average_precision=high),
        PerQuery(rows=rows, precision=low, average_precision=low),
    )


def test_부트스트랩은_실측과_베이스라인에_같은_추출을_쓴다() -> None:
    """따로 뽑으면 둘의 **차**가 추출 잡음까지 타서 구간이 실제보다 넓어진다.

    같은 색인을 쓰면 상수 베이스라인의 구간은 폭이 0이다 — 그 점이 짝맞춤의 증거다.
    """
    measured, baseline = _paired(200)
    drawn = bootstrap_pair(measured, baseline, repeats=300, seed=17)
    assert drawn is not None
    (precision, average), (random_precision, _) = drawn
    assert precision == average
    assert random_precision.std == pytest.approx(0.0, abs=1e-12)
    assert random_precision.low == pytest.approx(0.1)
    assert precision.low < precision.mean < precision.high
    assert precision.repeats == 300


def test_부트스트랩_평균은_표본평균_근처다() -> None:
    measured, baseline = _paired(400)
    drawn = bootstrap_pair(measured, baseline, repeats=500, seed=23)
    assert drawn is not None
    (precision, _), _ = drawn
    assert precision.mean == pytest.approx(measured.mean().precision_at_k, abs=0.01)


def test_시드가_같으면_같은_구간이_나온다() -> None:
    measured, baseline = _paired(120)
    first = bootstrap_pair(measured, baseline, repeats=200, seed=5)
    second = bootstrap_pair(measured, baseline, repeats=200, seed=5)
    assert first == second


def test_쿼리가_모자라면_구간을_내지_않는다() -> None:
    """**표준편차 0.0을 내지 않는다.** 0.0은 «흔들리지 않는다»로 읽히고 그것이 거짓이다."""
    single = PerQuery(rows=(0,), precision=(0.5,), average_precision=(0.5,))
    assert bootstrap_pair(single, single, repeats=100, seed=1) is None
    measured, baseline = _paired(50)
    assert bootstrap_pair(measured, baseline, repeats=0, seed=1) is None


def test_쿼리_집합이_다르면_거부한다() -> None:
    measured, _ = _paired(10)
    other = PerQuery(
        rows=tuple(range(1, 11)),
        precision=measured.precision,
        average_precision=measured.precision,
    )
    with pytest.raises(ValueError, match="쿼리 집합이 다르다"):
        bootstrap_pair(measured, other, repeats=10, seed=1)
