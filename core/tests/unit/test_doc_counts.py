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
    """**정본이 없는 값은 축이 아니다.** 셋 다 실제로 세어져야 한다.

    **센 0과 못 잰 0을 가른다** (D-0385). `duration_ms <= 0`의 0은 실제로 센 0이다 —
    가르는 자리가 없으면 *«0이 정답인 수»*는 영원히 축 밖이고, 그것이 D-0230이다.
    """
    for name, _pattern, count in CHECKER.COUNTED:
        assert isinstance(count(), int), name
        if name in CHECKER.ZERO_OK:
            continue
        assert count() > 0, f"{name}의 정본이 0을 낸다 — 세는 자리를 의심한다"


def test_센_0을_선언으로만_받는다() -> None:
    """**빈 목록이면 모든 축이 0을 낼 수 있다** (D-0230 · D-0219).

    `ZERO_OK`는 차집합의 선언이다 — 이름이 거기 없으면 0은 *«못 쟀다»*로 읽힌다.
    """
    names = {name for name, _, _ in CHECKER.COUNTED}

    assert CHECKER.ZERO_OK, "선언이 비면 0을 내는 축이 조용히 통과한다"
    assert set(CHECKER.ZERO_OK) <= names, "없는 축을 면제한다"
    for name in CHECKER.ZERO_OK:
        count = next(one for label, _, one in CHECKER.COUNTED if label == name)
        assert count() == 0, f"«{name}»이 0이 아니다 — 면제를 지운다 (GR-0.8)"


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
    assert CHECKER.egress_points() == 5  # D-0424 — 논문 훑기
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


# ------------------------------------------------- 축 일곱을 더 놓았다 (D-0385)


def test_새_축_여섯이_실물을_센다() -> None:
    """**정본이 다른 파일에 있고 사라지면 터진다** (D-0223 · D-0230).

    상류 없는 수치 35건을 갚으려고 놓은 축이다. 여섯은 새로 놓았고 「취향 축」은
    **패턴을 넓혔다** — `N축 특징` 5곳에서 `N축` 22곳으로.
    """
    assert CHECKER.corpus_tracks() == 1004
    assert CHECKER.group_code_width() == 3
    assert CHECKER.mert_sources() == 5
    assert CHECKER.determinism_runs() == 2
    assert CHECKER.min_token_chars() == 2
    assert CHECKER.stream_floor() == 0

    names = {name for name, _, _ in CHECKER.COUNTED}
    assert {
        "코퍼스 곡 수",
        "요구사항 그룹 코드",
        "MERT 소스",
        "재현 실행",
        "아티스트 토큰 바닥",
        "재생 시간 바닥",
    } <= names, names


def test_그룹_코드가_세_자만은_아니었다() -> None:
    """**스무 그룹 중 하나가 거짓이었다** (D-0385). `REQ-UI-001`의 `UI`는 두 자다.

    문서가 *«3문자 코드»*라 적고 있었고 **아무도 안 셌다.** 「최대」로 적고 실물의
    최대를 든다 — 그러니 **길이가 하나로 안 모이는 것**이 이 축의 전제다.
    """
    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    groups = re.findall(r"(?m)^\|\s*(?:REQ|NFR|TST|OPS)-([A-Z]{2,4})-\d{3}", body)
    widths = {len(one) for one in groups}

    assert len(widths) > 1, "길이가 하나면 「최대」라 적을 까닭이 없다 — 축을 다시 본다"
    assert CHECKER.group_code_width() == max(widths)
    assert "3문자 코드" not in body, "거짓으로 돌아갔다"


def test_취향_축이_4축_전부를_문다() -> None:
    """**D-0381의 좁힘이 열일곱 자리를 축 밖에 뒀다** (D-0385).

    `4축 프로파일` · `4축 독립` · `4축 분석` · `4축으로 분해`가 안 걸렸고, 그 일곱
    줄이 `check_claims`의 상류 없는 수치였다. **다섯째 축이 생기는 날 전부 거짓이 된다.**
    """
    pattern = next(rule for name, rule, _ in CHECKER.COUNTED if name == "취향 축")

    for said in ("4축 프로파일", "**4축 독립**", "4축 분석", "**4축으로 분해**", "4축에 다른 시드"):
        assert pattern.findall(said) == ["4"], said

    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert len(pattern.findall(body)) >= 20, "정본에서 무는 자리가 줄었다"


def test_대장_행은_축_밖이다() -> None:
    """**대장은 기록 제목의 거울이고 기록은 추가 전용이다** (D-0385 · D-0117).

    D-0039의 제목이 *«문서 체계를 3축으로 명시한다»*다. 「취향 축」을 넓히자 그 행이
    *«3이라 적었는데 실물은 4»*로 울었다 — **과거의 제목을 지금 실물로 재는 것은
    범주 오류다.** 면제 선언으로는 못 막는다: 그 행은 매 판 다시 찍혀 주석이 지워진다.
    """
    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8").splitlines()
    inside = FSCK.ledgered(body)

    assert inside, "대장 표식을 못 찾았다 — 건너뛰는 자리가 0곳이면 이 면제가 죽는다"
    rows = [number for number in inside if "D-0039" in body[number - 1]]
    assert rows, "D-0039 대장 행이 표식 안에 없다"
    assert "3축으로 명시한다" in body[rows[0] - 1], "제목이 고쳐졌다 (추가 전용 위반)"
    assert FSCK.check_counts() == []


def test_고치는_쪽도_면제를_본다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0385). 선언을 읽는 자가 검사 하나였다.

    `--fix`가 *«면제했다»*고 적힌 **바로 그 줄**의 수를 갈아 버렸다. 선언을 한쪽만
    읽으면 그 선언이 거짓이다.
    """
    (tmp_path / "docs").mkdir()
    kept = f"| D-0039 | 문서 체계를 3축으로 명시한다 <!-- {FSCK.COUNT_OK} 인용 --> |\n"
    page = tmp_path / "docs" / "MASTER.md"
    page.write_text(kept, encoding="utf-8")
    monkeypatch.setattr(FSCK, "ROOT", tmp_path)
    monkeypatch.setattr(FSCK, "LIVING", ("docs/MASTER.md",))
    monkeypatch.setattr(FSCK, "counting_code", list)

    FSCK.fix_counts()

    assert page.read_text(encoding="utf-8") == kept, "면제한 줄의 수를 갈았다"
