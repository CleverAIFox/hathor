"""전이 사전의 단위 검사 (O-32 · D-0107)."""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services.transition_prior import (
    is_empty,
    transition_prior,
    transition_row,
)

DEGREES = 12
MAJOR_ROOTS = (0, 2, 4, 5, 7, 9)


def _windows(order: list[int], sharpness: float = 40.0) -> list[list[float]]:
    """도수 하나가 뚜렷한 창을 이어 붙인다."""
    made = []
    for cell in order:
        vector = np.full(DEGREES, 1.0)
        vector[cell] = sharpness
        made.append(list(vector / vector.sum()))
    return made


def test_다음_도수가_행에_들어간다():
    matrix = transition_prior(_windows([0, 7, 0, 7]))
    assert matrix[0, 7] > matrix[7, 2]
    assert matrix[7, 0] > matrix[0, 2]


def test_대각선을_버린다():
    """**자기 전이는 창 길이가 정한다** (D-0103)."""
    matrix = transition_prior(_windows([0, 0, 0, 7]))
    assert matrix.diagonal() == pytest.approx(np.zeros(DEGREES))


@pytest.mark.parametrize("hold", [2, 3, 8])
def test_창_길이에_정확히_불변이다(hold):
    """**D-0103의 근거가 통째로 여기 걸려 있다.**

    부드러운 집계를 써 봤더니 잡음 바닥끼리의 외적이 유지 길이에 비례해 쌓여
    불변이 깨졌다. **정확도가 조금 낫더라도 불변을 잃으면 안 된다.**
    """
    quick = transition_prior(_windows([0, 7, 5, 9]))
    held = transition_prior(_windows([c for c in [0, 7, 5, 9] for _ in range(hold)]))
    assert quick == pytest.approx(held, abs=1e-12)


def test_합이_1이다():
    assert transition_prior(_windows([0, 7, 5])).sum() == pytest.approx(1.0)


def test_창이_둘_미만이면_빈_사전이다():
    """**없는 것을 있는 척하지 않는다** (GR-0.5)."""
    assert is_empty(transition_prior(_windows([0])))
    assert is_empty(transition_prior([]))


def test_한_도수만_나오면_빈_사전이다():
    """자기 전이뿐이면 대각선을 버린 뒤 아무것도 안 남는다."""
    assert is_empty(transition_prior(_windows([4, 4, 4, 4])))


def test_모양이_틀리면_거부한다():
    with pytest.raises(ValueError, match="12"):
        transition_prior([[0.5, 0.5]])


def test_애매한_창에서_임의로_집는다():
    """**`argmax`가 남기는 자의성이다.** 숨기지 않고 검사로 적어 둔다.

    두 도수가 거의 같은 창에서 어느 쪽을 고를지는 부동소수 비교가 정한다.
    부드러운 집계는 이것을 없애지만 창 길이 불변을 깨서 안 쓴다.
    """
    matrix = transition_prior(_windows([0, 7], sharpness=1.0001))
    assert matrix.sum() == pytest.approx(1.0)


# ------------------------------------------------------------------ 행 뽑기


def test_행이_코드_풀만_남긴다():
    row = transition_row(transition_prior(_windows([0, 7, 0, 7])), 0, MAJOR_ROOTS)
    assert len(row) == len(MAJOR_ROOTS)
    assert sum(row) == pytest.approx(1.0)
    assert row[MAJOR_ROOTS.index(7)] == max(row)


def test_빈_행은_열_합으로_되돌린다():
    """그 도수가 참조곡에 안 나왔다는 뜻이므로 **곡 전체의 도착 빈도**를 쓴다."""
    matrix = transition_prior(_windows([0, 7, 0, 7]))
    row = transition_row(matrix, 4, MAJOR_ROOTS)
    assert sum(row) == pytest.approx(1.0)
    assert row[MAJOR_ROOTS.index(0)] > 0.1


def test_빈_사전이면_균등이다():
    empty = np.zeros((DEGREES, DEGREES))
    row = transition_row(empty, 0, MAJOR_ROOTS)
    assert row == pytest.approx((1 / 6,) * 6)
