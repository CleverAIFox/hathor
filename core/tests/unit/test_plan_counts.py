"""`PLAN.md` §3이 적은 빚의 크기가 실물과 같은가 (D-0222).

**크기를 재서 적는다**가 §3의 규칙이다 (D-0126). 그런데 잰 뒤로 아무도 다시 안 쟀다 —
«재현 불명 95건»이 실물 93건이 된 채 남아 있었다. **적되 묶는다** (thoth `check_counts.py`).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "docs" / "PLAN.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"


def _claim(pattern: str) -> int:
    found = re.search(pattern, PLAN.read_text(encoding="utf-8"))
    assert found, f"PLAN §3에서 `{pattern}`을 못 찾았다 — 문구를 바꿨으면 이 시험도 고친다"
    return int(found.group(1))


def test_재현_불명_건수가_실물과_같다() -> None:
    actual = sum(
        1
        for line in DECISIONS.read_text(encoding="utf-8").splitlines()
        if line.startswith("재현 불명")
    )
    assert _claim(r"재현 불명 (\d+)건") == actual


def test_시험_코드_타입_오류가_래칫과_같다() -> None:
    """**갚은 뒤에도 문구와 실물은 같아야 한다** (D-0264).

    옛 문구는 «검사 코드 타입 오류 66건»이었다. 다 갚아 0이 되자 그 줄이 취소선이 되고
    수는 «1421 → 75 → 66 → **0**»의 끝으로 옮겼다 — **줄의 모양이 바뀌어도 이 시험이
    같은 것을 물어야 한다.** 묻는 것은 «그 줄이 말하는 수가 못과 같은가»다.
    """
    path = ROOT / "tools" / "check_test_types.py"
    spec = importlib.util.spec_from_file_location("check_test_types", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_test_types"] = module
    spec.loader.exec_module(module)
    pinned: dict[str, int] = module.PINNED
    assert _claim(r"검사 코드 타입 오류.*?\*\*(\d+)\*\*") == sum(pinned.values())


def test_합성만으로_선_강제자_수가_대장과_같다() -> None:
    """**«뭘 믿냐»에 답하는 수다** (D-0265).

    대장 201건 중 자료 칸이 `합성`인 것이 몇인가. 이 수가 PLAN의 주장과 어긋나면
    **둘 중 하나가 낡았고, 낡은 쪽은 사람이 읽는 쪽이다.**
    """
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    block = master.split("<!-- decision-ledger:begin -->")[1].split("<!-- decision-ledger:end -->")[
        0
    ]
    rows = [line for line in block.splitlines() if line.startswith("| D-")]
    synthetic = [row for row in rows if row.rsplit("|", 2)[1].strip() == "합성"]

    assert rows, "대장이 비었다"
    assert _claim(r"강제자 \*\*(\d+)건\*\*이 합성 자료만으로") == len(synthetic)
