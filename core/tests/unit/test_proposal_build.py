"""기획서 빌드의 순수 부분 (D-0221).

**빌드 전체는 pandoc · graphviz · 글꼴이 있어야 돈다** — CI에 없다. 여기서는 그것 없이
돌 수 있는 부분만 본다: 정본을 자르는 법 · 그림 자리를 찾는 법 · 표지를 가르는 법.
그림 자리가 사라지면 빌드가 멈추는데, **빌드를 안 돌리는 날에도** 여기서 먼저 멈춘다.
"""

from __future__ import annotations

import ast
import json
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


# --------------------------------------------------------- 자물쇠 (D-0376)
#
# 지문(`hathor-source-sha256:`)은 **정본**만 본다. 정본이 그대로여도 **생성기가 바뀌면
# 제출본은 낡는다** — 실측으로 생성기를 건드린 판 11 중 **1판**이 docx를 다시 안 내고
# 지나갔다. 그 구멍을 `docs/proposal/build.lock.json`이 막는다.
#
# **바이트로 견주지 않는다.** docx는 zip이라 같은 입력에서 같은 바이트가 안 나온다
# (graphviz 2.43.0 ↔ 14.1.2). 그래서 **입력의 지문**을 적는다.


def _lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marks: dict[str, str]) -> Path:
    """생성기만 보는 자물쇠. **렌더러는 못과 맞춰 둔다** — 한 번에 한 가지만 본다."""
    path = tmp_path / "build.lock.json"
    path.write_text(
        json.dumps(
            {"적는이": "시험", "생성기": marks, "렌더러": dict(SOURCE.RENDERERS)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(SOURCE, "LOCK", path)
    return path


def test_저장소의_자물쇠가_생성기_전부를_담는다() -> None:
    """**목록이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    assert set(SOURCE.locked()) == set(SOURCE.GENERATORS)
    assert len(SOURCE.GENERATORS) >= 5, "생성기가 줄었다 — 무엇이 빠졌나 (D-0257)"


def test_생성기가_바뀌면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 그 1판이 이 자리를 지나갔다."""
    marks = dict(SOURCE.generator_marks())
    marks["tools/render_figures.py"] = "0" * 16
    _lock(tmp_path, monkeypatch, marks)

    problems = SOURCE.stale()

    assert len(problems) == 1, problems
    assert "render_figures.py" in problems[0]
    assert "다시 안 냈다" in problems[0]


def test_자물쇠에만_남은_이름도_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**양방향** (D-0363). 한쪽만 보면 목록에서 뺀 날 자물쇠의 줄이 조용히 죽는다."""
    marks = {**SOURCE.generator_marks(), "tools/떠난것.py": "1" * 16}
    _lock(tmp_path, monkeypatch, marks)

    problems = SOURCE.stale()

    assert any("떠난것.py" in one and "빠졌다" in one for one in problems), problems


def test_자물쇠가_없으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 것을 「맞다」로 읽지 않는다** (GR-0.5)."""
    monkeypatch.setattr(SOURCE, "LOCK", tmp_path / "없다.json")

    assert any("없다" in one for one in SOURCE.stale())


def test_자물쇠가_깨지면_죽는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**조용히 빈 것으로 읽지 않는다.** 빈 것으로 읽으면 「없다」와 구분이 안 간다."""
    path = tmp_path / "build.lock.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(SOURCE, "LOCK", path)

    with pytest.raises(SOURCE.SourceError, match="깨졌다"):
        SOURCE.locked()


def test_없는_생성기는_없다고_적는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**빠진 파일이 조용히 목록에서 사라지면** 자물쇠가 짧아지고 아무도 모른다."""
    monkeypatch.setattr(SOURCE, "GENERATORS", (*SOURCE.GENERATORS, "tools/있을리없다.py"))

    assert SOURCE.generator_marks()["tools/있을리없다.py"] == "없다"


def test_빌드가_자물쇠를_쓴다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0352). 읽는 쪽만 있고 **쓰는 쪽이 없으면** 영원히 낡는다.

    D-0368 ~ D-0370이 세 판 연속 *«부품을 재고 배선을 안 쟀다»*였다.
    """
    path = tmp_path / "깊은" / "자리" / "build.lock.json"
    monkeypatch.setattr(BUILD, "LOCK", path)

    BUILD.seal()

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["적는이"] == "tools/build_proposal.py"
    assert written["생성기"] == SOURCE.generator_marks()


def test_빌드가_자물쇠를_부른다() -> None:
    """**심은 결함** (D-0069 · D-0352). 위 시험은 `seal()`을 **직접** 부른다.

    `build()`가 안 부르면 자물쇠는 영원히 첫 판에 머물고 아무 시험도 안 운다.
    `build()`는 pandoc·graphviz·글꼴이 있어야 돌아 CI에서 못 돌린다 — 그래서 **부르는
    것 자체**를 글로 본다. `mutate_gate`도 이 자리를 못 끊는다(입구가 pandoc을 쓴다).
    """
    tree = ast.parse((ROOT / "tools" / "build_proposal.py").read_text(encoding="utf-8"))
    build = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build"
    )
    called = {
        node.func.id
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "seal" in called, "제출본을 내면서 자물쇠를 안 쓴다 (D-0376)"
    assert "cover" in called and "freeze" in called, "표지와 봉인이 빠졌다"


def test_표지가_날짜가_아니라_지문이다() -> None:
    """**그가 물은 그 자리다** — *«빌드라는 게 현재 판이 마지막으로 언제 수정됐는지를
    말하는 게 아니냐»*. 아니었다. `dt.date.today()`는 **명령을 친 날**을 적었고,
    아무것도 안 고치고 다시 빌드해도 움직였다.
    """
    body = (ROOT / "tools" / "build_proposal.py").read_text(encoding="utf-8")

    assert "stamp = fingerprint()[:12]" in body, "표지가 다시 날짜를 적는다"
    assert 'f"정본 {stamp} · docs/MASTER.md Part I ~ III"' in body
    assert "dt.date.today()" not in body, "날짜 라벨이 돌아왔다"


# --------------------------------------------------------- 렌더러 (D-0377)
#
# 자물쇠는 **입력**만 봉인했다. 같은 입력에서 **두 기기가 다른 그림을 내고 둘 다
# 통과한다** — 실측: 그의 `dot` 14.1.2와 내 컨테이너 2.43.0이 같은 입력에서 **높이가
# 15~27% 다른** PNG를 냈다. *«빌더는 그의 기기다»*가 주장이었고 관문이 아니었다.
#
# 파이썬 쪽은 `uv.lock`이 이미 박는다. **안 박힌 하나(`dot`)만** 박는다.


def test_못이_비지_않았다() -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    assert SOURCE.RENDERERS
    assert all(mark and mark[0].isdigit() for mark in SOURCE.RENDERERS.values())


def test_다른_렌더러가_그리면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 이것이 없으면 「빌더는 그의 기기다」는 글일 뿐이다."""
    path = tmp_path / "build.lock.json"
    path.write_text(
        json.dumps(
            {"생성기": SOURCE.generator_marks(), "렌더러": {"dot": "2.43.0"}}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(SOURCE, "LOCK", path)

    problems = SOURCE.stale()

    assert len(problems) == 1, problems
    assert "dot 2.43.0이 그렸다" in problems[0]
    assert SOURCE.RENDERERS["dot"] in problems[0], "못을 안 찍으면 무엇으로 고칠지 모른다"


def test_옛_자물쇠에_렌더러가_없으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 것을 「맞다」로 읽지 않는다** (GR-0.5). D-0376이 낸 자물쇠가 그렇다."""
    path = tmp_path / "build.lock.json"
    path.write_text(
        json.dumps({"생성기": SOURCE.generator_marks()}, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(SOURCE, "LOCK", path)

    assert any("안 적혔다" in one for one in SOURCE.stale())


def test_빌드가_실제로_돈_판을_읽는다() -> None:
    """**적는 것은 못이 아니라 실측이다** (GR-0.5). 거짓말하면 관문이 무의미해진다."""
    found = BUILD.drew()

    assert set(found) >= {"dot", "pandoc", "python", "matplotlib"}
    assert found["python"][0].isdigit()


def test_렌더러가_없는_기기에서는_없다고_적는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 못 읽은 것을 조용히 빼면 자물쇠가 짧아지고 못이 안 문다."""

    def 터진다(*_args: object, **_kw: object) -> None:
        raise OSError("없다")

    monkeypatch.setattr(BUILD.subprocess, "run", 터진다)

    assert BUILD.drew()["dot"] == "없다"


def test_판을_못_읽으면_그렇게_적는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """`dot -V`의 글이 바뀌는 날 **조용히 빈 값이 들어가면** 못이 늘 운다 (GR-0.8)."""
    monkeypatch.setattr(BUILD, "re", _Blind())

    assert BUILD.drew()["dot"] == "못 읽었다"


class _Blind:
    """아무것도 못 찾는 가짜 `re`."""

    @staticmethod
    def search(*_args: object) -> None:
        return None


def test_자물쇠가_렌더러를_담는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0352). 재는 함수가 있어도 **안 적으면** 아무 일도 없다."""
    path = tmp_path / "build.lock.json"
    monkeypatch.setattr(BUILD, "LOCK", path)

    BUILD.seal()

    assert json.loads(path.read_text(encoding="utf-8"))["렌더러"] == BUILD.drew()
