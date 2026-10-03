"""요구사항 규약 검사의 단위 검사 (D-0350).

**규약을 적어 두고 아무도 안 세면 영원히 잠긴다** (D-0126). Part II가 MVP 경계를 못 박고
**아홉 건이 그것을 어기고 있었다.**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_requirements")


def _rows(raw: list[tuple[str, ...]]) -> list[Any]:
    """경로로 실은 모듈의 반환은 `Any`다 (D-0264). 여기서 한 번만 좁힌다."""
    return [CHECKER.Row(one) for one in raw]


def _verdict(
    raw: list[tuple[str, ...]],
    groups: set[str] | None = None,
    exempt: dict[str, str] | None = None,
) -> list[str]:
    """합성 표를 검사한다. **예외는 안 주면 빈 것으로 본다** — 실물 예외를 들이대면
    합성 표에 없는 아홉이 전부 「낡은 면제」로 운다."""
    rows = _rows(raw)
    where = groups if groups is not None else {row.group for row in rows}
    return cast("list[str]", CHECKER.check(rows, where, {} if exempt is None else exempt))


def _row(
    rid: str = "REQ-ING-001",
    rank: str = "M",
    phase: str = "P1",
    state: str = "완료",
    note: str = "근거",
) -> tuple[str, ...]:
    group, number = rid.split("-")[1], rid.split("-")[2]
    return (rid, group, number, " 무엇을 한다 ", rank, phase, state, f" {note} ")


# ------------------------------------------------------------------ 그물


def test_저장소가_통과한다() -> None:
    assert cast("list[str]", CHECKER.check(CHECKER.rows(), CHECKER.declared_groups())) == []


def test_행을_실제로_읽는다() -> None:
    """**첫 측정이 97을 72로 셌다** (D-0350).

    정규식이 `\\| (.*?) \\|$`였고 `| |`(한 칸)인 **빈 비고 23건을 떨어뜨렸다.** 그 23건
    안에 이 판의 결함 둘이 있었다 — `REQ-INF-002`·`004`가 **완료인데 근거가 없었다.**
    **세는 자 자신이 빈 그물이었다** (D-0230).
    """
    found = CHECKER.rows()

    assert len(found) >= 95, len(found)
    assert {row.group for row in found} == CHECKER.declared_groups()
    # **빈 비고가 실제로 있다.** 없다고 세던 것이 그 사고다 — 21건은 미착수라 정상이다.
    blank = [row for row in found if not row.note]
    assert blank, "빈 비고를 또 떨어뜨리고 있다"
    assert all(row.state not in CHECKER.DONE for row in blank), [row.rid for row in blank]


def test_두_글자_그룹을_읽는다() -> None:
    """**`REQ-UI`는 두 글자다.** `[A-Z]{3}`으로 훑으면 6행이 통째로 빠진다."""
    assert "UI" in CHECKER.declared_groups()
    assert any(row.group == "UI" for row in CHECKER.rows())


def test_그물이_비면_통과시키지_않는다() -> None:
    assert cast("list[str]", CHECKER.check([], {"ING"}, {}))
    assert _verdict([_row()], groups=set())


# ------------------------------------------------------------------ 판정 (카나리아)


def test_MVP_경계를_어기면_운다() -> None:
    """**그날의 꼴이다.** M인데 P5 이후인데 예외 선언이 없다."""
    problems = cast("list[str]", CHECKER.check(_rows([_row("REQ-ING-001", "M", "P5")]), {"ING"}))

    assert problems and "MVP 경계" in problems[0]


def test_선언된_예외는_통과한다() -> None:
    """**아홉을 S로 내리는 것이 답이 아니다** — `REQ-QUA-001`이 D-0003이다."""
    rid, why = next(iter(CHECKER.MVP_EXEMPT.items()))
    group, number = rid.split("-")[1], int(rid.split("-")[2])
    # **번호를 1부터 채운다** — 한 행만 두면 그 앞이 전부 결번으로 울고 판정이 가린다.
    filler = [_row(f"REQ-{group}-{one:03d}", "S", "P1") for one in range(1, number)]

    assert _verdict([*filler, _row(rid, "M", "P7")], exempt={rid: why}) == []


def test_예외마다_사유가_붙어_있다() -> None:
    """**사유 없는 예외는 그냥 구멍이다.** 다음 판이 왜 예외인지 몰라 지운다."""
    assert CHECKER.MVP_EXEMPT
    for rid, why in CHECKER.MVP_EXEMPT.items():
        assert rid.startswith("REQ-"), rid
        assert len(why) > 10, (rid, why)


def test_쓸모_없어진_예외를_잡는다() -> None:
    """**`fire-lane`의 `assert bad`다** — 면제가 낡으면 그 자리가 사각지대가 된다."""
    problems = _verdict([_row()], exempt={"REQ-ING-999": "표에 없는 면제"})

    assert problems and any("낡은 면제" in one for one in problems)


def test_끝났는데_근거가_없으면_운다() -> None:
    """`REQ-INF-002`·`004`가 **완료인데 비고가 비어 있었다** — 무엇이 끝냈는지 모른다."""
    for state in CHECKER.DONE:
        problems = _verdict([_row(state=state, note="")])
        assert any("무엇이 끝냈는지" in one for one in problems), state


def test_안_끝난_행은_비어도_된다() -> None:
    """**미착수에 근거를 요구하면 오탐이 쏟아진다** (GR-0.8). 23건 중 21건이 그쪽이다."""
    problems = _verdict([_row(state="미착수", note="")])

    assert not any("무엇이 끝냈는지" in one for one in problems)


def test_규약_밖_상태를_잡는다() -> None:
    problems = _verdict([_row(state="대충")])

    assert problems and "규약 밖" in problems[0]


def test_체계도에_없는_그룹을_잡는다() -> None:
    problems = _verdict([_row("REQ-ZZZ-001")], groups={"ING"})

    assert any("체계도에 없다" in one for one in problems)


def test_표에_0행인_그룹을_잡는다() -> None:
    """**거꾸로도 본다** — 체계도에 있고 표가 비면 그 그룹은 설계만 있는 것이다."""
    problems = _verdict([_row()], groups={"ING", "ZZZ"})

    assert any("표에 0행" in one for one in problems)


@pytest.mark.parametrize("numbers", [("001", "001"), ("001", "003")])
def test_중복과_결번을_잡는다(numbers: tuple[str, str]) -> None:
    """**번호는 재사용하지 않는다.** 폐기해도 「폐기」 행으로 남긴다."""
    assert _verdict([_row(f"REQ-ING-{one}") for one in numbers])


def test_첫_문제에서_안_멈춘다() -> None:
    rows = [_row(state="대충", note=""), _row("REQ-ING-003", "M", "P9")]

    assert len(_verdict(rows)) >= 3
