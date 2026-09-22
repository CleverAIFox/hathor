"""문서 레이아웃 강제자의 단위 검사 (D-0129).

**도구 자신을 검사한다** (D-0080). 그리고 **기각한 규칙이 왜 기각됐는지도 검사한다** —
다음 세션이 "1인칭을 막자"고 다시 제안하지 않도록 실측을 검사로 굳힌다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "check_doc_style.py"
    spec = importlib.util.spec_from_file_location("check_doc_style", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_style"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()


def _layout(text: str) -> list[str]:
    return CHECKER.check_layout("x.md", text)


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


@pytest.mark.parametrize("name", ["README.md", "MASTER.md", "docs/MASTER.md"])
def test_세_축을_다_본다(name):
    assert name in CHECKER.DOCUMENTS


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
    problems = CHECKER.check_sixth_document()
    assert len(problems) == 1
    assert "여섯 번째 문서" in problems[0]


def test_하위_폴더까지_본다(tmp_path, monkeypatch):
    """`docs/_patch/` 같은 자리가 **두 검사 사이로 빠져나가는 것**을 막는다."""
    nested = tmp_path / "docs" / "_patch"
    nested.mkdir(parents=True)
    (nested / "copy.md").write_text("# 사본\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_sixth_document()


def test_축_셋만_통과한다(tmp_path, monkeypatch):
    """**하위 폴더도 안 된다** (D-0187). 넷째 축이 숨어들 자리다."""
    for name in CHECKER.AXES:
        (tmp_path / "docs" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / name).write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_sixth_document() == []

    nested = tmp_path / "docs" / "decisions" / "D-0001-0050.md"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("# x\n", encoding="utf-8")
    assert CHECKER.check_sixth_document() != []


def test_저장소에_여섯_번째가_없다():
    assert CHECKER.check_sixth_document() == []


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
