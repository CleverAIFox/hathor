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


def test_부류별로_못이_박혀_있다():
    """**합계만 박으면 어느 부류가 달라졌는지 모른다** (D-0151)."""
    assert isinstance(RATCHET.PINNED, dict)
    assert RATCHET.total(RATCHET.PINNED) > 0


def test_못_재면_0으로_안_넘긴다(monkeypatch):
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert RATCHET.measure() is None


def test_오류_수를_읽는다(monkeypatch):
    """**요약 줄이 아니라 오류 줄을 센다** (D-0150). 요약은 환경 의존까지 포함한다."""

    class Done:
        stdout = (
            "tests/x.py:1: error: 뭐가 틀렸다  [arg-type]\n"
            "tests/x.py:2: error: 또  [index]\n"
            "Found 2 errors in 1 file\n"
        )
        stderr = ""

    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: Done())
    assert RATCHET.measure() == 2


def test_없으면_0이다(monkeypatch):
    class Done:
        stdout = "Success: no issues found in 61 source files\n"
        stderr = ""

    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: Done())
    assert RATCHET.measure() == 0


def test_못_재면_None이다(monkeypatch):
    """**0과 못 잰 것은 다르다** (GR-0.5)."""
    monkeypatch.setattr(RATCHET.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert RATCHET.measure() is None


def test_성장에는_결정_기록이_필요하다():
    """**손이 한 번 멈추는 것이 요점이다** (D-0118)."""
    source = (ROOT / "tools" / "check_test_types.py").read_text(encoding="utf-8")
    assert "--allow-growth" in source
    assert "D-0118" in source


# ------------------------------------------------------------------ 흔들리지 않는다 (D-0150)


def test_환경_의존_부류를_안_센다():
    """첫 못이 75였는데 **다른 기기에서 76이 나왔다.**

    같은 코드에서 수가 다르면 래칫이 아니다. `unused-ignore`는 스텁이 깔렸는지에,
    `import-not-found`는 `MYPYPATH`에 따라 달라진다.
    """
    assert "unused-ignore" in RATCHET.VOLATILE
    assert "import-not-found" in RATCHET.VOLATILE


def test_부류별로_센다():
    text = (
        "tests/a.py:1: error: 뭐가 틀렸다  [arg-type]\n"
        "tests/a.py:2: error: 또 틀렸다  [arg-type]\n"
        "tests/b.py:3: error: 스텁이 생겼다  [unused-ignore]\n"
    )
    assert RATCHET.tally(text) == {"arg-type": 2}


def test_어긋나면_어디가_다른지_찍는다():
    """**다음 어긋남을 한 번에 가리게 한다.** 수만 보면 또 추측한다."""
    source = (ROOT / "tools" / "check_test_types.py").read_text(encoding="utf-8")
    body = source.split("if counts != PINNED:")[1].split("return 1")[0]
    assert "_report(" in body


# ------------------------------------------------------------------ 부류별 못 (D-0151)


def test_어긋난_부류의_줄을_찍는다(capsys):
    """**부류만 보면 또 한 판 물어야 한다.**

    D-0150이 부류 표를 찍게 했더니 `assignment` 하나가 다른 것이 보였다. 그런데
    **어느 줄인지는 여전히 몰랐다.**
    """
    counts = dict(RATCHET.PINNED)
    counts["assignment"] = 1
    raw = "tests/unit/test_x.py:10: error: 대입 형이 안 맞는다  [assignment]\n"
    RATCHET._report(counts, raw)
    text = capsys.readouterr().err
    assert "assignment" in text
    assert "test_x.py:10" in text


def test_안_달라진_부류는_표시가_없다(capsys):
    RATCHET._report(dict(RATCHET.PINNED), "")
    assert "←" not in capsys.readouterr().err


def test_못을_정렬해_쓴다():
    """**차례가 기기마다 달라지면 못 읽는다.**"""
    source = (ROOT / "tools" / "check_test_types.py").read_text(encoding="utf-8")
    assert "sorted(counts.items()" in source
