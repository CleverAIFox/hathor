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
    text = "".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "docs" / "decisions").glob("*.md"))
    )
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


@pytest.mark.parametrize("name", ["README.md", "CONTRIBUTING.md", "docs/DESIGN.md"])
def test_세_축을_다_본다(name):
    assert name in CHECKER.DOCUMENTS


def test_폐기_문서는_안_본다():
    """`docs/archive`는 **고칠 것이 아니다** (D-0042)."""
    assert not any("archive" in path.as_posix() for path in CHECKER.targets())


def test_백틱_안의_예시는_경어체가_아니다():
    """**이 검사를 설명하는 기록이 `합니다`를 예로 든다.**"""
    assert _layout("`합니다`·`입니다`는 잡는다.\n") == []
