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
    """**수가 화면에 없으면 0인 것도 모른다** (D-0230).

    두 시야를 다 찍는다 — `living_documents()`와 `counting_code()`. 뒤쪽은 D-0361이
    넓힌 자리고, **그 수가 화면에 없으면 다시 조용히 0이 될 수 있다.**
    """
    monkeypatch.setattr("sys.argv", ["doc_fsck.py", "--check"])

    code, spoke = _ran(FSCK, ["--check"], capsys)

    assert code == 0
    assert f"문서 {len(cast('list[Any]', FSCK.living_documents()))}개" in spoke
    assert "문서 0개" not in spoke
    assert f"코드 {len(cast('list[Any]', FSCK.counting_code()))}개" in spoke
    assert "코드 0개" not in spoke


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


def test_축의_시야에_코드가_들어_있다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**축은 멀쩡하고 시야가 좁았다** (D-0361 · D-0349와 같은 자리).

    «관문 도구» 축은 D-0350부터 살아 있었는데 `check_counts`가 **살아 있는 문서 셋만**
    봤다. `mutate_gate`의 독스트링이 틀린 수를 적고 338판이 통과했다.
    """
    code = tmp_path / "tools"
    code.mkdir()
    (code / "거짓말.py").write_text('"""관문 도구 9999개."""\n', encoding="utf-8")
    monkeypatch.setattr(FSCK, "ROOT", tmp_path)
    monkeypatch.setattr(FSCK, "FLOOR_CODE", 1)
    monkeypatch.setattr(FSCK, "living_documents", lambda: [])

    problems = [one for one in FSCK.check_counts() if "거짓말.py" in one]

    assert len(problems) == 1, f"코드에 적힌 틀린 수를 못 봤다: {problems}"
    assert "9999" in problems[0]


def test_과거를_인용한_줄은_선언으로_면제한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**선언 없는 면제는 없다** (D-0219). 그때 틀렸던 수를 적는 문장은 살려야 한다."""
    code = tmp_path / "tools"
    code.mkdir()
    (code / "인용.py").write_text(
        f'"""그때는 관문 도구 9999개라 적혀 있었다.  {FSCK.COUNT_OK} 과거 인용 """\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(FSCK, "ROOT", tmp_path)
    monkeypatch.setattr(FSCK, "FLOOR_CODE", 1)
    monkeypatch.setattr(FSCK, "living_documents", lambda: [])

    assert [one for one in FSCK.check_counts() if "인용.py" in one] == []


def test_코드_시야가_비면_막는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230).

    판정은 **입구에서** 한다 — `counting_code()`가 직접 울면 임시 뿌리를 쓰는 시험이
    전부 터진다 (GR-0.8). 그래서 `main()`이 그 수를 보는지까지 본다.
    """
    # **뿌리를 바꾸지 않는다** — 바꾸면 다른 검사가 없는 파일을 보고 터진다. 바닥만
    # 올려 「시야가 바닥 밑」 상황을 만든다.
    monkeypatch.setattr(FSCK, "FLOOR_CODE", 9999)
    assert FSCK.code_shortfall(), "시야가 바닥 밑인데 조용하다"

    monkeypatch.setattr(FSCK, "code_shortfall", lambda: ["심은 문제"])
    monkeypatch.setattr("sys.argv", ["doc_fsck.py", "--check"])
    assert FSCK.main() == 1
    assert "심은 문제" in capsys.readouterr().err


def test_두_셈이_다른_이름을_쓴다() -> None:
    """**같은 이름에 두 셈이 붙어 있었다** (D-0043 · D-0361).

    «관문 도구» 축은 `--check`를 받는 `check_*.py`만 세고(실측 17), `mutate_gate`는
    **불리는 것 전부**를 센다(실측 37). 이름이 같은 동안 *«관문 도구 N개»*가 어느
    셈인지 알 수 없었다.
    """
    counts = tool_module("doc_counts")
    mutate = tool_module("mutate_gate")

    assert not hasattr(mutate, "gate_tools"), "이름이 다시 겹쳤다"
    assert len(mutate.invoked_tools()) > len(counts.gate_tools())
