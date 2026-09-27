"""관문에 서는 도구가 지켜야 할 것 (D-0257).

### 왜 이 층을 따로 세는가

**`GREEN`이 ANSI 색 코드였는데 D-0255가 같은 이름으로 튜플을 정의해 덮었다.**
`make ship`이 섹션마다 `('success', 'skipped', 'neutral')`을 찍는 채로 **모든 검사를
통과했다.** 세 그물의 구멍이 한 자리에서 겹쳤다.

| 왜 안 걸렸나 |
|---|
| `ruff` F811은 **import · 함수** 재정의만 본다. 상수 재할당은 합법이다 |
| `mypy`는 `hathor`만 본다 — `tools/`는 타입 검사 밖이다 |
| `make check`는 **`ship.py`를 실행하지 않는다** — ship이 check를 부르지 그 반대가 아니다 |

그 자리가 하필 **«내보내도 되는가»를 판정하는 자리**였다. 사용자의 말이 여기 꽂힌다 —
*"최상단 위계의 뭔가는 절대로 무결해야 해."*

**지금까지 이 저장소의 검사는 평평했다.** 모든 도구가 같은 층에 있고, 판정하는 자리와
판정당하는 자리를 안 갈랐다. 여기가 그 층을 처음으로 이름 붙이는 자리다 —
**관문 도구**는 `Makefile` · 워크플로 · 커밋 훅이 부르는 것이다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
TESTS = ROOT / "core" / "tests"
CALLERS = (
    ROOT / "Makefile",
    ROOT / ".githooks" / "pre-commit",
    *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
)

TOOL_CALL = re.compile(r"tools/([a-z_0-9]+)\.(?:py|sh)")

UNTESTED = 8
"""**자기 시험이 없는 관문 도구의 수** (D-0257).

한 번에 여덟을 채우면 큰 차이가 되고, 안 걸면 다음 세션이 아홉 번째를 더한다.
D-0117이 파일 길이에, D-0149가 타입 오류에 쓴 래칫을 여기에 그대로 쓴다.

늘리려면 `--allow-growth`가 아니라 **결정 기록**이 필요하다. 줄이면 이 수를 내려 박는다."""


def gate_tools() -> list[str]:
    """`Makefile` · 워크플로 · 훅이 부르는 도구. **이것이 관문 층이다.**"""
    blob = "\n".join(path.read_text(encoding="utf-8") for path in CALLERS if path.exists())
    return sorted(set(TOOL_CALL.findall(blob)))


def _tested() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in TESTS.rglob("test_*.py"))


def untested_gate_tools() -> list[str]:
    """관문에 서는데 **어느 시험도 열어 보지 않는** 도구."""
    blob = _tested()
    return [
        name
        for name in gate_tools()
        if not any(token in blob for token in (f'"{name}.py"', f'"{name}.sh"', f"tools/{name}."))
    ]


def _redefined(path: Path) -> list[str]:
    """**모듈 몸통 직속**의 이름 재할당. `if`·`try` 갈래는 정당하므로 안 본다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    clashes: list[str] = []
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for name in names:
            if name in seen:
                clashes.append(f"{name} ({seen[name]}행 → {node.lineno}행)")
            seen[name] = node.lineno
    return clashes


def test_관문_층을_실제로_찾는다() -> None:
    """그물이 비면 아래 시험이 **아무것도 안 보고 초록이 된다** (D-0219)."""
    assert len(gate_tools()) >= 20


def test_도구가_최상위_이름을_두_번_안_쓴다() -> None:
    """**D-0257의 강제자.** 덮어쓴 이름은 조용히 다른 뜻이 된다."""
    offenders = {
        path.name: clashes for path in sorted(TOOLS.glob("*.py")) if (clashes := _redefined(path))
    }

    assert not offenders, (
        f"같은 이름을 두 번 준다: {offenders}. "
        "뒤엣것이 앞엣것을 덮고 **`ruff`도 `mypy`도 안 잡는다** (D-0257)"
    )


def test_덮어쓴_이름을_실제로_잡는다(tmp_path: Path) -> None:
    """그물이 무는지 본다. **오늘 놓친 것과 같은 모양이다.**"""
    fake = tmp_path / "ship.py"
    fake.write_text('GREEN = "\\033[32m"\nGREEN = ("success",)\n', encoding="utf-8")

    assert _redefined(fake) == ["GREEN (1행 → 2행)"]


def test_갈래_안의_같은_이름은_안_잡는다(tmp_path: Path) -> None:
    """`if`·`try` 안에서 같은 이름을 주는 것은 **정당하다.**"""
    fake = tmp_path / "x.py"
    fake.write_text(
        "import sys\n\nif sys.platform:\n    A = 1\nelse:\n    A = 2\n", encoding="utf-8"
    )

    assert _redefined(fake) == []


def test_시험_없는_관문_도구가_래칫과_같다() -> None:
    """**판정하는 자리가 판정당하지 않고 있다.** 늘면 빨개지고 줄이면 못을 내려 박는다."""
    missing = untested_gate_tools()

    assert len(missing) == UNTESTED, (
        f"시험 없는 관문 도구가 {len(missing)}개다 (못은 {UNTESTED}): {missing}. "
        "늘었으면 시험을 붙이고, 줄었으면 `UNTESTED`를 내려 박는다 (D-0257)"
    )
