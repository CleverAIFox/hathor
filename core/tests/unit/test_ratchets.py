"""래칫 방향 검사의 단위 검사 (D-0352).

**`check_sight`가 화면에 *"`--loosen`에는 결정 기록이 필요하다"*고 적고, 아무도 안 셌다.**
못을 내려 박고 기록을 안 쓰면 그 판은 영원히 초록이다 — `fire-lane`은 커버리지 래칫이
실물 아래인 것을 **나흘 몰랐다.**
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_ratchets")


def _loosened(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return cast("list[str]", CHECKER.loosened(before, after))


# ------------------------------------------------------------------ 그물


def test_저장소가_통과한다() -> None:
    problems, _ = cast("tuple[list[str], str]", CHECKER.check())

    assert problems == []


def test_못을_실제로_읽는다() -> None:
    """**어휘가 망가지면 0개를 읽고 통과한다** (D-0230). 정수 상수 74개 중 못만 가린다."""
    here = cast("dict[str, int]", CHECKER.measure())

    assert len(here) >= CHECKER.FLOOR_NAILS, len(here)
    assert "deadcheck.CEILING[빈 그물]" in here
    assert "test_gate_tools.UNTESTED" in here
    # **시험 치수는 못이 아니다** — 걸리면 오탐이 쏟아지고 관문이 죽는다 (GR-0.8).
    assert not [key for key in here if key.endswith((".DIM", ".DEGREES", ".SR", ".SEED"))]


def test_정본이_둘이_되지_않는다() -> None:
    """`check_sight.PINNED`는 저 자신이 방향을 안다. **정본은 하나다** (D-0117)."""
    here = cast("dict[str, int]", CHECKER.measure())

    assert "check_sight.PINNED" not in here
    assert not [key for key in here if key.startswith("check_sight.PINNED")]


# ------------------------------------------------------------------ 방향 (카나리아)


def test_천장이_오르면_느슨하다() -> None:
    assert _loosened({"deadcheck.CEILING[빈 그물]": 0}, {"deadcheck.CEILING[빈 그물]": 3})


def test_천장이_내리면_조인_것이다() -> None:
    """**조이는 쪽을 막으면 아무도 안 조인다** (GR-0.8)."""
    assert _loosened({"deadcheck.CEILING[빈 그물]": 3}, {"deadcheck.CEILING[빈 그물]": 0}) == []


def test_바닥이_내리면_느슨하다() -> None:
    assert _loosened({"debts.STALE_FLOOR": 10}, {"debts.STALE_FLOOR": 2})


def test_바닥이_오르면_조인_것이다() -> None:
    assert _loosened({"debts.STALE_FLOOR": 2}, {"debts.STALE_FLOOR": 10}) == []


def test_사라진_못은_늘_느슨하다() -> None:
    """**없는 것은 0이 아니다** (GR-0.5 · D-0349). 지우면 그 자리가 사각지대가 된다."""
    problems = _loosened({"test_gate_tools.UNTESTED": 0}, {})

    assert problems and "사라졌다" in problems[0]


def test_강제_시작이_오르면_느슨하다() -> None:
    """**헷갈리는 자리다** — 늦게 강제하면 **덜** 강제한다.

    `FORMAT_ENFORCED_FROM = 80`을 81로 올리면 기록 하나가 형식 검사 밖으로 빠진다.
    """
    assert _loosened(
        {"check_decisions.FORMAT_ENFORCED_FROM": 80},
        {"check_decisions.FORMAT_ENFORCED_FROM": 81},
    )
    assert (
        _loosened(
            {"check_decisions.FORMAT_ENFORCED_FROM": 81},
            {"check_decisions.FORMAT_ENFORCED_FROM": 80},
        )
        == []
    )


@pytest.mark.parametrize(
    ("name", "which"),
    [
        ("FLOOR", "바닥"),
        ("STALE_FLOOR", "바닥"),
        ("CEILING", "천장"),
        ("QUARANTINE_CEILING", "천장"),
        ("UNTESTED", "천장"),
        ("UNTYPED_FAKES", "천장"),
        ("UNKNOWN_EVIDENCE", "천장"),
        ("NODE_FROM", "천장"),
    ],
)
def test_이름이_부류를_정한다(name: str, which: str) -> None:
    got = cast("str | None", CHECKER.kind(name))

    assert got is not None
    assert CHECKER.NAILS[got] == which


@pytest.mark.parametrize("name", ["DIM", "DEGREES", "WIDTH", "TIMEOUT", "MVP_PHASE"])
def test_못이_아닌_것은_안_센다(name: str) -> None:
    assert CHECKER.kind(name) is None


# ------------------------------------------------------------------ 기록을 요구한다


def test_느슨하면_기록을_요구한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**이것이 D-0118의 `GROW=1`과 같은 규율이다.** 마찰의 값이 기록 한 줄이다."""
    monkeypatch.setattr(CHECKER, "at", lambda _: {"debts.STALE_FLOOR": 99})
    monkeypatch.setattr(CHECKER, "against", lambda: ("아무것", {"tools/debts.py"}, "시험"))

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems and "기록 없다" in what


def test_기록을_같이_담으면_통과한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**내려 박지 말라는 것이 아니라 왜인지 적으라는 것이다.**"""
    monkeypatch.setattr(CHECKER, "at", lambda _: {"debts.STALE_FLOOR": 99})
    monkeypatch.setattr(
        CHECKER, "against", lambda: ("아무것", {CHECKER.PAST, "tools/debts.py"}, "시험")
    )

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems == []
    assert "기록 있다" in what


def test_비교_상대가_없으면_통과로_안_적는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**못 잰 것을 통과로 세지 않는다** (GR-0.5)."""
    monkeypatch.setattr(CHECKER, "against", lambda: (None, set(), "시험"))

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems == []
    assert "안 돌렸다" in what


def test_비교할_짝을_맞춘다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**첫 판이 짝을 틀렸다** (D-0352).

    작업 트리를 `HEAD`의 **부모**와 비교하면서 기록은 `HEAD`의 커밋에서 찾았다 — 둘이
    다른 판이고, 그러면 *"앞 판이 기록을 썼다"*는 이유로 이 판의 느슨함이 통과한다.
    """
    monkeypatch.setattr(CHECKER, "pending", lambda: {"tools/x.py"})
    _, changed, how = cast("tuple[str | None, set[str], str]", CHECKER.against())
    assert "HEAD" in how and "부모" not in how
    assert changed == {"tools/x.py"}, "더러우면 커밋 안 된 변경에서 기록을 찾는다"

    monkeypatch.setattr(CHECKER, "pending", set)
    monkeypatch.setattr(CHECKER, "touched", lambda _: {"담긴것"})
    _, changed, how = cast("tuple[str | None, set[str], str]", CHECKER.against())
    assert "부모" in how
    assert changed == {"담긴것"}, "깨끗하면 HEAD가 담은 것에서 찾는다"


def test_못을_하나도_안_읽으면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "measure", dict)

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems and "그물이 비었다" in problems[0]
    assert "못 쟀다" in what


# ------------------------------------------------------------------ 배선


@pytest.mark.parametrize("where", ["Makefile", ".githooks/pre-commit", ".github/workflows/ci.yml"])
def test_세_곳에_다_걸려_있다(where: str) -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126)."""
    assert "tools/check_ratchets.py" in (ROOT / where).read_text(encoding="utf-8")
