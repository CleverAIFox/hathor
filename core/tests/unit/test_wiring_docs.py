"""**부품은 재고 배선은 안 쟀다** — 문서·산출물 쪽 (D-0358).

`make mutate WIRING=1`이 `doc_fsck` 열 곳과 `check_artifacts` 여섯 곳을 세었다. 작은
검사를 **직접** 부르는 시험만 있으면 `main()`에서 그 줄을 지워도 아무도 안 운다.

여기는 **입구를 거쳐서** 본다 — 심은 문제를 `main()`이 들고 나오는가.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
FSCK = tool_module("doc_fsck")
ARTIFACTS = tool_module("check_artifacts")

PLANTED = "심은 문제"


def _ran(module: Any, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """`main()`을 돌리고 (종료코드, 화면 전부)를 돌려준다."""
    code = cast("int", module.main())
    spoke = capsys.readouterr()
    return code, spoke.out + spoke.err


# ------------------------------------------------------------------ doc_fsck


@pytest.mark.parametrize(
    "part",
    [
        "check_paths",
        "check_commands",
        "check_orphan_tools",
        "check_wiring",
        "check_reserved_packages",
        "check_counts",
        "check_album_lift",
        "check_orphan_workflows",
    ],
)
def test_대조_여덟이_배선돼_있다(
    part: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**여덟을 `main()`이 더해서 낸다.** 한 줄만 지워도 그 축은 영원히 안 본다."""
    monkeypatch.setattr(FSCK, part, lambda: [PLANTED])
    monkeypatch.setattr("sys.argv", ["doc_fsck.py", "--check"])

    code, spoke = _ran(FSCK, ["--check"], capsys)

    assert code == 1
    assert PLANTED in spoke


def test_fix가_고친_줄을_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--fix`가 **무엇을 고쳤는지 안 찍으면** 사람이 모르고 커밋한다."""
    monkeypatch.setattr(FSCK, "fix_counts", lambda: ["심은 줄"])
    monkeypatch.setattr("sys.argv", ["doc_fsck.py", "--fix"])

    code, spoke = _ran(FSCK, ["--fix"], capsys)

    assert code == 0
    assert "심은 줄" in spoke and "고친 자리 1곳" in spoke


def test_통과줄이_문서_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**수가 화면에 없으면 0인 것도 모른다** (D-0230). `living_documents()`를 거친다."""
    monkeypatch.setattr("sys.argv", ["doc_fsck.py", "--check"])

    code, spoke = _ran(FSCK, ["--check"], capsys)

    assert code == 0
    assert f"문서 {len(cast('list[Any]', FSCK.living_documents()))}개" in spoke
    assert "문서 0개" not in spoke


def test_살아_있는_문서가_셋_이상이다() -> None:
    assert len(cast("list[Any]", FSCK.living_documents())) >= 3


# ------------------------------------------------------------------ check_artifacts


def test_대장_검사가_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ARTIFACTS, "check_ledger", lambda _: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_artifacts.py", "--check"])

    code, spoke = _ran(ARTIFACTS, ["--check"], capsys)

    assert code == 1
    assert PLANTED in spoke


def test_통과줄이_계열_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`load()`를 끊으면 **계열 0개**가 찍히고 그래도 통과했다 (D-0230)."""
    monkeypatch.setattr("sys.argv", ["check_artifacts.py", "--check"])

    code, spoke = _ran(ARTIFACTS, ["--check"], capsys)

    assert code == 0
    assert f"계열 {len(cast('dict[str, Any]', ARTIFACTS.load()))}개" in spoke
    assert "계열 0개" not in spoke


def test_실물도_교두보도_없으면_못_쟀다고_말한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**0건으로 넘기지 않는다** (GR-0.5). `store_side()`를 거쳐야 이 자리가 선다."""
    monkeypatch.setattr(ARTIFACTS, "store_side", lambda: None)
    monkeypatch.setattr(
        "sys.argv", ["check_artifacts.py", "--audit", "--root", str(tmp_path / "없는곳")]
    )

    code, spoke = _ran(ARTIFACTS, [], capsys)

    assert code == 1
    assert "산출물이 있는 기기에서 돌린다" in spoke


def test_격리가_천장을_넘으면_막는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`audit()`가 낸 판정을 `main()`이 **실제로 읽는가.**"""
    root = tmp_path / "var"
    root.mkdir()
    monkeypatch.setattr(ARTIFACTS, "store_side", lambda: None)
    monkeypatch.setattr(
        ARTIFACTS,
        "audit",
        lambda *_, **__: ARTIFACTS.Verdict(
            missing=[], orphan=["심은계열"], stale=[], normal=0, examples={}
        ),
    )
    monkeypatch.setattr("sys.argv", ["check_artifacts.py", "--audit", "--root", str(root)])

    code, spoke = _ran(ARTIFACTS, [], capsys)

    assert code == 1
    assert "심은계열" in spoke
    assert "천장" in spoke


def test_suggest가_등재_자리를_찍는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`skeleton()`을 거치지 않으면 **붙여 넣을 것이 안 나온다.**"""
    root = tmp_path / "var"
    root.mkdir()
    monkeypatch.setattr(ARTIFACTS, "store_side", lambda: None)
    monkeypatch.setattr(
        ARTIFACTS,
        "audit",
        lambda *_, **__: ARTIFACTS.Verdict(
            missing=[], orphan=["심은계열"], stale=[], normal=0, examples={}
        ),
    )
    monkeypatch.setattr(ARTIFACTS, "skeleton", lambda name, detail: f"[뼈대 {name} {detail}]")
    monkeypatch.setattr(
        "sys.argv", ["check_artifacts.py", "--audit", "--suggest", "--root", str(root)]
    )

    code, spoke = _ran(ARTIFACTS, [], capsys)

    assert code == 1
    assert "[뼈대 심은계열" in spoke


def test_격리된_것의_크기를_찍는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`measure()`를 거쳐야 **무엇이 얼마나 쌓였는지** 보인다 — 없으면 이름만 나온다."""
    root = tmp_path / "var"
    (root / "심은계열").mkdir(parents=True)
    monkeypatch.setattr(ARTIFACTS, "store_side", lambda: None)
    monkeypatch.setattr(
        ARTIFACTS,
        "audit",
        lambda *_, **__: ARTIFACTS.Verdict(
            missing=[], orphan=["심은계열"], stale=[], normal=0, examples={}
        ),
    )
    monkeypatch.setattr(ARTIFACTS, "measure", lambda base, name: f"[잰 것 {name}]")
    monkeypatch.setattr("sys.argv", ["check_artifacts.py", "--audit", "--root", str(root)])

    code, spoke = _ran(ARTIFACTS, [], capsys)

    assert code == 1
    assert "[잰 것 심은계열]" in spoke
