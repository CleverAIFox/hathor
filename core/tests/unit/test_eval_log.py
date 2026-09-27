"""평가가 찍은 것을 남긴다 (D-0250).

**표를 화면에만 찍고 끝내는 평가 명령이 넷 있었다.** 창을 닫으면 수치가 사라졌고, 그것이
결정 기록 74건이 «재현 불명»인 이유다. 여기가 «사라지지 않는다»를 못 박는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hathor.interfaces.cli.eval_log import command, recorded, save


def _logs(root: Path) -> list[Path]:
    return sorted((root / "eval").glob("*.eval.log"))


def test_찍은_것이_파일에도_남는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with recorded(tmp_path, "harmony-output"):
        print("도수거리  0.1234")

    shown = capsys.readouterr()
    assert "도수거리  0.1234" in shown.out, "화면에도 그대로 찍힌다"
    assert "기록:" not in shown.out, (
        "남긴 자리는 `stderr`로 알린다 — 파일 이름에 시각이 있어 `stdout`에 찍으면 "
        "같은 시드의 출력이 달라진다 (D-0009)"
    )
    assert "기록:" in shown.err, "어디 남았는지는 말해 준다"
    (log,) = _logs(tmp_path)
    assert "도수거리  0.1234" in log.read_text(encoding="utf-8")
    assert "harmony-output" in log.name


def test_명령이_첫_줄에_있다(tmp_path: Path) -> None:
    """수치만 있으면 «무슨 조건이었나»가 또 없다."""
    with recorded(tmp_path, "harmony-order"):
        print("표")

    (log,) = _logs(tmp_path)
    assert log.read_text(encoding="utf-8").startswith("$ ")


def test_집_경로를_줄인다() -> None:
    """산출물이 사람 이름을 들고 다닐 이유가 없다."""
    home = str(Path.home())
    assert command(["hathor", f"{home}/음악"]) == "hathor ~/음악"


def test_명령_이름만_남긴다() -> None:
    """`argv[0]`은 `.venv/bin/hathor` 같은 것이다."""
    assert command(["/opt/x/.venv/bin/hathor", "eval", "harmony-order"]) == (
        "hathor eval harmony-order"
    )


def test_중간에_죽어도_찍힌_것까지는_남는다(tmp_path: Path) -> None:
    """**중간에 죽은 실측도 단서다.** 예외가 기록을 삼키면 그 단서가 사라진다."""
    with pytest.raises(RuntimeError), recorded(tmp_path, "time-drift"):
        print("여기까지 왔다")
        raise RuntimeError("멈췄다")

    (log,) = _logs(tmp_path)
    assert "여기까지 왔다" in log.read_text(encoding="utf-8")


def test_아무것도_안_찍으면_안_남긴다(tmp_path: Path) -> None:
    """빈 파일이 쌓이면 `var_fsck`가 세는 수가 뜻을 잃는다."""
    with recorded(tmp_path, "mfcc"):
        pass

    assert _logs(tmp_path) == []


def test_쓰기가_실패해도_평가는_산다(tmp_path: Path) -> None:
    """**사람이 보는 것이 먼저다.** 읽기 전용 경로에서 평가가 죽으면 바꿔치기가 손해다."""
    blocker = tmp_path / "막힘"
    blocker.write_text("파일이라 그 아래에 폴더를 못 만든다", encoding="utf-8")

    assert save(blocker, "mfcc", "표") is None

    with recorded(blocker, "mfcc"):
        print("살아 있다")


def test_라벨의_이상한_글자는_파일_이름에_안_들어간다(tmp_path: Path) -> None:
    assert save(tmp_path, "a/b c", "표") is not None
    (log,) = _logs(tmp_path)
    assert "/" not in log.name and " " not in log.name


def test_eval_분기가_기록을_거친다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**`recorded`가 초록인 것과 `main`이 그것을 거치는 것은 다르다** (D-0244).

    감싸는 자리가 하나이므로 여기가 빠지면 하위 명령 열 개가 다 안 남는다.

    **`_dispatch_eval`을 갈아끼우던 시험이다** (D-0273). 등재표가 러너를 **함수 객체로
    들고** 있으므로 모듈 속성을 바꿔도 표는 옛 함수를 계속 가리킨다 — 그렇게 쓰면 시험이
    조용히 실물을 돌린다. 그래서 **표째로** 갈아끼운다. 등재와 배선을 같이 지나므로
    예전보다 지나는 자리가 오히려 넓다.
    """
    from hathor.interfaces.cli import eval_retrieval
    from hathor.interfaces.cli import main as cli
    from hathor.interfaces.cli.registry import Command, Group

    table = (
        Group(
            "eval",
            "h",
            "eval_command",
            (
                Command(
                    "retrieval",
                    "h",
                    eval_retrieval._build_retrieval,
                    lambda _args: _shout(),
                ),
            ),
        ),
    )
    monkeypatch.setattr(cli, "entries", lambda: table)

    assert cli.main(["eval", "retrieval", "--out", str(tmp_path)]) == 0
    (log,) = _logs(tmp_path)
    assert "도수거리  0.4242" in log.read_text(encoding="utf-8")


def _shout() -> int:
    print("도수거리  0.4242")
    return 0
