"""기획서 수치의 상류 (D-0378).

**내가 안 센 수를 두 판 연속 적었다.** D-0371이 *«약 127줄»*, D-0372가 *«345줄»* —
둘 다 세지 않았고, 345는 `REQ-ING-007` · `D-0174` · `2026-08-10` 같은 **식별자를 수로
센** 것이다. 실제로 세니 **수치 주장 180 · 상류 없음 40**이었다.

여기 시험은 **가르는 법**과 **배선**을 본다. 저장소 실측은 한 줄로 못을 박는다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("check_claims")
ROOT = Path(__file__).resolve().parents[3]


def _claims(lines: list[str]) -> list[str]:
    return cast("list[str]", TOOL.claims(lines))


# ------------------------------------------------------------------ 가르는 법


def test_식별자는_수가_아니다() -> None:
    """**345를 만든 그 자리다.** 이름과 날짜를 수로 세면 빚이 세 배로 보인다."""
    assert _claims(
        [
            "| REQ-ING-007 | Chromaprint 지문을 산출한다 | M | P1 | 폐기 |",
            "| D-0174 | 반주가 앞에서 논다 | 층마다 세기 |",
            "| R-8 | 노트북 2대 환경 불일치 |",
            "| 2026-08-10 | 초판 작성 | 전환 |",
        ]
    ) == ["| R-8 | 노트북 2대 환경 불일치 |"], "`2대`는 주장이고 나머지는 이름·날짜다"


def test_첫_칸_번호는_차례다() -> None:
    """`| 3 | 인제스트 파이프라인 | …`의 3은 수치가 아니다. **뒤에 수가 있으면 남는다.**"""
    assert _claims(["| 3 | 인제스트 파이프라인 | 코드 + CLI | 완료 |"]) == []
    assert _claims(["| 09 | 0.1725 | 0.1952 |"]) == ["| 09 | 0.1725 | 0.1952 |"]


def test_코드_조각_안의_수는_이름이다() -> None:
    """`` `layer03` ``은 상수 이름이지 측정값이 아니다."""
    assert _claims(["| 검색 | `layer00` | 레이어 곡선이 0에서 최대 |"]) == [
        "| 검색 | `layer00` | 레이어 곡선이 0에서 최대 |"
    ], "울타리 밖의 0은 남는다"
    assert _claims(["| 검색 | `layer00` | 최대 |"]) == []


def test_그물이_비면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**지울 꼴이 없으면 모든 줄이 주장이 되고 천장이 뜻을 잃는다** (D-0230)."""
    monkeypatch.setattr(TOOL, "IDENTS", ())

    assert any("그물이 비었다" in one for one in cast("list[str]", TOOL.check()))


def test_표를_한_줄도_못_읽으면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**빈 목록을 통과로 읽지 않는다** (GR-0.5)."""
    monkeypatch.setattr(TOOL, "rows", list)

    assert any("한 줄도 못 읽었다" in one for one in cast("list[str]", TOOL.check()))


# ------------------------------------------------------------------ 상류


def test_저장소가_천장과_같다() -> None:
    """**실측이 못이다** (D-0269 · D-0117). 줄면 `check_ratchets --update`가 조인다."""
    groups = cast("dict[str, list[str]]", TOOL.sort(_claims(cast("list[str]", TOOL.rows()))))

    assert TOOL.tally(groups["상류 없음"]) == TOOL.UNSOURCED_CEILING
    assert groups["헛인용"] == [], "대장에 없는 결정을 인용한다"
    assert len(groups["기록"]) > 0 and len(groups["거울"]) > 0, "상류를 하나도 못 찾았다"


def test_머리말이_상류를_물려준다() -> None:
    """**표 한 장의 상류는 보통 그 표 위 제목에 한 번 적힌다** (D-0378).

    `### □ 레이어 곡선 — 검색축 (D-0027)` 아래 일곱 줄이 그 꼴이다. 줄마다 번호를
    반복하면 사람이 안 읽는다.
    """
    heads = cast("dict[str, set[str]]", TOOL.captions())

    assert heads, "머리말을 하나도 못 읽었다"
    assert any("0027" in one for one in heads.values()), "레이어 곡선 표가 D-0027을 못 물었다"


def test_없는_결정을_인용하면_헛인용이다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 번호만 적어 두면 상류가 있는 척이 된다."""
    monkeypatch.setattr(TOOL, "recorded", set)
    monkeypatch.setattr(TOOL, "captions", dict)
    monkeypatch.setattr(TOOL, "mirrored", set)
    monkeypatch.setattr(TOOL, "required", set)

    groups = cast("dict[str, list[str]]", TOOL.sort(["| 임베딩 | 20.4배 (D-0027) |"]))

    assert groups["헛인용"] == ["| 임베딩 | 20.4배 (D-0027) |"]
    assert groups["상류 없음"] == []


def test_헛인용이_판정까지_닿는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0352). 가르는 함수만 맞고 `check()`가 안 보면 소용없다."""
    monkeypatch.setattr(TOOL, "recorded", set)

    assert any("대장에 없는 결정" in one for one in cast("list[str]", TOOL.check()))


def test_천장을_넘으면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**표를 손으로 늘리면 여기서 걸린다.**"""
    monkeypatch.setattr(TOOL, "UNSOURCED_CEILING", 0)

    assert any("천장 0" in one for one in cast("list[str]", TOOL.check()))


def test_줄면_조이라고_말한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**좋아졌으면 박는다** (D-0257 · D-0363). 조이는 자는 `check_ratchets` 하나다 (D-0117)."""
    monkeypatch.setattr(TOOL, "UNSOURCED_CEILING", 9999)

    problems = cast("list[str]", TOOL.check())

    assert any("check_ratchets.py --update" in one for one in problems), problems


# ------------------------------------------------------------------ 배선


def test_판정이_입구까지_닿는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**부품을 재고 배선을 안 쟀다** (D-0352). `main()`을 거쳐 화면까지 본다."""
    monkeypatch.setattr(TOOL, "check", lambda: ["심은 것"])
    monkeypatch.setattr("sys.argv", ["check_claims.py", "--check"])

    assert TOOL.main() == 1
    assert "심은 것" in capsys.readouterr().err


def test_수를_눈앞에_둔다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**통과 줄이 넷을 든다** (D-0269). 상류가 어디서 오는지 사람이 본다."""
    monkeypatch.setattr("sys.argv", ["check_claims.py", "--check"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    for word in ("거울", "요구사항", "기록", "상류 없음"):
        assert word in spoke, spoke
    assert f"천장 {TOOL.UNSOURCED_CEILING}" in spoke

    # **센 수가 화면에 닿는가** (D-0269 · D-0352). 쓸기로 재니 `tally()`를 끊어도
    # 아무 시험이 안 울었다 — 건수가 틀린 채로 통과 줄에 찍혀도 조용했다.
    groups = cast("dict[str, list[str]]", TOOL.sort(_claims(cast("list[str]", TOOL.rows()))))
    assert f"{TOOL.tally(groups['상류 없음'])}건" in spoke, spoke
    assert f"{len(groups['상류 없음'])}줄" in spoke, spoke


def test_목록이_상류_없는_줄을_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**40을 적고 끝내지 않는다.** 무엇인지 봐야 갚는다."""
    monkeypatch.setattr("sys.argv", ["check_claims.py", "--list"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    assert spoke.count("건  |") >= 1
    assert f"{TOOL.UNSOURCED_CEILING}건" in spoke, spoke

    # **줄마다 찍은 건수의 합이 총계와 같다** (D-0352). 쓸기로 재니 줄별 `tally()`를
    # 끊어도 조용했다 — 「0건」이 마흔 줄 찍혀도 총계는 맞으니 아무도 안 울었다.
    each = [int(one) for one in re.findall(r"^  (\d+)건  \|", spoke, re.M)]
    assert sum(each) == TOOL.UNSOURCED_CEILING, each


@pytest.mark.parametrize("where", ["Makefile", ".githooks/pre-commit", ".github/workflows/ci.yml"])
def test_세_곳에_다_걸려_있다(where: str) -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126 · D-0219)."""
    assert "tools/check_claims.py" in (ROOT / where).read_text(encoding="utf-8")


# ------------------------------------------------------------------ 단위


def test_빚은_줄이_아니라_건수로_센다() -> None:
    """**그의 지적이다** — *«빚 상환은 건수가 중요하지 라인 수가 아니다»*.

    줄로 세면 빚이 작아 보인다. 한 줄이 수 셋을 들면 **틀릴 수 있는 자리가 셋**이다.
    """
    row = "| fp16 · 120초 곡 | 확산 68초 · 옮기기 189초 뒤 NaN |"

    assert TOOL.tally([row]) == 3
    assert len(_claims([row])) == 1, "줄로는 하나다 — 그래서 줄로 안 센다"


def test_판_번호는_한_건이다() -> None:
    """**거짓 경보를 안 만든다** (GR-0.8). `8.0.1`을 둘로 세면 천장이 부푼다."""
    assert TOOL.tally(["| 시스템 바이너리 | ffmpeg 8.0.1 |"]) == 1
    assert TOOL.tally(["| 임베딩 | 0.0699 · 0.0034 |"]) == 2
