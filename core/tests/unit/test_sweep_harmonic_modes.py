"""배음 강도를 선법으로 나눠 훑는다 (O-57 · D-0197)."""

from __future__ import annotations

import numpy as np

from hathor.application.sweep_harmonic_modes import (
    DEFAULT_STRENGTHS,
    _null_floors,
    sweep_harmonic_modes,
)
from hathor.domain.services.key_estimation import (
    HARMONIC_STRENGTH,
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


def test_고정_집합_바닥이_전체_바닥보다_낮다():
    """**짝이 되는 바닥을 안 붙여 같은 실수가 새 열에서 되풀이됐다** (D-0201).

    귀무에서도 고정 집합은 훨씬 덜 애매하다 — 선법이 안 흔들린 표본만 남기면
    경계가 걸러진다. 그래서 `stable_ambiguous`를 `floor`에 대면 실력을 크게
    부풀려 읽는다.
    """
    full, stable = _null_floors(DEFAULT_STRENGTHS, "krumhansl")

    for strength in DEFAULT_STRENGTHS[1:]:
        assert stable[strength, Mode.MINOR] < full[strength, Mode.MINOR]


def test_전체_바닥은_도메인_정본과_같다():
    """**두 바닥이 다른 난수에서 나오면 안 된다.** 같은 표의 두 열이 갈린다."""
    full, _ = _null_floors(DEFAULT_STRENGTHS, "krumhansl")

    for strength in DEFAULT_STRENGTHS:
        table = random_baseline_by_mode(harmonic=strength)
        for mode in (Mode.MAJOR, Mode.MINOR):
            assert abs(full[strength, mode] - table[mode][1]) < 1e-12


def test_고정초과가_고정바닥을_뺀다():
    """`excess`는 전체끼리, `stable_excess`는 고정끼리. **섞으면 안 된다.**"""
    chromas = [_rotated(KRUMHANSL_MAJOR, step) for step in range(12)]
    chromas += [_rotated(KRUMHANSL_MINOR, step) for step in range(12)]

    cell = sweep_harmonic_modes(chromas).rows[0].cell(Mode.MAJOR)

    assert abs(cell.stable_excess - (cell.stable_ambiguous - cell.stable_floor) * 100) < 1e-9
    assert cell.stable_floor != cell.floor


def test_기본값이_실측에서_왔다():
    """**D-0059를 뒤집었다** (D-0201). 켜는 것이 기본이다."""
    assert HARMONIC_STRENGTH == 0.5
