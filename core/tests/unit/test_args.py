"""인자 대조 검사의 단위 검사 (D-0350).

**첫 판이 자기를 만든 결함을 못 잡았다.** 정규식이 `--no-print-directory`의 `no`를 타깃으로
집고 `tidy`를 지나쳤다 — 그래서 여기 **그날의 줄을 그대로 심는다.**
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_args")

THAT_DAY = """\
hygiene:
\t@$(MAKE) --no-print-directory doctor
\t@$(MAKE) --no-print-directory tidy $(if $(YES),YES=1,) $(if $(FIX),FIX=1,)

tidy:
\tpython3 tools/tidy.py $(if $(YES),--yes,)
"""
"""**그날의 Makefile 그대로다.** `FIX=1`이 `tidy`로 넘어가는데 `tidy`가 안 쓴다."""


# ------------------------------------------------------------------ 넘기는 변수


def test_받는_쪽이_안_쓰는_변수를_잡는다() -> None:
    """**사용자가 `make tidy YES=1 FIX=1`을 쳤고 아무 일도 안 났다** (D-0350).

    D-0064가 *"인자가 조용히 무시된다"*를 닫았고 D-0069가 네 시간 뒤 같은 부류를 또
    잡았다. **이번이 세 번째다.**
    """
    problems = cast("list[str]", CHECKER.check_passthrough(THAT_DAY))

    assert problems, "`FIX=1`이 사라지는데 안 운다"
    assert "FIX" in problems[0] and "tidy" in problems[0]


def test_받는_쪽이_쓰면_통과한다() -> None:
    """`YES`는 `tidy`가 쓴다 — **그것까지 잡으면 오탐이다** (GR-0.8)."""
    problems = cast("list[str]", CHECKER.check_passthrough(THAT_DAY))

    assert not any("YES" in one for one in problems)


def test_타깃을_토큰으로_집는다() -> None:
    """**`--no-print-directory`의 `no`를 타깃으로 집으면 안 된다** (D-0350).

    첫 판이 그랬고 **`tidy`를 지나쳐 이 결함을 못 잡았다.** 아는 타깃 이름과 맞는
    토큰만 쓴다.
    """
    made = cast("dict[str, list[str]]", CHECKER.recipes(THAT_DAY))

    assert set(made) == {"hygiene", "tidy"}
    assert "no" not in made


def test_모르는_타깃으로_넘기면_안_본다() -> None:
    """바깥 `make`를 부르는 자리까지 잡으면 오탐이다."""
    text = "x:\n\t@$(MAKE) -C other thing FIX=1\n"

    assert cast("list[str]", CHECKER.check_passthrough(text)) == []


# ------------------------------------------------------------------ 플래그


def test_안_받는_플래그를_잡는다() -> None:
    text = "x:\n\tpython3 tools/tidy.py --없는플래그 --fix\n"
    problems = cast("list[str]", CHECKER.check_flags(text, "시험"))

    assert any("--fix" in one for one in problems)


def test_받는_플래그는_통과한다() -> None:
    text = "x:\n\tpython3 tools/tidy.py --yes\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험")) == []


def test_줄을_넘지_않는다() -> None:
    r"""**첫 판이 `\s+`로 꼬리를 받아 다음 줄의 플래그까지 끌어왔다** (D-0350).

    `gh_ops.py`에 `--ratchet`을 준다고 **네 건을 거짓으로 냈다** — 그것이 GR-0.8이다.
    """
    text = "x:\n\tpython3 tools/tidy.py --yes\n\tpython3 tools/deadcheck.py --ratchet\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험")) == []


def test_없는_도구를_부르면_잡는다() -> None:
    text = "x:\n\tpython3 tools/no_such_tool.py --check\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험"))


# ------------------------------------------------------------------ 화면 안내


def test_문서_문자열은_안_본다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**설명과 출력은 다르다.**

    첫 판이 문서 문자열까지 훑어 **이 도구가 사고를 설명하는 문장**에 제 검사가 걸렸다.
    """
    planted = tmp_path / "tools" / "심은것.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        '"""`make tidy FIX=1`을 설명하는 문서 문자열이다."""\nX = "찍는 말"\n',
        encoding="utf-8",
    )
    found = cast("list[tuple[int, str]]", CHECKER.printed_strings(planted))

    assert [text for _, text in found] == ["찍는 말"]


def test_붙어_있지_않은_변수도_잡는다() -> None:
    """**그날의 문장이 그랬다** — *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*.

    `FIX=1`이 `make tidy`에서 **떨어져 있었고** 사용자는 둘을 같이 쳤다. 첫 판은
    붙어 있는 것만 봐서 못 잡았다. **읽는 대로 잡는다.**
    """
    import re

    advice = re.compile(r"make ([a-z][a-z0-9-]*)(.*)")
    target, tail = advice.findall("치우려면 `make tidy YES=1` · 바이트코드는 `FIX=1`")[0]

    assert target == "tidy"
    assert set(re.findall(r"([A-Z_]+)=1", tail)) == {"YES", "FIX"}


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다() -> None:
    assert cast("list[str]", CHECKER.check()) == []


def test_그물이_비지_않았다() -> None:
    """**호출을 0개 읽으면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    calls = cast("list[tuple[str, str]]", CHECKER.CALL.findall(make))

    assert len(calls) >= 30, len(calls)
    assert len({tool for tool, _ in calls}) >= 20


def test_tidy가_이제_FIX를_쓴다() -> None:
    """**화면을 말에 맞추는 것이 아니라 도구를 말에 맞췄다** (D-0350)."""
    made = cast("dict[str, list[str]]", CHECKER.recipes((ROOT / "Makefile").read_text("utf-8")))

    assert "$(FIX)" in "\n".join(made["tidy"])
