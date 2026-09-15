"""문서 ↔ 실물 대조 검사 (D-0189)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("doc_fsck", ROOT / "tools" / "doc_fsck.py")
assert _spec and _spec.loader
CHECKER = importlib.util.module_from_spec(_spec)
sys.modules["doc_fsck"] = CHECKER
_spec.loader.exec_module(CHECKER)


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
