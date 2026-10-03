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


# ------------------------------------- 셸 · 워크플로 · 쓰임새 주석 (D-0352)


def test_바깥_파일을_실제로_읽는다() -> None:
    """**첫 판은 `Makefile`과 훅만 봤다** — 셸·워크플로는 영원히 안 보는 자리였다.

    그물이 비면 「전부 맞다」가 거짓으로 참이 된다 (D-0230). 그래서 바닥이 넷이다.
    """
    found = cast("list[tuple[str, str]]", CHECKER.sources())
    names = [name for name, _ in found]

    assert len(found) >= CHECKER.FLOOR["바깥 파일"], names
    assert any("make_patch.sh" in one for one in names)
    assert any("ci.yml" in one for one in names)
    # **셸은 전부 본문이 있다.** 워크플로는 `run:`이 하나도 없을 수 있고(`codeql.yml`이
    # 그렇다 — 전부 `uses:`다) 그때 빈 것이 **맞다.** 그래도 **적어도 하나는** 내용이
    # 있어야 한다 — 전부 비면 추출기가 망가진 것이다 (D-0230 · GR-0.5).
    shell = [text for name, text in found if not name.endswith("(run:)")]
    flows = [text for name, text in found if name.endswith("(run:)")]
    assert all(shell) and len(shell) >= 5
    assert sum(1 for text in flows if text) >= 4, "워크플로에서 run:을 거의 못 읽었다"


def test_워크플로_꼴의_호출을_읽는다() -> None:
    """**`CALL`은 한 건도 못 읽고 있었다.** 워크플로는 `uv run python ../tools/X.py`다."""
    text = "        run: cd core && uv run python ../tools/gpu_smoke.py --check\n"
    got = cast("list[tuple[str, str]]", CHECKER.ANY_CALL.findall(text))

    assert got and got[0][0] == "tools/gpu_smoke.py"


def test_명령_치환을_넘지_않는다() -> None:
    r"""**실물에서 거짓 경보를 냈다** (GR-0.8).

        gh release create … --title "$(… release_notes.py --title)" --notes-file notes.md

    꼬리가 `)`를 넘어 `--notes-file`을 그 도구의 인자로 읽었다. 그것은 `gh`의 인자다.
    """
    text = 'x --title "$(python3 tools/release_notes.py --title)" --notes-file notes.md'
    flags = cast("list[tuple[str, str]]", CHECKER.ANY_CALL.findall(text))

    assert flags
    assert "--notes-file" not in flags[0][1]


def test_명령_자리의_make만_센다() -> None:
    """**실측으로 먼저 틀렸다** (D-0352).

    `apt-get install -y --no-install-recommends make ffmpeg graphviz`에서 `make ffmpeg`를
    집어 「없는 타깃」이라고 울었다. `ffmpeg`는 apt 꾸러미다 — `make`가 인자인 자리다.
    **`--no-print-directory`의 `no`를 집은 것과 같은 결함이다** (D-0350).
    """
    apt = "sudo apt-get install -y --no-install-recommends make ffmpeg graphviz\n"
    real = "cd core && make check\nmake sync\n"

    assert cast("list[tuple[str, str]]", CHECKER.MAKE_CALL.findall(apt)) == []
    assert {t for t, _ in cast("list[tuple[str, str]]", CHECKER.MAKE_CALL.findall(real))} == {
        "check",
        "sync",
    }


def test_없는_타깃을_부르면_잡는다() -> None:
    made = cast("dict[str, list[str]]", CHECKER.recipes("check:\n\techo\n"))
    problems = cast("list[str]", CHECKER.check_make_calls("make nosuch\n", "시험", made))

    assert problems and "그 타깃이 없다" in problems[0]


def test_쓰임새_주석이_없는_타깃을_가리키면_잡는다() -> None:
    """**사람이 그대로 치는 줄이다.** 타깃 이름을 바꾸면 스크립트 제 설명이 거짓이 된다."""
    made = cast("dict[str, list[str]]", CHECKER.recipes("patch:\n\techo\n"))

    assert cast("list[str]", CHECKER.check_usage("#   make patch REV=x\n", "시험", made)) == []
    problems = cast("list[str]", CHECKER.check_usage("#   make oldname\n", "시험", made))
    assert problems and "쓰임새 주석" in problems[0]


def test_run_블록만_읽는다() -> None:
    """**`with:`·`env:`까지 훑으면 설정 문자열을 명령으로 읽는다.**"""
    yaml = (
        "jobs:\n  a:\n    steps:\n      - uses: x\n        with:\n"
        "          args: make 없는것\n      - run: make check\n"
    )
    got = cast("str", CHECKER.run_blocks(yaml))

    assert "make check" in got
    assert "nosuch" not in got


def test_속성_문서_문자열은_출력이_아니다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**첫 판은 블록의 첫 줄만 문서로 봤다** (D-0352).

    그래서 `X = re.compile(...)` 아래 붙는 **속성 문서 문자열**을 출력으로 읽고, 이 도구가
    apt 줄을 설명하는 문장에 제 검사가 걸렸다. 찍는 문자열은 늘 인자이거나 대입된 값이다.
    """
    planted = tmp_path / "심은것.py"
    planted.write_text(
        'X = 1\n"""설명이다 — `make nosuch`을 든다."""\nY = "찍는 말"\n', encoding="utf-8"
    )
    found = cast("list[tuple[int, str]]", CHECKER.printed_strings(planted))

    assert [text for _, text in found] == ["찍는 말"]


def test_쓰임새_검사가_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**부품을 재고 배선을 안 쟀다** (D-0352).

    심은 결함으로 재니 `check()`에서 `check_usage` 한 줄을 지워도 아무 시험이 안 울었다 —
    시험이 그 함수를 **직접** 부르고 있었기 때문이다. 여기는 `check()`를 거쳐서 본다.
    """
    monkeypatch.setattr(CHECKER, "check_usage", lambda *_: ["심은 것"])

    assert "심은 것" in cast("list[str]", CHECKER.check())


def test_셸_워크플로_검사가_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "check_any_calls", lambda *_: ["심은 것"])
    monkeypatch.setattr(CHECKER, "check_make_calls", lambda *_: ["심은 둘"])
    problems = cast("list[str]", CHECKER.check())

    assert "심은 것" in problems and "심은 둘" in problems
