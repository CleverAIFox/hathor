"""래칫 방향 검사의 단위 검사 (D-0352).

**`check_sight`가 화면에 *"`--loosen`에는 결정 기록이 필요하다"*고 적고, 아무도 안 셌다.**
못을 내려 박고 기록을 안 쓰면 그 판은 영원히 초록이다 — `fire-lane`은 커버리지 래칫이
실물 아래인 것을 **나흘 몰랐다.**
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_ratchets")


def _loosened(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return cast("list[str]", CHECKER.loosened(before, after))


# ------------------------------------------------------------------ 그물


def test_저장소가_통과한다() -> None:
    problems, _ = cast("tuple[list[str], str]", CHECKER.check())

    assert problems == []


def test_못을_실제로_읽는다() -> None:
    """**어휘가 망가지면 0개를 읽고 통과한다** (D-0230). 정수 상수 74개 중 못만 가린다."""
    here = cast("dict[str, int]", CHECKER.measure())

    assert len(here) >= CHECKER.FLOOR_NAILS, len(here)
    assert "deadcheck.CEILING[빈 그물]" in here
    assert "test_gate_tools.UNTESTED" in here
    # **시험 치수는 못이 아니다** — 걸리면 오탐이 쏟아지고 관문이 죽는다 (GR-0.8).
    assert not [key for key in here if key.endswith((".DIM", ".DEGREES", ".SR", ".SEED"))]


def test_정본이_둘이_되지_않는다() -> None:
    """`check_sight.PINNED`는 저 자신이 방향을 안다. **정본은 하나다** (D-0117)."""
    here = cast("dict[str, int]", CHECKER.measure())

    assert "check_sight.PINNED" not in here
    assert not [key for key in here if key.startswith("check_sight.PINNED")]


# ------------------------------------------------------------------ 방향 (카나리아)


def test_천장이_오르면_느슨하다() -> None:
    assert _loosened({"deadcheck.CEILING[빈 그물]": 0}, {"deadcheck.CEILING[빈 그물]": 3})


def test_천장이_내리면_조인_것이다() -> None:
    """**조이는 쪽을 막으면 아무도 안 조인다** (GR-0.8)."""
    assert _loosened({"deadcheck.CEILING[빈 그물]": 3}, {"deadcheck.CEILING[빈 그물]": 0}) == []


def test_바닥이_내리면_느슨하다() -> None:
    assert _loosened({"debts.STALE_FLOOR": 10}, {"debts.STALE_FLOOR": 2})


def test_바닥이_오르면_조인_것이다() -> None:
    assert _loosened({"debts.STALE_FLOOR": 2}, {"debts.STALE_FLOOR": 10}) == []


def test_사라진_못은_늘_느슨하다() -> None:
    """**없는 것은 0이 아니다** (GR-0.5 · D-0349). 지우면 그 자리가 사각지대가 된다."""
    problems = _loosened({"test_gate_tools.UNTESTED": 0}, {})

    assert problems and "사라졌다" in problems[0]


def test_강제_시작이_오르면_느슨하다() -> None:
    """**헷갈리는 자리다** — 늦게 강제하면 **덜** 강제한다.

    `FORMAT_ENFORCED_FROM = 80`을 81로 올리면 기록 하나가 형식 검사 밖으로 빠진다.
    """
    assert _loosened(
        {"check_decisions.FORMAT_ENFORCED_FROM": 80},
        {"check_decisions.FORMAT_ENFORCED_FROM": 81},
    )
    assert (
        _loosened(
            {"check_decisions.FORMAT_ENFORCED_FROM": 81},
            {"check_decisions.FORMAT_ENFORCED_FROM": 80},
        )
        == []
    )


@pytest.mark.parametrize(
    ("name", "which"),
    [
        ("FLOOR", "바닥"),
        ("STALE_FLOOR", "바닥"),
        ("CEILING", "천장"),
        ("QUARANTINE_CEILING", "천장"),
        ("UNTESTED", "천장"),
        ("UNTYPED_FAKES", "천장"),
        ("UNKNOWN_EVIDENCE", "천장"),
        ("NODE_FROM", "천장"),
    ],
)
def test_이름이_부류를_정한다(name: str, which: str) -> None:
    got = cast("str | None", CHECKER.kind(name))

    assert got is not None
    assert CHECKER.NAILS[got] == which


@pytest.mark.parametrize("name", ["DIM", "DEGREES", "WIDTH", "TIMEOUT", "MVP_PHASE"])
def test_못이_아닌_것은_안_센다(name: str) -> None:
    assert CHECKER.kind(name) is None


# ------------------------------------------------- 가장 조였던 값 (D-0353)


def test_기준선이_비면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**못이 안 박혀 있으면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(CHECKER, "BASELINE", {})

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems and "빈 그물" in problems[0]
    assert "못 쟀다" in what


def test_기준선이_실측과_같다() -> None:
    """`--update`가 멱등인지 보는 자리다. 어긋나면 다음 판에 터진다."""
    assert cast("list[str]", CHECKER.verdict(CHECKER.measure(), CHECKER.BASELINE)) == []


def test_누적_침식을_잡는다() -> None:
    """**첫 판은 부모 커밋만 봤다** (D-0352 → D-0353).

    한 판에 1씩 내려가면 **둘째 판부터 영원히 초록이다** — 1 → 1은 느슨해진 것이 아니고
    **원래가 0이었다는 사실을 아무도 안 들고 있다.** 기준선은 들고 있다.
    """
    nail = "deadcheck.CEILING[빈 그물]"
    pinned = {nail: 0}

    once = cast("list[str]", CHECKER.verdict({nail: 1}, pinned))
    twice = cast("list[str]", CHECKER.verdict({nail: 1}, pinned))

    assert once and twice, "그대로 1인 둘째 판도 빨개야 한다"


def test_안_박힌_새_못을_잡는다() -> None:
    """**새 못이 기준선에 없으면 그 자리는 안 보는 자리다.** `--update`로 조인다."""
    problems = cast("list[str]", CHECKER.verdict({"새것.CEILING": 0}, {}))

    assert problems and "못에 없다" in problems[0]


def test_이사를_사라짐으로_안_읽는다() -> None:
    """**실측에서 거짓 경보가 나왔다** (GR-0.8 · D-0353).

    이력을 훑으니 `check_decisions.UNKNOWN_EVIDENCE`가 「사라졌다」로 떴는데
    `decision_evidence.py`로 **옮겨간 것**이었다. 키가 `모듈.상수`라서 이사가 사라짐으로
    보인다 — 같은 상수 이름이 다른 모듈에 있으면 **그 자리에서 값을 비교한다.**
    """
    before = {"check_decisions.UNKNOWN_EVIDENCE": 0}

    assert CHECKER.loosened(before, {"decision_evidence.UNKNOWN_EVIDENCE": 0}) == []
    assert CHECKER.loosened(before, {"decision_evidence.UNKNOWN_EVIDENCE": 3})
    assert CHECKER.loosened(before, {})


def test_이사가_아니면_사라짐이다() -> None:
    """**이름까지 같아야 이사다.** 아니면 지워진 것이고, 지워진 못은 사각지대다."""
    assert CHECKER.moved("a.CEILING", {"b.FLOOR": 0}) is None
    assert CHECKER.moved("a.CEILING", {"b.CEILING": 0}) == "b.CEILING"


def test_이력을_훑는_자가_있다() -> None:
    """**기준선을 지금 값에서 시작하면 이미 침식된 것을 모른다** (GR-0.5).

    실측: 내 미러 125판에서 `건너뛴 시험` 천장의 가장 조였던 값이 **2**였다. 부모만 보는
    검사는 그 열셋을 영원히 못 본다.
    """
    assert callable(CHECKER.tightest_in_history)
    # 이력 훑기는 느리다(125판에 70초). 여기서는 **기준선에 그 값이 들어왔는지**로 본다.
    assert CHECKER.BASELINE["deadcheck.CEILING[건너뛴 시험]"] >= 2


# ------------------------------------------------------------------ 기록을 요구한다


def test_조이는_쪽은_그냥_박힌다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**조이는 쪽을 막으면 아무도 안 조인다** (GR-0.8)."""
    fake = tmp_path / "check_ratchets.py"
    fake.write_text("BASELINE: dict[str, int] = {\n}\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "HERE", fake)
    monkeypatch.setattr(CHECKER, "BASELINE", {"deadcheck.CEILING[빈 그물]": 9})

    assert CHECKER.update() == 0
    assert '"deadcheck.CEILING[빈 그물]": 0,' in fake.read_text(encoding="utf-8")


def test_느슨한_쪽은_loosen_없이_안_박힌다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "check_ratchets.py"
    fake.write_text("BASELINE: dict[str, int] = {\n}\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "HERE", fake)
    monkeypatch.setattr(CHECKER, "BASELINE", {"deadcheck.CEILING[건너뛴 시험]": 0})

    assert CHECKER.update() == 1
    assert fake.read_text(encoding="utf-8") == "BASELINE: dict[str, int] = {\n}\n"


def test_내려_박으려면_기록이_같은_변경에_있어야_한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**규약을 화면에만 적으면 아무도 안 쓴다** (D-0126).

    `check_sight`가 *"`--loosen`에는 결정 기록이 필요하다"*고 적고 **아무도 안 썼다.**
    여기서는 기록이 같은 변경에 없으면 **안 박힌다.**
    """
    fake = tmp_path / "check_ratchets.py"
    fake.write_text("BASELINE: dict[str, int] = {\n}\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "HERE", fake)
    monkeypatch.setattr(CHECKER, "BASELINE", {"deadcheck.CEILING[건너뛴 시험]": 0})
    monkeypatch.setattr(CHECKER, "pending", lambda: {"tools/deadcheck.py"})

    assert CHECKER.update(allow_loosening=True) == 1

    monkeypatch.setattr(CHECKER, "pending", lambda: {CHECKER.PAST, "tools/deadcheck.py"})
    assert CHECKER.update(allow_loosening=True) == 0


def test_정본이_사라지면_터지지_않고_말한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
    fake = tmp_path / "check_ratchets.py"
    fake.write_text("# 블록이 없다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "HERE", fake)

    assert CHECKER.update() == 1


def test_표식_주석을_안_쓴다() -> None:
    """**첫 판이 제 표식에 걸려 상수 정의를 집어삼켰다** (D-0353).

    `# ---- 못 시작 ----` 꼴 표식을 쓰면 그 표식을 정의하는 `OPEN = "…"` 줄이 정규식에
    **먼저 걸린다** — `--update`가 파일을 문법 오류로 만들었다. `check_sight`가
    `PINNED = {`를 바로 겨누는 것이 그 이유다.
    """
    source = (ROOT / "tools" / "check_ratchets.py").read_text(encoding="utf-8")

    assert "BASELINE" in CHECKER.BLOCK.pattern, "블록 자신을 안 겨눈다"
    assert "----" not in CHECKER.BLOCK.pattern, "표식 주석을 쓰면 제 정의에 걸린다"
    assert len(CHECKER.BLOCK.findall(source)) == 1, "블록이 하나가 아니다"


def test_loosen만_주면_안_돈다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["check_ratchets.py", "--loosen"])

    assert CHECKER.main() == 1


def test_못을_하나도_안_읽으면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "measure", dict)

    problems, what = cast("tuple[list[str], str]", CHECKER.check())

    assert problems and "그물이 비었다" in problems[0]
    assert "못 쟀다" in what


# ------------------------------------------------------------------ 배선


@pytest.mark.parametrize("where", ["Makefile", ".githooks/pre-commit", ".github/workflows/ci.yml"])
def test_세_곳에_다_걸려_있다(where: str) -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126)."""
    assert "tools/check_ratchets.py" in (ROOT / where).read_text(encoding="utf-8")


# ------------------------------------------------- 배선 (심은 결함 · D-0353)


def test_기준선_대조가_check에_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**부품은 재고 배선은 안 쟀다 — 두 판 연속으로.**

    `make mutate WIRING=1`이 `check()`에서 `verdict(…)`를 끊어도 아무 시험이 안 운다고
    찍었다. D-0352에서 똑같이 물렸고 **기억이 아니라 기계가 잡아야 한다.**
    """
    monkeypatch.setattr(CHECKER, "verdict", lambda *_: ["심은 것"])

    problems, _ = cast("tuple[list[str], str]", CHECKER.check())

    assert "심은 것" in problems


def test_update가_main에_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "update", lambda **_: 7)
    monkeypatch.setattr("sys.argv", ["check_ratchets.py", "--update"])

    assert CHECKER.main() == 7


def test_화면이_센_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**통과 줄의 수가 거짓이면 사람이 0을 통과로 읽는다** (D-0230 · GR-0.5)."""
    monkeypatch.setattr("sys.argv", ["check_ratchets.py", "--check"])

    assert CHECKER.main() == 0
    printed = capsys.readouterr().out
    assert f"못 {len(CHECKER.measure())}개" in printed
    assert "못 0개" not in printed


def test_목록이_방향까지_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--list`가 **부류를 안 거치면** 방향이 전부 같은 값으로 찍힌다."""
    monkeypatch.setattr("sys.argv", ["check_ratchets.py", "--list"])

    assert CHECKER.main() == 0
    printed = capsys.readouterr().out
    assert "천장" in printed and "바닥" in printed
