"""검색 지표 테스트.

손으로 계산할 수 있는 작은 행렬만 쓴다. 지표 정의가 바뀌면 여기가 깨져야 한다.
"""

import numpy as np
import pytest

from hathor.domain.services.retrieval_metrics import (
    cosine_similarity,
    expected_random_precision,
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
