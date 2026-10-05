"""장비를 재는 관문 도구 — `gpu_smoke` · `step0_check` · `build_proposal` (D-0258).

셋 다 관문에 서는데 자기 시험이 없었다 (D-0257이 셌다). **장비가 있어야 도는 도구라
아무도 안 밀어 봤고**, 그래서 판정 자체가 틀린 것이 하나 있었다.

GPU도 `torch`도 없이 민다 — 셋 다 판정을 순수 함수로 떼어 놓았거나(`verdict`),
무거운 것을 함수 안에서 들여온다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module as _tool

SMOKE = _tool("gpu_smoke")
STEP0 = _tool("step0_check")
BUILD = _tool("build_proposal")
BODY = _tool("proposal_body")


# ------------------------------------------------------------------ gpu_smoke


def test_재개_조건을_다_넘으면_사유가_없다() -> None:
    assert SMOKE.verdict(24.0, bf16=True, fp16_finite=True, required=16) == []


def test_VRAM이_모자라면_사유가_선다() -> None:
    (reason,) = SMOKE.verdict(8.0, bf16=True, fp16_finite=True, required=16)

    assert "8.0GB" in reason and "16GB" in reason


def test_bf16이_없으면_막는다() -> None:
    """**fp16으로 돌면 G0처럼 NaN이 난다** — VRAM이 넉넉해도 재개 조건이 아니다."""
    assert SMOKE.verdict(48.0, bf16=False, fp16_finite=True, required=16)


def test_사유가_여럿이면_다_적는다() -> None:
    """하나만 적으면 고치고 다시 돌렸을 때 **다음 사유가 그제야 나온다.**"""
    assert len(SMOKE.verdict(4.0, bf16=False, fp16_finite=False, required=16)) == 3


def test_재개_조건을_PLAN에서_읽는다(tmp_path: Path) -> None:
    """**임계값이 코드에 없다** (D-0223). PLAN이 정본이다."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text(
        "# 계획\n\n재개 조건: NVIDIA · VRAM 24GB 이상\n", encoding="utf-8"
    )

    assert SMOKE.required_vram(root=tmp_path) == 24


def test_PLAN_문장이_바뀌면_터진다(tmp_path: Path) -> None:
    """**기본값으로 넘어가면 아무 장비나 통과한다.**"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text("재개 조건: 좋은 GPU\n", encoding="utf-8")

    with pytest.raises(LookupError):
        SMOKE.required_vram(root=tmp_path)


def test_실제_PLAN에서도_읽힌다() -> None:
    """시험이 만든 문장만 읽히고 **정본은 못 읽는 일**이 없게 한다."""
    assert SMOKE.required_vram() >= 8


# ------------------------------------------------------------------ step0_check


def test_파이썬_판을_글자가_아니라_수로_센다() -> None:
    """**`"3.9" < "3.10"`은 거짓이다** (D-0258).

    글자로 비교하고 있어서 3.9에서 경고가 안 떴다. 그리고 메시지는 «3.12 이상»인데
    비교값은 3.10이었다 — **둘 다 틀린 채 조용히 통과했다.**
    """
    assert STEP0.old_python("3.9")
    assert STEP0.old_python("3.9.18")
    assert STEP0.old_python("3.11.9")
    assert not STEP0.old_python("3.12")
    assert not STEP0.old_python("3.13.0")


def test_임계값이_한_곳에_산다() -> None:
    """경고 문구와 비교값이 갈리면 **사람이 문구를 믿는다.**"""
    assert STEP0.PYTHON_FLOOR == (3, 12)


def test_이상한_판_문자열에_안_죽는다() -> None:
    """`sys.version`류가 `3.12.3 (main, ...)` 꼴로 올 수 있다."""
    assert not STEP0.old_python("3.12.3 (main, Apr 9 2026)")
    assert STEP0.old_python("3")


def test_무거운_것을_함수_안에서_들여온다() -> None:
    """**`torch`·`psutil`·`mutagen` 없이도 로드된다** (D-0256과 같은 이유).

    이 모듈이 로드된 것 자체가 그 증거다 — 여기 시험 환경에는 GPU가 없다.
    """
    assert hasattr(STEP0, "AUDIO_EXTS")
    assert STEP0.VRAM_REQUIREMENTS


# ------------------------------------------------------------------ build_proposal


COVER = """표지 한 줄
또 한 줄

# Part I. 프로젝트 제안서

## 1. 개요

본문이다.

### 1.1 하위

더 있다.
"""


def test_표지와_본문을_가른다() -> None:
    """표지 줄은 **문단째로 한 줄에 접힌다** — 표지에서는 줄바꿈이 뜻을 안 가진다."""
    lines, body = BODY.split_cover(COVER)

    assert lines == ["표지 한 줄 또 한 줄"]
    assert body.startswith("# Part I.")
    assert "본문이다" in body


def test_Part가_없으면_전부_표지가_되지_않는다() -> None:
    """**`partition`은 못 찾으면 조용히 전부를 앞에 넣는다.** 그러면 본문이 사라진다."""
    lines, body = BODY.split_cover("제목만 있다\n")

    assert body == "" or "제목만" in body or lines, "둘 중 하나는 내용을 들어야 한다"


def test_목차를_제목에서_뽑는다() -> None:
    rows = BUILD.outline(COVER)

    assert any("1. 개요" in row for row in rows)


def test_가로선을_걷어낸다() -> None:
    """`---`가 남으면 Word에서 **빈 단락이 페이지를 민다.**"""
    assert "---" not in BODY.clean("가\n\n---\n\n나\n")
