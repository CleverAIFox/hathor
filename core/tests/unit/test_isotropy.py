"""등방화 테스트."""

import numpy as np
import pytest

from hathor.domain.services.isotropy import anisotropy, center, mean_direction


def cone(count: int = 20, spread: float = 0.05) -> np.ndarray:
    """공통 방향이 강한 벡터 다발. 실제 임베딩에서 관측된 형태다."""
    generator = np.random.default_rng(3)
    shared = np.zeros(8, dtype=np.float32)
    shared[0] = 1.0
    noise = generator.normal(0.0, spread, size=(count, 8))
    return np.asarray(shared + noise, dtype=np.float32)


def test_anisotropy_is_high_for_cone():
    assert anisotropy(cone()) > 0.9


def test_anisotropy_is_low_for_orthogonal_rows():
    assert anisotropy(np.eye(6, dtype=np.float32)) == pytest.approx(0.0, abs=1e-6)


def test_anisotropy_excludes_self_similarity():
    """대각을 포함하면 곡 수가 적을수록 값이 커져 코퍼스 간 비교가 깨진다."""
    assert anisotropy(np.eye(3, dtype=np.float32)) == pytest.approx(
        anisotropy(np.eye(30, dtype=np.float32)), abs=1e-6
    )


def test_anisotropy_of_single_row_is_zero():
    assert anisotropy(np.ones((1, 4), dtype=np.float32)) == 0.0


def test_centering_reduces_anisotropy():
    matrix = cone()
    centered = center(matrix, mean_direction(matrix))
    assert anisotropy(centered) < anisotropy(matrix)


def test_mean_direction_is_unit_length():
    assert np.linalg.norm(mean_direction(cone())) == pytest.approx(1.0)


def test_mean_direction_ignores_magnitude():
    """노름을 그대로 두면 음량이 큰 곡이 중심을 끌고 간다."""
    quiet = np.asarray([[0.01, 0.0], [0.0, 0.01]], dtype=np.float32)
    loud = np.asarray([[100.0, 0.0], [0.0, 0.01]], dtype=np.float32)
    assert np.allclose(mean_direction(quiet), mean_direction(loud), atol=1e-5)


def test_mean_direction_of_isotropic_is_zero():
    axes = np.concatenate([np.eye(4), -np.eye(4)]).astype(np.float32)
    assert np.allclose(mean_direction(axes), 0.0)


def test_center_with_zero_direction_is_identity():
    matrix = cone()
    assert np.array_equal(center(matrix, np.zeros(8, dtype=np.float32)), matrix)


def test_center_removes_projection_not_constant():
    """상수를 빼면 노름이 작은 벡터의 방향이 통째로 뒤집힌다."""
    direction = np.asarray([1.0, 0.0], dtype=np.float32)
    matrix = np.asarray([[10.0, 1.0], [0.1, 1.0]], dtype=np.float32)
    result = center(matrix, direction)
    assert np.allclose(result[:, 0], 0.0, atol=1e-5)
    assert np.allclose(result[:, 1], [1.0, 1.0])


def test_center_rejects_dimension_mismatch():
    with pytest.raises(ValueError):
        center(np.zeros((2, 4), np.float32), np.zeros(3, np.float32))


def test_mean_direction_rejects_empty():
    with pytest.raises(ValueError):
        mean_direction(np.zeros((0, 4), dtype=np.float32))


def test_centering_breaks_hub_dominance():
    """중심에 가까운 곡이 여러 질의의 1위를 독차지하는 현상이 완화되어야 한다.

    허브는 중심 방향과 코사인이 가장 큰 곡이다. 노름이 가장 긴 곡이 아니다 —
    그렇게 잡으면 음량이 큰 곡을 허브로 오인한다.
    """
    generator = np.random.default_rng(11)
    shared = np.zeros(16, dtype=np.float32)
    shared[0] = 1.0
    matrix = np.asarray(shared + generator.normal(0.0, 0.15, size=(60, 16)), dtype=np.float32)
    direction = mean_direction(matrix)
    units = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    hub = int(np.argmax(units @ direction))

    def nearest_neighbours(data: np.ndarray) -> list[int]:
        norms = np.linalg.norm(data, axis=1, keepdims=True)
        rows = data / np.where(norms < 1e-12, 1.0, norms)
        similarity = rows @ rows.T
        np.fill_diagonal(similarity, -np.inf)
        return [int(row) for row in np.argmax(similarity, axis=1)]

    before = nearest_neighbours(matrix).count(hub)
    after = nearest_neighbours(center(matrix, direction)).count(hub)
    assert before >= 5
    assert after < before
