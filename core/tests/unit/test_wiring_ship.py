"""**부품은 재고 배선은 안 쟀다** — 내보내기 쪽 (D-0359).

`make mutate WIRING=1`이 `ship` 열 곳 · `tidy` 네 곳 · `check_coverage` 여섯 곳을 세었다.
작은 검사를 **직접** 부르는 시험만 있으면 `main()`에서 그 줄을 지워도 아무도 안 운다.

`ship.main()`은 `make check`을 부른다 — **`_run`을 쥐어야 시험이 돈다.** 그 `_run` 자체도
배선 중 하나라, 쥐는 행위가 곧 그 자리를 세우는 일이다.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
SHIP = tool_module("ship")
TIDY = tool_module("tidy")
COVERAGE = tool_module("check_coverage")

PLANTED = "심은 문제"


@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """바깥 명령을 전부 막는다. **`make check`을 시험에서 돌릴 수는 없다.**"""
    monkeypatch.setattr(SHIP, "_run", lambda *_: (0, ""))
    monkeypatch.setattr(SHIP, "_git", lambda *_: "0")
    monkeypatch.setattr(SHIP, "check_git", list)
    monkeypatch.setattr(SHIP, "payable_debts", list)
    monkeypatch.setattr(SHIP, "_recent_runs", list)
    monkeypatch.setattr(SHIP, "ci_verdict", lambda _: [])
    monkeypatch.setattr(SHIP, "bot_verdict", lambda _: [])
    monkeypatch.setattr(SHIP, "count_leftovers", list)
    monkeypatch.setattr("sys.argv", ["ship.py"])


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


# ------------------------------------------------------------------ ship


@pytest.mark.parametrize("part", ["payable_debts", "ci_verdict", "bot_verdict", "count_leftovers"])
def test_절_넷이_배선돼_있다(
    part: str,
    quiet: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """**화면의 한 절이 통째로 사라져도 종료코드는 0이다** — 수가 안 보일 뿐이다."""
    monkeypatch.setattr(SHIP, part, lambda *_: [PLANTED])

    assert SHIP.main() == 0
    assert PLANTED in _spoke(capsys)


def test_git이_막으면_밀지_않는다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**찍기만 하고 `git push`를 쳤던 자리다** (D-0283). 사람은 빨간 줄을 두 번 봤다."""
    monkeypatch.setattr(SHIP, "check_git", lambda: [PLANTED])
    monkeypatch.setattr("sys.argv", ["ship.py", "--push"])

    assert SHIP.main() == 1
    spoke = _spoke(capsys)
    assert PLANTED in spoke and "밀지 않았다" in spoke


def test_미푸시_수를_git에게_묻는다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(SHIP, "_git", lambda *_: "7")

    assert SHIP.main() == 0
    assert "미푸시 커밋 7개" in _spoke(capsys)


def test_최근_실행을_한_번_읽어_둘에_넘긴다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**`gh`를 두 번 부르면 그 사이 목록이 바뀌어 두 절이 모순된 화면을 낸다.**"""
    monkeypatch.setattr(SHIP, "_recent_runs", lambda: ["심은 실행"])
    monkeypatch.setattr(SHIP, "ci_verdict", lambda runs: [f"CI {runs}"])
    monkeypatch.setattr(SHIP, "bot_verdict", lambda runs: [f"봇 {runs}"])

    assert SHIP.main() == 0
    spoke = _spoke(capsys)
    assert "CI ['심은 실행']" in spoke and "봇 ['심은 실행']" in spoke


def test_규약이_막으면_까닭을_찍는다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`blocked()`를 안 거치면 **왜 막혔는지 없이 1만 돌려준다.**"""
    monkeypatch.setattr(SHIP, "_run", lambda *_: (1, "터진 까닭"))
    monkeypatch.setattr(SHIP, "blocked", lambda *_, **__: [PLANTED])

    assert SHIP.main() == 1
    assert PLANTED in _spoke(capsys)


def test_산출물_절이_바깥_명령을_거친다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_run`을 끊으면 **대장 줄이 통째로 사라진다** — 「네 판 연속 틀린 채 내보냈다」의 자리."""
    monkeypatch.setattr(
        SHIP,
        "_run",
        lambda *cmd: (
            0,
            "정상 20 · 결손 0" if any("check_artifacts" in one for one in cmd) else "",
        ),
    )

    assert SHIP.main() == 0
    assert "대장 정상 20" in _spoke(capsys)


def test_교두보_세트를_only_flags로_만든다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--push`에서만 쓰인다. **안 거치면 세트 선택이 조용히 사라진다** (D-0119)."""
    seen: list[list[str]] = []

    def spy(*command: str) -> tuple[int, str]:
        seen.append(list(command))
        return 0, ""

    monkeypatch.setattr(SHIP, "_run", spy)
    monkeypatch.setattr(SHIP, "only_flags", lambda raw: ["--심은", raw])
    monkeypatch.setattr("sys.argv", ["ship.py", "--push", "--only", "keys"])

    assert SHIP.main() == 0
    assert any("--심은" in one and "keys" in one for one in seen)


# ------------------------------------------------------------------ tidy


def test_찌꺼기가_없으면_깨끗하다고_한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(TIDY, "survey", list)
    monkeypatch.setattr("sys.argv", ["tidy.py"])

    assert TIDY.main() == 0
    assert "깨끗하다" in _spoke(capsys)


def test_찾은_것을_report로_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`report()`를 안 거치면 **무엇이 쌓였는지 안 나온다** — 수만 나온다."""
    monkeypatch.setattr(TIDY, "survey", lambda: ["심은 찌꺼기"])
    monkeypatch.setattr(TIDY, "report", lambda found: [f"{PLANTED} {len(found)}"])
    monkeypatch.setattr("sys.argv", ["tidy.py"])

    assert TIDY.main() == 0
    assert f"{PLANTED} 1" in _spoke(capsys)


def test_YES가_있어야_sweep을_부른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**`tidy`는 기본이 세기만이다** (D-0225). 치우는 것은 따로 말한다."""
    swept: list[object] = []
    only_one = SimpleNamespace(kind="심은 찌꺼기")
    monkeypatch.setattr(TIDY, "survey", lambda: [only_one])
    monkeypatch.setattr(TIDY, "report", lambda _: ["한 줄"])
    monkeypatch.setattr(TIDY, "git", lambda *_: [])
    monkeypatch.setattr(TIDY, "sweep", swept.append)

    monkeypatch.setattr("sys.argv", ["tidy.py"])
    assert TIDY.main() == 0
    assert swept == [], "YES 없이 치웠다"

    monkeypatch.setattr("sys.argv", ["tidy.py", "--yes"])
    assert TIDY.main() == 0
    assert swept == [only_one], "YES를 줬는데 안 치웠다"


def test_하나가_막혀도_나머지를_치운다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**첫 실패에서 멈추지 않는다.**"""
    blocked_one = SimpleNamespace(kind="막힌 것")
    good_one = SimpleNamespace(kind="되는 것")
    done: list[object] = []

    def flaky(finding: SimpleNamespace) -> None:
        if finding.kind == "막힌 것":
            raise OSError("막혔다")
        done.append(finding)

    monkeypatch.setattr(TIDY, "survey", lambda: [blocked_one, good_one])
    monkeypatch.setattr(TIDY, "report", lambda _: ["두 줄"])
    monkeypatch.setattr(TIDY, "git", lambda *_: [])
    monkeypatch.setattr(TIDY, "sweep", flaky)
    monkeypatch.setattr("sys.argv", ["tidy.py", "--yes"])

    assert TIDY.main() == 1
    assert done == [good_one]
    assert "실패 1" in _spoke(capsys)


# ------------------------------------------------------------------ check_coverage


def test_바닥과_실측을_둘_다_읽는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**둘 중 하나만 읽으면 비교가 아니다.**"""
    monkeypatch.setattr(COVERAGE, "floor", lambda _: 20.0)
    monkeypatch.setattr(COVERAGE, "measured", lambda: 22.0)
    monkeypatch.setattr("sys.argv", ["check_coverage.py"])

    assert COVERAGE.main() == 0
    spoke = _spoke(capsys)
    assert "22.00%" in spoke and "20%" in spoke


def test_판정이_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(COVERAGE, "floor", lambda _: 20.0)
    monkeypatch.setattr(COVERAGE, "measured", lambda: 22.0)
    monkeypatch.setattr(COVERAGE, "verdict", lambda *_: PLANTED)
    monkeypatch.setattr("sys.argv", ["check_coverage.py"])

    assert COVERAGE.main() == 1
    assert PLANTED in _spoke(capsys)


def test_도구가_죽으면_2를_낸다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 쟀으면 통과가 아니다** (GR-0.5). 0도 1도 아닌 2다."""

    def dead(_: str) -> float:
        raise LookupError("못 읽었다")

    monkeypatch.setattr(COVERAGE, "floor", dead)
    monkeypatch.setattr("sys.argv", ["check_coverage.py"])

    assert COVERAGE.main() == 2
    assert "죽었다" in _spoke(capsys)


def test_update가_bumped를_거친다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**`bumped()`를 안 거치면 바닥이 안 올라간다** — 「올렸다」만 찍힌다."""
    fake = tmp_path / "pyproject.toml"
    fake.write_text("fail_under = 10\n", encoding="utf-8")
    monkeypatch.setattr(COVERAGE, "PYPROJECT", fake)
    monkeypatch.setattr(COVERAGE, "measured", lambda: 90.0)
    monkeypatch.setattr(COVERAGE, "bumped", lambda text, actual: "fail_under = 89\n")
    monkeypatch.setattr("sys.argv", ["check_coverage.py", "--update"])

    assert COVERAGE.main() == 0
    assert fake.read_text(encoding="utf-8") == "fail_under = 89\n"


def test_update가_바닥을_안_내린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**래칫은 조이는 쪽으로만** (D-0223)."""
    fake = tmp_path / "pyproject.toml"
    fake.write_text("fail_under = 87\n", encoding="utf-8")
    monkeypatch.setattr(COVERAGE, "PYPROJECT", fake)
    monkeypatch.setattr(COVERAGE, "measured", lambda: 50.0)
    monkeypatch.setattr("sys.argv", ["check_coverage.py", "--update"])

    assert COVERAGE.main() == 0
    assert fake.read_text(encoding="utf-8") == "fail_under = 87\n"
    assert "내리지 않는다" in _spoke(capsys)


# ------------------------------------------------------------------ 두 번째 판


def test_교두보가_막혀도_배는_안_가라앉지만_까닭은_찍는다(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**`git push`는 이미 끝났다** (D-0068 · D-0239) — 0을 낸다. 그래도 **왜 막혔는지는 찍는다.**

    이 자리의 `blocked()`는 종료코드를 안 바꾼다. 그래서 **코드만 보는 시험은 못 잡는다.**
    """
    monkeypatch.setattr(
        SHIP,
        "_run",
        lambda *cmd: (1, "드라이브 빠졌다") if "push" in cmd and "git" not in cmd else (0, ""),
    )
    monkeypatch.setattr(SHIP, "blocked", lambda *_, **__: [PLANTED])
    monkeypatch.setattr("sys.argv", ["ship.py", "--push"])

    assert SHIP.main() == 0, "교두보가 배를 가라앉혔다 (D-0068)"
    assert PLANTED in _spoke(capsys)


def test_origin이_있으면_치우기_전에_prune한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**남의 저장소에서 지워진 가지를 내 쪽에서 「쌓였다」로 센다.**

    `git("remote")`를 안 거치면 `origin`이 없는 기기에서 `fetch`가 터지고, 거치고도 안
    부르면 **없는 가지를 치우라고 적는다.** 두 방향 다 본다.
    """
    import subprocess

    ran: list[list[str]] = []
    monkeypatch.setattr(TIDY, "survey", lambda: [SimpleNamespace(kind="심은 찌꺼기")])
    monkeypatch.setattr(TIDY, "report", lambda _: ["한 줄"])
    monkeypatch.setattr(TIDY, "sweep", lambda _: None)

    def noted(command: list[str], **_: object) -> SimpleNamespace:
        ran.append(list(command))
        return SimpleNamespace()

    monkeypatch.setattr(subprocess, "run", noted)
    monkeypatch.setattr("sys.argv", ["tidy.py", "--yes"])

    monkeypatch.setattr(TIDY, "git", lambda *_: ["origin"])
    assert TIDY.main() == 0
    assert any("--prune" in one for one in ran), "origin이 있는데 prune을 안 했다"

    ran.clear()
    monkeypatch.setattr(TIDY, "git", lambda *_: [])
    assert TIDY.main() == 0
    assert ran == [], "origin이 없는데 fetch를 쳤다"
