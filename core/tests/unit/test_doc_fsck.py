"""문서 ↔ 실물 대조 검사 (D-0189)."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("doc_fsck")


def test_저장소가_통과한다():
    """**이것이 `make docs`가 매번 보는 것이다.**"""
    assert CHECKER.check_paths() == []
    assert CHECKER.check_commands() == []
    assert CHECKER.check_orphan_tools() == []
    assert CHECKER.check_wiring() == []


def test_배선이_없는_스크립트를_부르면_잡는다(tmp_path, monkeypatch):
    """**`make apply`를 커밋 직전에 죽인 것이 이것이다** (D-0196).

    `check_orphan_tools`는 *"도구가 불리는가"*를 묻고 이쪽은 *"부르는 이름이
    실재하는가"*를 묻는다. 방향이 반대라 저쪽이 초록인 채로 이것이 났다.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "붙인다.sh").write_text(
        "python3 tools/없어진도구.py --check\n", encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring()


def test_주석_속_예시는_안_잡는다(tmp_path, monkeypatch):
    """사용법 예시가 주석에 산다. **실행되지 않으므로 없어도 안 죽는다.**"""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "붙인다.sh").write_text(
        "#   python3 tools/예시.py 처럼 쓴다\ntrue\n", encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring() == []


def test_없는_경로를_잡는다(tmp_path, monkeypatch):
    """**백틱 안의 저장소 경로만 본다** — 산문의 예시와 구분이 안 된다."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "README.md").write_text("`tools/없다.py`를 쓴다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_paths()


def test_산출물은_없어도_된다(tmp_path, monkeypatch):
    """`.park` 뒤에 있어 없는 것이 정상이다 (D-0075)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "README.md").write_text("`docs/x.jsonl`을 읽는다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_paths() == []


def test_과거_문서는_안_본다():
    """**결정 기록은 그때를 적는다.** 소급해서 고치지 않는다 (GR-0.2 · D-0081)."""
    assert "DECISIONS.md" not in CHECKER.LIVING


def test_파이썬이_인자로_부르는_도구도_본다(tmp_path, monkeypatch):
    """**`ship.py`가 `_run("python3", "tools/x.py")`로 부른다** (D-0199).

    인자가 쪼개져 있어 셸용 정규식이 못 본다. 개명하면 같은 자리에서 같은
    모양으로 죽는다 — D-0196이 겪은 그것이다.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "보낸다.py").write_text(
        'run("python3", "tools/없어진도구.py", "status")\n', encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring()


def test_문서_문자열_속_예시는_안_잡는다(tmp_path, monkeypatch):
    """`ast`로 **호출 인자만** 보므로 산문은 공짜로 빠진다."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "보낸다.py").write_text(
        '"""사용법:\n\n    python3 tools/예시.py --check\n"""\n', encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring() == []


# --------------------------------------------------------- 세어서 적은 수 (D-0263)


def test_저장소의_수가_실물과_같다():
    """**D-0263의 강제자.** `make docs`가 매번 보는 것이다."""
    assert CHECKER.check_counts() == []


def test_계약_수가_어긋나면_잡는다(tmp_path, monkeypatch):
    """**D-0261이 여섯째 계약을 넣고 «계약 5종» 네 곳을 안 고쳤다** (D-0263).

    경로도 도구도 실재하므로 이 검사의 다른 눈에는 안 걸렸다 — **숫자만 틀렸다.**
    경로가 틀리면 명령이 죽어서 알게 되지만 수가 틀리면 아무 일도 안 일어난다.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MASTER.md").write_text("**계약 5종**\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(
        CHECKER, "COUNTED", ((CHECKER.COUNTED[0][0], CHECKER.COUNTED[0][1], lambda: 6),)
    )

    problems = CHECKER.check_counts()
    assert len(problems) == 1
    assert "5종이라 적혔는데 실물은 6종이다" in problems[0]


def test_맞는_수는_안_잡는다(tmp_path, monkeypatch):
    """**맞을 때 조용해야 검사다.** 비교를 뒤집으면 여기가 운다."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MASTER.md").write_text(
        "import-linter 계약 6종 전부 KEPT\n| 계층 계약 | import-linter 6종 |\n", encoding="utf-8"
    )
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(
        CHECKER, "COUNTED", ((CHECKER.COUNTED[0][0], CHECKER.COUNTED[0][1], lambda: 6),)
    )

    assert CHECKER.check_counts() == []


def test_계약_수를_pyproject에서_센다():
    """**정본은 `core/pyproject.toml` 하나다** (D-0223). 문서가 아니라 선언을 센다."""
    assert CHECKER.contract_count() == 6
