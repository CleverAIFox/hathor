"""래칫을 지키는 도구를 지킨다 — `check_coverage` · `deadcheck` (D-0258).

**둘 다 관문에 서는데 자기 시험이 없었다** (D-0257이 셌다). 래칫이 톱니를 지키는데
그 톱니를 지키는 것이 없으면, 조용히 헐거워진 판정이 몇 판이고 통과한다.
"""

from __future__ import annotations

import pytest

from tests.conftest import tool_module as _tool

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

# ------------------------------ 낮은 파이썬에서는 아무 수도 내지 않는다 (D-0275)


def test_저장소가_요구하는_파이썬을_한_곳에서_읽는다() -> None:
    """**정본은 `core/pyproject.toml`이다.** 손으로 적으면 두 곳이 어긋난다 (D-0199)."""
    assert DEAD.python_floor() == (3, 12)


def test_낮은_파이썬이면_돌기를_거부한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**«0건»이 거짓이 되는 자리다** (D-0275).

    `ast`가 `type X = …`(PEP 695)를 3.12부터 안다. 3.11에서는 그 문장이 든 파일이
    `SyntaxError`가 되고 `parsed`가 그것을 삼켜 **다섯 프로브에서 조용히 빠졌다** —
    작성자의 컨테이너가 3.11이라 9파일이 안 보였고, 결함 8건을 **초록으로** 내보냈다.
    사용자 기기(3.12)에서 터졌다.

    이 저장소가 반복해 당한 «검사가 있는데 안 운다»가 **그 검사 자신에게** 난 자리다.
    """
    assert DEAD.too_old() == ""

    monkeypatch.setattr(DEAD.sys, "version_info", (3, 11, 15))
    reason = DEAD.too_old()
    assert "3.11.15" in reason and "3.12" in reason


def test_못_읽는_파일을_센다() -> None:
    """**양성 대조** (D-0230). 어느 파이썬도 못 읽는 파일을 심어 우는지 본다."""
    assert DEAD.planted_unreadable()
    assert DEAD.unreadable() == [], "이 파이썬이 저장소를 다 못 읽는다"


def test_타입_별칭_뒤의_문서_문자열은_정상이다() -> None:
    """**닻이 셋이다** — 대입 · 주석 대입 · `type X = …` (D-0275).

    첫 판에 셋째를 빼서 **8건을 거짓으로 잡았다.** `Embedding` · `Waveform` 같은 별칭에
    근거를 적는 것이 이 저장소의 꼴이고, 파이썬이 버리는 것은 대입 뒤와 똑같다.
    """
    import ast

    kept = ast.parse('type X = int\n"""닻이 있다."""\n')
    dropped = ast.parse('type X = int\n"""닻이 있다."""\n"""이건 버려진다."""\n')

    assert DEAD.dropped_docs(kept) == []
    assert len(DEAD.dropped_docs(dropped)) == 1


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
