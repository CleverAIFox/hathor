"""빚을 **축마다** 세는가 (D-0328).

`make ship`이 *"갚을 수 있는 빚 없다"*를 찍는 동안 128건이 서 있었다 — 세던 축이
「합성으로만 선 판단」 하나뿐이었기 때문이다.

**0을 찍는 것이 이 도구의 일이다.** 안 세는 것은 0으로 보이고, 0은 다 끝난 것으로
읽힌다. 「없다」를 말할 자격은 **모든 축을 세어 본 뒤에** 생긴다.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def test_모든_축을_찍는다() -> None:
    """**0인 축도 줄을 낸다.** 안 찍으면 「안 센다」와 「없다」가 안 갈린다."""
    debts = tool_module("debts")
    axes = debts.survey()

    assert len(axes) >= 3, "축이 셋 미만이면 옛 꼴로 돌아간 것이다"
    names = [axis.name for axis in axes]
    assert "합성으로만 선 판단" in names, "기존 축을 잃었다"
    assert "PLAN 열린 질문" in names, "항목 그 자체가 빚이다"


def test_합계가_0일_때만_없다고_말한다() -> None:
    """**「없다」는 합계가 0일 때만 나온다.** 한 축이 0인 것으로는 부족하다."""
    debts = tool_module("debts")
    zero = [debts.Axis("가짜", 0)]
    some = [debts.Axis("가짜", 0), debts.Axis("남은 것", 3)]

    assert any("정말 없다" in line for line in debts.report(zero))
    assert not any("정말 없다" in line for line in debts.report(some))
    assert debts.report(some)[-1].split()[-1] == "3"


def test_열린_질문을_실제로_센다() -> None:
    """PLAN의 `O-` 행 수와 같아야 한다. **손으로 적은 수를 안 믿는다.**"""
    debts = tool_module("debts")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    block = plan.split("<!-- open-issues:begin -->")[1].split("<!-- open-issues:end -->")[0]

    counted = debts.plan_open_issues().count
    assert counted == len([line for line in block.splitlines() if line.startswith("| O-")])
    assert counted > 0, "열린 질문이 0이면 PLAN이 빈 것이다 — 그때는 이 검사를 지운다"


def test_판결_난_행은_PLAN에_없다() -> None:
    """**미래 문서가 과거를 이고 가지 않는다** (D-0262 · D-0328).

    「승격 아님」은 *"더 갚을 것이 없다"*는 뜻이고, 그 판단은 `자료` 칸이 든다.
    한자리에서 보려고 PLAN에 두었더니 **일곱 줄이 쌓였다.**
    """
    assert tool_module("debts").plan_settled_rows().count == 0


def test_신선도는_못_읽으면_0이_아니라_모름이다() -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5).

    git을 못 읽었을 때 0을 내면 «최신»으로 읽힌다 — 이 도구가 막으려는 바로 그 병이다.
    """
    debts = tool_module("debts")
    axes = debts.staleness()
    for axis in axes:
        if "모름" in axis.note:
            assert axis.count == 0, "모를 때는 수를 지어내지 않는다"


# ------------------------------------------------------------------ 뒤집힘 꼬리표


def _record(body: str, number: int = 91) -> object:
    ledger = tool_module("decision_ledger")
    return ledger.Record(identifier=f"D-{number:04d}", number=number, title="어떤 판", body=body)


def test_뒤집은_판을_확인으로_적으면_잡는다() -> None:
    """**기각을 통과로 읽게 만든다** (D-0328). 실제로 두 줄이 그랬다."""
    evidence = tool_module("decision_evidence")
    body = (
        "> **갱신됨 — D-0327.** **가설이 기각됐다.** 실물에서 누설 구간이다.\n\n"
        "본문\n\n자료  합성 · 실물 1004곡 (D-0327 확인)\n"
    )
    problems = evidence.check_evidence([_record(body)])
    assert any("뒤집힘" in line for line in problems), problems


def test_통과시킨_판은_확인이_맞다() -> None:
    """**거짓 경보가 진짜 경보를 죽인다** (GR-0.8).

    처음에 낱말 `뒤집`을 넣었더니 *"박 뒤집힘이 4/39에서 1/39로 줄었다"*가 걸렸다 —
    **지표 이름**이고 그 판은 진짜 확인이었다. 셋 중 하나가 거짓이면 아무도 안 읽는다.
    """
    evidence = tool_module("decision_evidence")
    body = (
        "> **갱신됨 — D-0171.** 사전 등록 예측이 **통과했다.** 박 뒤집힘이 4 / 39에서\n"
        "> **1 / 39**로 줄었다.\n\n본문\n\n자료  합성 · 실물 39곡 (D-0171 확인)\n"
    )
    assert evidence.check_evidence([_record(body, 169)]) == []
