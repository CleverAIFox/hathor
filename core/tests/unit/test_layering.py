"""계층 계약에 예외가 없는지 본다 (O-56 · D-0236).

`lint-imports`는 계약을 지키지만 **예외 목록도 같이 지킨다.** 한 줄 적어 두면 그 줄만큼
계약이 아니다. D-0190이 다섯 줄을 적어 두고 «빚이 보이게» 했고, 여기가 그 빚을 다 갚은
자리를 못 박는다 — **다시 적으려면 이 시험을 지워야 하고, 그것은 결정 기록이 필요하다.**
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "core" / "hathor"

MOVED = (
    "track_features",
    "scan_record",
    "scan_summary",
    "resolution_record",
    "resolution_summary",
)
"""저장소가 담는 DTO. **응용이 아니라 도메인에 있다.**"""


def test_계층_계약에_예외가_없다() -> None:
    """**D-0236의 강제자.** 예외 한 줄이 계약 한 줄을 지운다."""
    project = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    assert "ignore_imports" not in project, (
        "계층 계약에 예외가 생겼다. 예외를 적기 전에 그 의존을 끊는 길을 먼저 본다 (O-56 · D-0236)"
    )


def test_저장소가_담는_DTO는_도메인에_있다() -> None:
    entities = ROOT / "core" / "hathor" / "domain" / "entities"
    missing = [name for name in MOVED if not (entities / f"{name}.py").is_file()]
    assert not missing, f"도메인에 없다: {missing}"


def test_저장소는_응용을_아예_안_본다() -> None:
    """`TYPE_CHECKING` 안이라도 본 것은 본 것이다 — 그것이 예외 다섯 줄의 정체였다."""
    offenders: list[str] = []
    for path in sorted((CORE / "infrastructure").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "hathor.application"
            ):
                offenders.append(f"{path.name}:{node.lineno} -> {node.module}")
    assert not offenders, f"저장소가 응용을 본다: {offenders}"
