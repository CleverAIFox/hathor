"""푸시 파이프라인의 단위 검사 (D-0147).

**도구는 열다섯인데 파이프라인이 없었다.** 이 검사가 지키는 것은 순서가 코드에
있다는 것이다 — 사람 머리에 있으면 언젠가 하나를 빠뜨린다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# **`ship.py`가 `tidy`를 임포트한다.** 이 줄이 없으면 이 파일만 따로 돌릴 때 수집에서
# 죽고, 전체를 돌릴 때는 *다른 시험이 먼저 넣어 준 덕에* 통과한다 — 순서에 기댄 초록이다.
# 병렬 실행은 순서를 안 지켜 준다 (D-0238 · D-0239).
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


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


# ------------------------------------------------------------------ 세는 범위 (D-0148)


def test_venv를_안_센다():
    """첫 실측 449개 중 **대부분이 `.venv`였다.**

    **세는 수가 틀리면 그 수를 보고 한 행동도 틀린다.**
    """
    assert ".venv" in SHIP.OUTSIDE
    assert "var" in SHIP.OUTSIDE


def test_산출물은_찌꺼기가_아니다():
    """`var/`는 안 센다 (D-0067)."""
    lines = SHIP.count_leftovers()
    assert not any("var/" in line for line in lines)


def test_지우는_범위를_두_곳에_안_적는다():
    """**`--fix`는 `make clean`을 부른다.** 두 곳에 적으면 어긋난다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split("if args.fix:")[1].split("print(")[0]
    assert '"make", "clean"' in body
    assert "rm" not in body


def test_clean이_venv를_지나친다():
    """D-0067이 *"`.venv/`는 남긴다"*고 적었는데 **`clean`은 안 지켰다.**"""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = makefile.split("clean:")[1].split("\nclean-all:")[0]
    assert "-prune" in body
    assert ".venv" in body


def test_교두보가_배를_가라앉히지_않는다():
    """**`git push`는 이미 끝났다** (D-0068 · D-0239).

    외장이 빠졌거나 DrvFs가 토라진 것으로 «내보내기 실패»를 찍으면, 사람은 무엇이
    밀려갔는지 모른 채 다시 친다. 실제로 `make ship`이 push 뒤에 역추적을 뿜고 죽었다.
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    tail = source.split('"push", "--only"', 1)[1]
    assert "교두보로 못 보냈다" in tail
    assert "return code" not in tail, "교두보 실패가 종료 코드를 잡으면 배가 가라앉는다"
