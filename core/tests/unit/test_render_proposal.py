"""**사본을 대조로 지키는 것보다 사본을 만들지 않는 것이 싸다** (D-0368).

fire-lane의 `render_workflow.py`가 적어 둔 문장이다. 그쪽은 협업 방침 화면을 손으로
썼다가 **정본이 둘이 됐고, 같은 날 한 절만 낡은 채로 머지를 통과해 작업 하나가 소리
없이 사라졌다.**

hathor의 `site/proposal.html`은 **PDF를 끼워 보여 주는 34줄**이었다 (D-0229) — 사본은
아니었지만 **화면이 정본을 안 읽었다.**
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import tool_module

TOOL = tool_module("render_proposal")
SCRIPT = tool_module("check_script")
ROOT = Path(__file__).resolve().parents[3]


def test_화면이_정본과_같다() -> None:
    """`make check`이 보는 그 판정 — **재생성 결과와 바이트로 같은가.**"""
    assert TOOL.check() == []


def test_손으로_고치면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**이것이 이 관문의 값이다.** 화면만 고치는 길을 막는다."""
    fake = tmp_path / "proposal.html"
    fake.write_text(TOOL.build().replace("<h2", "<h2 data-손", 1), encoding="utf-8")
    monkeypatch.setattr(TOOL, "OUT", fake)

    problems = TOOL.check()

    assert any("정본과 다르다" in one for one in problems), problems
    # **어느 파일인지 적는다** — `short()`가 안 닿으면 사람이 어디를 다시 낼지 모른다.
    assert any(TOOL.short(fake) in one for one in problems), problems


def test_생성물이_없으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**커밋하는 생성물이다** — 배포 때만 만들면 대조할 대상이 없다 (fire-lane 방침)."""
    gone = tmp_path / "없다.html"
    monkeypatch.setattr(TOOL, "OUT", gone)

    problems = TOOL.check()

    assert any("없다" in one for one in problems), problems
    assert any(TOOL.short(gone) in one for one in problems), problems


def test_색인에_없는_절이_생기면_죽는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**정본 → 화면** 방향 (fire-lane `index()`).

    색인이 가르는 축이고 **서식은 그리는 방법일 뿐**이다. 저쪽은 서식으로 갈랐다가
    *«누가 표를 목록으로 바꾸면 그 절이 조용히 다른 칸으로 옮겨간다»*로 되돌렸다.
    """
    real = TOOL.headings()
    monkeypatch.setattr(TOOL, "headings", lambda: [*real, "없는 절"])

    with pytest.raises(LookupError, match="색인에 없는 절"):
        TOOL.index()


def test_색인이_든_절이_화면에_다_담긴다() -> None:
    """**화면 → 정본** 방향 (fire-lane `audit()`). 둘이 있어야 도킹이 닫힌다."""
    slots = TOOL.index()
    groups = TOOL.classify(slots)

    TOOL.audit(groups, slots)
    assert len(dict.fromkeys(slots.values())) >= TOOL.FLOOR_SLOTS


def test_색인이_비면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(TOOL, "FLOOR_SLOTS", 99)

    with pytest.raises(LookupError, match="바닥"):
        TOOL.index()


def test_표식이_없으면_막는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "docs"
    fake.mkdir()
    (fake / "MASTER.md").write_text("색인이 없다\n", encoding="utf-8")
    monkeypatch.setattr(TOOL, "ROOT", tmp_path)

    with pytest.raises(LookupError, match="표식이 없다"):
        TOOL.index()


def test_와꾸의_자리가_사라지면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """템플릿의 `{자리}`를 지우면 **그 내용이 조용히 빠진다.**"""
    monkeypatch.setattr(TOOL, "TEMPLATE", TOOL.TEMPLATE.replace("{panes}", ""))

    with pytest.raises(LookupError, match="자리가 없다"):
        TOOL.build()


def test_임의_HTML을_안_만든다() -> None:
    """**정본의 글자가 태그가 되지 않는다.** 굵게 · 코드 · 그림만 푼다."""
    assert TOOL.inline("<script>나쁜 것</script>") == "&lt;script&gt;나쁜 것&lt;/script&gt;"
    assert TOOL.inline("**굵게**") == "<b>굵게</b>"
    assert "<figure>" in TOOL.inline("![설명](var/proposal/figures/concept.png)")


def test_제출본은_칸을_안_쓴다() -> None:
    """**심사 서식의 순서를 지킨다** — 칸을 나누는 것은 화면 쪽만이다 (D-0368).

    fire-lane의 `workflow.html`은 제출물이 아니라 그 제약이 없었다.
    """
    for name in ("build_proposal.py", "proposal_body.py"):
        build = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "proposal-index" not in build, f"{name}이 색인을 읽는다 — 순서가 바뀐다"


def test_스크립트_문법_관문이_있다() -> None:
    """**JS가 나쁜 것이 아니라 관문이 없는 것이 나쁘다** (fire-lane의 까닭)."""
    assert SCRIPT.main is not None
    assert SCRIPT.missing() == []
    assert SCRIPT.embedded() == []


def _plant(root: Path, script: str, screen: str) -> None:
    (root / "site").mkdir(parents=True, exist_ok=True)
    (root / "site" / "proposal.js").write_text(script, encoding="utf-8")
    (root / "site" / "proposal.html").write_text(screen, encoding="utf-8")


def test_볼_스크립트가_없으면_운다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069). 목록에 적고 파일을 안 두면 **관문이 빈손으로 초록이 된다.**"""
    monkeypatch.setattr(SCRIPT, "SCRIPTS", ("site/없는것.js",))
    monkeypatch.setattr("sys.argv", ["check_script.py", "--check"])

    assert SCRIPT.main() == 1
    assert "site/없는것.js가 없다" in capsys.readouterr().err


def test_화면에_안_박혔으면_운다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069 · D-0043). 박는 쪽을 누가 고치면 **화면만 바뀐다.**"""
    _plant(tmp_path, "const a = 1;\n", "<html><script>다른 것</script></html>")
    monkeypatch.setattr(SCRIPT, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["check_script.py", "--check"])

    assert SCRIPT.main() == 1
    assert "박혀 있지 않다" in capsys.readouterr().err


def test_문법이_깨지면_막는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069). 문법 판정이 `main()`까지 **닿는가.**

    `node`가 있든 없든 이 자리를 잰다 — 판정기를 가짜로 세우고 **배선만** 본다.
    `node`가 정말 문법을 보는지는 `test_깨진_스크립트를_잡는다`가 실물로 본다.
    """
    body = "const a = (;\n"
    _plant(tmp_path, body, f"<html><script>{body}</script></html>")
    monkeypatch.setattr(SCRIPT, "ROOT", tmp_path)
    monkeypatch.setattr(SCRIPT.shutil, "which", lambda _: "/가짜/node")
    monkeypatch.setattr(SCRIPT, "syntax", lambda _: "심은 문제")
    monkeypatch.setattr("sys.argv", ["check_script.py", "--check"])

    assert SCRIPT.main() == 1
    said = capsys.readouterr().err
    assert "문법이 깨졌다 — 심은 문제" in said, said
    # **`targets()`가 든 것마다 한 줄씩 나온다** — 목록이 안 닿으면 조용히 통과한다.
    assert said.count("문법이 깨졌다") == len(SCRIPT.targets())


def test_깨진_스크립트를_잡는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**심은 결함** (D-0069). `node --check`가 정말 문법을 보는가.

    **건너뛰지 않는다.** `node`가 없는 기기에서는 *«안 쟀다»*를 적는지를 본다 —
    건너뛰면 `deadcheck`의 천장이 오르고(D-0353이 그 둘을 없앴다) **그 기기에서는
    이 시험이 아무것도 안 본다.**
    """
    if shutil.which("node") is None:
        monkey = SCRIPT.main
        assert monkey is not None
        SCRIPT.main()
        assert "안 쟀다" in capsys.readouterr().out, "못 쟀는데 통과로 적는다 (GR-0.5)"
        return

    bad = tmp_path / "깨진.js"
    bad.write_text("const a = (;\n", encoding="utf-8")
    good = tmp_path / "멀쩡한.js"
    good.write_text("const a = 1;\n", encoding="utf-8")

    assert SCRIPT.syntax(bad) is not None
    assert SCRIPT.syntax(good) is None


def test_node가_없으면_안_쟀다고_적는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 잰 것을 통과로 적지 않는다** (GR-0.5 · `check_patch`의 `--no-live`와 같다)."""
    monkeypatch.setattr(SCRIPT.shutil, "which", lambda _: None)
    monkeypatch.setattr("sys.argv", ["check_script.py", "--check"])

    assert SCRIPT.main() == 0
    assert "안 쟀다" in capsys.readouterr().out


def test_스크립트가_화면에_박혀_있다() -> None:
    """**두 벌이 되지 않게 파일 하나에만 있다** (D-0043)."""
    body = (ROOT / "site" / "proposal.html").read_text(encoding="utf-8")
    source = (ROOT / "site" / "proposal.js").read_text(encoding="utf-8")

    assert source in body
    assert body.count("<script>") == 1, "스크립트가 여러 곳에 있다"


def test_운영_장부는_기획서_밖에_있다() -> None:
    """**밖이 읽는 문서에 내부 장부가 실렸다** (D-0332 → D-0368로 옮겨 왔다).

    닫힘표와 갚음표가 `## 3. 시장현황 및 유사 서비스 분석` 안에 있었다. 그래서
    **닫힌 질문 한 줄만 고쳐도 지문이 깨져 기획서를 다시 빌드해야 했다.**

    **이 시험이 한 번 사라졌다.** `docx_check`를 흡수하며 그 파일을 지웠고, 이 시험도
    같이 지워졌다 — `check_decisions`가 *«D-0332의 강제자가 없는 파일을 가리킨다»*로
    잡았다. fire-lane이 적은 **«작업 하나가 소리 없이 사라졌다»**가 그 꼴이고, 여기서는
    **관문이 사라짐을 잡았다.**
    """
    source = tool_module("proposal_source").source()

    assert "closed-issues:begin" not in source, "닫힘표가 기획서 구간에 있다 (D-0332)"
    assert "### 갚은 빚" not in source, "갚음표가 기획서 구간에 있다 (D-0332)"
    assert "proposal-index:begin" not in source, "화면 색인이 기획서 구간에 있다 (D-0368)"
    # **열린 것은 남는다** — 제안서의 정직한 리스크 공개이고 짧다.
    assert "### □ 진행 중 미해결" in source, "열린 미해결까지 빼면 제안서가 리스크를 감춘다"


def test_지문이_다르면_낡았다고_말한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**D-0221의 강제자.** Part I ~ III를 고치고 다시 빌드하지 않으면 멈춘다."""
    monkeypatch.setattr(TOOL, "stamped_docx", lambda _: "0" * 64)

    assert any("지문이 정본과 다르다" in one for one in TOOL.check())


def test_지문이_없으면_손으로_만든_판이다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TOOL, "stamped_docx", lambda _: None)

    assert any("지문이 없다" in one for one in TOOL.check())


def test_제출본이_없으면_그것만_말한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 것을 어긋남으로 세지 않는다** — 빌드 안 한 기기에서 쏟아지면 안 읽는다."""
    monkeypatch.setattr(TOOL, "DOCX", tmp_path / "없다.docx")

    problems = TOOL.check()

    assert problems == ["docs/proposal.docx가 없다"], problems


def test_화면을_낼_때_어디에_몇_칸을_냈는지_적는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--check` 없이 부르는 길 (D-0368). **낸 자리와 칸 수가 화면에 오른다.**

    `make docs-fix`가 이 길로 부른다. 여기가 끊기면 **파일이 안 써지는데 조용하다.**
    """
    out = tmp_path / "낸다.html"
    monkeypatch.setattr(TOOL, "OUT", out)
    monkeypatch.setattr("sys.argv", ["render_proposal.py"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    assert TOOL.short(out) in spoke, spoke
    assert f"칸 {len(dict.fromkeys(TOOL.index().values()))}개" in spoke, spoke
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_제출본에_정본의_수가_없으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). `truths()`가 안 돌면 **아무것과도 안 맞춰진다** (D-0230).

    `docx_check`에서 흡수한 그 판정이다 (D-0220). 제출본에서 글자를 다 지우고도
    통과하면, 기획서는 정본의 수를 **하나도 안 지고** 초록이 된다.
    """
    monkeypatch.setattr(TOOL, "docx_text", lambda _: "")

    problems = TOOL.check()

    assert problems, "제출본이 비었는데 통과했다"
    assert all("제출본에" in one for one in problems), problems
    assert len(problems) == len(TOOL.truths())
