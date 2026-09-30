"""빚의 크기가 실물과 같은가 (D-0222 · D-0308).

**크기를 재서 적는다**가 §3의 규칙이다 (D-0126). 그런데 잰 뒤로 아무도 다시 안 쟀다 —
«재현 불명 95건»이 실물 93건이 된 채 남아 있었다. **적되 묶는다** (thoth `check_counts.py`).

**갚은 빚은 `MASTER.md`로 내려간다** (D-0308). PLAN은 미갚만 든다 — 그래서 이 시험은
두 문서를 다 본다. 갚혔다고 수가 틀려도 되는 것이 아니다.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "docs" / "PLAN.md"
MASTER = ROOT / "docs" / "MASTER.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"


def _claim(pattern: str) -> int:
    """PLAN §3이나 `MASTER.md` 갚음표가 적은 수. **둘 다 본다** (D-0308).

    갚은 빚은 PLAN에서 지우고 `MASTER.md`로 내린다 — 미래 문서가 과거를 이고 가지 않게
    하려는 것이다. **그러면 이 시험이 찾던 줄이 PLAN에서 사라진다.** 옮겨 간 자리에서도
    같은 것을 묻는다: «그 줄이 말하는 수가 실물과 같은가».
    """
    for path in (PLAN, MASTER):
        found = re.search(pattern, path.read_text(encoding="utf-8"))
        if found:
            return int(found.group(1))
    raise AssertionError(
        f"PLAN §3에도 갚음표에도 `{pattern}`이 없다 — 문구를 바꿨으면 이 시험도 고친다"
    )


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

    **그리고 줄 자체가 `MASTER.md`로 옮겨 갔다** (D-0308). 같은 물음을 그 자리에 한다.
    """
    pinned: dict[str, int] = tool_module("check_test_types").PINNED
    assert _claim(r"검사 코드 타입 오류.*?\*\*(\d+)\*\*") == sum(pinned.values())


def test_합성만으로_선_강제자_수가_대장과_같다() -> None:
    """**«뭘 믿냐»에 답하는 수다** (D-0265).

    대장 201건 중 자료 칸이 `합성`인 것이 몇인가. 이 수가 PLAN의 주장과 어긋나면
    **둘 중 하나가 낡았고, 낡은 쪽은 사람이 읽는 쪽이다.**

    **꼬리표를 떼는 것은 `decision_ledger.evidence_base`가 든다** (D-0323). 이 식이 여기
    한 벌 더 있었고 `합성 (D-xxxx 승격 아님)`이 생기자 **열이 넷으로 보였다** — 세 번째
    사본이었다.
    """
    base = tool_module("decision_ledger").evidence_base
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    block = master.split("<!-- decision-ledger:begin -->")[1].split("<!-- decision-ledger:end -->")[
        0
    ]
    rows = [line for line in block.splitlines() if line.startswith("| D-")]
    synthetic = [row for row in rows if base(row.rsplit("|", 2)[1]) == "합성"]

    assert rows, "대장이 비었다"
    assert _claim(r"강제자 \*\*(\d+)건\*\*이 합성 자료만으로") == len(synthetic)
