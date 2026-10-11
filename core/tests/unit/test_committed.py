"""커밋된 트리를 보는 관문 (D-0380).

**관문 스물다섯이 전부 작업 트리를 읽었다.** D-0379에서 `make apply`가 제출본을 다시
만들고 커밋에 안 담았는데 `make check`은 초록이었다 — *«커밋된 산출물이 커밋된 정본과
맞는가»*를 보는 자리가 하나도 없었다.

`ship.check_git()`이 더러운 트리를 막으므로 **트리가 깨끗하면 트리 = 커밋**이고 그 길은
이미 막혀 있다. 안 막힌 길은 `--no-verify` · 부분 담기 · 머지가 낸 트리 ·
`apply_patch`가 권하던 `git push`다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("check_committed")
SHIP = tool_module("ship")
ROOT = Path(__file__).resolve().parents[3]


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, capture_output=True, text=True, timeout=120, check=True
    ).stdout.strip()


# ------------------------------------------------------------------ 그물


def test_돌릴_관문이_비지_않았다() -> None:
    """**목록이 비면 「커밋도 맞다」가 거짓으로 참이 된다** (D-0230)."""
    assert len(TOOL.GATES) >= TOOL.FLOOR_GATES
    for gate in TOOL.GATES:
        assert (ROOT / gate).is_file(), gate


def test_그물이_비면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 관문을 다 빼면 아무것도 안 보고 통과한다."""
    monkeypatch.setattr(TOOL, "GATES", ())

    assert any("그물이 비었다" in one for one in cast("list[str]", TOOL.check()))


def test_못_꺼내면_통과로_안_적는다() -> None:
    """**못 잰 것을 통과로 세지 않는다** (GR-0.5). 없는 커밋은 0이 아니라 문제다."""
    problems = cast("list[str]", TOOL.check("이런커밋은없다"))

    assert problems and "못 꺼냈다" in problems[0], problems


# ------------------------------------------------------------------ 실물


def test_지금_HEAD는_스스로_맞는다() -> None:
    """**합성만 보면 실물이 어긋난 것을 놓친다.** 이 저장소의 커밋으로 잰다."""
    assert TOOL.check() == []


PLANT = "\n심은 결함 한 줄 (D-0386).\n\n## 부록 A."
"""정본에만 넣는 한 줄. 제출본은 그 줄을 모르므로 **커밋된 산출물이 낡는다.**"""


def test_제출본만_낡은_커밋을_잡는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0379). 꺼낸 트리에서 **정본만 한 줄 바꾼다.**

    그러면 커밋된 제출본이 커밋된 정본보다 낡고, **작업 트리는 초록인 채로** 그
    판정만 어긋난다 — D-0379에서 실제로 샌 자리 그대로다.

    ### git에 **아무것도 쓰지 않는다** (D-0386)

    앞선 세 판이 전부 여기서 깨졌다. 셋 다 **로컬은 초록이고 CI만 빨갰다**:

    | 판 | 쓴 것 | 왜 CI에서만 깨졌나 |
    |---|---|---|
    | D-0377 | — | `dot`이 없어 `OSError`가 먼저 났다 |
    | D-0382 | `HEAD~3`의 blob | `fetch-depth: 2`라 그 커밋이 없다 |
    | D-0385 | `commit-tree` | **까닭을 못 봤다** — `check=True`가 stderr를 삼켰다 |

    쓰기는 **ident · 인덱스 파일 · 이력 깊이**를 묻고 그 셋이 기기마다 다르다.
    `picked()`를 갈아끼우면 **읽기만 남는다** — 꺼내는 일은 `check()`가 어차피 하는
    실물 경로이므로 그 길을 그대로 타고, 꺼낸 뒤 파일 하나를 고칠 뿐이다.
    """
    real = TOOL.picked

    def planted(rev: str, into: Path) -> str | None:
        broken = cast("str | None", real(rev, into))
        if broken:
            return broken
        page = into / "docs" / "MASTER.md"
        body = page.read_text(encoding="utf-8")
        assert "\n## 부록 A." in body, "심을 자리가 사라졌다 — 심은 결함이 안 심긴다"
        page.write_text(body.replace("\n## 부록 A.", PLANT, 1), encoding="utf-8")
        return None

    monkeypatch.setattr(TOOL, "picked", planted)

    problems = cast("list[str]", TOOL.check())

    assert problems, "정본보다 낡은 제출본을 담은 커밋을 통과시켰다"
    assert any("render_proposal" in one for one in problems), problems


# ------------------------------------------------------------------ 배선


def test_ship이_밀기_전에_본다() -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126).

    `make check`에는 **안 넣는다** — 커밋 전에 도는 것이 정상이라 늘 빨갛고, 늘 빨간
    관문은 사람이 끈다 (D-0129). 내보내는 자리가 그 자리다.
    """
    body = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")

    assert "check_committed.check()" in body
    assert "커밋된 트리" in body
    assert "tools/check_committed.py" not in (ROOT / "Makefile").read_text(encoding="utf-8"), (
        "`make check`에 넣으면 커밋 전에 늘 빨갛다 (D-0129)"
    )


def test_붙이기가_git_push를_안_권한다() -> None:
    """**그 길이 `ship`을 건너뛴다** (D-0380). D-0379가 샌 자리가 거기다."""
    body = (ROOT / "tools" / "apply_patch.sh").read_text(encoding="utf-8")
    said = [
        line
        for line in body.splitlines()
        if "git push" in line and not line.lstrip().startswith("#")
    ]

    assert all("make ship" in line for line in said), said


def test_막히면_밀지_않는다() -> None:
    """**찍기만 하고 미는 길이 있으면 관문이 아니다** (D-0283)."""
    body = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    block = body[body.index("committed = check_committed.check()") : body.index("── 기록")]

    assert "return 1" in block, "막혔는데 내려간다"
    assert "commit --amend" in block, "고치는 한 줄이 없다 (D-0269)"
