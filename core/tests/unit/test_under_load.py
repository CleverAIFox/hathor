"""부하 검사의 단위 검사 (D-0355).

**한 갈래로는 안 보이는 결함이 있다.** D-0354가 그랬다 — `grep -q`가 파이프를 먼저 닫고
`pipefail`이 그것을 실패로 읽는데, 한가하면 `git`이 먼저 끝나서 안 보인다. 관문 하나씩,
시험 한 갈래로는 전부 통과했고 **네 갈래에서 3/3 났다.** 사용자 기기에서 터져서야 알았다.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
TOOL = tool_module("check_under_load")


# ------------------------------------------------------------------ 그물


def test_관문을_실제로_읽는다() -> None:
    """**정규식이 망가지면 0개를 돌고 통과한다** (D-0230)."""
    found = cast("list[str]", TOOL.gates())

    assert len(found) >= TOOL.FLOOR, found
    assert "tools/check_decisions.py" in found
    assert "tools/doc_fsck.py" in found


def test_저_자신은_안_돈다() -> None:
    """**제가 저를 부르면 갈래가 제곱으로 는다.**"""
    assert not [one for one in cast("list[str]", TOOL.gates()) if TOOL.MINE in one]


def test_레시피_줄만_읽는다() -> None:
    """주석이나 문서의 `python3 tools/X.py --check`를 관문으로 세면 안 된다."""
    text = "# python3 tools/fake.py --check\ncheck:\n\tpython3 tools/real.py --check\n"
    found = cast("list[str]", TOOL.GATE.findall(text))

    assert found == ["tools/real.py"]


def test_관문이_적으면_막는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(TOOL, "gates", list)
    monkeypatch.setattr("sys.argv", ["check_under_load.py", "--check"])

    assert TOOL.main() == 1
    assert "그물이 비었다" in capsys.readouterr().err


# ------------------------------------------------------------------ 판정 (카나리아)


def test_빨개진_관문을_잡는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**이것이 D-0354의 자리다.** 하나라도 빨개지면 들어 올려야 한다."""
    monkeypatch.setattr(TOOL, "once", lambda tool: (tool, 1, "심은 실패"))
    monkeypatch.setattr(TOOL, "gates", lambda: ["tools/fake.py"])

    bad = cast("list[tuple[str, str]]", TOOL.sweep(2))

    assert len(bad) == 2
    assert bad[0] == ("tools/fake.py", "심은 실패")


def test_전부_초록이면_빈_목록이다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TOOL, "once", lambda tool: (tool, 0, "통과"))
    monkeypatch.setattr(TOOL, "gates", lambda: ["tools/fake.py"])

    assert cast("list[tuple[str, str]]", TOOL.sweep(3)) == []


def test_판수를_실제로_곱한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**한 판만 돌면 D-0354를 못 잡는다** — 경주라서 여러 판이 필요하다."""
    seen: list[str] = []

    def spy(tool: str) -> tuple[str, int, str]:
        seen.append(tool)
        return tool, 0, ""

    monkeypatch.setattr(TOOL, "once", spy)
    monkeypatch.setattr(TOOL, "gates", lambda: ["a", "b"])
    TOOL.sweep(4)

    assert len(seen) == 8


def test_실제로_한꺼번에_돈다() -> None:
    """**갈래가 하나면 부하가 아니다.** D-0354는 넷에서 났다."""
    assert TOOL.WORKERS >= 4


def test_관문_하나를_정말_돌린다() -> None:
    """**`once`가 거짓을 돌려주면 전부가 거짓이다.** 실물 하나로 확인한다."""
    tool, code, tail = cast("tuple[str, int, str]", TOOL.once("tools/check_decisions.py"))

    assert tool == "tools/check_decisions.py"
    assert code == 0, tail
    assert "결정 기록" in tail


# ------------------------------------------------------------------ 배선


def test_make에_걸려_있다() -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126)."""
    assert "tools/check_under_load.py" in (ROOT / "Makefile").read_text(encoding="utf-8")


def test_CI가_돌린다() -> None:
    """**`make check`에는 안 넣는다** — 관문을 한 번 더 전부 도는 것이라 겹친다.

    대신 **CI가 제 잡으로 나란히 돌린다.** 거기가 사람 인내심과 무관한 자리다 (D-0129).
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "tools/check_under_load.py" in workflow
    assert "gates-under-load:" in workflow


def test_make_check_사슬에는_없다() -> None:
    """겹쳐 돌면 `make check`이 두 배가 되고, 그러면 사람이 검사를 끈다 (D-0129)."""
    made = (ROOT / "Makefile").read_text(encoding="utf-8")
    chain = made.split("\ndocs:", 1)[1].split("\n\n", 1)[0]

    assert "check_under_load" not in chain
