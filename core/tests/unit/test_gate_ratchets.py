"""래칫을 지키는 도구를 지킨다 — `check_coverage` · `deadcheck` (D-0258).

**둘 다 관문에 서는데 자기 시험이 없었다** (D-0257이 셌다). 래칫이 톱니를 지키는데
그 톱니를 지키는 것이 없으면, 조용히 헐거워진 판정이 몇 판이고 통과한다.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from hathor.shared.config.paths import repo_root


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, repo_root() / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COVERAGE = _tool("check_coverage")
DEAD = _tool("deadcheck")


# ------------------------------------------------------------------ check_coverage


def test_바닥을_pyproject에서_읽는다() -> None:
    """**숫자는 한 곳에만 산다** (D-0223). 정본이 사라지면 조용히 넘어가면 안 된다."""
    assert COVERAGE.floor("[x]\nfail_under = 87\n") == 87.0
    assert COVERAGE.floor("fail_under=87.5\n") == 87.5


def test_바닥이_없으면_터진다() -> None:
    try:
        COVERAGE.floor("[tool.coverage]\n")
    except LookupError as failure:
        assert "fail_under" in str(failure)
    else:
        raise AssertionError("바닥이 사라졌는데 통과했다")


def test_바닥보다_낮으면_막는다() -> None:
    assert COVERAGE.verdict(86.9, 87) is not None


def test_바닥에_닿으면_통과한다() -> None:
    """**경계에서 갈린다.** 같은 값이 미달로 세어지면 매번 바닥을 내리게 된다."""
    assert COVERAGE.verdict(87.0, 87) is None


def test_여유보다_많이_남으면_올리라고_한다() -> None:
    """**5%p가 놀면 그 사이로 시험 없는 코드가 들어온다.**"""
    assert COVERAGE.verdict(87 + COVERAGE.SLACK, 87) is not None
    assert COVERAGE.verdict(87 + COVERAGE.SLACK - 0.01, 87) is None


def test_못을_실측에서_하나_내려_박는다() -> None:
    """기기마다 실측이 1%p 안팎 갈린다 — **실측 그대로 박으면 다른 기기가 빨개진다.**"""
    assert COVERAGE.bumped("fail_under = 87\n", 91.4) == "fail_under = 90\n"


def test_못을_한_번만_바꾼다() -> None:
    """`fail_under`가 주석이나 다른 절에 또 있으면 **둘이 갈린다.**"""
    text = "fail_under = 87\n[other]\nfail_under = 87\n"

    assert COVERAGE.bumped(text, 91.4).count("fail_under = 90") == 1


# ------------------------------------------------------------------ deadcheck


def test_그물이_심은_결함에_운다() -> None:
    """**`deadcheck`의 자가 시험을 시험이 부른다.**

    프로브가 조용히 죽으면 «무검증 시험 0»이 **아무것도 못 본 0**이 된다. `positive_control`이
    임시 폴더에 결함을 심고 우는지 보는데, 그것을 아무도 안 불렀다 (D-0257).
    """
    assert DEAD.positive_control() == []


def test_천장이_프로브를_전부_덮는다() -> None:
    """프로브를 더하고 천장에 안 적으면 **그 부류는 세어도 안 막힌다.**"""
    assert set(DEAD.CEILING) == set(DEAD.PROBES)


def test_늘어도_줄어도_말한다() -> None:
    """**D-0117의 규율이다.** 줄어든 것을 안 말하면 못이 헐거운 채로 남는다."""
    assert DEAD.verdict({"무검증 시험": 1}, {"무검증 시험": 0})
    assert DEAD.verdict({"무검증 시험": 0}, {"무검증 시험": 1})
    assert DEAD.verdict({"무검증 시험": 0}, {"무검증 시험": 0}) == []


def test_빠진_부류는_0으로_센다() -> None:
    """프로브가 죽어 결과가 아예 없으면 **0으로 세어 천장과 어긋나야 한다.**"""
    assert DEAD.verdict({}, {"삼킨 예외": 2})


# ------------------------------------------------------------------ mutate_gate

MUTATE = _tool("mutate_gate")


def test_비교를_뒤집는다() -> None:
    """**«시험이 있다»와 «시험이 민다»는 다르다** (D-0259). 뒤집기가 안 되면 전부 통과한다."""
    import ast

    tree = ast.parse("def f(a, b):\n    return a < b\n")
    flipper = MUTATE.Flipper()

    changed = ast.unparse(ast.fix_missing_locations(flipper.visit(tree)))

    assert flipper.count == 1
    assert "a >= b" in changed


def test_뒤집을_것이_없으면_센_수가_0이다() -> None:
    """비교가 없는 도구를 «울지 않았다»로 세면 **거짓 고발이 된다.**"""
    import ast

    flipper = MUTATE.Flipper()
    flipper.visit(ast.parse("x = 1\n"))

    assert flipper.count == 0


def test_관문_도구를_실제로_찾는다() -> None:
    assert len(MUTATE.gate_tools()) >= 20
