"""검사 코드 타입 래칫의 단위 검사 (D-0149).

**래칫이 래칫이려면 양방향이어야 한다** (D-0117). 늘어도 줄어도 빨개진다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "check_test_types.py"
    spec = importlib.util.spec_from_file_location("check_test_types", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_test_types"] = module
    spec.loader.exec_module(module)
    return module


RATCHET = _module()


def test_주석을_요구하지_않는다():
    """`-> None` **1111개는 잡음이고 잡음이 많으면 검사를 끈다.**"""
    assert "--allow-untyped-defs" in RATCHET.COMMAND
    assert "--allow-untyped-calls" in RATCHET.COMMAND


def test_못이_박혀_있다():
    assert RATCHET.PINNED > 0


def test_못_재면_0으로_안_넘긴다(monkeypatch):
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert RATCHET.measure() is None


def test_오류_수를_읽는다(monkeypatch):
    class Done:
        stdout = "tests/x.py:1: error: 뭐가 틀렸다\nFound 12 errors in 3 files\n"
        stderr = ""

    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: Done())
    assert RATCHET.measure() == 12


def test_없으면_0이다(monkeypatch):
    class Done:
        stdout = "Success: no issues found in 61 source files\n"
        stderr = ""

    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: Done())
    assert RATCHET.measure() == 0


def test_성장에는_결정_기록이_필요하다():
    """**손이 한 번 멈추는 것이 요점이다** (D-0118)."""
    source = (ROOT / "tools" / "check_test_types.py").read_text(encoding="utf-8")
    assert "--allow-growth" in source
    assert "D-0118" in source
