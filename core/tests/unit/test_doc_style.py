"""문서 레이아웃 강제자의 단위 검사 (D-0129).

**도구 자신을 검사한다** (D-0080). 그리고 **기각한 규칙이 왜 기각됐는지도 검사한다** —
다음 세션이 "1인칭을 막자"고 다시 제안하지 않도록 실측을 검사로 굳힌다.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    """`tools/check_doc_style.py`. 싣는 자리는 `tests.conftest` 하나다 (D-0272)."""
    return tool_module("check_doc_style")


CHECKER = _module()
# **저장소 전체를 보는 넷은 `doc_style_repo`로 뗐다** (D-0356 · 611줄 > 상한 600).
REPO = tool_module("doc_style_repo")


def _layout(text: str) -> list[str]:
    # **경로로 실은 모듈의 속성은 `mypy`가 못 본다** — 그 반환은 `Any`다 (D-0264).
    # 여기 적는 형이 곧 «이 도구가 무엇을 내는가»에 대한 시험의 주장이다.
    return cast("list[str]", CHECKER.check_layout("x.md", text))


# ------------------------------------------------------------------ 잡는다


def test_산문이_표를_끊는_것을_잡는다():
    """**실측 결함이다.** DESIGN과 D-0001-0050에서 셋 나왔고 표가 둘로 렌더됐다."""
    problems = _layout("| A | B |\n|---|---|\n| 1 | 2 |\n설명 문장이다.\n| 3 | 4 |\n")
    assert len(problems) == 1
    assert "산문이 표를 끊는다" in problems[0]


def test_빈_줄이_표를_끊는_것을_잡는다():
    """머리글이 없는 조각은 표로 안 보인다."""
    problems = _layout("| A | B |\n|---|---|\n| 1 | 2 |\n\n| 3 | 4 |\n")
    assert len(problems) == 1
    assert "빈 줄이 표를 끊는다" in problems[0]


def test_행끝_공백을_잡는다():
    assert len(_layout("문장이다. \n")) == 1


@pytest.mark.parametrize("text", ["이렇게 합니다.", "맞습니다.", "그렇게 해요.", "입니다"])
def test_경어체를_잡는다(text):
    """`-ㅂ니다`·`-습니다`를 종성으로 판정한다."""
    problems = _layout(text + "\n")
    assert problems and "경어체" in problems[0]


@pytest.mark.parametrize("text", ["그것이 아니다.", "그렇지 않다.", "표본이 아니다."])
def test_아니다는_경어체가_아니다(text):
    """**`니다`만 보면 `아니다`가 전부 잡힌다** — 실측 196곳이었다."""
    assert _layout(text + "\n") == []


def test_제목_건너뜀을_잡는다():
    problems = _layout("## 둘\n\n#### 넷\n")
    assert problems and "건너뛴다" in problems[0]


def test_긴_줄을_잡는다():
    assert len(_layout("가" * (CHECKER.WIDTH + 1) + "\n")) == 1


def test_배경이_없는_기록을_잡는다():
    problems = CHECKER.check_records("d.md", "## D-9999. 제목\n\n- **결과**: 했다.\n")
    assert problems and "D-9999" in problems[0]


def _record(number: int, repro: str) -> str:
    """**`재현` 칸은 줄이 그 낱말로 시작해야 한다** (D-0136). «불명»은 한 줄이다."""
    return f"## D-{number:04d}. 제목\n\n- **배경**: 있다.\n\n{repro}\n\n강제자 없음 — 사유: 없다\n"


def test_경계_뒤의_재현_불명을_잡는다():
    """**D-0250의 강제자.** 평가가 찍은 것을 남기므로 «모른다»고 적을 이유가 없다."""
    after = CHECKER.UNKNOWN_UNTIL + 1
    problems = CHECKER.check_records("d.md", _record(after, "재현 불명 — 못 찾았다"))

    assert problems and "«불명»" in problems[0]


def test_경계_앞의_재현_불명은_통과한다():
    """**과거 74건은 소급하지 않는다** — 산출물이 없으니 추측해야 하고, 그것은 빈칸보다 나쁘다."""
    last = _record(CHECKER.UNKNOWN_UNTIL, "재현 불명 — 못 찾았다")
    assert CHECKER.check_records("d.md", last) == []


# ------------------------------------------------------------------ 안 잡는다


def test_따로_선_두_표는_통과한다():
    """머리글이 있으면 **의도한 두 표다.**"""
    assert _layout("| A | B |\n|---|---|\n| 1 | 2 |\n\n| C | D |\n|---|---|\n| 3 | 4 |\n") == []


def test_코드블록은_안_본다():
    """코드에 긴 줄과 경어체가 있을 수 있다."""
    long_line = "x" * (CHECKER.WIDTH + 40)
    assert _layout(f"```\n{long_line}\n```\n") == []


def test_표와_인용은_길이를_안_잰다():
    wide = "가" * (CHECKER.WIDTH + 20)
    assert _layout(f"| {wide} |\n|---|\n") == []
    assert _layout(f"> {wide}\n") == []


def test_표_앞_산문에_빈_줄이_있으면_통과한다():
    assert _layout("설명 문장이다.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n") == []


# ------------------------------------------------------------------ 기각한 규칙


def _records() -> list[tuple[str, str]]:
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    parts = re.split(r"^## (D-\d{4})\.", text, flags=re.M)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]


def test_1인칭_금지는_못_건다():
    """**진짜 1인칭이 기존 기록에 있다.** 막으면 낡은 기록을 고쳐야 하고 D-0081이 막는다."""
    found = [number for number, body in _records() if "나는 " in body or "내가 " in body]
    assert found, "1인칭이 하나도 없으면 이 기각 근거가 사라진 것이다"


def test_용어_통일은_못_건다():
    """`임계`와 `문턱`이 **둘 다 살아 있다.** 통일하려면 128건을 고쳐야 한다 (D-0081)."""
    text = "".join(body for _, body in _records())
    assert text.count("임계") > 5 and text.count("문턱") > 5


def test_분량_강제는_근거가_없다():
    """실측 중앙 2,059자 대 2,200자. **7% 차이는 없는 문제다.**"""
    sizes = sorted(len(body) for _, body in _records())
    middle = sizes[len(sizes) // 2]
    assert 1500 < middle < 2600


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다():
    """**지금 초록이 아니면 이 검사를 켤 수 없다.**"""
    assert CHECKER.check() == []


@pytest.mark.parametrize("name", ["README.md", "docs/PLAN.md", "docs/MASTER.md"])
def test_살아_있는_문서를_다_본다(name: str) -> None:
    """**이 시험이 죽은 항목을 붙들고 있었다** (D-0349).

    뿌리 `MASTER.md`를 요구했는데 **그 파일은 D-0189가 흡수해 없다.** `exists()`에
    걸려 조용히 지나가므로 검사는 초록이었고, **지우려면 이 시험이 막았다** — 그래서
    아무도 안 지웠다. 시험이 **사장된 사실을 못으로 박고 있던 것**이다.
    """
    assert name in CHECKER.DOCUMENTS
    assert (ROOT / name).exists(), f"{name}이 없는데 검사 대상에 있다"


def test_검사_대상이_전부_실재한다() -> None:
    """**없는 것을 목록에 두면 「본다」와 「봤다」가 갈린다** (D-0349)."""
    for name in CHECKER.DOCUMENTS:
        assert (ROOT / name).exists(), name


def test_폐기_보관소가_없다():
    """**git이 이력을 든다** (D-0133). `docs/`에는 축 셋과 기획서뿐이다 (D-0187 · D-0220)."""
    assert not (ROOT / "docs" / "archive").exists()
    assert CHECKER.ALLOWED_TREES == ()
    expected = sorted(CHECKER.AXES + CHECKER.OUTSIDE_TENSE)
    assert sorted(path.name for path in (ROOT / "docs").iterdir()) == expected


def test_백틱_안의_예시는_경어체가_아니다():
    """**이 검사를 설명하는 기록이 `합니다`를 예로 든다.**"""
    assert _layout("`합니다`·`입니다`는 잡는다.\n") == []


# ------------------------------------------------------------------ 여섯 번째 문서 (D-0130)


def test_축_셋만_허용한다():
    """**미래·현재·과거 세 시제가 다 찼다.** 넷째 축은 만들지 않는다."""
    assert set(CHECKER.AXES) == {"PLAN.md", "MASTER.md", "DECISIONS.md"}


def test_여섯_번째_문서를_잡는다(tmp_path, monkeypatch):
    """새 문서를 만들면 **어느 시제인지 모르는 항목**이 생긴다."""
    base = tmp_path / "docs"
    base.mkdir()
    (base / "NOTES.md").write_text("# 메모\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    problems = REPO.check_sixth_document()
    assert len(problems) == 1
    assert "여섯 번째 문서" in problems[0]


def test_하위_폴더까지_본다(tmp_path, monkeypatch):
    """`docs/_patch/` 같은 자리가 **두 검사 사이로 빠져나가는 것**을 막는다."""
    nested = tmp_path / "docs" / "_patch"
    nested.mkdir(parents=True)
    (nested / "copy.md").write_text("# 사본\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert REPO.check_sixth_document()


def test_축_셋만_통과한다(tmp_path, monkeypatch):
    """**하위 폴더도 안 된다** (D-0187). 넷째 축이 숨어들 자리다."""
    for name in CHECKER.AXES:
        (tmp_path / "docs" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / name).write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert REPO.check_sixth_document() == []

    nested = tmp_path / "docs" / "decisions" / "D-0001-0050.md"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("# x\n", encoding="utf-8")
    assert REPO.check_sixth_document() != []


def test_저장소에_여섯_번째가_없다():
    assert REPO.check_sixth_document() == []


def test_미래_축을_검사한다():
    """PLAN이 검사 대상에 있어야 **새 축만 규약 밖에서 자라는 일**이 없다."""
    assert "docs/PLAN.md" in CHECKER.DOCUMENTS


# ------------------------------------------------------------------ 문체·강조 (D-0131)


@pytest.mark.parametrize("text", ["그렇게 하라.", "여기서 멈춰라 지워라", "그러지 마라."])
def test_명령형을_잡는다(text):
    problems = _layout(text + "\n")
    assert problems and "명령형" in problems[0]


@pytest.mark.parametrize("text", ["추가하자 잡혔다.", "말라는 말이 아니다.", "마라고 적었다."])
def test_청유형과_연결어미는_안_잡는다(text):
    """**검사가 시끄러우면 끈다.** `~하자`는 연결어미와 구분이 안 된다."""
    assert _layout(text + "\n") == []


@pytest.mark.parametrize("text", ["이렇게 합니다.", "그렇게 하라."])
def test_탈출구가_있는_줄은_안_본다(text):
    """**인용을 위반으로 세면 회고를 쓸 수 없다.**"""
    assert _layout(f"{text} {CHECKER.ALLOW}\n") == []


def test_강조가_많으면_절을_쪼개라고_한다():
    text = "### 큰 절\n\n" + ("**강조** 가나다라마바사아자차카타파하" * 3 + "\n") * 8
    problems = CHECKER.check_bold_density("x.md", text)
    assert problems and "쪼갠다" in problems[0]


def test_표의_강조는_절의_강조가_아니다():
    """표의 강조는 **행의 강조**다. 절을 쪼개라는 신호로 쓸 수 없다."""
    rows = "".join("| **가** | **나** | **다** |\n" for _ in range(20))
    text = "### 표만 있는 절\n\n" + rows + "가" * 300 + "\n"
    assert CHECKER.check_bold_density("x.md", text) == []


def test_결정_기록에는_강조_밀도를_안_건다():
    """**덧붙이기만 하는 문서라 못 고친다** (D-0081)."""
    assert CHECKER.check() == []


def test_강제자_없는_기록을_잡는다():
    number = f"D-{CHECKER.ENFORCER_FROM:04d}"
    body = f"## {number}. 제목\n\n- **배경**: 있다.\n- **결과**: 했다.\n"
    problems = CHECKER.check_records("d.md", body)
    assert problems and "강제자" in problems[0]


def test_옛_기록에도_강제자를_요구한다():
    """**표기는 전수 소급한다** (D-0081). `강제자`는 그때의 판단을 안 바꾼다."""
    assert CHECKER.ENFORCER_FROM == 1
    body = "## D-0001. 제목\n\n- **배경**: 있다.\n"
    assert CHECKER.check_records("d.md", body)


def test_없는_강제자를_잡는다():
    """**칸을 채우는 것과 그 칸이 참인 것은 다르다.** 도구를 지우면 포인터가 낡는다."""
    body = "## D-0001. 제목\n\n- **배경**: 있다.\n\n강제자  `tools/없다.py`\n"
    problems = CHECKER.check_records("d.md", body)
    assert problems and "없다" in problems[0]


def test_본문의_경로는_안_본다():
    """`강제자` 줄만 본다. 본문은 폐기한 파일을 과거형으로 적는 것이 정상이다."""
    body = (
        "## D-0001. 제목\n\n- **배경**: `tools/옛날.py`를 지웠다.\n\n"
        "강제자 없음 — 사유: x\n재현 없음 — 사유: 수치가 없다\n"
    )
    assert CHECKER.check_records("d.md", body) == []


def test_기록_131건이_전부_칸을_갖는다():
    assert CHECKER.check() == []


def test_강제자_없음도_기술이다():
    """**없다는 사실 자체가 기록이어야 한다.**"""
    number = f"D-{CHECKER.ENFORCER_FROM:04d}"
    body = (
        f"## {number}. 제목\n\n- **배경**: 있다.\n\n"
        "강제자 없음 — 사유: 자료만으로 닫는다.\n재현 없음 — 사유: 수치가 없다\n"
    )
    assert CHECKER.check_records("d.md", body) == []


def test_들여쓴_인용_블록은_산문이_아니다():
    """**결정 기록은 폐기한 문언을 증거로 인용한다.**"""
    assert _layout('    "이런 느낌으로 생성하라"는 사례다.\n') == []


# ------------------------------------------------------------------ 재현 (D-0135)


def test_재현이_없는_새_기록을_잡는다():
    """**D-0123이 수치만 적고 명령을 안 적어 원인을 못 가렸다** (O-40)."""
    number = f"D-{CHECKER.REPRODUCE_FROM:04d}"
    body = f"## {number}. 제목\n\n- **배경**: 있다.\n\n강제자 없음 — 사유: x\n"
    problems = CHECKER.check_records("d.md", body)
    assert problems and "재현" in problems[0]


def test_옛_기록에는_재현을_안_요구한다():
    """**명령은 그때 무엇을 쳤는지이고 우리는 모른다.** 지어내면 GR-0.5다."""
    number = f"D-{CHECKER.REPRODUCE_FROM - 1:04d}"
    body = f"## {number}. 제목\n\n- **배경**: 있다.\n\n강제자 없음 — 사유: x\n"
    assert CHECKER.check_records("d.md", body) == []


def test_재현_없음도_기술이다():
    number = f"D-{CHECKER.REPRODUCE_FROM:04d}"
    body = f"## {number}. 제목\n\n- **배경**: x\n\n강제자 없음 — 사유: x\n재현 없음 — 사유: x\n"
    assert CHECKER.check_records("d.md", body) == []


def test_둘_다_전수로_요구한다():
    """**현재를 조사해 채울 수 있으면 표기이고 표기는 전수 소급한다** (D-0081 · D-0136)."""
    assert CHECKER.ENFORCER_FROM == 1
    assert CHECKER.REPRODUCE_FROM == 1


def test_낱말이_아니라_칸을_본다():
    """`재현성`을 적은 기록 **29건**이 칸이 있는 것으로 세어졌다 (D-0136)."""
    body = "## D-0001. 제목\n\n- **배경**: 재현성이 핵심이다.\n\n강제자 없음 — 사유: x\n"
    problems = CHECKER.check_records("d.md", body)
    assert problems and "재현" in problems[0]


def test_불명도_기술이다():
    """**모르는 것을 빈칸으로 두면 안 보이고 적어 두면 세어진다.**"""
    body = "## D-0001. 제목\n\n- **배경**: x\n\n강제자 없음 — 사유: x\n재현 불명 — 못 찾았다\n"
    assert CHECKER.check_records("d.md", body) == []


def test_PLAN에_취소선이_남으면_잡는다() -> None:
    """**미래 문서가 과거를 이고 가면 안 된다** (D-0308).

    빚 표 14행 중 **13행이 취소선**이었고 남은 진짜 빚 하나가 그 안에 묻혀 있었다.
    규율은 이미 옆 표에 있었다 — *"닫힌 질문은 여기 없다"*.
    """
    assert REPO.check_plan_leftovers() == []


def test_취소선_못이_실제로_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**아무것도 못 잡는 검사는 늘 통과하는 하네스와 같다** (GR-0.9 · D-0071)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PLAN.md").write_text(
        "| 빚 | 크기 |\n|---|---|\n| ~~다 갚았다~~ | 0 |\n- ~~이것도~~\n", encoding="utf-8"
    )
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    found = REPO.check_plan_leftovers()
    assert len(found) == 2
    assert "MASTER.md" in found[0]


def test_강조_밀도_가지가_실제로_돈다() -> None:
    """**`not name.startswith("")`는 늘 거짓이라 이 가지가 한 번도 안 돌았다** (D-0349).

    27곳을 놓쳤다 — `MASTER` 3 · `DECISIONS` 24. 검사가 **있는** 것과 **도는** 것은
    다르다. 과밀을 심어 가지가 살아 있는지 본다.
    """
    planted = "### 절\n\n" + "**굵게** " * 40 + "\n" + "가" * 300 + "\n"
    assert cast("list[str]", CHECKER.check_bold_density("docs/MASTER.md", planted))

    whole = cast("list[str]", CHECKER.check())
    assert whole == [], whole
