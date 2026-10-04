"""**부품은 재고 배선은 안 쟀다** — 한 곳씩 남은 것들 (D-0359).

`bake_proposal` · `build_proposal` · `check_decisions` · `check_doc_style` ·
`check_model_licenses` · `check_patch` · `check_secrets` · `docx_check` · `var_fsck`.

**한 곳이라 가볍게 보이지만 그 한 곳이 입구다.** 끊으면 도구가 통째로 조용해진다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module

BAKE = tool_module("bake_proposal")
BUILD = tool_module("build_proposal")
DECISIONS = tool_module("check_decisions")
STYLE = tool_module("check_doc_style")
LICENSES = tool_module("check_model_licenses")
PATCH = tool_module("check_patch")
SECRETS = tool_module("check_secrets")
DOCX = tool_module("docx_check")
VAR = tool_module("var_fsck")

PLANTED = "심은 문제"


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


def test_굽기가_배선돼_있다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`bake()` 자리. **PDF를 굽지 않고 0을 내면 배포가 빈 파일을 올린다.**"""
    stub = tmp_path / "기획서.docx"
    stub.write_bytes(b"PK")
    monkeypatch.setattr(BAKE, "bake", lambda docx, out: 5)
    monkeypatch.setattr("sys.argv", ["bake_proposal.py", "--docx", str(stub)])

    assert BAKE.main() == 5


def test_빌드한_수가_화면에_오른다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`build()` 자리. **그림 0장을 0장이라고 안 찍으면 빈 기획서가 나간다** (D-0221)."""
    monkeypatch.setattr(BUILD, "build", lambda out, figures: {"figures": 3, "tables": 4})
    monkeypatch.setattr("sys.argv", ["build_proposal.py", "--out", str(tmp_path / "나온다.docx")])

    assert BUILD.main() == 0
    assert "그림 3장 · 표 4개" in _spoke(capsys)


def test_결정_기록_검사가_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`run_checks()` 자리 — **기록 축 전부가 이 한 줄을 지난다** (D-0189)."""
    monkeypatch.setattr(DECISIONS, "run_checks", lambda *_: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_decisions.py", "--check"])

    assert DECISIONS.main() == 1
    assert PLANTED in _spoke(capsys)


def test_문서_레이아웃_통과줄이_문서_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`targets()` 자리. **0개를 보고 「통과」를 찍던 모양** (D-0230)."""
    monkeypatch.setattr(STYLE, "check", list)
    monkeypatch.setattr(STYLE, "targets", lambda: [Path("가"), Path("나")])
    monkeypatch.setattr("sys.argv", ["check_doc_style.py", "--check"])

    assert STYLE.main() == 0
    assert "문서 2개" in _spoke(capsys)


def test_문서_레이아웃_list가_대상을_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--list` 쪽 `targets()` 자리. **무엇을 보는지 못 찍으면 시야를 사람이 못 센다.**"""
    monkeypatch.setattr(STYLE, "ROOT", Path("/뿌리"))
    monkeypatch.setattr(STYLE, "targets", lambda: [Path("/뿌리/심은문서.md")])
    monkeypatch.setattr("sys.argv", ["check_doc_style.py", "--list"])

    assert STYLE.main() == 0
    assert "심은문서.md" in _spoke(capsys)


def test_상업_불가_수가_화면에_오른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`blocked()` 자리 (D-0217). **몇 개가 상업 불가인지 눈앞에 둔다** — 가리키면 안 본다."""
    monkeypatch.setattr(LICENSES, "check", list)
    monkeypatch.setattr(LICENSES, "blocked", lambda: ["하나", "둘"])
    monkeypatch.setattr("sys.argv", ["check_model_licenses.py", "--check"])

    assert LICENSES.main() == 0
    assert "상업 불가 2" in _spoke(capsys)


def test_패치_머리_곳의_수가_화면에_오른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`places()` 자리 (D-0043). **네 곳이 셋으로 줄어도 통과가 떴다.**"""
    monkeypatch.setattr(PATCH, "check_heads", list)
    monkeypatch.setattr(PATCH, "check_floor", list)
    monkeypatch.setattr(PATCH, "places", lambda: {"가": "", "나": ""})
    monkeypatch.setattr("sys.argv", ["check_patch.py", "--no-live"])

    assert PATCH.main() == 0
    assert "곳 2개" in _spoke(capsys)


def test_비밀정보_검사가_추적_목록을_거친다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tracked()` 자리 (D-0128). 끊으면 **파일 0개를 보고 「통과」가 뜬다.**"""
    monkeypatch.setattr(SECRETS, "check", lambda _: [])
    monkeypatch.setattr(SECRETS, "tracked", lambda: ["가", "나"])
    monkeypatch.setattr("sys.argv", ["check_secrets.py", "--check"])

    assert SECRETS.main() == 0
    assert "추적 2개" in _spoke(capsys)


def test_정본_대조_건수가_화면에_오른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`truths()` 자리 (D-0220). **대조 0건이면 기획서는 아무것과도 안 맞춰진 것이다.**"""
    monkeypatch.setattr(DOCX, "check", list)
    monkeypatch.setattr(DOCX, "truths", lambda _: ["가", "나", "다"])
    monkeypatch.setattr("sys.argv", ["docx_check.py", "--check"])

    assert DOCX.main() == 0
    assert "정본 대조 3건" in _spoke(capsys)


def test_산출물_판정이_래칫_여부를_그대로_받는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`report()` 자리 (D-0203 · D-0245). **`--ratchet`이 안 닿으면 옛 실행이 영원히 남는다.**"""
    seen: list[bool] = []

    def noted(root: Path, ratchet: bool) -> int:
        seen.append(ratchet)
        return 7

    monkeypatch.setattr(VAR, "report", noted)

    monkeypatch.setattr("sys.argv", ["var_fsck.py", "--root", str(tmp_path)])
    assert VAR.main() == 7
    monkeypatch.setattr("sys.argv", ["var_fsck.py", "--root", str(tmp_path), "--ratchet"])
    assert VAR.main() == 7

    assert seen == [False, True]
