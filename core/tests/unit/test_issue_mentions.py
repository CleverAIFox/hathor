"""닫힌 질문 표기 검사의 단위 검사 (D-0126).

**도구 자신을 검사한다** (D-0080의 규율). 검사가 아무것도 안 잡으면 통과해도 뜻이
없고, 반대로 옳게 적은 줄을 잡으면 사람이 검사를 끄게 된다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module():
    """`tools/`는 패키지가 아니다. 파일에서 직접 읽는다."""
    path = ROOT / "tools" / "check_issue_mentions.py"
    spec = importlib.util.spec_from_file_location("check_issue_mentions", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_issue_mentions"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()

DESIGN = """
<!-- closed-issues:begin -->

| # | 항목 | 결말 |
|---|---|---|
| O-38 | **닫힘 (D-0114)** | 표본 부족이다. |

<!-- closed-issues:end -->
"""


def _scan(tmp_path, monkeypatch, text: str) -> list[str]:
    """임시 나무 하나만 훑게 한다."""
    tree = tmp_path / "core" / "hathor"
    tree.mkdir(parents=True)
    (tree / "target.py").write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "DOCUMENTS", ())
    return CHECKER.check(DESIGN)


# ------------------------------------------------------------------ 잡는다


def test_맨몸_참조를_잡는다(tmp_path, monkeypatch):
    """**이것이 D-0125 세션을 헛돌게 한 자리다.**"""
    problems = _scan(tmp_path, monkeypatch, '"""O-38은 다른 원인을 찾아야 한다."""\n')
    assert len(problems) == 1
    assert "O-38" in problems[0]


def test_첫_문제에서_안_멈춘다(tmp_path, monkeypatch):
    text = "# O-38 하나\n# O-38 둘\n"
    assert len(_scan(tmp_path, monkeypatch, text)) == 2


def test_줄_번호를_적는다(tmp_path, monkeypatch):
    """고치러 갈 자리를 알려주지 않으면 검사가 일을 안 한 것이다."""
    problems = _scan(tmp_path, monkeypatch, "\n\n# O-38\n")
    assert ":3:" in problems[0]


# ------------------------------------------------------------------ 안 잡는다


def test_결정을_적으면_통과한다(tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, "# O-38 (닫힘 D-0114)\n") == []


def test_닫은_결정이_아닌_번호도_통과한다(tmp_path, monkeypatch):
    """**출처 쪽이 더 쓸모 있을 때가 있다** — `(O-31 · D-0083)`처럼.

    닫은 결정을 콕 집어 요구하는 안은 옳게 적은 줄 24곳을 잡아 기각했다.
    """
    assert _scan(tmp_path, monkeypatch, "# O-38 (D-0109)\n") == []


def test_열린_질문은_안_본다(tmp_path, monkeypatch):
    """**열린 질문에는 닫은 결정이 없다.**"""
    assert _scan(tmp_path, monkeypatch, "# O-26이 남긴 자리다\n") == []


# ------------------------------------------------------------------ 닫힘표


def test_닫힘표에서_읽는다():
    """**목록을 도구에 적지 않는다** — 두 곳이 어긋난다 (D-0043)."""
    assert CHECKER.closed_issues(DESIGN) == {"O-38": {114}}


def test_표식이_없으면_문제로_낸다():
    """조용히 0건 통과하면 검사가 사라진 것과 같다 (D-0121의 부류)."""
    assert CHECKER.check("표식 없음") != []


def test_저장소가_통과한다():
    """**지금 상태가 초록이어야 이 검사를 켤 수 있다.**"""
    design = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert CHECKER.check(design) == []


def test_검사가_실제로_자리를_본다():
    """닫힌 질문이 한 건도 안 읽히면 통과가 뜻이 없다."""
    design = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert len(CHECKER.closed_issues(design)) >= 10


@pytest.mark.parametrize("tree", ["core/hathor", "tools", "core/tests"])
def test_나무_셋을_다_훑는다(tree):
    """**검사 나무도 본다** (D-0146). 전수로 훑으니 25곳이 나왔고 전부 산문이었다."""
    assert tree in CHECKER.TREES


def test_가짜_자료를_든_검사만_뺀다():
    """**나무가 아니라 파일을 뺀다.** 둘 다 질문 번호를 자료로 들고 있다 (D-0183).

    앞의 것은 맨몸 참조를 일부러 담고, 뒤의 것은 합성한 열림·닫힘표로 색인 도구를
    시험한다. **거기 적힌 번호는 참조가 아니다.**
    """
    assert CHECKER.SKIP_FILES == (
        "core/tests/unit/test_issue_mentions.py",
        "core/tests/unit/test_check_decisions.py",
    )
