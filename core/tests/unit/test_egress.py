"""망 송신 접점 검사의 단위 검사 (D-0134).

**오디오 비이동(D-0015)은 이 저장소에서 어기면 가장 나쁜 규약이다.** 그런데 D-0132가
`강제자`를 전수로 채울 때까지 **아무것도 그것을 지키지 않았다.**
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "check_egress.py"
    spec = importlib.util.spec_from_file_location("check_egress", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_egress"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()


def _tree(tmp_path, monkeypatch, name: str, text: str):
    target = tmp_path / "core" / "hathor" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "ALLOWED", {})
    return CHECKER.check()


# ------------------------------------------------------------------ 잡는다


def test_새_망_접점을_잡는다(tmp_path, monkeypatch):
    problems = _tree(tmp_path, monkeypatch, "interfaces/rest/api.py", "import httpx\n")
    assert len(problems) == 1
    assert "httpx" in problems[0]


def test_from_임포트도_잡는다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a.py", "from urllib import request\n")


def test_하위_폴더까지_본다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a/b/c.py", "import socket\n")


def test_허용_목록이_실물보다_넓으면_잡는다(tmp_path, monkeypatch):
    """**목록이 실물보다 넓으면 방패가 아니라 사각지대다.**"""
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "ALLOWED", {"없는파일.py": "사유"})
    problems = CHECKER.check()
    assert problems and "없다" in problems[0]


# ------------------------------------------------------------------ 안 잡는다


def test_파일을_여는_것은_안_본다(tmp_path, monkeypatch):
    """**로컬 분석은 당연히 음원을 읽는다.** 막으려는 것은 기기 밖으로 나가는 것이다."""
    assert _tree(tmp_path, monkeypatch, "a.py", "from pathlib import Path\nopen('x.mp3')\n") == []


def test_넘파이는_망이_아니다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a.py", "import numpy as np\n") == []


# ------------------------------------------------------------------ 저장소


def test_접점이_전부_musicbrainz다():
    """**구멍을 못 박아 두면 다음 구멍은 이 검사를 지나야 생긴다.**

    D-0146이 `tools`를 훑기 시작하며 하나가 늘었다 — `probe_musicbrainz.py`가
    `urllib`을 쓰는데 **검사 밖이었다.**
    """
    assert all("musicbrainz" in name for name in CHECKER.ALLOWED)


def test_도구도_훑는다():
    """**도구도 이 기기에서 돈다.** 나무를 빼면 그만큼이 사각지대다."""
    assert "tools" in CHECKER.TREES
    assert any(path.as_posix().endswith("probe_musicbrainz.py") for path in CHECKER.found_files())


def test_허용된_접점이_사유를_적는다():
    """**늘리지 않는 것이 목표다.** 사유 없는 줄은 다음 줄을 부른다."""
    for reason in CHECKER.ALLOWED.values():
        assert len(reason) > 30


def test_저장소가_통과한다():
    assert CHECKER.check() == []
