"""짝지은 차이와 두 판정 (D-0327).

**옛 규칙에는 떨어질 수 있는 검사가 하나도 없었다.** `가 > 0 and 승률 > 0.5`가 진짜
차이 0에서 50% 통과하는데, 통과하는 자료만 넣은 검사가 붙어 있어 전부 초록이었다.

여기 있는 검사는 **음성 자료에서 규칙이 떨어지는지**를 본다 — 그것이 규칙의 값이다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.compare_output import PAIRED_T_FLOOR, PairedGap, gap_of


def _noise(size: int, *, shift: float, seed: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """같은 쌍에서 나온 두 줄. `shift`가 0이면 **참 차이가 0이다.**"""
    rng = np.random.default_rng(seed)
    shared = rng.normal(0.25, 0.20, size)  # 곡 사이 변동 — 짝지으면 지워진다
    left = shared + rng.normal(shift, 0.03, size)
    right = shared + rng.normal(0.0, 0.03, size)
    return tuple(float(v) for v in left), tuple(float(v) for v in right)


# ------------------------------------------------------------------ 짝지은 차이


def test_쌍_수가_다르면_거부한다() -> None:
    """**길이가 다르면 짝지은 차이가 아니다.** 조용히 자르면 무엇을 뺀 것인지 모른다."""
    with pytest.raises(ValueError, match="쌍 수가 다르면"):
        PairedGap(target=(0.1, 0.2), baseline=(0.1,))


def test_오차를_못_재면_통과시키지_않는다() -> None:
    """쌍이 하나면 표준오차가 없다. **없는 것을 0이라 하지 않는다** (GR-0.5).

    0으로 두면 `t`가 무한이 되어 **한 점짜리 자료가 가장 강한 증거가 된다.**
    """
    one = PairedGap(target=(0.9,), baseline=(0.1,))
    assert one.gain == pytest.approx(0.8)
    assert one.standard_error == 0.0
    assert one.t == 0.0
    assert one.beats is False


def test_짝지으면_곡_사이_변동이_지워진다() -> None:
    """**선별 표준오차를 쓰면 안 되는 이유다** (D-0311).

    두 줄 각각의 표준편차는 곡 사이 변동(0.08)이 지배하고, 차이의 표준편차는
    거기서 벗어나 훨씬 작다. 따로 재면 **있는 신호를 없다고 말한다.**
    """
    left, right = _noise(200, shift=0.02, seed=3)
    gap = gap_of(left, right)
    apart = float(np.std(left, ddof=1) / np.sqrt(len(left)))
    assert gap.standard_error < apart / 3.0
    assert gap.t > PAIRED_T_FLOOR


# ------------------------------------------------------------------ 규칙이 떨어진다


def test_참_차이가_0이면_거의_다_떨어진다() -> None:
    """**이것이 옛 규칙이 못 한 것이다** (D-0327).

    `가 > 0 and 승률 > 0.5`는 여기서 절반쯤 통과한다 — 부호와 승률이 같은 방향으로
    움직이기 때문이다. 합성 1000곡 24회에서 **50%였다.**
    """
    passes = 0
    old_rule = 0
    trials = 40
    for seed in range(trials):
        gap = gap_of(*_noise(100, shift=0.0, seed=seed))
        passes += gap.beats
        old_rule += gap.gain > 0.0 and gap.win_rate > 0.5
    assert passes <= trials * 0.1, f"오경보가 {passes}/{trials}다"
    assert old_rule > passes * 3, "옛 규칙이 더 무르지 않으면 이 검사가 의미가 없다"


def test_참_차이가_있으면_잡는다() -> None:
    """**질 수만 있는 규칙도 규칙이 아니다** (O-25 (2)). 양방향으로 확인한다 (D-0303)."""
    caught = sum(gap_of(*_noise(100, shift=0.02, seed=seed)).beats for seed in range(20))
    assert caught == 20


def test_음수_쪽으로_큰_차이는_통과가_아니다() -> None:
    """**부호를 본다.** `t`의 크기만 보면 반대 방향이 통과한다 (D-0315)."""
    gap = gap_of(*_noise(100, shift=-0.05, seed=11))
    assert gap.t < -PAIRED_T_FLOOR
    assert gap.beats is False


def test_승률은_판정이_아니다() -> None:
    """승률 과반이어도 `t`가 낮으면 떨어진다 — **실물이 52.0%로 통과했던 자리다.**

    쌍 60개 중 **52개가 아주 조금 이기고** 8개가 크게 진다. 승률 86.7%에 이득은
    음수다. 승률만으로는 이 자료가 통과한다.
    """
    differences = [0.001] * 52 + [-0.30] * 8
    gap = PairedGap(target=tuple(differences), baseline=(0.0,) * 60)
    assert gap.win_rate > 0.8
    assert gap.gain < 0.0
    assert gap.beats is False
