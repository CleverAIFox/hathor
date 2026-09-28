"""푸시 파이프라인의 단위 검사 (D-0147).

**도구는 열다섯인데 파이프라인이 없었다.** 이 검사가 지키는 것은 순서가 코드에
있다는 것이다 — 사람 머리에 있으면 언젠가 하나를 빠뜨린다.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]

# **`ship.py`가 `tidy`를 임포트한다.** 이 줄이 없으면 이 파일만 따로 돌릴 때 수집에서
# 죽고, 전체를 돌릴 때는 *다른 시험이 먼저 넣어 준 덕에* 통과한다 — 순서에 기댄 초록이다.
# 병렬 실행은 순서를 안 지켜 준다 (D-0238 · D-0239).
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


def _module() -> ModuleType:
    """`tools/ship.py`. 싣는 자리는 `tests.conftest` 하나다 (D-0272)."""
    return tool_module("ship")


SHIP = _module()


# ------------------------------------------------------------------ 순서가 코드에 있다


def test_make_check를_부른다():
    """**중복 구현하지 않는다.** `make check`가 규약을 보고 `ship`은 내보낼 수 있는지 본다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"make", "check"' in source


def test_푸시와_교두보가_한_줄에_있다():
    """`make check && git push && make artifacts-push`가 머리에만 있었다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"git", "push"' in source
    assert "sync_artifacts.py" in source


def test_검사_없이는_안_밀어낸다():
    """`make check`가 빨가면 **그 자리에서 멈춘다.**"""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split('print(f"{DIM}── 규약')[1].split("── git")[0]
    assert "return 1" in body


# ------------------------------------------------------------------ 지우지 않는다


def test_찌꺼기를_세기만_한다():
    """**무엇이 쌓이는지 실측 안 하고 지우는 정책은 지어낸 규칙이다** (GR-0.5)."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split("def count_leftovers")[1].split("\ndef ")[0]
    assert "rm" not in body
    assert "unlink" not in body


def test_유물_목록이_비어_있지_않다():
    """`.backup/`과 `.o7-*/`는 D-0072가 없앤 것이다. **쌓여 있다면 소식이다.**"""
    assert ".backup" in SHIP.LEFTOVERS


def test_저장소에_유물이_없다():
    lines = SHIP.count_leftovers()
    assert not any("유물" in line for line in lines)


# ------------------------------------------------------------------ git


def test_워킹트리가_더러우면_막는다(monkeypatch):
    monkeypatch.setattr(SHIP, "_git", lambda *a: "M x.py" if a[0] == "status" else "origin/main")
    problems = SHIP.check_git()
    assert problems and "워킹트리" in problems[0]


def test_upstream이_없으면_막는다(monkeypatch):
    monkeypatch.setattr(SHIP, "_git", lambda *a: "")
    assert any("upstream" in line for line in SHIP.check_git())


def test_깨끗하면_안_막는다(monkeypatch):
    """**원격 읽기도 흉내낸다** (D-0283). 망 없는 기기에서 빨개지면 그 시험은 환경을 잰다."""
    monkeypatch.setattr(
        SHIP, "_git", lambda *a: "" if a[0] in ("status", "rev-list") else "origin/main"
    )
    monkeypatch.setattr(SHIP, "_run", lambda *a: (0, ""))
    assert SHIP.check_git() == []


def test_원격이_앞서면_막는다(monkeypatch):
    """**«미푸시 2개»를 찍고 곧바로 거절당한 자리다** (D-0283)."""
    monkeypatch.setattr(
        SHIP,
        "_git",
        lambda *a: "2" if a[0] == "rev-list" else ("" if a[0] == "status" else "origin/main"),
    )
    monkeypatch.setattr(SHIP, "_run", lambda *a: (0, ""))
    (problem,) = SHIP.check_git()
    assert "원격이 2개 앞선다" in problem and "pull --rebase" in problem


def test_원격을_못_읽으면_판정하지_않는다(monkeypatch):
    """**망이 없는 기기에서 «0개»라고 찍으면 그것이 거짓이다.**"""
    monkeypatch.setattr(SHIP, "_git", lambda *a: "" if a[0] == "status" else "origin/main")
    monkeypatch.setattr(SHIP, "_run", lambda *a: (1, "fatal: 못 붙었다"))
    (problem,) = SHIP.check_git()
    assert "원격을 못 읽었다" in problem


def test_check는_안_받는다():
    """`--check`를 달면 `make check` 사슬에 넣으라고 부류 검사가 요구한다 (D-0121).

    **`ship`은 `make check`를 부르는 쪽이라 사슬에 들어갈 수 없다.**
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert '"--check"' not in source


# ------------------------------------------------------------------ 세는 범위 (D-0148)


def test_venv를_안_센다():
    """첫 실측 449개 중 **대부분이 `.venv`였다.**

    **세는 수가 틀리면 그 수를 보고 한 행동도 틀린다.**
    """
    assert ".venv" in SHIP.OUTSIDE
    assert "var" in SHIP.OUTSIDE


def test_산출물은_찌꺼기가_아니다():
    """`var/`는 안 센다 (D-0067)."""
    lines = SHIP.count_leftovers()
    assert not any("var/" in line for line in lines)


def test_지우는_범위를_두_곳에_안_적는다():
    """**`--fix`는 `make clean`을 부른다.** 두 곳에 적으면 어긋난다."""
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source.split("if args.fix:")[1].split("print(")[0]
    assert '"make", "clean"' in body
    assert "rm" not in body


def test_clean이_venv를_지나친다():
    """D-0067이 *"`.venv/`는 남긴다"*고 적었는데 **`clean`은 안 지켰다.**"""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = makefile.split("clean:")[1].split("\nclean-all:")[0]
    assert "-prune" in body
    assert ".venv" in body


def test_교두보가_배를_가라앉히지_않는다():
    """**`git push`는 이미 끝났다** (D-0068 · D-0239).

    외장이 빠졌거나 DrvFs가 토라진 것으로 «내보내기 실패»를 찍으면, 사람은 무엇이
    밀려갔는지 모른 채 다시 친다. 실제로 `make ship`이 push 뒤에 역추적을 뿜고 죽었다.
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    assert "교두보로 못 보냈다" in source

    # **글자 자리가 아니라 동작을 본다** (D-0283). 문구를 상수로 빼자 옛 글자 검사가
    # 빨개졌는데 동작은 그대로였다 — 자리를 세던 검사였다.
    tail = source[source.index('sync_artifacts.py", "push"') :]
    assert "return 1" not in tail, "교두보 실패가 push를 «실패»로 만들면 안 된다"
    assert "return code" not in tail, "교두보 실패가 종료 코드를 잡으면 배가 가라앉는다"


def test_교두보로_평가_산출물도_보낸다() -> None:
    """**`keys`만 보내다 74건을 잃었다** (D-0253).

    D-0119가 개수를 줄이려 `keys`만 골랐고 `eval/`이 같이 빠졌다. 광인사가 죽을 때
    (D-0122) 옛 평가 산출물이 함께 사라졌고, 그래서 그 수치를 낸 명령을 못 찾는다.
    """
    assert "eval" in SHIP.DEFAULT_ONLY.split(",")
    assert "keys" in SHIP.DEFAULT_ONLY.split(",")


def test_세트를_쉼표로_나눠_넘긴다() -> None:
    """`sync_artifacts`는 `--only`를 여러 번 받는다. 한 덩이로 주면 아무것도 안 맞는다."""
    assert SHIP.only_flags("keys,eval") == ["--only", "keys", "--only", "eval"]
    assert SHIP.only_flags("keys") == ["--only", "keys"]
    assert SHIP.only_flags("") == []


def test_gh가_없어도_안_죽는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 명령을 `_run`에 넘기면 `FileNotFoundError`로 배가 가라앉는다** (D-0068).

    실측으로 확인했다 — `gh`가 없는 기기에서 `make ship`이 역추적을 뿜고 죽었다.
    """
    monkeypatch.setattr(SHIP.shutil, "which", lambda _name: None)

    (line,) = SHIP.ci_verdict()

    assert "gh" in line


def test_직전_커밋의_CI가_빨가면_그렇게_말한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**여덟 판을 빨간 CI 위에 쌓았다** (D-0254). 내보내기 전에 말한다."""
    monkeypatch.setattr(SHIP.shutil, "which", lambda _name: "/usr/bin/gh")
    runs = [
        {"conclusion": "failure", "name": "ci", "headSha": "abc"},
        {"conclusion": "success", "name": "proposal", "headSha": "abc"},
        {"conclusion": "failure", "name": "ci", "headSha": "older"},
    ]
    monkeypatch.setattr(SHIP, "_run", lambda *_args: (0, json.dumps(runs)))

    verdict = " ".join(SHIP.ci_verdict())

    assert "빨강" in verdict
    assert "ci" in verdict
    assert "proposal" not in verdict, "같은 커밋의 초록까지 빨갛다고 적지 않는다"


def test_옛_커밋의_실패는_안_센다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**직전 커밋을 본다.** 지난 실패까지 세면 고친 뒤에도 계속 빨갛다고 한다."""
    monkeypatch.setattr(SHIP.shutil, "which", lambda _name: "/usr/bin/gh")
    runs = [
        {"conclusion": "success", "name": "ci", "headSha": "new"},
        {"conclusion": "failure", "name": "ci", "headSha": "old"},
    ]
    monkeypatch.setattr(SHIP, "_run", lambda *_args: (0, json.dumps(runs)))

    assert "초록" in " ".join(SHIP.ci_verdict())


def test_모르는_결론은_빨강이다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**`failure`만 걸렀더니 `timed_out`이 초록으로 샜다** (D-0255).

    차단 목록은 모르는 값을 통과시킨다. GitHub가 결론 종류를 더하면 그때마다 사각이 는다.
    """
    monkeypatch.setattr(SHIP.shutil, "which", lambda _name: "/usr/bin/gh")
    runs = [{"conclusion": "timed_out", "name": "ci", "headSha": "abc"}]
    monkeypatch.setattr(SHIP, "_run", lambda *_args: (0, json.dumps(runs)))

    assert "빨강" in " ".join(SHIP.ci_verdict())


def test_건너뛴_것은_빨강이_아니다(monkeypatch: pytest.MonkeyPatch) -> None:
    """조건이 안 맞아 안 돈 잡까지 빨갛다고 하면 **사람이 그 줄을 안 믿게 된다.**"""
    monkeypatch.setattr(SHIP.shutil, "which", lambda _name: "/usr/bin/gh")
    runs = [{"conclusion": "skipped", "name": "gpu-smoke", "headSha": "abc"}]
    monkeypatch.setattr(SHIP, "_run", lambda *_args: (0, json.dumps(runs)))

    assert "초록" in " ".join(SHIP.ci_verdict())


# ------------------------------- 판정하면서 근거를 버리지 않는다 (D-0282)


def test_막혔을_때_꼬리를_보여_준다() -> None:
    """**«어느 단계»만 알려 주고 «어느 시험»은 안 알려 줬다** (D-0282).

    사용자가 `make check`를 초록으로 돌린 **바로 뒤** `make ship`에서 막혔고, 찍힌 것은
    마지막 한 줄뿐이었다.

        막힘  make[1]: *** [Makefile:74: test] Error 1

    그리고 안내가 *"`make check`를 먼저 초록으로 만든다"*였다 — **방금 초록이었으므로 그
    안내는 사람을 제자리에 세운다.**
    """
    text = "\n".join([f"줄 {number}" for number in range(100)] + ["FAILED tests/x.py::test_y"])
    lines = SHIP.blocked(text)

    assert "FAILED tests/x.py::test_y" in lines[0], "마지막 줄은 그대로 머리에 온다"
    body = "\n".join(lines)
    assert "줄 99" in body and "줄 71" in body, "꼬리 30줄이 있다"
    assert "줄 40" not in body, "전부 찍지는 않는다"
    assert "같은 명령이 여기서 빨갰다" in body


def test_출력이_없으면_한_줄로_끝낸다() -> None:
    """**없는 꼬리를 꾸며 내지 않는다.**"""
    assert any("출력이 없다" in line for line in SHIP.blocked(""))
    assert len(SHIP.blocked("한 줄뿐")) == 4


# ------------------------------- 실패는 전부 꼬리를 낸다 (D-0283)


def failure_branches() -> list[str]:
    """`code != 0`을 보고 **멈추거나 «막힘»을 찍으면서** 꼬리를 안 내는 자리.

    알리기만 하고 넘어가는 자리는 세지 않는다 — CI를 못 읽는 것과 교두보가 없는 것은
    **막힘이 아니라 소식이다** (D-0068 · D-0239).
    """
    import ast

    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.If):
            continue
        test = ast.unparse(node.test)
        if "code != 0" not in test:
            continue
        body = "\n".join(ast.unparse(one) for one in node.body)
        stops = "return 1" in body or "막힘" in body
        if stops and "blocked(" not in body:
            found.append(f"ship.py:{node.lineno} {test}")
    return found


def test_실패한_자리는_꼬리를_낸다() -> None:
    """**판정을 내면 근거를 같이 낸다** (D-0282 · D-0283).

    D-0282가 `make check` 한 자리만 고쳤고 **같은 꼴이 두 자리 남아 있었다** — `git push`와
    교두보 보내기다. 사용자가 그 다음 판에서 바로 `git push` 실패를 맞았고, 찍힌 것은 또
    한 줄이었다. **한 벌을 고칠 때 같은 꼴을 세지 않으면 그 자리가 다음 실패다** (D-0272).
    """
    assert failure_branches() == []


def test_원격을_읽고_판정한다() -> None:
    """**`git fetch` 없이 «미푸시 N개»를 찍으면 그 수는 마지막으로 읽은 원격 기준이다.**

    그 사이 원격이 움직이면 초록을 찍어 놓고 곧바로 거절당한다 (D-0283).
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")
    body = source[source.index("def check_git(") : source.index("def count_leftovers(")]

    assert '"fetch"' in body, "원격을 안 읽고 판정한다"
    assert "HEAD..@{upstream}" in body, "받을 것을 안 센다"
    assert "못 읽었다" in body, "못 읽었을 때 0으로 찍으면 거짓이다"


# --------------------------- 내보내는 자리가 어디까지 갔는지 말한다 (D-0287)


def test_마지막_결정_번호를_낸다():
    """**다음 판을 짜는 쪽이 「어디까지 붙었나」를 몰랐다** (D-0287).

    D-0283이 푸시까지 끝난 뒤 *"아직 안 붙었다"*는 지시가 나갔다. 사람은 그 지시를
    믿고 돌렸고 실패를 보고 **자기가 뭘 지웠나** 의심했다. 낡은 자료로 내린 판정이
    빨강보다 나쁘다는 것을 D-0283이 적었고, 이번에는 그 낡은 자료가 사람 머릿속에 있었다.
    """
    line = SHIP.last_decision()
    assert re.fullmatch(r"D-\d{4} · 총 \d+건", line), line


def test_대장이_비면_그렇게_말한다(monkeypatch, tmp_path):
    """**«없다»와 «0건»을 가르지 못하면 빈 대장이 조용히 지나간다** (D-0230)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text("# 결정 기록\n", encoding="utf-8")
    monkeypatch.setattr(SHIP, "ROOT", tmp_path)
    assert SHIP.last_decision() == "(없다)"


def test_main이_그_줄을_찍는다():
    """**강제자다.** 재기만 하고 안 찍으면 이 관문은 아무 일도 안 한다.

    **글자가 어디 있는지 보지 않는다** — D-0283에서 그렇게 틀렸다. `main` 안에서
    `last_decision`이 **불리는가**를 `ast`로 본다.
    """
    source = Path(str(SHIP.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    (main,) = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    called = {
        node.func.id
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "last_decision" in called


# ------------------------------ 꼬리가 이유를 들고 있는가 (D-0289)


def _coverage_noise(rows: int = 140) -> str:
    """사용자가 실제로 맞은 꼴 — 커버리지 표가 꼬리를 통째로 먹는다."""
    body = "\n".join(
        f"hathor/x{index}.py    {index}   {index}   9{index % 10}%" for index in range(rows)
    )
    return (
        "==================== tests coverage ====================\n"
        "Name                                 Stmts   Miss  Cover\n"
        "--------------------------------------------------------\n"
        f"{body}\n"
        "--------------------------------------------------------\n"
        "TOTAL                                 7526    858    89%\n"
        "Required test coverage of 87.0% reached. Total coverage: 88.60%\n"
    )


def test_터진_자리부터_낸다():
    """**이름은 줬는데 이유를 못 줬다** (D-0289).

    D-0282가 한 줄에서 30줄로 늘렸는데, 그 30줄이 **전부 커버리지 표**였다. 사용자는
    «어느 시험»만 받고 «왜»는 못 받았다 — 고치려면 같은 명령을 한 번 더 돌려야 한다.
    """
    text = (
        _coverage_noise()
        + "=================================== FAILURES ===================================\n"
        "______________________ test_무언가 ______________________\n"
        "E   torch.OutOfMemoryError: CUDA out of memory.\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/unit/test_x.py::test_무언가\n"
        "make[1]: *** [Makefile:77: test] Error 1"
    )
    printed = "\n".join(SHIP.blocked(text))

    assert "OutOfMemoryError" in printed, "이유가 빠졌다"
    assert "FAILURES" in printed
    assert "hathor/x0.py" not in printed, "커버리지 표가 아직 꼬리를 먹는다"


def test_터진_표식이_없으면_잡음만_뺀다():
    """**꼬리가 그대로 쓸모 있을 때가 있다** — `ruff`·`mypy`는 FAILURES를 안 찍는다."""
    text = _coverage_noise(3) + "tools/x.py:1: error: 무언가\nmake: *** Error 1"
    printed = "\n".join(SHIP.blocked(text))

    assert "error: 무언가" in printed
    assert "hathor/x0.py" not in printed


def test_출력이_한_줄이면_그_줄을_낸다():
    printed = "\n".join(SHIP.blocked("Error 1"))
    assert "Error 1" in printed
