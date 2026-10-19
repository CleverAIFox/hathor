"""산출물 대장의 `regen`이 **실제로 도는 명령인가** (D-0441).

### 왜 시험에 있고 도구에 없나

`tools/`는 맨 `python3`로 돈다 — `hathor`를 못 들인다. 명령이 성립하는지 보려면
`build_parser`가 필요하고, 그것은 `uv` 환경 안에만 있다. **pytest가 유일한 자리다.**

### 왜 argparse만으로는 모자라나

`ingest keys`에는 **거절 함수가 둘** 있다 (`refusal` · `replay_refusal`). argparse를
통과하고도 실행 첫 줄에서 죽는 조합이 있다 — 실측으로 대장이 적고 있던
`--from-bundles --series`가 그랬다. **argparse만 보면 값만 채워 넣고 통과한다.**
"""

from __future__ import annotations

import contextlib
import io
import shlex
import tomllib
from pathlib import Path

import pytest

from hathor.interfaces.cli.ingest_keys_bundles import refusal
from hathor.interfaces.cli.main import build_parser
from hathor.interfaces.cli.tables import replay_refusal

LEDGER = Path(__file__).resolve().parents[3] / "artifacts.toml"
ENTRY = "hathor.cli"
FLOOR = 10
"""`regen`이 명령인 행의 바닥. **표가 비면 0건이 조용히 초록이 된다** (D-0230)."""


def _commands() -> list[tuple[str, str]]:
    """`(계열, 명령)`. 명령이 아닌 칸(`불가` · `폐기` · 산문)은 안 본다."""
    data = tomllib.loads(LEDGER.read_text(encoding="utf-8"))
    return [
        (name, body["regen"].strip())
        for name, body in data.get("series", {}).items()
        if ENTRY in (body.get("regen") or "")
    ]


def _argv(command: str) -> list[str]:
    return shlex.split(command.split(ENTRY, 1)[1])


def test_대장에_명령이_남아_있다() -> None:
    """**셀 것이 없으면 아래가 전부 공짜로 통과한다** (D-0230)."""
    assert len(_commands()) >= FLOOR


@pytest.mark.parametrize(("name", "command"), _commands(), ids=lambda one: str(one)[:40])
def test_재생성_명령이_성립한다(name: str, command: str) -> None:
    """**적어 둔 명령이 안 돌면 안내가 없는 것보다 나쁘다** (D-0292 · D-0203).

    실측으로 16줄 중 **1줄**이 죽어 있었다 — `keys-*.series`가
    *«--series»*를 값 없이 적어 argparse가 바로 거절했다. 대장은 산출물을 다시
    만들라고 있는 것이므로, 그 줄이 죽으면 **대장이 제 일을 못 한다.**
    """
    said = io.StringIO()
    try:
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(io.StringIO()):
            args = build_parser().parse_args(_argv(command))
    except SystemExit:  # pragma: no cover — 초록일 때는 안 지난다
        pytest.fail(f"{name}: argparse가 거절한다 — {said.getvalue().strip()}\n  {command}")

    # **argparse를 지나고도 죽는 조합이 있다.** 거절 함수가 그 자리다.
    for reason in (refusal(args), replay_refusal(args)):
        assert not reason, f"{name}: {reason}\n  {command}"


def test_그물이_안_비었다() -> None:
    """**고치기 전 줄을 넣어 본다** (D-0230).

    둘 다 잡혀야 한다 — 값이 없으면 argparse가, 값을 채우면 거절 함수가.
    """
    parser = build_parser()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        parser.parse_args(["ingest", "keys", "--from-bundles", "--series"])

    args = parser.parse_args(["ingest", "keys", "--from-bundles", "--series", "2"])
    assert refusal(args), "argparse를 지난 잘못된 조합을 거절 함수도 못 잡는다"
