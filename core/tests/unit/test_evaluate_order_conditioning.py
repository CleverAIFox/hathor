"""배열 조건화 판정의 단위 검사 (O-32 · D-0112)."""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.evaluate_harmony_output import OutputCondition, ReferencePrior
from hathor.application.evaluate_order_conditioning import (
    EvaluateOrderConditioning,
    OrderReference,
    holding_indices,
    references_from,
    restrict_transition,
    sweep_self_transition,
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


# ------------------------------------------------------------------ 곡 단위 (D-0113)


def test_표본이_곡_수와_같다():
    """**시드는 곡 안의 반복이지 표본이 아니다** (D-0113).

    시드마다 하나씩 세면 같은 곡의 시드들이 **같은 전이 사전을 쓰므로** 독립이
    아니다. 실측 200곡x200시드에서 `t = 531`이 나왔고 곡 단위로는 38이었다.
    """
    made = _references(12)
    report = EvaluateOrderConditioning(OutputCondition(seed_count=15, bar_count=32)).run(made)
    assert len(report.self_distances) == len(made)
    assert len(report.other_distances) == len(made)


def test_시드를_늘려도_표본_수가_안_는다():
    """**늘어나면 표준오차가 가짜로 줄어든다.**"""
    made = _references(10)
    few = EvaluateOrderConditioning(OutputCondition(seed_count=5, bar_count=32)).run(made)
    many = EvaluateOrderConditioning(OutputCondition(seed_count=40, bar_count=32)).run(made)
    assert len(few.self_distances) == len(many.self_distances) == len(made)


def test_곡_승률이_곡_단위다():
    """D-0062가 \"곡 과반\"이라 한 것은 곡 단위였다."""
    made = _references(20)
    report = EvaluateOrderConditioning(OutputCondition(seed_count=15, bar_count=32)).run(made)
    wins = sum(
        1
        for mine, theirs in zip(report.self_distances, report.other_distances, strict=True)
        if theirs > mine
    )
    assert report.win_rate == pytest.approx(wins / len(made))


# ------------------------------------------------- 자기 전이 훑기 (O-38·D-0114)


def test_훑기가_모든_칸을_낸다():
    made = _references(12)
    rows = sweep_self_transition(made, (0.0, 0.3), (8, 16), FAST)
    assert [(row[0], row[1]) for row in rows] == [(0.0, 8), (0.0, 16), (0.3, 8), (0.3, 16)]


def test_훑기의_0_0_칸은_현행과_같다():
    """**비교선이 현행이어야 읽을 수 있다** (O-25 (1))."""
    made = _references(12)
    from dataclasses import replace

    expected = EvaluateOrderConditioning(replace(FAST, bar_count=8)).run(made)
    assert sweep_self_transition(made, (0.0,), (8,), FAST)[0][2] == expected.gap


def test_자기_전이가_판정을_움직인다():
    """**손잡이가 지표에 닿는지부터 본다** (D-0064). 방향은 실측이 정한다."""
    made = _references(12)
    rows = sweep_self_transition(made, (0.0, 0.6), (8,), FAST)
    assert rows[0][2] != rows[1][2]


# ---------------------------------------------------------------- 곡별 유지 (O-37·D-0125)


def _with_holds(holds: list[float]) -> list[OrderReference]:
    """같은 사전·같은 전이, `hold`만 다른 참조곡들."""
    from dataclasses import replace

    base = _references(len(holds), seed=11)
    return [replace(item, hold=value) for item, value in zip(base, holds, strict=True)]


def test_hold_기본값은_현행과_한_비트도_다르지_않다():
    """D-0109가 검사로 고정한 규율. 기본 경로가 안 바뀌어야 한다."""
    references = _with_holds([0.0, 0.0, 0.0])
    plain = EvaluateOrderConditioning(FAST).run(references)
    held = EvaluateOrderConditioning(FAST).run(references, use_hold=True)
    assert held.self_distances == plain.self_distances
    assert held.other_distances == plain.other_distances


def test_holds를_주면_곡마다_물린다():
    made = _references(3)
    priors = [ReferencePrior(item.source_key, item.prior) for item in made]
    table = {item.source_key: item.transition for item in made}
    holds = {made[0].source_key: 0.4, made[2].source_key: 0.7}
    built = references_from(priors, table, holds)
    assert [item.hold for item in built] == [0.4, 0.0, 0.7]


def test_holds를_안_주면_전부_0이다():
    """**기본값이 현행이다.** 이 인자가 생겨도 예전 호출이 안 바뀐다."""
    made = _references(3)
    priors = [ReferencePrior(item.source_key, item.prior) for item in made]
    table = {item.source_key: item.transition for item in made}
    assert all(item.hold == 0.0 for item in references_from(priors, table))


def test_유지_확률이_곡을_거르지_않는다():
    """**선마다 표본이 다르면 짝지은 차이가 아니다** (D-0113).

    `holds`에 없는 곡도 남아야 두 선이 같은 곡들 위에서 비교된다.
    """
    made = _references(3)
    priors = [ReferencePrior(item.source_key, item.prior) for item in made]
    table = {item.source_key: item.transition for item in made}
    assert len(references_from(priors, table, {made[1].source_key: 0.5})) == 3


def test_움직이는_곡만_고른다():
    """**D-0123이 남긴 49곡(4.9%)을 따로 보기 위한 것이다.**"""
    assert holding_indices(_with_holds([0.0, 0.3, 0.0, 0.5])) == (1, 3)


def test_부분집합이_같은_거리를_그대로_쓴다():
    """**다시 돌리면 `other` 추첨이 달라져 두 표를 못 견준다.**"""
    references = _with_holds([0.0, 0.2, 0.0, 0.4, 0.1])
    report = EvaluateOrderConditioning(OutputCondition(seed_count=10, bar_count=32)).run(references)
    picked = report.restricted_to((1, 3))
    assert picked.reference_count == 2
    assert picked.self_distances == (report.self_distances[1], report.self_distances[3])
    assert picked.other_distances == (report.other_distances[1], report.other_distances[3])


def test_부분집합도_같은_판정_규칙을_쓴다():
    references = _with_holds([0.0] * 10)
    report = EvaluateOrderConditioning(OutputCondition(seed_count=10, bar_count=32)).run(references)
    picked = report.restricted_to(range(len(references)))
    assert picked.gap == pytest.approx(report.gap)
    assert picked.carries_reference_order == report.carries_reference_order


def test_hold는_0과_1_사이여야_한다():
    """1.0이면 첫 화음이 영원히 유지된다. 생성기가 요구하는 범위와 같다."""
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(_references(1)[0], hold=1.0)
    with pytest.raises(ValueError):
        replace(_references(1)[0], hold=-0.1)


def test_hold와_self_transition은_같이_못_쓴다():
    """섞으면 어느 쪽이 값을 움직였는지 못 가린다."""
    with pytest.raises(ValueError):
        EvaluateOrderConditioning(FAST).run(
            _with_holds([0.3, 0.3]), use_hold=True, self_transition=0.2
        )


def test_hold는_곡마다_다른_값이_쓰인다():
    """**하나를 코퍼스에 고르는 것이 아니다** (O-37·D-0125).

    전역 손잡이라면 두 실행이 같은 결과를 낼 자리에서 갈려야 한다.
    """
    mixed = EvaluateOrderConditioning(FAST).run(_with_holds([0.0, 0.9, 0.0]), use_hold=True)
    uniform = EvaluateOrderConditioning(FAST).run(_with_holds([0.0, 0.0, 0.0]), use_hold=True)
    assert mixed.self_distances != uniform.self_distances
    # **첫 곡은 hold가 0이라 안 움직여야 한다.** 움직이면 곡 경계가 샌 것이다
    assert mixed.self_distances[0] == uniform.self_distances[0]
