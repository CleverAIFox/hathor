"""임베딩 풀링 테스트. 모델도 파일도 쓰지 않는다."""

import numpy as np
import pytest

from hathor.domain.services.embedding_pooling import (
    CombineMode,
    PoolMode,
    build_view,
    l2_normalize,
    pool,
    split_odd_even,
)


def embedding(rows: int, dim: int = 4, start: float = 1.0) -> np.ndarray:
    values = np.arange(rows * dim, dtype=np.float32).reshape(rows, dim)
    return np.asarray(values + start, dtype=np.float32)


def test_l2_normalize_makes_unit_rows():
    result = l2_normalize(embedding(3))
    assert np.allclose(np.linalg.norm(result, axis=1), 1.0)


def test_l2_normalize_keeps_zero_rows_finite():
    """무음 스템은 영벡터가 될 수 있다. NaN 하나가 유사도 행렬 전체를 오염시킨다."""
    matrix = np.zeros((2, 4), dtype=np.float32)
    matrix[1] = 1.0
    result = l2_normalize(matrix)
    assert np.isfinite(result).all()
    assert np.allclose(result[0], 0.0)


def test_pool_mean_averages_chunks():
    result = pool(embedding(2), PoolMode.MEAN)
    assert result.shape == (4,)
    assert np.allclose(result, [3.0, 4.0, 5.0, 6.0])


def test_pool_mean_std_doubles_dimension():
    result = pool(embedding(3), PoolMode.MEAN_STD)
    assert result.shape == (8,)
    assert np.allclose(result[4:], np.std(embedding(3), axis=0))


def test_pool_single_chunk_has_zero_deviation():
    result = pool(embedding(1), PoolMode.MEAN_STD)
    assert np.allclose(result[4:], 0.0)


def test_pool_rejects_empty():
    with pytest.raises(ValueError):
        pool(np.zeros((0, 4), dtype=np.float32))


def test_chunk_l2_changes_result():
    """에너지가 큰 청크가 곡 벡터를 지배하는지 여부가 달라진다."""
    matrix = np.asarray([[1.0, 0.0], [0.0, 100.0]], dtype=np.float32)
    plain = pool(matrix)
    normalized = pool(matrix, chunk_l2=True)
    assert not np.allclose(plain / np.linalg.norm(plain), normalized / np.linalg.norm(normalized))


def test_split_odd_even_covers_all_chunks():
    odd, even = split_odd_even(embedding(5))
    assert odd.shape[0] + even.shape[0] == 5
    assert np.allclose(odd[0], embedding(5)[0])
    assert np.allclose(even[0], embedding(5)[1])


def test_split_odd_even_rejects_single_chunk():
    with pytest.raises(ValueError):
        split_odd_even(embedding(1))


def test_build_view_concat_grows_dimension():
    embeddings = {"mixture": embedding(2), "drums": embedding(2, start=9.0)}
    result = build_view(embeddings, ("mixture", "drums"))
    assert result.shape == (8,)


def test_build_view_average_keeps_dimension():
    embeddings = {"mixture": embedding(2), "drums": embedding(2, start=9.0)}
    result = build_view(embeddings, ("mixture", "drums"), combine=CombineMode.AVERAGE)
    assert result.shape == (4,)


def test_build_view_average_rejects_mismatched_dimensions():
    embeddings = {"a": embedding(2, dim=4), "b": embedding(2, dim=6)}
    with pytest.raises(ValueError):
        build_view(embeddings, ("a", "b"), combine=CombineMode.AVERAGE)


def test_build_view_reports_missing_key():
    with pytest.raises(KeyError):
        build_view({"mixture": embedding(2)}, ("vocals",))


def test_build_view_requires_keys():
    with pytest.raises(ValueError):
        build_view({"mixture": embedding(2)}, ())


def test_build_view_key_order_matters():
    embeddings = {"a": embedding(2), "b": embedding(2, start=9.0)}
    assert not np.allclose(build_view(embeddings, ("a", "b")), build_view(embeddings, ("b", "a")))


def test_block_l2_makes_each_part_unit_length():
    """서로 다른 추출기를 붙일 때 노름이 큰 블록이 코사인을 지배하는 것을 막는다."""
    embeddings = {"big": embedding(2, dim=4) * 100.0, "small": embedding(2, dim=4) * 0.01}
    plain = build_view(embeddings, ("big", "small"))
    normalized = build_view(embeddings, ("big", "small"), block_l2=True)
    assert np.linalg.norm(plain[:4]) / np.linalg.norm(plain[4:]) > 1000
    assert np.linalg.norm(normalized[:4]) == pytest.approx(1.0)
    assert np.linalg.norm(normalized[4:]) == pytest.approx(1.0)


def test_block_l2_equalizes_cosine_contribution():
    """블록 정규화 후 concat의 코사인은 블록 코사인의 평균이다."""
    from hathor.domain.services.retrieval_metrics import cosine_similarity

    left = {"a": embedding(2, dim=4), "b": embedding(2, dim=4, start=5.0) * 0.001}
    right = {"a": embedding(2, dim=4, start=2.0), "b": embedding(2, dim=4) * 0.001}
    views = [build_view(side, ("a", "b"), block_l2=True).reshape(1, -1) for side in (left, right)]
    combined = float(cosine_similarity(views[0], views[1])[0, 0])

    blocks = [
        float(
            cosine_similarity(
                build_view(left, (key,), block_l2=True).reshape(1, -1),
                build_view(right, (key,), block_l2=True).reshape(1, -1),
            )[0, 0]
        )
        for key in ("a", "b")
    ]
    assert combined == pytest.approx(sum(blocks) / 2, abs=1e-5)


def test_block_l2_keeps_zero_block_finite():
    embeddings = {"a": embedding(2, dim=4), "b": np.zeros((2, 4), dtype=np.float32)}
    assert np.isfinite(build_view(embeddings, ("a", "b"), block_l2=True)).all()
