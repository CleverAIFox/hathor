"""기획서 빌드의 순수 부분 (D-0221).

**빌드 전체는 pandoc · graphviz · 글꼴이 있어야 돈다** — CI에 없다. 여기서는 그것 없이
돌 수 있는 부분만 본다: 정본을 자르는 법 · 그림 자리를 찾는 법 · 표지를 가르는 법.
그림 자리가 사라지면 빌드가 멈추는데, **빌드를 안 돌리는 날에도** 여기서 먼저 멈춘다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SOURCE = _load("proposal_source")
BUILD = _load("build_proposal")


def test_그림_자리가_전부_정본에_있다() -> None:
    """**제목을 바꾸면 그림이 조용히 빠진다** — 그래서 제목 줄로 건다."""
    lines = SOURCE.source().splitlines()
    for heading, _name, _caption, _where in BUILD.FIGURES:
        BUILD._span(lines, heading)


def test_바꿀_자리에는_코드_블록이_있다() -> None:
    lines = SOURCE.source().splitlines()
    for heading, _name, _caption, where in BUILD.FIGURES:
        if where == "replace":
            start, end = BUILD._span(lines, heading)
            assert any(lines[i].startswith("```") for i in range(start, end)), heading


def test_표지와_본문을_가른다() -> None:
    cover, body = BUILD.split_cover(SOURCE.source())
    assert cover[0].startswith("## 취향 잠재 표현")
    assert any(line.startswith("**※ 데이터 경계 전제**") for line in cover)
    assert body.startswith("# Part I.")


def test_기획서는_부록_앞에서_끝난다() -> None:
    text = SOURCE.source()
    assert "## 12. 산출물 목록" in text
    assert "## 부록 A." not in text
    assert "## 결정 대장" not in text


def test_표를_읽는다() -> None:
    found = SOURCE.table("### □ 레이어 곡선 — 검색축 (D-0027)")
    assert found.header[0] == "층"
    assert SOURCE.number(found.rows[0][2]) == pytest.approx(0.2327)


def test_모르는_제목은_멈춘다() -> None:
    with pytest.raises(SOURCE.SourceError):
        SOURCE.section(SOURCE.source(), "### □ 없는 절")


def test_칸의_첫_수를_읽는다() -> None:
    assert SOURCE.number("**3.7/0.8/0.7%**") == pytest.approx(3.7)
    assert SOURCE.plain("**`a`**<br>~~b~~") == "a b"


def test_그림을_제목_자리에_넣는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = pytest.importorskip("PIL.Image", reason="docs 의존 묶음이 없다")
    picture = tmp_path / "x.png"
    image.new("RGB", (400, 200), "white").save(picture)
    body = "## 가\n\n문단\n\n```text\n그림\n```\n\n## 나\n\n끝\n"
    places = [("## 가", "x", "캡션", "replace"), ("## 나", "x", "둘", "end")]
    monkeypatch.setattr(BUILD, "FIGURES", places)
    placed = BUILD.place_figures(body, {"x": picture})
    assert "```" not in placed
    assert placed.count("![") == 2
