"""CI와 `make check`이 같은 것을 보는가 (D-0184).

**둘이 갈라지면 기계가 지키는 줄 알았던 것이 안 지켜진다.** 실측으로
`check_test_types.py`가 Makefile에만 있었고 **검사 코드 타입 래칫 66건이 CI에서
빠져 있었다.** `ruff`도 CI는 `core`만 보고 `tools/`를 안 봤다 — 그 세션의 lint
오류 대부분이 `tools/`에서 났다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
HOOK = ROOT / ".githooks" / "pre-commit"

CHECK_TOOLS = re.compile(r"tools/(check_\w+\.py|sync_decision_index\.py|split_decisions\.py)")


def test_메이크파일이_부르는_검사는_전부_CI에도_있다():
    """**빠진 것이 조용한 사각이 된다.**

    `make check`이 부르는 도구를 센다. `ship.py` · `sync_artifacts.py`처럼 다른
    목표의 도구는 검사가 아니므로 `CHECK_TOOLS`가 애초에 안 잡는다.
    """
    makefile = MAKEFILE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    wanted = set(CHECK_TOOLS.findall(makefile))
    assert wanted, "Makefile에서 검사 도구를 못 찾았다"
    missing = sorted(name for name in wanted if name not in workflow)
    assert not missing, f"CI에 없는 검사: {missing}"


def test_CI도_tools를_본다():
    """`working-directory: core`라 **`.`만 주면 `tools/`가 빠진다.**"""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    lint = [line for line in workflow.splitlines() if "ruff " in line]
    assert lint, "CI에 ruff 단계가 없다"
    assert all("../tools" in line for line in lint), f"tools를 안 보는 줄: {lint}"


def test_저장소_훅이_있고_실행_가능하다():
    """전역 `~/.githooks/pre-commit`이 **이 파일을 찾아 부른다** (D-0184).

    배선은 원래 있었고 파일만 없었다. **없으면 전역 훅이 조용히 지나간다.**
    """
    assert HOOK.is_file(), f"{HOOK}가 없다"
    assert os.access(HOOK, os.X_OK), f"{HOOK}에 실행 권한이 없다"


def test_훅은_느린_검사를_안_돌린다():
    """**커밋마다 99초를 물리면 `--no-verify`를 쓰게 된다.**

    `doctor`가 *"느려지면 안 돌리게 된다"*고 적은 그 함정이다. 실측으로 문서
    검사와 `ruff`가 2.6초, `pytest`가 99초였다.
    """
    text = HOOK.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "pytest" not in body
    assert "mypy" not in body
