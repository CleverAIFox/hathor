"""변이 도구의 단위 검사 (D-0353).

**판정하는 자리가 판정당하지 않고 있었다.** `mutate_gate`는 다른 도구를 망가뜨려 시험이
우는지 보는데, **저 자신에게는 시험이 없었다** — 그리고 첫 배선 모드가 **거짓 빨강**을
냈다. `ast.unparse`로 파일을 통째로 다시 쓰니 소스를 읽는 시험이 변이와 무관하게 터졌고,
`check_ratchets`의 배선 다섯이 전부 「울었다」로 나왔다. 손으로 잰 것과 어긋나서 알았다.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
TOOL = tool_module("mutate_gate")

SAMPLE = '''\
"""문서 문자열은 그대로 남아야 한다."""


def gather() -> list[str]:
    return []


def helper() -> int:
    return 1


def check() -> list[str]:
    # 주석도 그대로 남아야 한다
    problems = gather()
    return problems


def main() -> int:
    return len(check())
'''


# ------------------------------------------------------------------ 배선 읽기


def test_입구에서_부르는_제_함수를_읽는다() -> None:
    found = cast("list[tuple[int, str]]", TOOL.wiring(ast.parse(SAMPLE)))

    assert [name for _, name in found] == ["gather"]


def test_입구_자신은_안_센다() -> None:
    """`main()`이 `check()`를 부르는 것은 배선이 아니라 **입구끼리**다."""
    found = cast("list[tuple[int, str]]", TOOL.wiring(ast.parse(SAMPLE)))

    assert "check" not in [name for _, name in found]


def test_남의_함수는_안_센다() -> None:
    text = "import os\n\n\ndef check() -> int:\n    return len(os.listdir('.'))\n"

    assert cast("list[tuple[int, str]]", TOOL.wiring(ast.parse(text))) == []


# ------------------------------------------------------------------ 자르기 (카나리아)


def test_글자_단위로_자른다() -> None:
    """**첫 판은 `ast.unparse`로 파일을 다시 썼다** (D-0353).

    그러면 주석과 줄 나눔이 통째로 바뀌고 **소스를 읽는 시험이 변이와 무관하게 터진다.**
    실측: 그 탓에 배선 다섯이 거짓으로 「울었다」가 됐고 **메울 자리가 가려졌다.**
    """
    line, name = cast("list[tuple[int, str]]", TOOL.wiring(ast.parse(SAMPLE)))[0]
    maimed = cast("str | None", TOOL.cut(SAMPLE, line, name))

    assert maimed is not None
    changed = [
        (a, b) for a, b in zip(SAMPLE.splitlines(), maimed.splitlines(), strict=True) if a != b
    ]
    assert len(changed) == 1, changed
    assert "주석도 그대로 남아야 한다" in maimed
    assert "문서 문자열은 그대로 남아야 한다" in maimed


def test_자른_자리가_빈_목록이_된다() -> None:
    line, name = cast("list[tuple[int, str]]", TOOL.wiring(ast.parse(SAMPLE)))[0]
    maimed = cast("str", TOOL.cut(SAMPLE, line, name))

    assert "problems = []" in maimed
    ast.parse(maimed)


def test_없는_호출은_None이다() -> None:
    assert TOOL.cut(SAMPLE, 1, "없는함수") is None


# ------------------------------------------------------------------ 천장


def test_천장이_실측과_같은_꼴이다() -> None:
    """**이 수는 내려가기만 한다** (D-0257 · D-0353). `check_ratchets`가 못으로 들고 있다."""
    ratchets = tool_module("check_ratchets")

    assert TOOL.WIRING_CEILING >= 0
    assert ratchets.BASELINE["mutate_gate.WIRING_CEILING"] == TOOL.WIRING_CEILING


def test_여는_시험을_찾는다() -> None:
    found = cast("list[str]", TOOL.tests_for("check_ratchets"))

    assert any("test_ratchets.py" in one for one in found)


def test_관문_도구를_실제로_읽는다() -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    tools = cast("list[str]", TOOL.invoked_tools())

    assert len(tools) >= 25, tools
    assert "check_ratchets" in tools and "check_patch" in tools


@pytest.mark.parametrize("mode", ["", "WIRING"])
def test_두_모드가_다_걸려_있다(mode: str) -> None:
    """**모드를 만들고 안 걸면 아무도 안 쓴다** (D-0126)."""
    made = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "tools/mutate_gate.py" in made
    assert not mode or mode in made


# ------------------------------------------------- 빨간 이름으로 센다 (D-0357)


def test_빨간_시험의_이름을_읽는다(tmp_path: Path) -> None:
    """**종료코드 하나로는 「내 탓」과 「원래 빨갰다」가 안 갈린다** (D-0356 → D-0357).

    실측으로 생존자가 **53 ↔ 92**로 흔들렸고 53이 틀렸다. 이름을 받아 오면 **새로 빨개진
    것만** 보면 되고, 원래 빨간 것이 있어도 잴 수 있다.
    """
    planted = ROOT / "core" / "tests" / "unit" / "test_심은빨강.py"
    planted.write_text("def test_원래_빨갛다() -> None:\n    assert False\n", encoding="utf-8")
    try:
        found = cast("set[str]", TOOL.failing(["tests/unit/test_심은빨강.py"]))
    finally:
        planted.unlink()

    assert found == {"tests/unit/test_심은빨강.py::test_원래_빨갛다"}


def test_초록이면_빈_집합이다() -> None:
    """**제 파일을 겨누면 재귀한다** — 안쪽 pytest가 이 시험을 또 돌린다. 심은 초록을 쓴다."""
    planted = ROOT / "core" / "tests" / "unit" / "test_심은초록.py"
    planted.write_text("def test_초록이다() -> None:\n    assert True\n", encoding="utf-8")
    try:
        found = cast("set[str]", TOOL.failing(["tests/unit/test_심은초록.py"]))
    finally:
        planted.unlink()

    assert found == set()


def test_이름_없는_실패를_0으로_안_센다(tmp_path: Path) -> None:
    """**수집 오류는 `FAILED` 줄을 안 찍는다** — 그것을 빈 집합으로 읽으면 통과가 된다 (GR-0.5)."""
    broken = ROOT / "core" / "tests" / "unit" / "test_깨진것.py"
    broken.write_text("import 없는모듈\n", encoding="utf-8")
    try:
        found = cast("set[str]", TOOL.failing(["tests/unit/test_깨진것.py"]))
    finally:
        broken.unlink()

    assert found, "수집 오류를 초록으로 읽었다"


def test_첫_실패에서_안_멈춘다() -> None:
    r"""**`-x`를 떼었다** (D-0357).

    첫 실패에서 멈추면 **기준 판의 빨간 목록이 잘리고**, 잘린 뒤의 실패가 「새로 빨개졌다」로
    보인다 — 없던 결함을 만들어 낸다.
    """
    import inspect

    source = inspect.getsource(TOOL.failing)

    assert '"-x"' not in source
    assert '"-rf"' in source and '"--tb=no"' in source


# ------------------------------------------------------------------ 죽어도 되돌린다


def test_죽으면_되돌리는_손잡이가_있다(tmp_path: Path) -> None:
    """**첫 판이 `SIGKILL`에 변이를 남겼다** (D-0353).

    시간 제한에 죽으면서 `sync_artifacts.py`를 변이된 채로 뒀고, `check_args`가
    *"`--full`을 안 받는다"*로 잡아서야 알았다. **잡은 것이 다행이고 남긴 것이 결함이다** —
    변이 도구가 저장소를 망가뜨린 채 끝나면 다음 사람이 그것을 커밋한다.
    """
    import signal as sig

    fake = tmp_path / "x.py"
    fake.write_text("원본\n", encoding="utf-8")
    before = {one: sig.getsignal(one) for one in (sig.SIGINT, sig.SIGTERM, sig.SIGHUP)}
    try:
        TOOL.restore_on_death(fake, "원본\n")
        fake.write_text("망가뜨렸다\n", encoding="utf-8")
        handler = sig.getsignal(sig.SIGTERM)
        assert callable(handler)
        with pytest.raises(SystemExit):
            handler(sig.SIGTERM, None)
        assert fake.read_text(encoding="utf-8") == "원본\n"
    finally:
        for one, was in before.items():
            sig.signal(one, was)


def test_끝난_뒤_남은_변이를_센다() -> None:
    """**`finally`는 죽을 때 안 돈다.** 끝나고 한 번 더 본다."""
    source = (ROOT / "tools" / "mutate_gate.py").read_text(encoding="utf-8")

    assert "dirty_tools()" in source
    assert "변이가 남았다" in source
    assert callable(TOOL.dirty_tools)


def test_미리_빨간_시험이_있으면_수를_판정하지_않는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**미리 빨간 시험이 그 자리를 겨눈 시험일 수 있다** (D-0359).

    그 시험을 빼고 세면 **울었어야 하는 자리가 살아남은 것으로 잡힌다** — 실제로
    `doc_fsck:living_documents`가 그렇게 부풀었고, 문서 수 하나가 어긋난 것이 까닭이었다.
    수가 **위로** 틀리므로 천장을 내릴 때는 안 걸리고 **올릴 때 거짓 근거가 된다.**
    """
    monkeypatch.delenv("ONLY", raising=False)
    monkeypatch.setattr(TOOL, "dirty_tools", list)
    monkeypatch.setattr(TOOL, "invoked_tools", lambda: ["tidy"])
    monkeypatch.setattr(TOOL, "tests_for", lambda _: ["tests/unit/가짜.py"])
    monkeypatch.setattr(TOOL, "wiring", lambda _: [(1, "survey")])
    monkeypatch.setattr(TOOL, "cut", lambda *_: "# 잘렸다\n")
    monkeypatch.setattr(TOOL, "failing", lambda _: {"tests/unit/가짜.py::미리_빨강"})

    assert TOOL.cut_wiring() == 1
    spoke = capsys.readouterr()
    assert "못 믿는다" in spoke.out + spoke.err


def test_이름을_입에_올리는_시험을_겨눔으로_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`aimed()` — **약한 증거다.** 이름을 안 불러도 겨눌 수 있다 (D-0360)."""
    monkeypatch.setattr(TOOL, "ROOT", tmp_path)
    where = tmp_path / "core" / "tests" / "unit" / "test_가짜.py"
    where.parent.mkdir(parents=True)
    where.write_text("def test_하나():\n    survey()\n", encoding="utf-8")

    assert TOOL.aimed({"tests/unit/test_가짜.py::test_하나"}, "survey") is True
    assert TOOL.aimed({"tests/unit/test_가짜.py::test_하나"}, "verdict") is False


def test_못_읽은_파일을_혐의로_세지_않는다() -> None:
    """**거짓 경보는 진짜 경보를 죽인다** (GR-0.8). 못 읽었으면 의심하지 않는다."""
    assert TOOL.aimed({"tests/unit/없는파일.py::test_하나"}, "survey") is True


def test_겨눔_불명이_늘면_막는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**「울었다」가 「그 자리를 겨눈 시험이 울었다」와 같지 않다** (D-0360).

    절단이 엉뚱한 것을 깨뜨려 아무 시험이나 울어도 예전에는 「메워졌다」가 됐다.
    """
    monkeypatch.delenv("ONLY", raising=False)
    monkeypatch.setattr(TOOL, "UNAIMED_CEILING", 0)
    monkeypatch.setattr(TOOL, "WIRING_CEILING", 0)
    monkeypatch.setattr(TOOL, "dirty_tools", list)
    monkeypatch.setattr(TOOL, "invoked_tools", lambda: ["tidy"])
    monkeypatch.setattr(TOOL, "tests_for", lambda _: ["tests/unit/가짜.py"])
    monkeypatch.setattr(TOOL, "wiring", lambda _: [(1, "survey")])
    monkeypatch.setattr(TOOL, "cut", lambda *_: "# 잘렸다\n")
    reds = [set(), {"tests/unit/가짜.py::남의_실패"}]
    monkeypatch.setattr(TOOL, "failing", lambda _: reds.pop(0))
    monkeypatch.setattr(TOOL, "aimed", lambda *_: False)

    assert TOOL.cut_wiring() == 1
    spoke = capsys.readouterr()
    assert "겨눔 불명" in spoke.out + spoke.err
