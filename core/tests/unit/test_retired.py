"""지운 말 검사의 단위 검사 (D-0349).

**여기 있는 넷은 카나리아다** — 그날 실물에 있던 네 문장을 그대로 심고 **우는지** 본다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_retired")


@pytest.mark.parametrize(
    "line",
    [
        "**`docs/DECISIONS.md`가 자기 색인을 든다** (D-0133 · D-0187).",
        "## 부록 A. 결정 기록 색인",
        "`make check`가 다음을 본다: 색인 일치 · 번호 중복·결번",
        "- `docs/DECISIONS.md` — 설계 결정 기록과 전체 색인",
    ],
)
def test_지운_말이_근거_없이_남으면_잡는다(line: str) -> None:
    """**그날 실물에 있던 네 문장 그대로다** (D-0349).

    D-0189가 색인을 없애며 *"같은 목록이 두 곳에 사는 구조"*라 적었는데 `MASTER`는
    **160판 뒤에도** 색인을 든다고 적고 있었다. `docx_check.RETIRED`가 같은 일을
    **기획서에만** 하고 있었다.
    """
    assert cast("list[str]", CHECKER.check_retired_words("docs/MASTER.md", line))


@pytest.mark.parametrize(
    "line",
    [
        "**색인은 없다** (D-0189가 없앴다 — D-0042 · D-0133 · D-0186을 되돌렸다).",
        "| D-0189 | 색인을 없애고 문서 ↔ 실물 강제자를 세운다 | … |",
        "보관소를 없앴다 — `docs/archive`는 D-0186이 지웠다",
    ],
)
def test_지운_결정을_같이_적으면_통과한다(line: str) -> None:
    """**지운 말을 「지웠다」고 쓰는 것은 정상이다.**

    `check_issue_mentions`가 닫힌 질문에 쓰는 규칙과 **같은 꼴**이다 (D-0126) — 번호가
    붙어 있으면 읽는 사람이 이력을 따라갈 수 있다. 막으려는 것은 **맨몸 부활**이다.
    """
    assert cast("list[str]", CHECKER.check_retired_words("docs/MASTER.md", line)) == []


def test_과거_축은_안_본다() -> None:
    """**그때는 살아 있던 말이고 소급 수정이 금지다** (D-0081).

    기획서도 안 본다 — `docx_check`가 **제 목록**으로 본다. 그 둘이 다른 부류라서다:
    저쪽은 *거짓이 된 주장*이고 여기는 *지워진 이름*이며, 여기만 「같은 줄에 결정 번호」
    탈출구가 있다.
    """
    assert "docs/DECISIONS.md" not in CHECKER.LIVING
    assert "docs/proposal.docx" not in CHECKER.LIVING
    assert len(CHECKER.LIVING) == 3, CHECKER.LIVING


def test_지운_말마다_결정과_사유가_붙어_있다() -> None:
    """**사유 없는 금지어는 다음 판이 왜 금지인지 몰라 되살린다** (GR-0.5)."""
    assert CHECKER.RETIRED_WORDS
    for word, decision, why in CHECKER.RETIRED_WORDS:
        assert word.strip()
        assert re.fullmatch(r"D-\d{4}", decision), decision
        assert len(why) > 3, (word, why)


def test_살아_있는_문서가_통과한다() -> None:
    for name in ("README.md", "docs/PLAN.md", "docs/MASTER.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert cast("list[str]", CHECKER.check_retired_words(name, text)) == [], name
