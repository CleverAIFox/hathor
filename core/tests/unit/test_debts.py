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


def test_보안_설정을_파일로_센다() -> None:
    """**설정은 축에 없다** (D-0329 · GR-0.5).

    «비공개 취약점 보고»는 GitHub 설정이라 파일이 없다. 세는 척하면 0이 «켜져 있다»로
    읽힌다 — 이 도구가 막으려는 바로 그 병이다. 파일로 확인되는 것만 든다.
    """
    debts = tool_module("debts")
    for name in debts.SECURITY_SETUP:
        assert (ROOT / name).is_file(), f"{name}이 없다"
    assert debts.security_setup().count == 0
    assert not any("보고" in name for name in debts.SECURITY_SETUP), "설정은 파일로 못 센다"


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


def test_안_갚은_행을_센다() -> None:
    """**판결 난 것만 세고 있었다** (D-0335).

    D-0328이 「판결 난 행」 축을 만들었는데 그것은 **0이어야 정상인 축**이다. 갚을 것이
    남은 행은 아무 데도 안 세어졌고, 화면이 「합계 35」를 찍는 동안 넷이 서 있었다 —
    **D-0328 · D-0329와 같은 병의 세 번째다.**
    """
    debts = tool_module("debts")
    table = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    block = table.split("### 3.1 합성으로만 선 판단")[1].split("\n## ")[0]
    rows = [line for line in block.splitlines() if line.startswith("| D-")]

    assert debts.plan_open_rows().count == len(rows) - debts.plan_settled_rows().count
    assert rows, "표가 비면 두 축이 다 0이 되고 그것은 「다 갚았다」로 읽힌다"


def test_경보를_못_읽으면_모름이다() -> None:
    """**`gh`가 없을 때 0을 내면 「경보가 없다」로 읽힌다** (GR-0.5 · D-0335).

    처음에 `FileNotFoundError`로 터지게 썼다. 터지는 것이 0보다는 낫지만 **빚을 세다가
    죽으면 나머지 축도 안 보인다** — 잡아서 「모름」을 낸다.
    """
    debts = tool_module("debts")
    found = debts.dependabot_alerts()

    assert found.name == "Dependabot 열린 경보"
    if "모름" in found.note:
        assert found.count == 0, "모를 때 수를 지어내지 않는다"
    else:
        assert not found.note, "읽었으면 「모름」이라고 적지 않는다"


def test_닫힌_질문을_막고_있다고_적으면_잡는다() -> None:
    """**손 표가 대장을 이겼다** (D-0338).

    §3.1에 D-0062·D-0064 행이 서 있었고 **둘 다 닫힌 질문이었다** — D-0063이 O-21을
    닫고 D-0065가 O-27 (b)를 기각했다. `payable()` 명단은 **비어 있었는데** 손으로 쓴
    표가 「빚 4건」을 찍었고, 그것을 보고 **D-0337이 끝난 질문의 자를 지었다.**

    0이어야 정상인 축이다. 0이 아니면 **미래 문서가 닫힌 과거를 막고 있다고 말하는
    것**이다.
    """
    debts = tool_module("debts")
    found = debts.plan_closed_question_rows()

    assert found.name == "PLAN 닫힌 질문 행"
    assert found.count == 0, f"닫힌 질문을 막고 있다고 적은 행: {found.note}"


def test_닫힌_질문_표를_실제로_읽는다() -> None:
    """**빈 집합이면 축이 늘 0이다** (GR-0.5 · GR-0.8).

    `MASTER`의 표식 이름이 바뀌면 `_closed_issues()`가 조용히 빈 집합을 내고 축이
    영원히 통과한다 — 그러면 **안 세는 것이 0으로 보인다.**
    """
    debts = tool_module("debts")
    closed = debts._closed_issues()

    assert len(closed) > 20, "닫힌 질문 표를 못 읽었다 — 표식 이름이 바뀌었나 본다"
    assert {"O-21", "O-27"} <= closed, "둘(닫힘 D-0074)이 표에 있어야 이 축이 작동한다"


def test_조건이_걸린_질문을_따로_센다() -> None:
    """**「아직 못 한다」와 「지금 할 수 있다」는 다른 빚이다** (D-0336).

    «P5 착수 때» 같은 조건을 적어 두고 **아무도 안 세면 영원히 잠긴다** (D-0126).
    O-17의 조건은 **283건 전**에 걸렸고 그동안 열린 질문 35에 섞여 안 보였다.
    """
    debts = tool_module("debts")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    block = plan.split("<!-- open-issues:begin -->")[1].split("<!-- open-issues:end -->")[0]

    counted = debts.plan_unblocked().count
    assert counted == len([x for x in block.splitlines() if debts.CONDITION_MET in x])
    assert counted <= debts.plan_open_issues().count, "조건 걸린 것은 열린 것의 부분집합이다"
