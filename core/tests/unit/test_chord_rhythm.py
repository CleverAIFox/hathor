"""화성 리듬 검사 (O-37).

**합성으로 회수되는지 먼저 본다.** 안 되면 실측 숫자를 읽을 이유가 없다.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from hathor.domain.services.chord_rhythm import (
    BUNDLES,
    bundle,
    curve,
    half_fall,
    hold_probability,
    limit_spikiness,
    measure,
    shuffled,
    spikiness,
)

DEGREE_COUNT = 12


def synth(chord_windows: int, total: int = 960, noise: float = 0.25, seed: int = 0) -> np.ndarray:
    """`chord_windows`창마다 화음이 바뀌는 시계열."""
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    current = int(rng.integers(0, DEGREE_COUNT))
    for index in range(total):
        if index % chord_windows == 0 and index:
            current = (current + int(rng.integers(1, DEGREE_COUNT))) % DEGREE_COUNT
        row = np.full(DEGREE_COUNT, noise, dtype=np.float64)
        for offset in (0, 4, 7):
            row[(current + offset) % DEGREE_COUNT] += 1.0
        rows.append(np.maximum(row + rng.normal(0.0, noise, DEGREE_COUNT), 0.0))
    return np.asarray(rows)


def test_spikiness_is_one_twelfth_for_uniform():
    assert spikiness(np.ones((4, DEGREE_COUNT))) == pytest.approx(1.0 / DEGREE_COUNT)


def test_spikiness_is_one_for_single_pitch():
    row = np.zeros((3, DEGREE_COUNT))
    row[:, 0] = 1.0
    assert spikiness(row) == pytest.approx(1.0)


def test_bundle_averages_exactly():
    """**크로마는 시간 평균이므로 정확히 `size`배 긴 창이다** (D-0104)."""
    series = np.arange(8 * DEGREE_COUNT, dtype=np.float64).reshape(8, DEGREE_COUNT)
    grouped = bundle(series, 2)
    assert grouped.shape == (4, DEGREE_COUNT)
    assert grouped[0] == pytest.approx((series[0] + series[1]) / 2.0)


def test_bundle_drops_the_tail():
    """길이가 다른 창을 섞으면 뾰족함이 창 길이만으로 달라진다."""
    series = np.ones((7, DEGREE_COUNT))
    assert len(bundle(series, 3)) == 2


def test_bundle_returns_empty_when_too_short():
    assert len(bundle(np.ones((2, DEGREE_COUNT)), 5)) == 0


def test_limit_is_the_whole_song_as_one_window():
    series = synth(4, total=120, seed=1)
    assert limit_spikiness(series) == pytest.approx(spikiness(series.mean(axis=0, keepdims=True)))


def test_half_fall_is_none_when_flat():
    """올라가기만 하거나 평평하면 없는 것을 있는 척하지 않는다 (GR-0.5)."""
    assert half_fall([(1, 0.5), (2, 0.5), (4, 0.5)], floor=0.5) is None


def test_half_fall_interpolates_between_grid_points():
    """**연속값이어야 한다.** 격자 위 정수로 뭉치면 곡이 안 갈린다."""
    value = half_fall([(1, 1.0), (2, 0.0), (4, 0.0)], floor=0.0)
    assert value is not None
    assert 1.0 < value < 2.0


def test_half_fall_needs_three_points():
    assert half_fall([(1, 1.0), (2, 0.0)], floor=0.0) is None


@pytest.mark.parametrize("truth", [2, 4, 8, 16])
def test_measure_rises_with_chord_length(truth):
    """참 화음 길이가 길수록 반감점도 길다. **순서만 본다** — 눈금이 아니다."""
    shorter = float(np.median([measure(synth(truth // 2, seed=s)) or 0.0 for s in range(4)]))
    longer = float(np.median([measure(synth(truth, seed=s)) or 0.0 for s in range(4)]))
    assert longer > shorter


def test_measure_is_monotone_in_log():
    truths = [2, 4, 8, 16]
    values = [
        float(np.median([measure(synth(t, seed=s)) or 0.0 for s in range(6)])) for t in truths
    ]
    assert all(left < right for left, right in pairwise(values))
    assert float(np.corrcoef(np.log(truths), np.log(values))[0, 1]) > 0.95


def test_shuffled_keeps_every_window():
    """크로마 분포·잡음·곡 고유 어휘는 그대로고 **시간 구조만 죽는다.**"""
    series = synth(4, total=60, seed=2)
    mixed = shuffled(series)
    assert sorted(map(tuple, mixed.tolist())) == sorted(map(tuple, series.tolist()))


def test_shuffled_is_deterministic():
    series = synth(4, total=60, seed=2)
    assert np.array_equal(shuffled(series), shuffled(series))


def test_hold_probability_is_zero_without_persistence():
    """**질 수 있는가** (O-25 (2)). 화음이 안 이어지면 유지 확률이 0이어야 한다.

    합성 대조에서 참 길이 1창은 `t = -12.9`로 졌다. 여기서 0이 안 나오면
    하네스가 고장이므로 실측 숫자를 읽지 않는다.
    """
    assert hold_probability(synth(1, seed=3)) == 0.0


@pytest.mark.parametrize("truth", [4, 8, 16])
def test_hold_probability_is_positive_with_persistence(truth):
    assert hold_probability(synth(truth, seed=3)) > 0.2


def test_hold_probability_rises_with_chord_length():
    values = [hold_probability(synth(t, seed=4)) for t in (2, 4, 8, 16)]
    assert all(left < right for left, right in pairwise(values))


def test_hold_probability_stays_below_one():
    """`generate_harmony`가 `[0, 1)`을 요구한다. 1.0이면 영원히 안 바뀐다."""
    assert hold_probability(synth(64, total=960, noise=0.01, seed=5)) < 1.0


def test_hold_probability_is_zero_for_degenerate_input():
    assert hold_probability(np.ones((3, DEGREE_COUNT))) == 0.0


def test_curve_stops_when_windows_run_out():
    points = curve(synth(2, total=20, seed=6))
    assert len(points) < len(BUNDLES)
    assert points[0][0] == 1
