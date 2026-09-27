"""워크플로가 맨 `python3`으로 부르는 도구는 표준 라이브러리만 쓴다 (D-0256).

**`bake_proposal.py`가 `python-docx`를 쓰는데 `proposal.yml`이 맨 `python3`으로 불렀다.**
그래서 D-0246이 그 워크플로를 만든 뒤로 **한 번도 초록인 적이 없었다.** 로컬에서는
`uv run`으로 돌아 보이지 않았다.

이것이 D-0255가 적은 «경계»의 또 한 줄이다 — **묶음 안의 파이썬 ↔ 시스템 파이썬.**
어느 쪽 검사도 그 사이를 안 봤다.

규칙은 둘 중 하나다.

- 맨 `python3 tools/X.py`로 부른다 → `X`는 **표준 라이브러리만** 쓴다.
- 서드파티가 필요하다 → 워크플로가 `uv run`으로 부른다.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
TOOLS = ROOT / "tools"

BARE_CALL = re.compile(r"(?<!uv run )python3 (tools/[a-z_0-9]+\.py)")
"""워크플로가 **맨 `python3`으로** 부르는 도구. `uv run python3 ...`은 묶음 안이라 뺀다."""

LOCAL = {path.stem for path in TOOLS.glob("*.py")} | {"hathor"}
"""저장소 안의 모듈. `tools/`끼리 부르는 것과 `hathor`는 서드파티가 아니다."""


def _bare_tools() -> set[str]:
    found: set[str] = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for match in BARE_CALL.finditer(path.read_text(encoding="utf-8")):
            found.add(match.group(1))
    return found


def _third_party(path: Path) -> set[str]:
    """**함수 안 import까지 본다** — `bake_proposal`이 그렇게 숨어 있었다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return {name for name in names if name not in sys.stdlib_module_names and name not in LOCAL}


def test_맨_python3로_부르는_도구를_실제로_찾는다() -> None:
    """그물이 비면 아래 시험이 **아무것도 안 보고 초록이 된다** (D-0219)."""
    assert len(_bare_tools()) >= 10


def test_맨_python3로_부르는_도구는_표준_라이브러리만_쓴다() -> None:
    """**D-0256의 강제자.** 시스템 파이썬에는 묶음이 없다."""
    offenders = {
        name: sorted(deps) for name in sorted(_bare_tools()) if (deps := _third_party(ROOT / name))
    }

    assert not offenders, (
        f"맨 `python3`으로 부르는데 서드파티를 쓴다: {offenders}. "
        "워크플로에서 `uv run`으로 부르거나 그 의존을 없앤다 (D-0256)"
    )


def test_uv_run으로_부르는_것은_안_본다() -> None:
    """`uv run python3 tools/X.py`는 묶음 안이다. 그물이 그것까지 잡으면 못 고친다."""
    assert not BARE_CALL.search("uv run python3 tools/bake_proposal.py")
    assert BARE_CALL.search("python3 tools/bake_proposal.py")
