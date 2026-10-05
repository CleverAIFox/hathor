"""기획서 빌드의 순수 부분 (D-0221).

**빌드 전체는 pandoc · graphviz · 글꼴이 있어야 돈다** — CI에 없다. 여기서는 그것 없이
돌 수 있는 부분만 본다: 정본을 자르는 법 · 그림 자리를 찾는 법 · 표지를 가르는 법.
그림 자리가 사라지면 빌드가 멈추는데, **빌드를 안 돌리는 날에도** 여기서 먼저 멈춘다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module as _load

ROOT = Path(__file__).resolve().parents[3]


SOURCE = _load("proposal_source")
BUILD = _load("build_proposal")
BODY = _load("proposal_body")


def test_그림_자리가_전부_정본에_있다() -> None:
    """**제목을 바꾸면 그림이 조용히 빠진다** — 그래서 제목 줄로 건다."""
    # deadcheck: ok `_span`이 제목을 못 찾으면 던진다 — 예외가 판정이다
    lines = SOURCE.source().splitlines()
    for heading, _name, _caption, _where in BODY.FIGURES:
        BODY._span(lines, heading)


def test_바꿀_자리에는_코드_블록이_있다() -> None:
    lines = SOURCE.source().splitlines()
    for heading, _name, _caption, where in BODY.FIGURES:
        if where == "replace":
            start, end = BODY._span(lines, heading)
            assert any(lines[i].startswith("```") for i in range(start, end)), heading


def test_표지와_본문을_가른다() -> None:
    cover, body = BODY.split_cover(SOURCE.source())
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
    monkeypatch.setattr(BODY, "FIGURES", places)
    placed = BODY.place_figures(body, {"x": picture})
    assert "```" not in placed
    assert placed.count("![") == 2


# ------------------------------------------------- 그림 도구의 배선 (D-0369)
#
# **D-0369가 배포 잡에 이 둘을 걸면서 「불리는 도구」가 됐다.** 그전에는 아무 사슬에도
# 없어서 `make mutate WIRING=1`이 안 봤고, `main()`의 배선 한 곳이 비어 있었다.
# 그리는 일 자체는 graphviz · matplotlib · 글꼴이 있어야 해서 **여기서는 안 그린다**
# (D-0129) — 그린 수가 **화면까지 닿는지**만 본다.

FIGURE_TOOLS = (("render_figures", "구조도"), ("render_charts", "수치 그림"))


@pytest.mark.parametrize(("name", "word"), FIGURE_TOOLS)
def test_그린_수가_화면에_오른다(
    name: str,
    word: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`render_all()` 자리 (D-0369). **0장을 그려도 조용하면 배포가 빈 그림을 올린다.**"""
    tool = _load(name)
    monkeypatch.setattr(
        tool, "render_all", lambda out: {"가": out / "가.png", "나": out / "나.png"}
    )
    monkeypatch.setattr("sys.argv", [f"{name}.py", "--out", str(tmp_path)])

    assert tool.main() == 0
    assert f"{word} 2장" in capsys.readouterr().out


@pytest.mark.parametrize(("name", "_word"), FIGURE_TOOLS)
def test_낼_곳을_받는다(
    name: str, _word: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`--out`이 안 닿으면 배포가 `var/`에 그리고 `_site/`는 빈 채로 올라간다** (D-0369)."""
    tool = _load(name)
    seen: list[Path] = []

    def noted(out: Path) -> dict[str, Path]:
        seen.append(out)
        return {}

    monkeypatch.setattr(tool, "render_all", noted)
    monkeypatch.setattr("sys.argv", [f"{name}.py", "--out", str(tmp_path / "낸다")])

    assert tool.main() == 0
    assert seen == [tmp_path / "낸다"]
