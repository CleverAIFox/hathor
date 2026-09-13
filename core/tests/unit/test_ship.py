"""푸시 파이프라인의 단위 검사 (D-0147).

**도구는 열다섯인데 파이프라인이 없었다.** 이 검사가 지키는 것은 순서가 코드에
있다는 것이다 — 사람 머리에 있으면 언젠가 하나를 빠뜨린다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "ship.py"
    spec = importlib.util.spec_from_file_location("ship", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ship"] = module
    spec.loader.exec_module(module)
    return module


SHIP = _module()


# ------------------------------------------------------------------ 순서가 코드에 있다


def test_make_check를_부른다():
    """**중복 구현하지 않는다.** `make check`가 규약을 보고 `ship`은 내보낼 수 있는지 본다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"make", "check"' in source


def test_푸시와_교두보가_한_줄에_있다():
    """`make check && git push && make artifacts-push`가 머리에만 있었다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"git", "push"' in source
    assert "sync_artifacts.py" in source


def test_검사_없이는_안_밀어낸다():
    """`make check`가 빨가면 **그 자리에서 멈춘다.**"""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split('print(f"{DIM}── 규약')[1].split("── git")[0]
    assert "return 1" in body


# ------------------------------------------------------------------ 지우지 않는다


def test_찌꺼기를_세기만_한다():
    """**무엇이 쌓이는지 실측 안 하고 지우는 정책은 지어낸 규칙이다** (GR-0.5)."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split("def count_leftovers")[1].split("\ndef ")[0]
    assert "rm" not in body
    assert "unlink" not in body


def test_유물_목록이_비어_있지_않다():
    """`.backup/`과 `.o7-*/`는 D-0072가 없앤 것이다. **쌓여 있다면 소식이다.**"""
    assert ".backup" in SHIP.LEFTOVERS


def test_저장소에_유물이_없다():
    lines = SHIP.count_leftovers()
    assert not any("유물" in line for line in lines)


# ------------------------------------------------------------------ git


def test_워킹트리가_더러우면_막는다(monkeypatch):
    monkeypatch.setattr(SHIP, "_git", lambda *a: "M x.py" if a[0] == "status" else "origin/main")
    problems = SHIP.check_git()
    assert problems and "워킹트리" in problems[0]


def test_upstream이_없으면_막는다(monkeypatch):
    monkeypatch.setattr(SHIP, "_git", lambda *a: "")
    assert any("upstream" in line for line in SHIP.check_git())


def test_깨끗하면_안_막는다(monkeypatch):
    monkeypatch.setattr(SHIP, "_git", lambda *a: "" if a[0] == "status" else "origin/main")
    assert SHIP.check_git() == []


def test_check는_안_받는다():
    """`--check`를 달면 `make check` 사슬에 넣으라고 부류 검사가 요구한다 (D-0121).

    **`ship`은 `make check`를 부르는 쪽이라 사슬에 들어갈 수 없다.**
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"--check"' not in source
