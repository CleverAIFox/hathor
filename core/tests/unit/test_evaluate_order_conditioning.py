"""배열 조건화 판정의 단위 검사 (O-32 · D-0112)."""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_harmony_output import OutputCondition, ReferencePrior
from hathor.application.evaluate_order_conditioning import (
    EvaluateOrderConditioning,
    OrderReference,
    references_from,
    restrict_transition,
)
from hathor.domain.value_objects.key import Mode
from hathor.engines.compose.harmony_generator import vocabulary_roots

DEGREES = 12
ROOTS = vocabulary_roots(Mode.MAJOR)
FAST = OutputCondition(seed_count=40, bar_count=64)


def _references(count: int, seed: int = 7) -> list[OrderReference]:
    """곡마다 다른 전이 사전. **대각선은 비어 있다** (D-0103)."""
    rng = np.random.default_rng(seed)
    made: list[OrderReference] = []
    for index in range(count):
        matrix = np.zeros((DEGREES, DEGREES))
        for left in ROOTS:
            for right in ROOTS:
                if left != right:
                    matrix[left, right] = rng.lognormal(0.0, 1.3)
        matrix /= matrix.sum()
        prior = rng.dirichlet(np.full(DEGREES, 3.0))
        made.append(
            OrderReference(
                source_key=f"곡{index:03d}.flac",
                prior=tuple(float(v) for v in prior / prior.sum()),
                transition=tuple(tuple(float(v) for v in row) for row in matrix),
            )
        )
    return made


# ------------------------------------------------------------------ 판정


def test_전이_사전을_주면_그_곡의_배열을_담는다():
    report = EvaluateOrderConditioning(FAST).run(_references(30))
    assert report.gap > 0.0
    assert report.win_rate > 0.5
    assert report.carries_reference_order


def test_전이_사전이_없으면_안_담는다():
    """**음성 대조.** 순서를 시드가 정하면 self와 other가 같아야 한다 (D-0062)."""
    report = EvaluateOrderConditioning(FAST).run(_references(30), use_transition=False)
    assert abs(report.gap) < 0.02
    assert not report.carries_reference_order


def test_문턱이_승인_문턱이다():
    """**이 판정이 O-32를 닫는다** (D-0098의 규율)."""
    strong = EvaluateOrderConditioning(FAST).run(_references(30))
    assert strong.t_statistic > 3.0


# ------------------------------------------------------------------ 자리 맞추기


def test_전이_사전을_코드_풀로_좁힌다():
    """사전은 12x12이고 출력 전이는 코드 풀 크기다. **같은 자리에 놓아야 한다.**"""
    matrix = np.ones((DEGREES, DEGREES))
    restricted = restrict_transition(matrix, ROOTS)
    assert restricted.shape == (len(ROOTS), len(ROOTS))
    assert restricted.sum() == pytest.approx(1.0)


def test_좁힐_때도_대각선을_버린다():
    """**자기 전이는 창 길이가 정한다** (D-0103). 비교에 쓸 수 없다."""
    matrix = np.eye(DEGREES) * 5.0 + 1.0
    restricted = restrict_transition(matrix, ROOTS)
    assert restricted.diagonal() == pytest.approx(np.zeros(len(ROOTS)))


def test_비어_있는_사전을_좁히면_0이다():
    """**0으로 나누지 않는다.**"""
    assert restrict_transition(np.zeros((DEGREES, DEGREES)), ROOTS).sum() == 0.0


# ------------------------------------------------------------------ 곁가지


def test_other를_여러_곡에서_뽑는다():
    """**한 곡만 쓰면 코퍼스 순서에 값이 달린다.**"""
    from hathor.application.evaluate_order_conditioning import OTHER_SAMPLES

    assert OTHER_SAMPLES > 1


def test_둘_다_있는_곡만_남긴다():
    made = _references(3)
    priors = [ReferencePrior(item.source_key, item.prior) for item in made]
    priors.append(ReferencePrior("전이없는곡.flac", made[0].prior))
    table = {item.source_key: item.transition for item in made}
    assert len(references_from(priors, table)) == 3


def test_같은_시드는_같은_수를_낸다():
    made = _references(20)
    first = EvaluateOrderConditioning(FAST).run(made)
    second = EvaluateOrderConditioning(FAST).run(made)
    assert first.gap == second.gap


@pytest.mark.parametrize(
    "field,value", [("prior", (0.1,) * 11), ("transition", ((0.0,) * 12,) * 11)]
)
def test_모양이_틀리면_거부한다(field, value):
    base = _references(1)[0]
    kwargs = {"source_key": base.source_key, "prior": base.prior, "transition": base.transition}
    kwargs[field] = value
    with pytest.raises(ValueError):
        OrderReference(**kwargs)


def test_참조곡이_둘_미만이면_거부한다():
    with pytest.raises(ValueError, match="2개 이상"):
        EvaluateOrderConditioning(FAST).run(_references(1))
