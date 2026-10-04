"""**부품은 재고 배선은 안 쟀다** — 못·릴리스 묶음 (D-0359).

`check_test_types` 다섯 · `check_args` 넷 · `check_sight` 넷 · `gh_ops` 넷 ·
`release_notes` 넷.

**래칫의 배선이 끊기면 래칫이 못이 아니라 장식이 된다** (D-0126) — 수는 화면에 뜨고
천장은 그대로 있는데 **아무도 둘을 비교하지 않는다.**
"""

from __future__ import annotations

import pytest

from tests.conftest import tool_module

TYPES = tool_module("check_test_types")
ARGS = tool_module("check_args")
SIGHT = tool_module("check_sight")
GH = tool_module("gh_ops")
NOTES = tool_module("release_notes")

PLANTED = "심은 문제"


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


# ------------------------------------------------------------------ check_test_types


def test_mypy가_안_돌면_통과하지_않는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**안 쟀으면 0이 아니다** (GR-0.5). `_mypy()`를 끊으면 빈 수로 통과한다."""
    monkeypatch.setattr(TYPES, "_mypy", lambda: None)
    monkeypatch.setattr("sys.argv", ["check_test_types.py", "--check"])

    assert TYPES.main() == 1


def test_센_것과_못을_대조한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tally()` → `_report()` 두 자리. **어느 줄을 봐야 하는지가 화면에 나온다** (D-0264)."""
    shown: list[dict[str, int]] = []
    monkeypatch.setattr(TYPES, "_mypy", lambda: ["심은 줄"])
    monkeypatch.setattr(TYPES, "tally", lambda _: {"assignment": 1})
    monkeypatch.setattr(TYPES, "_report", lambda counts, raw: shown.append(counts))
    monkeypatch.setattr("sys.argv", ["check_test_types.py", "--check"])

    assert TYPES.main() == 1
    assert shown == [{"assignment": 1}], "센 것이 화면까지 안 간다"
    assert "새로 쓴 검사의 타입을 맞춘다" in _spoke(capsys)


def test_update가_못을_다시_박고_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_rewrite()` · `total()` 두 자리. **안 거치면 「박았다」만 찍고 파일은 그대로다.**"""
    wrote: list[dict[str, int]] = []
    monkeypatch.setattr(TYPES, "_mypy", lambda: [])
    monkeypatch.setattr(TYPES, "tally", dict)
    monkeypatch.setattr(TYPES, "_rewrite", wrote.append)
    monkeypatch.setattr(TYPES, "total", lambda _: 42)
    monkeypatch.setattr("sys.argv", ["check_test_types.py", "--update"])

    assert TYPES.main() == 0
    assert wrote == [{}], "못을 안 박았다"
    assert "42 → 0" in _spoke(capsys)


def test_늘었는데_update하면_무엇이_늘었는지_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--update` 쪽 `_report()` 자리 (D-0118).

    **늘어난 것을 그냥 박아 주면 래칫이 뒤로 돈다.** 막는 것만으로는 안 된다 —
    *«무엇이 늘었는지»*를 같은 화면에 내야 사람이 고칠 수 있다.
    """
    shown: list[dict[str, int]] = []
    monkeypatch.setattr(TYPES, "_mypy", lambda: ["심은 줄"])
    monkeypatch.setattr(TYPES, "tally", lambda _: {"assignment": 1})
    monkeypatch.setattr(TYPES, "_report", lambda counts, raw: shown.append(counts))
    monkeypatch.setattr(TYPES, "_rewrite", lambda _: pytest.fail("늘었는데 박았다"))
    monkeypatch.setattr("sys.argv", ["check_test_types.py", "--update"])

    assert TYPES.main() == 1
    assert shown == [{"assignment": 1}], "늘어난 부류가 화면에 없다"
    assert "--allow-growth" in _spoke(capsys)


# ------------------------------------------------------------------ check_args


def test_던진_그물을_화면에_센다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()`의 `sources()` 자리 (D-0352).

    **워크플로 쪽을 한 건도 못 읽고 통과가 떴다** — 수가 화면에 없으면 0인 것도 모른다.
    실물에 한 곳을 더해, 화면의 수가 **센 것을 따라오는지** 본다.
    """
    real = ARGS.sources()
    monkeypatch.setattr(ARGS, "sources", lambda: [*real, ("심은곳", "python3 tools/뭔가.py\n")])
    monkeypatch.setattr(ARGS, "check", list)
    monkeypatch.setattr("sys.argv", ["check_args.py", "--check"])

    assert ARGS.main() == 0
    assert f"바깥 파일 {len(real) + 1}개" in _spoke(capsys)


@pytest.mark.parametrize("part", ["check_flags", "check_passthrough", "check_advice"])
def test_세_검사가_check에_배선돼_있다(part: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """셋 다 `check()`만 거쳐 나간다 — **빠지면 그 부류가 통째로 안 걸린다.**"""
    monkeypatch.setattr(ARGS, part, lambda *_: [PLANTED])

    assert PLANTED in ARGS.check()


def test_바깥_파일마다_세_검사를_돌린다(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check()`의 `sources()` 자리. 끊으면 **셸과 워크플로를 한 개도 안 본다.**"""
    seen: list[str] = []
    monkeypatch.setattr(ARGS, "sources", lambda: [("심은곳", "심은 본문")])

    def noted(text: str, where: str) -> list[str]:
        seen.append(text)
        return []

    monkeypatch.setattr(ARGS, "check_any_calls", noted)
    monkeypatch.setattr(ARGS, "check_make_calls", lambda *_: [])
    monkeypatch.setattr(ARGS, "check_usage", lambda *_: [])

    ARGS.check()

    assert seen == ["심은 본문"]


# ------------------------------------------------------------------ check_sight


def test_update가_느슨함_허락을_그대로_넘긴다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**사라진 못은 늘 느슨해지는 쪽이다** (D-0349). `--loosen`이 안 닿으면 조용히 풀린다."""
    seen: list[bool] = []

    def noted(allow_loosening: bool) -> int:
        seen.append(allow_loosening)
        return 3

    monkeypatch.setattr(SIGHT, "update", noted)

    monkeypatch.setattr("sys.argv", ["check_sight.py", "--update"])
    assert SIGHT.main() == 3
    monkeypatch.setattr("sys.argv", ["check_sight.py", "--update", "--loosen"])
    assert SIGHT.main() == 3

    assert seen == [False, True]


def test_list가_실측과_방향을_같이_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`measure()` · `is_ceiling()` 두 자리. **방향이 없으면 어느 쪽이 위반인지 모른다.**"""
    monkeypatch.setattr(SIGHT, "measure", lambda: {"어떤도구.허용": ["가", "나"]})
    monkeypatch.setattr(SIGHT, "is_ceiling", lambda _: True)
    monkeypatch.setattr("sys.argv", ["check_sight.py", "--list"])

    assert SIGHT.main() == 0
    spoke = _spoke(capsys)
    assert "어떤도구.허용" in spoke and "2" in spoke and "천장" in spoke


def test_판정이_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(SIGHT, "measure", lambda: {"어떤도구.허용": ["가"]})
    monkeypatch.setattr(SIGHT, "verdict", lambda *_: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_sight.py", "--check"])

    assert SIGHT.main() == 1
    assert PLANTED in _spoke(capsys)


# ------------------------------------------------------------------ gh_ops


def test_준비가_안_됐으면_아무것도_안_한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`ready()` 자리. **`gh`도 토큰도 없는 기기에서 2를 낸다** — 1이 아니다."""
    monkeypatch.setattr(GH, "ready", lambda: PLANTED)
    monkeypatch.setattr(GH, "setup", lambda: 0)
    monkeypatch.setattr("sys.argv", ["gh_ops.py", "setup"])

    assert GH.main() == 2
    assert PLANTED in _spoke(capsys)


def test_세_하위_명령이_각자에게_간다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`setup` · `bot` · `smoke` 세 자리. **하나가 빠지면 다른 일을 한다.**"""
    closed: list[bool] = []
    monkeypatch.setattr(GH, "ready", lambda: "")
    monkeypatch.setattr(GH, "setup", lambda: 5)

    def noted(close: bool) -> int:
        closed.append(close)
        return 6

    monkeypatch.setattr(GH, "bot", noted)
    monkeypatch.setattr(GH, "smoke", lambda: 7)

    monkeypatch.setattr("sys.argv", ["gh_ops.py", "setup"])
    assert GH.main() == 5
    monkeypatch.setattr("sys.argv", ["gh_ops.py", "bot", "--close"])
    assert GH.main() == 6
    monkeypatch.setattr("sys.argv", ["gh_ops.py", "smoke"])
    assert GH.main() == 7

    assert closed == [True], "`--close`가 안 닿는다"


# ------------------------------------------------------------------ release_notes


def test_태그는_가장_최근_결정에서_온다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`latest()` 자리. **손으로 적은 태그는 기록과 어긋난다** (D-0223)."""
    monkeypatch.setattr(NOTES, "latest", lambda _: "D-9999")
    monkeypatch.setattr("sys.argv", ["release_notes.py", "--tag"])

    assert NOTES.main() == 0
    assert "D-9999" in _spoke(capsys)


def test_표제는_그_번호의_행에서_온다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`latest()` · `records()` 두 자리. **번호와 표제가 다른 판에서 오면 어긋난다.**"""
    monkeypatch.setattr(NOTES, "latest", lambda _: "D-9999")
    monkeypatch.setattr(
        NOTES, "records", lambda _: [("D-9998", "옛 표제", ""), ("D-9999", "심은 표제", "")]
    )
    monkeypatch.setattr("sys.argv", ["release_notes.py", "--title"])

    assert NOTES.main() == 0
    assert "D-9999. 심은 표제" in _spoke(capsys)


def test_본문이_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`notes()` 자리. 끊으면 **빈 릴리스 노트가 올라간다.**"""
    seen: list[str | None] = []

    def noted(_: str, since: str | None) -> str:
        seen.append(since)
        return "심은 본문\n"

    monkeypatch.setattr(NOTES, "notes", noted)
    monkeypatch.setattr("sys.argv", ["release_notes.py", "--since", "D-0001"])

    assert NOTES.main() == 0
    assert "심은 본문" in _spoke(capsys)
    assert seen == ["D-0001"]


def test_못_읽으면_2를_낸다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def dead(_: str) -> str:
        raise LookupError("기록이 없다")

    monkeypatch.setattr(NOTES, "latest", dead)
    monkeypatch.setattr("sys.argv", ["release_notes.py", "--tag"])

    assert NOTES.main() == 2
    assert "릴리스를 낼 수 없다" in _spoke(capsys)
