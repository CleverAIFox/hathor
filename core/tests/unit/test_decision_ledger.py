"""강제자 파서는 **한 자리다** (D-0304).

`강제자` 칸을 읽는 정규식이 세 군데 있었고 **셋 다 다르게 틀렸다** — 대장은 행을 버리고
`check_doc_style`은 경로 존재를 안 보고 `check_keepers`는 함수를 안 봤다. 머리만 두고
들여쓴 꼴을 아무도 못 읽어 **네 판이 그 상태로 열일곱 관문을 통과하고 푸시까지 갔다.**

### 왜 이 파일이 따로 있는가

`test_check_decisions.py`가 700줄 상한에 닿았다 (D-0117). 파서가 `decision_ledger.py`에
있으므로 그 시험은 여기로 온다. **옛 대장 시험은 그 파일에 그대로 둔다** — 소급해 옮기면
«그때 무엇을 검사했나»가 흐려지고, 표기가 아니라 자리를 바꾸는 일이다 (D-0081의 정신).
"""

from __future__ import annotations

import sys

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import check_doc_style as style
import decision_evidence as evidence
import decision_ledger as ledger

DECISIONS = repo_root() / "docs" / "DECISIONS.md"

HEAD = "# 결정 기록\n\n"


def record(number: int, body: str = "- **배경**: 무엇이 있었다.\n") -> str:
    return f"\n---\n\n## D-{number:04d}. 제목 {number}\n\n{body}\n"


def decisions(*numbers: int) -> str:
    return HEAD + "".join(record(number) for number in numbers)


INDENTED = """강제자
    `core/tests/unit/test_check_decisions.py::test_하나`
    `core/tests/unit/test_check_decisions.py::test_둘`
"""


def test_여러_줄_강제자를_읽는다() -> None:
    """**시험 아홉 개는 한 줄에 안 들어간다** (100자 · D-0081).

    머리만 두고 들여쓴 꼴을 파서 셋이 다 놓쳐 **대장이 네 판을 버렸다** (D-0304).
    """
    read = ledger.keeper_text(INDENTED)
    assert read is not None
    assert read.count(" · ") == 1
    assert "test_하나" in read
    assert "test_둘" in read
    # 한 줄 꼴도 그대로 읽는다 — 옛 기록 전부가 그 꼴이다.
    assert (
        ledger.keeper_text("강제자  `tools/a.py` · `tools/b.py`") == "`tools/a.py` · `tools/b.py`"
    )


def test_빈_강제자_칸을_잡는다() -> None:
    """머리만 두고 들여쓰기를 잊으면 **다시 조용히 빠진다.** 구멍 0에 박은 못이다."""
    records = ledger.scan_records(decisions() + record(304, "강제자\n\n- **결과**: 없다.\n"))
    (problem,) = evidence.check_keeper_text(records)
    assert "비어 있다" in problem
    assert (
        evidence.check_keeper_text(ledger.scan_records(decisions() + record(304, INDENTED))) == []
    )


def test_없음_선언은_칸이_있는_것이다() -> None:
    """**«칸이 있는가»와 «내용이 무엇인가»는 다른 질문이다** (D-0132 · D-0304).

    `강제자 없음 — 사유: …`는 칸이 **있는** 것이고 대장에는 안 실린다. 한 함수로 합치면
    «없음»이 «칸이 없다»로 읽혀 전수 강제가 무너진다.
    """
    declared = "강제자 없음 — 사유: 방향 결정이다\n"
    assert ledger.keeper_text(declared) is None
    assert (
        evidence.check_keeper_text(ledger.scan_records(decisions() + record(304, declared))) == []
    )
    assert style._has_keeper(declared)
    assert not style._has_keeper("- **결과**: 없다.\n")


def test_지금_대장에_최근_판이_전부_있다() -> None:
    """**행이 없으면 아무도 없다는 것을 모른다** (D-0230 · D-0304).

    틀린 수가 실리면 검사가 잡는다. 빠진 행은 잡는 것이 없어 **네 판 연속으로 조용했다.**
    """
    text = DECISIONS.read_text(encoding="utf-8")
    table = ledger.build_ledger(text)
    listed = {line.split("|")[1].strip() for line in table.splitlines() if line.startswith("| D-")}
    for identifier, _, body in ledger.records_with_body(text):
        if ledger.keeper_text(body):
            assert identifier in listed, f"{identifier}의 강제자가 대장에 없다"


# ------------------------------------------ 승격 아님 꼬리표 (D-0317 · D-0323)


def marked(number: int, source: str, updated: int | None = None) -> str:
    """`자료` 칸과 갱신 배지를 가진 기록 하나."""
    badge = f"> **갱신됨 — D-{updated:04d}.** 무엇을 찾았다.\n\n" if updated else ""
    return (
        f"\n---\n\n## D-{number:04d}. 제목 {number}\n\n{badge}"
        "- **배경**: 무엇이 있었다.\n\n"
        f"자료  {source}\n"
    )


def test_승격_아님을_적으면_명단에서_나간다() -> None:
    """**「아니다」로만 찬 명단은 아무도 안 읽는다** (D-0323).

    첫 판에서 다섯이던 것이 두 판 만에 일곱이 됐다 — 뒤 판이 앞 판을 뒤집을 때마다
    한 줄이 영원히 쌓인다.
    """
    text = HEAD + marked(100, "합성", updated=200) + marked(200, "실물 1004곡")
    rows = ledger.scan_records(text)
    assert evidence.payable(rows) == ["D-0100 ← D-0200"]

    judged = HEAD + marked(100, "합성 (D-0200 승격 아님)", updated=200) + marked(200, "실물 1004곡")
    assert evidence.payable(ledger.scan_records(judged)) == []


def test_꼬리표가_붙어도_합성으로_센다() -> None:
    """**꼬리표는 「뒤 판이 안 올린다」이지 「실물이 됐다」가 아니다** (D-0323).

    합성 수가 줄면 빚이 갚인 것처럼 보이고 PLAN이 그 수를 든다.
    """
    assert ledger.EVIDENCE_VALUES.match("합성 (D-0200 승격 아님)")
    assert ledger.evidence_base("합성 (D-0200 승격 아님)") == "합성"
    assert ledger.evidence_base("합성 · 실물 40곡") == "합성 · 실물 40곡"
    # **세는 쪽이 같은 정본을 쓴다** — 두 벌이 되면 한쪽만 고치는 날이 온다.
    import doc_fsck

    assert doc_fsck.evidence_base is ledger.evidence_base


def test_꼬리표도_뒤_번호여야_한다() -> None:
    """`(D-xxxx 확인)`과 같은 규율이다 (D-0301 · D-0323). 앞 번호는 갱신할 수 없다."""
    bad = HEAD + marked(200, "합성 (D-0100 승격 아님)") + marked(100, "실물 1004곡")
    problems = evidence.check_evidence(ledger.scan_records(bad))
    assert any("앞 번호다" in problem for problem in problems)

    good = HEAD + marked(100, "합성 (D-0200 승격 아님)") + marked(200, "실물 1004곡")
    assert evidence.check_evidence(ledger.scan_records(good)) == []


def test_지금_명단이_비어_있다() -> None:
    """**모든 줄이 판단됐다는 뜻이다** (D-0323).

    0이 목표가 아니라 **판단을 기다리는 줄만 남는 것**이 목표다 — 새 합성 판을 뒤
    실물 판이 갱신하면 다시 한 줄이 선다.
    """
    rows = ledger.scan_records(DECISIONS.read_text(encoding="utf-8"))
    assert evidence.payable(rows) == []
