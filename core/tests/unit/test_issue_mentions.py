"""닫힌 질문 표기 검사의 단위 검사 (D-0126).

**도구 자신을 검사한다** (D-0080의 규율). 검사가 아무것도 안 잡으면 통과해도 뜻이
없고, 반대로 옳게 적은 줄을 잡으면 사람이 검사를 끄게 된다.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    """`tools/check_issue_mentions.py`. 싣는 자리는 `tests.conftest` 하나다 (D-0272)."""
    return tool_module("check_issue_mentions")


CHECKER = _module()

DESIGN = """
<!-- closed-issues:begin -->

| # | 항목 | 결말 |
|---|---|---|
| O-38 | **닫힘 (D-0114)** | 표본 부족이다. |

<!-- closed-issues:end -->
"""


def _scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> list[str]:
    """임시 나무 하나만 훑게 한다."""
    tree = tmp_path / "core" / "hathor"
    tree.mkdir(parents=True)
    (tree / "target.py").write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "DOCUMENTS", ())
    # **경로로 실은 모듈의 속성은 `mypy`가 못 본다** — 그 반환은 `Any`다 (D-0264).
    # 여기 적는 형이 곧 «이 도구가 무엇을 내는가»에 대한 시험의 주장이다.
    return cast("list[str]", CHECKER.check(DESIGN))


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


# ─────────────────────────────────────────── 카나리아: 그물이 비면 운다 (D-0349)


def test_문서를_실제로_훑는다():
    """**`SKIP_TREES = ("",)` 하나로 문서 축이 통째로 죽어 있었다** (D-0349).

    `name.startswith("")`는 **늘 참**이라 `DOCUMENTS` 다섯이 전부 떨어졌다. 대상 302개가
    **전부 코드**였고 문서는 0개였는데, 화면은 「닫힘 42 · 열림 30」을 찍었다 — 그 수는
    **표의 수**이지 **읽은 파일 수**가 아니라 아무도 못 알아챘다.

    **「검사가 있다」와 「검사가 본다」는 다르다.**
    """
    papers = [path for path in CHECKER.targets() if path.suffix == ".md"]
    names = {path.relative_to(ROOT).as_posix() for path in papers}

    assert names == {"README.md", "docs/PLAN.md", "docs/MASTER.md"}, names
    assert "docs/DECISIONS.md" not in names, "과거 축은 그 시점을 적는다 (D-0081)"


def test_빈_접두사를_건너뛰기로_쓰지_않는다():
    """**`startswith("")`는 전부 참이다.** 상수가 비면 그물이 통째로 빈다 (D-0349).

    `SKIP_TREES`의 독스트링에 **빈 백틱**이 남아 있었다 — 이름을 지우면서 상수까지
    비웠고, 그 뒤로 검사가 아무것도 안 보며 초록을 찍었다.
    """
    assert "" not in CHECKER.SKIP_TREES
    assert all(CHECKER.SKIP_TREES), "빈 문자열 하나가 모든 접두사에 맞는다"


def test_심은_맨몸_참조를_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**카나리아다** (D-0349 · `deadcheck.positive_control`과 같은 꼴).

    닫힌 질문을 일부러 맨몸으로 심고 **검사가 우는지** 본다. 안 울면 그 검사는
    「통과」를 찍을 자격이 없다 — 오늘 그 상태로 348판이 지났다.

    **문자열로는 못 심는다.** `check`는 `plan_text`를 열린 질문 목록으로만 쓰고
    맨몸 참조는 `targets()`로 **디스크를 읽는다** — 이 카나리아가 그것부터 잡았다.
    """
    design = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    shut = next(iter(CHECKER.closed_issues(design)))

    planted = tmp_path / "심은것.md"
    planted.write_text(f"{shut}은 아직 미해결이다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "targets", lambda: [planted])

    problems = CHECKER.check(design, "")

    assert problems, f"{shut}을 맨몸으로 심었는데 안 운다"
    assert shut in problems[0]


def test_시야가_바닥_위에_있다():
    """**시야 못이다** (D-0349 · `deadcheck.CEILING`과 같은 규율).

    카나리아는 **시야는 그대로인데 잡는 능력을 잃은 것**을 잡고, 못은 **시야 자체가
    조용히 줄어든 것**을 잡는다. `SKIP_TREES`가 비던 사고는 뒤쪽이었다 — 검사는
    멀쩡히 돌았고 **볼 것이 없었다.**
    """
    counted = {
        "문서": sum(1 for path in CHECKER.targets() if path.suffix == ".md"),
        "코드": sum(1 for path in CHECKER.targets() if path.suffix == ".py"),
    }
    for axis, floor in CHECKER.FLOOR.items():
        assert counted[axis] >= floor, f"{axis} {counted[axis]}개 < 바닥 {floor}개"


def test_못이_빈_상수에_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**시야 못의 카나리아다.** 상수를 비우고 **못이 우는지** 본다.

    `SKIP_TREES = ("",)`를 그대로 되살린다. 그날 이것이 통과했고 **348판 동안
    아무도 몰랐다.** 지금은 바닥에 걸려야 한다.
    """
    monkeypatch.setattr(CHECKER, "SKIP_TREES", ("",))
    assert CHECKER.shortfall(CHECKER.targets()), "`SKIP_TREES`를 비웠는데 못이 안 운다"

    monkeypatch.setattr(CHECKER, "SKIP_TREES", ("docs/DECISIONS.md",))
    monkeypatch.setattr(CHECKER, "TREES", ())
    assert CHECKER.shortfall(CHECKER.targets()), "`TREES`를 비웠는데 못이 안 운다"


def test_바닥이_실측보다_낮다():
    """**바닥을 실측에 딱 붙이지 않는다** (D-0058).

    딱 붙이면 파일 하나 지울 때마다 문서를 고쳐야 하고, 그러면 **수를 맞추려고
    바닥을 내리는 손버릇**이 생긴다 — 그것이 D-0058이 말한 그 죄다. 코드 바닥은
    **나무 하나가 통째로 빠지는 것**만 막는 자리에 둔다.
    """
    code = sum(1 for path in CHECKER.targets() if path.suffix == ".py")

    assert CHECKER.FLOOR["코드"] < code, "바닥이 실측 이상이면 다음 판에 터진다"
    assert CHECKER.FLOOR["코드"] > code // 2, "바닥이 절반 밑이면 나무 하나가 빠져도 안 운다"


# ------------------------------------------------------------------ 번호 전수 (D-0349)

CLOSED = (
    "<!-- closed-issues:begin -->\n"
    "| O-1 | 가 | D-0001 |\n| O-3 | 다 | D-0003 |\n"
    "<!-- closed-issues:end -->"
)
OPEN = "<!-- open-issues:begin -->\n| O-2 | 나 |\n<!-- open-issues:end -->"


def test_고아_번호에_운다():
    """**D-0349가 당한 꼴이다.** O-6 · O-14가 두 표 어디에도 없이 348판을 지났다.

    D-0346은 *"닫힘표에 셋. 번호 자리에 넣었다"*고 적었고 **들어간 것은 하나였다.**
    기존 검사는 **코드가 부르는 번호**만 봐서 아무도 안 부르는 고아를 못 잡았다.
    """
    hole = "<!-- closed-issues:begin -->\n| O-1 | 가 | D-0001 |\n<!-- closed-issues:end -->"
    problems = CHECKER.census(hole, OPEN, "O-3이 났다")

    assert problems, "O-3을 지웠는데 전수가 안 운다"
    assert "고아" in problems[0]


def test_맨_윗_행을_지우는_것도_잡는다():
    """**천장을 두 표에서 읽으면 안 된다.** 맨 위를 지우면 천장이 같이 내려간다.

    처음 안이 그랬고 **시험이 그것을 잡았다.** 천장은 과거 축에서 읽는다 — 추가만
    하는 문서라 줄지 않는다 (D-0081).
    """
    assert CHECKER.census(CLOSED, OPEN) == [], "O-3까지만 있으면 메워진 것이다"
    assert CHECKER.census(CLOSED, OPEN, "O-5가 났다"), "O-4 · O-5가 비었는데 안 운다"


def test_겹친_번호에_운다():
    """한 번호가 두 표에 다 있으면 **합계가 두 번 센다** — D-0346의 부풀린 수가 그것이다."""
    both = OPEN.replace("| O-2 | 나 |", "| O-1 | 가 |")
    problems = CHECKER.census(CLOSED, both)

    assert problems and "둘 다" in problems[0]


def test_메운_번호는_통과한다():
    assert CHECKER.census(CLOSED, OPEN) == []


def test_사유를_적은_번호는_건너뛴다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**사유 없이 비는 것만 막는다.** 흔적이 없는 번호를 억지로 메우면 가짜 행이 된다 (GR-0.5)."""
    hole = "<!-- closed-issues:begin -->\n| O-1 | 가 | D-0001 |\n<!-- closed-issues:end -->"

    assert CHECKER.census(hole, OPEN, "O-3이 났다")
    monkeypatch.setitem(CHECKER.SKIP_NUMBERS, 3, "시험용 — 사유를 넉넉히 적는다")
    assert CHECKER.census(hole, OPEN, "O-3이 났다") == []


def test_건너뛰는_번호마다_사유가_적혀_있다():
    """**사유 없는 면제는 그냥 구멍이다.** 시야 못이 이 목록의 크기를 잡고 있다."""
    assert CHECKER.SKIP_NUMBERS, "비면 전수가 꺼진 것과 같다고 적어 둘 자리도 없다"
    for number, why in CHECKER.SKIP_NUMBERS.items():
        assert isinstance(number, int)
        assert len(why) > 10, f"O-{number}의 사유가 비었다: {why!r}"


def test_표가_비면_통과시키지_않는다():
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    assert CHECKER.census("", OPEN)
    assert CHECKER.census(CLOSED, "")


def test_저장소_번호가_전부_메워져_있다():
    design = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")

    past = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")

    assert CHECKER.census(design, plan, past) == []
