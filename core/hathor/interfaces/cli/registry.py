"""하위 명령을 한 표에 등재한다 (D-0273).

### 왜 필요했나

`build_parser`가 599줄이고, 그 안에서 등재한 이름을 `main`과 `_dispatch_eval`이
**손으로 한 번 더** 적고 있었다. 두 목록이 어긋나도 argparse는 아무 말을 안 한다 —
등재만 되고 배선이 없으면 **떨어지는 기본이 대신 돈다.** `ingest all`이 그렇게 스캔을
돌리고 `AttributeError`로 죽었고, 그 바람에 산출물이 하나 더 생겼다 (D-0204 · D-0208).

그 사고 뒤 세운 검사가 `test_하위_명령이_전부_배선돼_있다`인데, 그것은 `main.py`의 **글자를
정규식으로 긁어** «배선에 없는 이름이 정확히 하나여야 한다»고 말한다. 위험을 없앤 것이
아니라 **하나로 못 박은 것**이다. 게다가 `add_parser`를 함수로 감싼 둘(`eval clap` ·
`ingest onsets`)은 그 정규식에 **아예 안 잡힌다** — 그 둘 중 하나의 배선을 빼먹으면
검사는 초록이다.

### 무엇이 달라지나

등재와 배선이 **같은 표**를 읽는다. 짝이 안 맞을 수 없으므로 떨어지는 기본이 필요 없고,
검사는 글자가 아니라 표를 본다.

    Command("scan", "라이브러리 스캔", _build_scan, _run_ingest_scan)

이름 · 도움말 · 인자를 붙이는 함수 · 실행하는 함수가 **한 줄에 같이 선다.**
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    import argparse


class Command(NamedTuple):
    """하위 명령 하나. **인자를 붙이는 쪽과 실행하는 쪽이 붙어 있다.**"""

    name: str
    help: str
    build: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int]


class Group(NamedTuple):
    """`ingest`·`eval`처럼 하위 명령을 또 갖는 묶음. `dest`가 argparse에 남을 이름이다."""

    name: str
    help: str
    dest: str
    commands: tuple[Command, ...]


type Entry = Command | Group
"""최상단에 설 수 있는 것. 명령 하나이거나 묶음이다."""


def no_arguments(parser: argparse.ArgumentParser) -> None:
    """인자가 없는 명령의 `build`. `env`·`doctor`가 이것을 쓴다."""
    del parser


def add_commands(
    commands: argparse._SubParsersAction,  # type: ignore[type-arg]
    table: Sequence[Command],
) -> None:
    """표에 적힌 대로 파서를 만든다."""
    for command in table:
        command.build(commands.add_parser(command.name, help=command.help))


def register(
    commands: argparse._SubParsersAction,  # type: ignore[type-arg]
    entries: Sequence[Entry],
) -> None:
    """최상단 등재. 묶음이면 한 겹 더 내려간다.

    **`required=True`를 여기서 준다** — 묶음 이름만 주고 끝내면 argparse가 거절한다.
    빠뜨리면 `args.<dest>`가 `None`이 되어 아래 `run`이 «등재되지 않은 이름»으로 죽는다.
    """
    for entry in entries:
        if isinstance(entry, Group):
            parser = commands.add_parser(entry.name, help=entry.help)
            add_commands(parser.add_subparsers(dest=entry.dest, required=True), entry.commands)
        else:
            entry.build(commands.add_parser(entry.name, help=entry.help))


def resolve(
    entries: Sequence[Entry],
    args: argparse.Namespace,
) -> Callable[[argparse.Namespace], int]:
    """파싱된 인자가 고른 명령의 실행 함수.

    **떨어지는 기본이 없다.** argparse가 등재 안 된 이름을 이미 거절하므로 여기서 못
    찾는 길은 «등재했는데 표에서 뺐다» 하나뿐이고, 그것은 조용히 다른 명령을 돌리는
    대신 죽어야 한다 — D-0204가 조용히 스캔을 돌렸던 자리다.
    """
    for entry in entries:
        if entry.name != args.command:
            continue
        if isinstance(entry, Group):
            chosen = getattr(args, entry.dest)
            for command in entry.commands:
                if command.name == chosen:
                    return command.run
            raise SystemExit(f"등재되지 않은 하위 명령: {entry.name} {chosen}")
        return entry.run
    raise SystemExit(f"등재되지 않은 명령: {args.command}")


def names(entries: Sequence[Entry]) -> tuple[str, ...]:
    """등재된 이름 전부. 묶음은 `묶음 하위` 꼴로 펼친다. **검사가 이것을 본다.**"""
    found: list[str] = []
    for entry in entries:
        if isinstance(entry, Group):
            found.extend(f"{entry.name} {command.name}" for command in entry.commands)
        else:
            found.append(entry.name)
    return tuple(found)
