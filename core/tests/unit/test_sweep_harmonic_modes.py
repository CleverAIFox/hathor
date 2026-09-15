"""배음 강도를 선법으로 나눠 훑는다 (O-57 · D-0197)."""

from __future__ import annotations

import numpy as np

from hathor.application.sweep_harmonic_modes import DEFAULT_STRENGTHS, sweep_harmonic_modes
from hathor.domain.services.key_estimation import (
    KRUMHANSL_MAJOR,
    KRUMHANSL_MINOR,
    random_baseline,
    random_baseline_by_mode,
)
from hathor.domain.value_objects.key import Mode


def _rotated(profile: tuple[float, ...], semitones: int) -> list[float]:
    vector = np.roll(np.asarray(profile, dtype=np.float64), semitones)
    return list(vector / vector.sum())


def test_선법별_바닥이_전체_바닥과_다르다():
    """**이것이 D-0191의 읽기를 뒤집은 실측이다.**

    전체 바닥 하나를 두 선법에 같이 대면 단조가 실제보다 좋아 보인다.
    """
    _, margins = random_baseline(harmonic=0.0)
    pooled = float((margins < 0.05).mean())
    table = random_baseline_by_mode(harmonic=0.0)

    major = table[Mode.MAJOR][1]
    minor = table[Mode.MINOR][1]
    assert major > pooled > minor
    # 6%p 넘게 벌어진다. 이 격차가 작았다면 나눌 이유가 없었다.
    assert major - minor > 0.06


def test_감산이_귀무를_단조_쪽으로_민다():
    """**배음 감산은 중립이 아니다.** 추정기 자체가 단조로 기운다.

    코퍼스의 선법 구성비가 강도마다 달라진다는 뜻이며, 그래서 선법별 애매율을
    강도끼리 비교하려면 고정 집합이 필요하다.
    """
    weak = random_baseline_by_mode(harmonic=0.0)[Mode.MINOR][0]
    strong = random_baseline_by_mode(harmonic=1.0)[Mode.MINOR][0]
    assert strong > weak


def test_선법이_안_바뀌면_고정_집합이_전부다():
    """뚜렷한 프로파일 벡터는 강도를 올려도 선법을 안 갈아탄다."""
    chromas = [_rotated(KRUMHANSL_MAJOR, step) for step in range(12)]
    chromas += [_rotated(KRUMHANSL_MINOR, step) for step in range(12)]

    sweep = sweep_harmonic_modes(chromas)

    assert sweep.song_count == 24
    assert sweep.stable_count == 24
    assert all(row.moved == 0 for row in sweep.rows)


def test_선법별_칸이_분해된다():
    """장조 12곡 · 단조 12곡이 칸으로 갈린다. **합이 곡 수여야 한다.**"""
    chromas = [_rotated(KRUMHANSL_MAJOR, step) for step in range(12)]
    chromas += [_rotated(KRUMHANSL_MINOR, step) for step in range(12)]

    row = sweep_harmonic_modes(chromas).rows[0]

    assert row.cell(Mode.MAJOR).count + row.cell(Mode.MINOR).count == 24
    assert abs(row.cell(Mode.MAJOR).share + row.cell(Mode.MINOR).share - 1.0) < 1e-9


def test_초과는_그_선법의_바닥을_뺀다():
    """**`floor`가 전체 바닥이면 안 된다** — 칸마다 자기 선법의 바닥을 든다."""
    chromas = [_rotated(KRUMHANSL_MAJOR, step) for step in range(12)]
    chromas += [_rotated(KRUMHANSL_MINOR, step) for step in range(12)]

    row = sweep_harmonic_modes(chromas).rows[0]
    table = random_baseline_by_mode(harmonic=0.0)

    for mode in (Mode.MAJOR, Mode.MINOR):
        cell = row.cell(mode)
        assert cell.floor == table[mode][1]
        assert abs(cell.excess - (cell.ambiguous - cell.floor) * 100) < 1e-9


def test_합이_0인_크로마는_빠진다():
    """감산이 벡터를 통째로 지우면 그 곡은 못 센다."""
    chromas = [_rotated(KRUMHANSL_MAJOR, 0), [0.0] * 12]

    sweep = sweep_harmonic_modes(chromas)

    assert sweep.song_count == 1


def test_강도는_다섯이_기본이다():
    """D-0060이 고른 다섯을 그대로 쓴다."""
    chromas = [_rotated(KRUMHANSL_MAJOR, step) for step in range(12)]

    sweep = sweep_harmonic_modes(chromas)

    assert tuple(row.strength for row in sweep.rows) == DEFAULT_STRENGTHS
