"""**부품은 재고 배선은 안 쟀다** — 검사 묶음 (D-0359).

`deadcheck` 여덟 · `check_issue_mentions` 일곱 · `step0_check` 여섯 · `sync_artifacts` 여섯.
작은 함수를 **직접** 부르는 시험만 있으면 `main()`에서 그 줄을 지워도 아무도 안 운다.

**이 묶음이 가장 위험하다.** `deadcheck`는 *«검사가 죽었는가»*를 보는 검사고,
`check_issue_mentions`는 *«아무도 안 세는 번호»*를 보는 검사다 — 그 둘의 배선이 끊기면
**그물을 보는 그물이 비는 것이다** (D-0230).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.conftest import tool_module

DEAD = tool_module("deadcheck")
ISSUES = tool_module("check_issue_mentions")
STEP0 = tool_module("step0_check")
SYNC = tool_module("sync_artifacts")

PLANTED = "심은 문제"


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


# ------------------------------------------------------------------ deadcheck


@pytest.fixture
def dead_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """프로브를 다 막는다. **진짜로 훑으면 한 판에 수십 초다** (D-0129)."""
    monkeypatch.setattr(DEAD, "too_old", lambda: "")
    monkeypatch.setattr(DEAD, "unreadable", list)
    monkeypatch.setattr(DEAD, "survey", list)


def test_파이썬이_낮으면_아무_수도_안_낸다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**낮은 파이썬에서 «0건»은 거짓이다** (D-0275). `too_old()`를 안 거치면 0을 찍는다."""
    monkeypatch.setattr(DEAD, "too_old", lambda: PLANTED)
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--ratchet"])

    assert DEAD.main() == 1
    assert PLANTED in _spoke(capsys)


def test_못_읽은_파일이_있으면_수를_믿지_말라고_한다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**덜 센 것을 통과로 적지 않는다** (GR-0.5)."""
    monkeypatch.setattr(DEAD, "unreadable", lambda: [PLANTED])
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--ratchet"])

    assert DEAD.main() == 1
    spoke = _spoke(capsys)
    assert PLANTED in spoke and "덜 센 것" in spoke


def test_양성_대조가_프로브를_본다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함에 안 우는 프로브** (D-0069). `positive_control()`을 안 거치면 늘 통과다."""
    monkeypatch.setattr(DEAD, "positive_control", lambda: [PLANTED])
    monkeypatch.setattr(DEAD, "planted_unreadable", lambda: True)
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--selftest"])

    assert DEAD.main() == 1
    assert PLANTED in _spoke(capsys)


def test_양성_대조가_못_읽는_파일도_본다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`planted_unreadable()` 자리. **못 읽는 파일을 심었는데 조용하면** 그쪽 눈이 멀었다."""
    monkeypatch.setattr(DEAD, "positive_control", list)
    monkeypatch.setattr(DEAD, "planted_unreadable", lambda: True)
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--selftest"])

    assert DEAD.main() == 0
    assert "양성 대조 통과" in _spoke(capsys)

    monkeypatch.setattr(DEAD, "planted_unreadable", lambda: False)
    assert DEAD.main() == 1
    assert "조용하다" in _spoke(capsys)


def test_훑은_것을_세어_화면에_올린다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`survey()` → `counted()` 두 자리. **수가 화면에 없으면 0인 것도 모른다** (D-0230)."""
    hit = DEAD.Hit(probe="무검증 시험", where="어딘가:1", what="심은 것")
    monkeypatch.setattr(DEAD, "survey", lambda: [hit])
    monkeypatch.setattr("sys.argv", ["deadcheck.py"])

    assert DEAD.main() == 0
    spoke = _spoke(capsys)
    assert "어딘가:1" in spoke, "survey()가 끊겼다"
    assert "무검증 시험 1" in spoke, "counted()가 끊겼다"


def test_판정이_배선돼_있다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(DEAD, "verdict", lambda *_: [PLANTED])
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--ratchet"])

    assert DEAD.main() == 1
    assert PLANTED in _spoke(capsys)


def test_update가_천장을_실제로_고친다(
    dead_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`update()`를 안 거치면 **「천장을 맞췄다」만 찍고 아무것도 안 고친다.**"""
    wrote: list[tuple[dict[str, int], Path]] = []
    monkeypatch.setattr(DEAD, "update", lambda seen, path: wrote.append((seen, path)))
    monkeypatch.setattr("sys.argv", ["deadcheck.py", "--update"])

    assert DEAD.main() == 0
    assert len(wrote) == 1, "천장을 안 고쳤다"
    assert wrote[0][1].name == "deadcheck.py"


# ------------------------------------------------------------------ check_issue_mentions


@pytest.fixture
def issues_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ISSUES, "targets", lambda: [Path("가짜.md"), Path("가짜.py")])
    monkeypatch.setattr(ISSUES, "shortfall", lambda _: [])
    monkeypatch.setattr(ISSUES, "census", lambda *_: [])
    monkeypatch.setattr(ISSUES, "check", lambda *_: [])
    # **번호를 글자로 적지 않는다.** 이 저장소의 `O-\d+`는 전부 실물로 읽힌다
    # (`check_issue_mentions`) — 시험의 가짜 번호가 「닫힌 질문을 맨몸으로 적었다」로
    # 잡힌다. 끼워 넣어 만들면 원문에 그 모양이 없다.
    monkeypatch.setattr(ISSUES, "closed_issues", lambda _: {f"O-{1}": {19}, f"O-{2}": {20}})
    monkeypatch.setattr(ISSUES, "open_issues", lambda _: {f"O-{3}", f"O-{4}", f"O-{5}"})


def test_통과줄이_두_표와_시야를_다_말한다(
    issues_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """네 자리를 한 줄이 떠받친다 — `targets` · `closed_issues` · `open_issues`.

    **「닫힘 42 · 열림 30」은 표의 수이지 읽은 파일 수가 아니다** (D-0349). 그래서
    훑은 수까지 같은 줄에 찍는다.
    """
    monkeypatch.setattr("sys.argv", ["check_issue_mentions.py", "--check"])

    assert ISSUES.main() == 0
    spoke = _spoke(capsys)
    assert "닫힘 2건" in spoke and "열림 3건" in spoke
    assert "훑은 것 2개(문서 1)" in spoke


def test_list가_닫힘표를_찍는다(
    issues_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["check_issue_mentions.py", "--list"])

    assert ISSUES.main() == 0
    spoke = _spoke(capsys)
    assert f"O-{1}" in spoke and "D-0019" in spoke


def test_시야가_바닥_밑이면_막는다(
    issues_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`shortfall()` 자리. **`SKIP_TREES` 하나가 비면서 문서를 한 줄도 안 봤다** (D-0349)."""
    monkeypatch.setattr(ISSUES, "shortfall", lambda _: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_issue_mentions.py", "--check"])

    assert ISSUES.main() == 1
    spoke = _spoke(capsys)
    assert PLANTED in spoke and "바닥 밑" in spoke


def test_번호_전수가_배선돼_있다(
    issues_quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`census()` 자리. **고아 번호는 아무도 안 부르니 코드만 보면 안 걸린다** (D-0126)."""
    monkeypatch.setattr(ISSUES, "census", lambda *_: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_issue_mentions.py", "--check"])

    assert ISSUES.main() == 1
    assert PLANTED in _spoke(capsys)


def test_고아_판정이_열린표를_거친다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`check()` 안의 `open_issues()` 자리 — **두 표 어디에도 없는 번호** (D-0183 · D-0349).

    이 자리를 끊으면 `living`이 비고, 빈 열린표는 **「아직 못 읽었다」로 읽혀** 고아
    판정이 통째로 꺼진다. **네 번호가 27자리에서 조용히 불리고 있던** 그 꼴이다 (D-0183).
    """
    orphan = f"O-{99}"
    where = tmp_path / "어딘가.py"
    where.write_text(f"# {orphan}를 부른다\n", encoding="utf-8")
    closed = f"{ISSUES.CLOSED_BEGIN}\n| O-{1} | D-0019 |\n{ISSUES.CLOSED_END}"
    opened = f"{ISSUES.OPEN_BEGIN}\n| O-{3} | 살아 있다 |\n{ISSUES.OPEN_END}"
    monkeypatch.setattr(ISSUES, "targets", lambda: [where])
    monkeypatch.setattr(ISSUES, "ROOT", tmp_path)

    problems = ISSUES.check(closed, opened)

    assert len(problems) == 1, f"고아를 못 봤다: {problems}"
    assert orphan in problems[0] and "열린표에도 닫힘표에도 없다" in problems[0]

    # **열린표가 비면 판정을 하지 않는다** — 못 읽은 것을 고아라 하지 않는다 (GR-0.5).
    assert ISSUES.check(closed, "") == []


# ------------------------------------------------------------------ step0_check


@pytest.fixture
def step0_quiet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """**바깥을 안 본다.** `nvidia-smi`도 `pip`도 시험에서 부르지 않는다."""
    where = tmp_path / "보고서.json"
    monkeypatch.setattr(STEP0, "REPORT_PATH", where)
    monkeypatch.setattr(STEP0, "check_system", lambda: {"심은": "기기"})
    monkeypatch.setattr(STEP0, "check_gpu", lambda: {"심은": "그래픽"})
    monkeypatch.setattr(STEP0, "check_python_env", lambda: {"심은": "파이썬"})
    return where


def test_세_절이_보고서에_그대로_들어간다(
    step0_quiet: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**이 보고서를 그대로 붙여넣어 다음 단계를 정한다** — 한 절이 비면 그 판단이 빈다."""
    monkeypatch.setattr("sys.argv", ["step0_check.py"])

    STEP0.main()

    report = json.loads(step0_quiet.read_text(encoding="utf-8"))
    assert report["system"] == {"심은": "기기"}
    assert report["gpu"] == {"심은": "그래픽"}
    assert report["python_env"] == {"심은": "파이썬"}
    assert report["library"] == {"skipped": True}


def test_경로를_주면_라이브러리를_훑는다(
    step0_quiet: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[Path] = []

    def planted(root: Path) -> dict[str, object]:
        seen.append(root)
        return {"심은": "음원"}

    monkeypatch.setattr(STEP0, "scan_library", planted)
    monkeypatch.setattr("sys.argv", ["step0_check.py", "/심은/경로"])

    STEP0.main()

    assert json.loads(step0_quiet.read_text(encoding="utf-8"))["library"] == {"심은": "음원"}
    assert seen == [Path("/심은/경로")]


def test_구분줄이_두_자리에_다_있다(
    step0_quiet: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hr()` 두 자리. **제목이 없으면 네 절이 한 덩어리로 흐른다** — 사람이 못 읽는다."""
    monkeypatch.setattr("sys.argv", ["step0_check.py"])

    STEP0.main()

    spoke = _spoke(capsys)
    assert "음원 라이브러리 스캔" in spoke, "건너뜀 절의 제목이 없다"
    assert "완료" in spoke, "끝 절의 제목이 없다"


# ------------------------------------------------------------------ sync_artifacts


def test_교두보_경로를_환경에서_읽는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`store_root()` 자리. **`--store`가 없으면 `.env`가 정본이다** (D-0118)."""
    seen: list[object] = []
    monkeypatch.setattr(SYNC, "store_root", lambda: tmp_path / "심은교두보")

    def noted(local: Path, store: Path | None) -> int:
        seen.append(store)
        return 0

    monkeypatch.setattr(SYNC, "status", noted)
    monkeypatch.setattr("sys.argv", ["sync_artifacts.py", "status"])

    assert SYNC.main() == 0
    assert seen == [tmp_path / "심은교두보"]


def test_status와_verify의_수가_그대로_나간다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**종료코드가 호출자의 판정이다.** 안 돌려주면 `ship`이 실패를 통과로 읽는다."""
    monkeypatch.setattr(SYNC, "status", lambda *_: 7)
    monkeypatch.setattr("sys.argv", ["sync_artifacts.py", "status", "--store", str(tmp_path)])
    assert SYNC.main() == 7

    full: list[bool] = []

    def noted(local: Path, store: Path | None, deep: bool) -> int:
        full.append(deep)
        return 9

    monkeypatch.setattr(SYNC, "verify", noted)
    monkeypatch.setattr(
        "sys.argv", ["sync_artifacts.py", "verify", "--store", str(tmp_path), "--full"]
    )
    assert SYNC.main() == 9
    assert full == [True], "`--full`이 verify에 안 닿는다"


def test_쓰기_전에_교두보를_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`probe()` 자리 (D-0119). **D-0118은 17192개 목록을 다 찍은 뒤 첫 복사에서 죽었다.**"""
    monkeypatch.setattr(SYNC, "probe", lambda _: (SYNC.MISSING, PLANTED))
    monkeypatch.setattr(SYNC, "transfer", lambda *_, **__: 0)
    monkeypatch.setattr("sys.argv", ["sync_artifacts.py", "push", "--store", str(tmp_path)])

    assert SYNC.main() == 2, "교두보를 못 쓰는데 옮기러 갔다"
    assert PLANTED in _spoke(capsys)


def test_두_방향이_각각_배선돼_있다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`transfer()` 두 자리. **방향이 뒤집히면 산출물을 덮어쓴다.**"""
    moved: list[tuple[str, str]] = []

    def planted(source: Path, target: Path, label: str, *_: object, **__: object) -> int:
        moved.append((label, source.name))
        return 4

    monkeypatch.setattr(SYNC, "probe", lambda _: (SYNC.ATTACHED, ""))
    monkeypatch.setattr(SYNC, "transfer", planted)

    monkeypatch.setattr("sys.argv", ["sync_artifacts.py", "push", "--store", str(tmp_path)])
    assert SYNC.main() == 4
    monkeypatch.setattr("sys.argv", ["sync_artifacts.py", "pull", "--store", str(tmp_path)])
    assert SYNC.main() == 4

    assert [label for label, _ in moved] == ["보냄", "가져옴"]
    assert subprocess is not None
