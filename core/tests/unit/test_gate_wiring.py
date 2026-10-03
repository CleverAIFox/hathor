"""**부품은 재고 배선은 안 쟀다** (D-0356 · D-0352 · D-0353에서 되풀이).

관문의 `check()`가 작은 검사 여럿을 이어 붙인다. 그중 **한 줄을 지워도** 저장소는 여전히
통과하고 — 그 작은 검사를 **직접** 부르는 시험만 있으면 아무도 안 운다. `make mutate
WIRING=1`이 그 자리를 **49곳** 세었다.

여기는 **입구를 거쳐서** 본다. 작은 검사를 「심은 문제」를 내도록 바꿔 놓고 `check()`가
그것을 들고 나오는지 본다. 안 들고 나오면 그 배선은 끊겨 있는 것이다.

**`tools/check_X.py`의 이름이 이 파일에 있어야** `mutate_gate.tests_for`가 여기를 연다.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from tests.conftest import tool_module

STYLE = tool_module("check_doc_style")
REPO = tool_module("doc_style_repo")
CODING = tool_module("encoding_check")

PLANTED = "심은 문제"


# ----------------------------------------------- check_doc_style (배선 9곳)


@pytest.mark.parametrize(
    "part",
    ["check_sixth_document", "check_duplicates", "check_plan_leftovers", "check_debt_rows"],
)
def test_문서_전체를_보는_검사가_배선돼_있다(part: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """**넷은 `doc_style_repo`로 떼어 냈다** (D-0356) — `check()`가 지연 임포트로 부른다.

    지연 임포트는 부를 때마다 모듈에서 다시 읽으므로 **거기를 바꾸면 그대로 먹힌다.**
    """
    monkeypatch.setattr(REPO, part, lambda: [PLANTED])

    assert PLANTED in cast("list[str]", STYLE.check())


@pytest.mark.parametrize("part", ["check_layout", "check_bold_density", "check_records"])
def test_문서마다_도는_검사가_배선돼_있다(part: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """`check_layout`은 모든 문서에, `check_bold_density`·`check_records`는 **갈라져** 돈다 —
    그래서 하나만 끊어도 **어떤 문서에서도** 안 울면 그 가지가 죽은 것이다."""

    def planted(*_: Any) -> list[str]:
        return [PLANTED]

    monkeypatch.setattr(STYLE, part, planted)

    assert PLANTED in cast("list[str]", STYLE.check())


def test_볼_문서가_없으면_통과시키지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**`targets()`가 비면 아래 루프가 한 번도 안 돈다** — 그런데 「통과」가 떴다 (D-0230)."""
    monkeypatch.setattr(STYLE, "targets", list)

    problems = cast("list[str]", STYLE.check())

    assert problems and "그물이 비었다" in problems[0]


def test_지금_문서를_바닥_넘게_본다() -> None:
    assert len(cast("list[Any]", STYLE.targets())) >= STYLE.FLOOR_DOCS


def test_화면이_문서_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**수가 화면에 없으면 0인 것도 모른다.** `main()`이 `targets()`를 거치는지 본다."""
    monkeypatch.setattr("sys.argv", ["check_doc_style.py", "--check"])

    assert STYLE.main() == 0
    assert f"문서 {len(cast('list[Any]', STYLE.targets()))}개" in capsys.readouterr().out


# ----------------------------------------------- encoding_check (배선 3곳)


def test_훑은_것이_0이면_통과시키지_않는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**`scan()`을 끊어도 「통과」가 떴다.** 추적 텍스트 수가 화면에만 있었다 (D-0356)."""
    monkeypatch.setattr(CODING, "tracked", lambda *_: [])
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--check"])

    assert CODING.main() == 1
    assert "그물이 비었다" in capsys.readouterr().err


def test_scan이_낸_문제를_들고_나온다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(CODING, "scan", lambda: [("심은파일", ["BOM"])])
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--check"])

    assert CODING.main() == 1
    assert "심은파일" in capsys.readouterr().err


def test_looked_at을_거쳐_센다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**거르는 자를 끊으면 수가 부풀고, 부푼 수는 「다 봤다」로 읽힌다.**"""
    monkeypatch.setattr(CODING, "looked_at", lambda _: False)
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--check"])

    assert CODING.main() == 1
    assert "그물이 비었다" in capsys.readouterr().err


def test_지금_추적_텍스트가_바닥_넘는다() -> None:
    seen = [one for one in cast("list[Any]", CODING.tracked()) if CODING.looked_at(one)]

    assert len(seen) >= CODING.FLOOR_TRACKED
