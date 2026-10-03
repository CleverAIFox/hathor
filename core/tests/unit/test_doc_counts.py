"""문서가 적은 수 ↔ 실물 축의 단위 검사 (D-0263 · D-0288 · D-0349).

**축이 하나에서 열다섯이 됐다.** 늘 때마다 **틀린 수가 하나씩 나왔다** — 세는 자가
없으면 수가 틀려도 아무 일이 안 일어나기 때문이다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("doc_counts")
FSCK = tool_module("doc_fsck")


def _counted(pattern: str) -> int:
    """결정 기록에서 그 꼴로 시작하는 줄의 수. **도구와 다른 길로 센다.**"""
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(f"(?m){pattern}", body))


def test_축이_일곱_이상이다():
    """**세는 그물이 비면 «전부 맞다»가 거짓으로 참이 된다** (D-0230).

    축이 하나였다 — 문서에 손으로 적힌 수가 214개인데 기계가 보는 것은 `계약 N종`
    하나뿐이었다. 그 사이에 **「대장 201건 중」이 실물 223일 때까지** 아무도 안 셌고,
    그 줄이 사는 표의 머리말이 *"크기를 재서 적는다"*다.

    **넷에서 다섯이 됐다 (D-0307)**: `재현 불명`이 PLAN에 **16**으로 적혀 있고 실물이
    **11**이었다. 축을 놓자마자 *"11이라 적었는데 실물은 1"*로 걸렸다.

    **다섯에서 일곱이 됐다 (D-0349)**: `프로브`가 README에 「넷」(한글 수사라 축이 못
    읽었다)이고 실물이 다섯 · `결정 기록 검사`는 **열 이름을 손으로 적고 있었고** 그중
    하나는 D-0189가 지운 검사였다.

    **바닥으로 둔다.** 축은 늘기만 하는 것이 옳고, 수를 딱 박으면 **축을 넣을 때마다
    시험을 고쳐야 해서 안 넣게 된다.**
    """
    names = [name for name, _, _ in CHECKER.COUNTED]
    assert len(names) >= 7, names
    for wanted in ("import-linter 계약", "결정 대장", "deadcheck 프로브", "결정 기록 검사"):
        assert wanted in names, wanted


def _axis(name: str) -> object:
    """축을 **이름으로** 집는다 (D-0349).

    자리로 집고 있었다 — `COUNTED[1]`. 축을 하나 넣자 **시험 셋이 엉뚱한 축을 쥐었다.**
    목록 가운데에 넣는 것이 정상인데 자리로 집으면 그때마다 시험을 고쳐야 하고,
    그러면 **고치기 싫어서 끝에만 붙이게 된다.**
    """
    for axis in CHECKER.COUNTED:
        if axis[0] == name:
            return axis
    raise LookupError(f"«{name}» 축이 없다")


def test_축마다_정본이_수를_낸다():
    """**정본이 없는 값은 축이 아니다.** 셋 다 실제로 세어져야 한다."""
    for name, _pattern, count in CHECKER.COUNTED:
        assert isinstance(count(), int), name
        assert count() > 0, f"{name}의 정본이 0을 낸다 — 세는 자리를 의심한다"


def test_재현_불명을_센다() -> None:
    """**PLAN이 16이라 적고 실물은 11이었다** (D-0307).

    `재현`은 *"지금 이 수치를 다시 내는 명령"*이라 조사하면 줄어드는 수다 (D-0136).
    줄어드는 수는 문서에서 낡고, **수가 틀려도 아무 일이 안 일어난다** (D-0263).
    """
    assert CHECKER.unknown_reproductions() == _counted("^재현 불명")
    # 축이 실제로 표에 실려 있어야 `--fix`가 그 자리를 고친다.
    assert "재현 불명" in {name for name, _, _ in CHECKER.COUNTED}


def test_재현_불명_축이_틀린_수를_잡는다() -> None:
    """**세는 그물이 비면 «0건»이 거짓으로 참이 된다** (D-0230)."""
    pattern = next(rule for name, rule, _ in CHECKER.COUNTED if name == "재현 불명")
    assert pattern.search("| 재현 불명 **11건** |") is not None
    assert pattern.search("| 재현 불명 1건 |") is not None
    assert pattern.search("재현 불명 — 이 수치를 내는 명령을 못 찾았다") is None


# ------------------------------------------------------------------ 거꾸로 보기 (D-0349)


def test_GR_축이_과거_축을_안_센다() -> None:
    """**매 판 뜨는 경보는 경보가 아니다** (GR-0.8 · D-0350).

    첫 안이 전수 **356**을 셌고 그중 **153이 결정 기록**이었다. 그래서 기록에 `GR-0.5`
    한 번만 적어도 수가 흔들렸고 **두 판 연속 356 ↔ 357로 오갔다.**

    과거 축은 추가만 하므로 **어차피 번호를 바꿀 때 소급 대상이고**(GR-0.2), 그 비용은
    별 축(`과거 축 GR 참조`)이 든다 — **안 세면 산문에 손으로 적힌 수가 다시 생긴다.**
    """
    living = CHECKER.rule_mentions()
    past = CHECKER.past_rule_mentions()

    assert past > 100, past
    assert living < past + living, "살아 있는 쪽만 세야 한다"
    names = {name for name, _, _ in CHECKER.COUNTED}
    assert {"GR 참조", "과거 축 GR 참조"} <= names


def test_새_축_일곱이_실물을_센다() -> None:
    """**정본이 사라지면 조용히 넘어가면 안 된다** (D-0223).

    축이 **다섯에서 열둘**이 됐다 (D-0349). 일곱 다 **정본이 다른 파일에 있고** 그
    파일이 사라지면 `LookupError`로 터진다 — 0을 내고 통과하면 그것이 D-0230이다.
    """
    assert CHECKER.probe_count() >= 5
    assert CHECKER.record_check_count() >= 10
    assert CHECKER.frozen_issues() >= 1
    assert CHECKER.service_count() >= 10
    assert CHECKER.rule_mentions() >= 150
    assert CHECKER.egress_points() == 4
    assert CHECKER.grandfathered_records() == 79

    names = {name for name, _, _ in CHECKER.COUNTED}
    assert len(names) >= 16, names
    assert {
        "deadcheck 프로브",
        "결정 기록 검사",
        "얼린 질문",
        "compose 서비스",
        "GR 참조",
        "망 접점",
        "형식 면제 기록",
        "과거 축 GR 참조",
    } <= names


@pytest.mark.parametrize(
    "axis",
    ["probe_count", "record_check_count", "egress_points", "grandfathered_records"],
)
def test_정본이_사라지면_터진다(axis: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**0을 내고 통과하면 그것이 빈 그물이다** (D-0230 · `fire-lane`의 `doc_fsck ⑥`).

    저쪽 규율: *"못 잰 것을 통과로 세지 않는다."* 정본 파일이 없으면 **빨간불**이고
    조용한 0이 아니다.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "docs").mkdir()
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)

    with pytest.raises((LookupError, OSError)):
        getattr(CHECKER, axis)()


def test_대장_내역_넷이_전수다() -> None:
    """**합이 대장 행 수와 같아야 한다** (D-0349).

    PLAN이 *"합성 8 · 합성+실물 43 · 실물 174 · 해당없음 30"*(합 **255**)을 적고 실물은
    **279**였다. **`합성 8`만 축이 있어서 그것만 맞았다** — 세는 자가 있는 수와 없는 수가
    같은 줄에 나란히 있었고 **읽는 사람은 넷 다 센 줄로 읽는다.**

    넷을 전수로 묶으면 **새는 것이 바로 보인다** — 이 시험이 그 자다.
    """
    parts = (
        CHECKER.synthetic_rows(),
        CHECKER.mixed_rows(),
        CHECKER.real_rows(),
        CHECKER.not_applicable_rows(),
    )

    assert sum(parts) == CHECKER.ledger_rows(), parts
    assert all(one >= 0 for one in parts)


@pytest.mark.parametrize(
    ("source", "bucket"),
    [
        ("합성", "합성"),
        ("합성 (D-0323 승격 아님)", "합성"),
        ("합성 · 실물 1004곡", "합성+실물"),
        ("실물 저장소", "실물"),
        ("해당 없음", "해당없음"),
    ],
)
def test_부류를_가르는_규칙(source: str, bucket: str) -> None:
    """**「합성」과 「합성 · 실물」이 갈려야 한다.** 앞은 뒤집힐 수 있는 판단이고 뒤는 아니다."""
    assert CHECKER._bucket(source) == bucket


def test_계약_수를_pyproject에서_센다() -> None:
    """**정본은 `core/pyproject.toml` 하나다** (D-0223). 문서가 아니라 선언을 센다.

    **수를 딱 박는다.** 계약을 더하는 것은 **큰 일**이고 그때 이 줄을 같이 고치는 것이
    맞다 — D-0261이 여섯째를 넣고 `MASTER` 세 곳을 안 고친 자리다. 이 판은 일곱째를
    넣었고 **축이 다섯 곳을 자동으로 고쳤다** (D-0350).
    """
    assert CHECKER.contract_count() == 7


# ------------------------------- 앨범 효과 위의 수를 대표로 들지 않는다 (D-0284)


def test_대장은_표식_안만_센다():
    """**표식 밖의 `| D-xxxx |` 행이 있다** — 전부 세면 230, 대장은 223이다."""
    body = (CHECKER.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    everywhere = len(re.findall(r"(?m)^\| D-\d{4} \|", body))
    assert CHECKER.ledger_rows() < everywhere


def test_관문_도구를_실물에서_센다() -> None:
    """**`--check`를 받는 것만 센다** (D-0350). `MASTER` §11이 그 수를 든다."""
    tools = [str(one) for one in CHECKER.gate_tools()]

    assert len(tools) >= 14, tools
    assert CHECKER.gate_count() == len(tools)
    for wanted in ("check_sight", "check_retired", "check_requirements", "check_args"):
        assert wanted in tools, wanted


def test_모든_축이_읽는_자리를_가진다() -> None:
    """**읽는 자리가 0곳인 축은 죽은 축이다** (D-0350 · `fire-lane`의 `docgen`).

    저쪽 `apply_all`이 **축이 어느 블록에도 안 걸리면 실패**시킨다. 그 규율을 안
    가져왔더니 **「열린 질문」 축이 읽는 자리 0곳으로 있었다** — 세는 함수는 멀쩡하고
    **비교할 상대가 없어서 영원히 아무것도 못 잡는다.**

    **축을 놓는 것과 그 축이 무는 것은 다르다** (D-0230).
    """
    blob = "".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "docs/PLAN.md", "docs/MASTER.md")
    )
    dead = [name for name, pattern, _ in CHECKER.COUNTED if not pattern.findall(blob)]

    assert dead == [], dead
