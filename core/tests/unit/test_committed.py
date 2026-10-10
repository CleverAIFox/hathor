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


def test_제출본만_낡은_커밋을_잡는다() -> None:
    """**심은 결함** (D-0069 · D-0379). 그날의 꼴 그대로를 만들어 재 본다.

    `HEAD`의 트리에서 `docs/proposal.docx`만 옛 blob으로 바꾼 커밋을 **배관으로** 짓는다
    — 작업 트리는 건드리지 않는다. 그 커밋은 **작업 트리가 초록인 채로** 어긋나 있다.
    """
    old = _git("rev-parse", "HEAD~3:docs/proposal.docx")
    index = Path(
        subprocess.run(["mktemp"], capture_output=True, text=True, check=True).stdout.strip()
    )
    env = {"GIT_INDEX_FILE": str(index)}
    for args in (
        ("read-tree", "HEAD"),
        ("update-index", "--cacheinfo", f"100644,{old},docs/proposal.docx"),
    ):
        subprocess.run(("git", *args), cwd=ROOT, env={**_environ(), **env}, timeout=120, check=True)
    tree = subprocess.run(
        ("git", "write-tree"),
        cwd=ROOT,
        env={**_environ(), **env},
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    ).stdout.strip()
    planted = _git("commit-tree", tree, "-p", "HEAD", "-m", "심은 결함: 제출본만 낡은 커밋")

    problems = cast("list[str]", TOOL.check(planted))

    assert problems, "제출본이 낡은 커밋을 통과시켰다"
    assert any("render_proposal" in one for one in problems), problems


def _environ() -> dict[str, str]:
    import os

    return dict(os.environ)


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
