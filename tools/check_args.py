#!/usr/bin/env python3
"""**부르는 쪽이 주는 인자를 받는 쪽이 받나** (D-0350 · `fire-lane`의 `argcheck`).

### 사용자가 돌린 명령이 조용히 아무것도 안 했다

```
$ make tidy YES=1 FIX=1
치웠다 · 1종 · 실패 0          ← 바이트코드 20개는 그대로다
```

`make ship`이 *"치우려면 `make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 찍는다. 읽으면
**둘 다 `tidy`에 주는 것처럼 보인다.** 그런데 `FIX=1`은 `make ship`의 것이고
(`ship.py --fix`), `tidy`의 레시피는 `YES`만 넘긴다 — **`FIX=1`은 그 자리에서 사라졌다.**

`make hygiene FIX=1`도 같은 자리를 지나갔다 — `$(MAKE) tidy FIX=1`로 넘기는데 받는
쪽이 안 썼다.

### 조용히 무시되는 인자는 D-0064가 이미 닫은 부류다

D-0064가 *"인자가 조용히 무시된다"*를 고쳤고, **검사를 안 넣었더니 네 시간 뒤 같은
부류가 다시 나왔다** (D-0069). 그리고 이번에 **세 번째**다. `fire-lane`은 같은 자리를
`argcheck.py`로 세며 호출 55종 · 인자 17종을 본다.

### 보는 것 둘

| | 묻는 것 |
|---|---|
| **플래그** | 레시피가 `python3 tools/X.py --flag`를 치면 `X.py`가 `--flag`를 받나 |
| **넘기는 변수** | 레시피가 `$(MAKE) 타깃 VAR=1`을 하면 그 타깃이 `$(VAR)`를 쓰나 |

둘째가 이 사고다. **주는 쪽만 보면 안 보인다** — 받는 쪽이 안 쓰는 것이 결함이다.

    python3 tools/check_args.py            # 검사한다
    python3 tools/check_args.py --list     # 호출과 인자를 찍는다
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"
HOOK = ROOT / ".githooks" / "pre-commit"

TARGET = re.compile(r"(?m)^([a-z][a-z0-9-]*):")
"""Makefile 타깃 머리. 들여쓴 줄이 그 타깃의 레시피다."""

CALL = re.compile(r"(?m)python3 (tools/[a-z_0-9]+\.py)([^\n]*)$")
r"""도구 호출과 **그 줄의 나머지**.

**줄을 넘지 않는다.** 첫 판이 `\s+`로 꼬리를 받아 **다음 줄들의 플래그까지 끌어왔고**
`gh_ops.py`에 `--ratchet`을 준다고 네 건을 거짓으로 냈다 — 그것이 GR-0.8이다.
"""

FLAG = re.compile(r"--[a-z][a-z-]*")
ACCEPTS = re.compile(r'add_argument\(\s*"(--[a-z][a-z-]*)"')
SUBMAKE = re.compile(r"\$\(MAKE\)([^\n]*)")
"""`$(MAKE)` 뒤 꼬리. **타깃은 정규식으로 안 집는다.**

첫 판이 `\b([a-z][a-z0-9-]*)\b`로 집었고 `--no-print-directory`의 **`no`**를 타깃으로
삼아 `tidy`를 지나쳤다 — **그래서 이 검사를 만든 결함을 이 검사가 못 잡았다.** 꼬리를
토큰으로 쪼개 **아는 타깃 이름과 맞는 것**만 쓴다.
"""

HANDED = re.compile(r"([A-Z_]+)=")
"""`$(MAKE)` 꼬리에서 넘기는 변수 이름. `$(if $(FIX),FIX=1,)` 꼴도 잡는다."""

USES = re.compile(r"\$\(([A-Z_]+)\)")

SKIP_FLAGS = ("--help",)
"""argparse가 저절로 주는 것. **목록이 길어지면 검사가 꺼진 것과 같다** — 하나다."""


def recipes(text: str) -> dict[str, list[str]]:
    """타깃 → 그 레시피 줄들. **들여쓴 줄만 센다.**"""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        head = TARGET.match(line)
        if head:
            current = head.group(1)
            found.setdefault(current, [])
            continue
        if current and line.startswith(("\t", "    ")):
            found[current].append(line)
        elif line and not line.startswith((" ", "\t", "#")):
            current = None
    return found


def accepted(tool: str) -> set[str]:
    """그 도구가 받는 플래그. **`argparse`를 안 돌린다** — 소스에서 읽는다."""
    path = ROOT / tool
    if not path.exists():
        raise LookupError(f"{tool}이 없다. 정본이 사라졌다")
    return set(ACCEPTS.findall(path.read_text(encoding="utf-8")))


def check_flags(text: str, where: str) -> list[str]:
    """레시피가 주는 플래그를 도구가 받나."""
    problems: list[str] = []
    for tool, tail in CALL.findall(text):
        if not (ROOT / tool).exists():
            problems.append(f"{where}: `{tool}`을 부르는데 그 파일이 없다")
            continue
        takes = accepted(tool)
        problems.extend(
            f"{where}: `{tool}`에 `{flag}`를 주는데 그 도구가 안 받는다 — "
            f"**조용히 무시된다** (D-0064 · D-0069)"
            for flag in dict.fromkeys(FLAG.findall(tail))
            if flag not in takes and flag not in SKIP_FLAGS
        )
    return problems


def check_passthrough(text: str) -> list[str]:
    """`$(MAKE) 타깃 VAR=1`을 넘기면 그 타깃이 `$(VAR)`를 쓰나 (D-0350).

    **받는 쪽을 봐야 보인다.** 주는 쪽만 보면 `FIX=1`은 멀쩡해 보인다.
    """
    made = recipes(text)
    problems: list[str] = []
    for caller, lines in sorted(made.items()):
        for line in lines:
            for tail in SUBMAKE.findall(line):
                tokens = re.split(r"[\s=,)]+", tail)
                targets = [one for one in tokens if one in made]
                if not targets:
                    continue
                body = "\n".join(made[targets[0]])
                used = set(USES.findall(body))
                problems.extend(
                    f"Makefile: `{caller}`가 `{targets[0]}`에 `{variable}=1`을 넘기는데 "
                    f"`{targets[0]}`이 `$({variable})`를 안 쓴다 — **그 자리에서 사라진다**"
                    for variable in dict.fromkeys(HANDED.findall(tail))
                    if variable not in used
                )
    return problems


def printed_strings(path: Path) -> list[tuple[int, str]]:
    """그 파일이 **화면에 찍을 수 있는 문자열**. 문서 문자열은 뺀다 (D-0350).

    문서 문자열까지 훑으면 **이 파일이 사고를 설명하는 문장**에 제 검사가 걸린다 —
    첫 판이 그랬다. 설명과 출력은 다르다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docs.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.lineno not in docs
    ]


def check_advice() -> list[str]:
    """화면이 알려 주는 명령이 실제로 그 일을 하나 (D-0350 · D-0310과 같은 자리).

    `ship`이 *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 찍었고 **읽으면 둘 다
    `tidy`에 주는 것으로 읽힌다.** 사용자가 그대로 쳤고 아무 일도 안 났다.

    여기서는 **도구가 찍는 문자열 안의 `make <타깃> <VAR>=1`**을 훑어 그 타깃이 그
    변수를 쓰는지 본다 — 화면이 거짓을 알려 주면 그것은 **없는 명령을 주는 것**이다.
    """
    made = recipes(MAKEFILE.read_text(encoding="utf-8"))
    advice = re.compile(r"make ([a-z][a-z0-9-]*)(.*)")
    """`make <타깃>`과 **그 뒤 전부.**

    첫 판은 `(?:\\s+[A-Z_]+=1)+`로 **붙어 있는 것만** 봤다. 그런데 사고가 난 문장은
    *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 `FIX=1`이 **떨어져 있었고**
    사용자는 둘을 같이 쳤다. **읽는 대로 잡는다.**
    """
    problems: list[str] = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        for number, line in printed_strings(path):
            for target, tail in advice.findall(line):
                if target not in made:
                    problems.append(
                        f"{path.relative_to(ROOT).as_posix()}:{number}: "
                        f"`make {target}`을 알려 주는데 그 타깃이 없다"
                    )
                    continue
                body = "\n".join(made[target])
                problems.extend(
                    f"{path.relative_to(ROOT).as_posix()}:{number}: "
                    f"`make {target} {variable}=1`을 알려 주는데 "
                    f"`{target}`이 `$({variable})`를 안 쓴다 — **화면이 거짓을 준다**"
                    for variable in re.findall(r"([A-Z_]+)=1", tail)
                    if variable not in set(USES.findall(body))
                )
    return problems


def check() -> list[str]:
    make = MAKEFILE.read_text(encoding="utf-8")
    problems = check_flags(make, "Makefile")
    if HOOK.exists():
        problems += check_flags(HOOK.read_text(encoding="utf-8"), ".githooks/pre-commit")
    return problems + check_passthrough(make) + check_advice()


def main() -> int:
    parser = argparse.ArgumentParser(description="부르는 쪽 ↔ 받는 쪽 인자 대조 (D-0350)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="호출과 인자를 찍는다")
    args = parser.parse_args()

    make = MAKEFILE.read_text(encoding="utf-8")
    calls = CALL.findall(make)
    if args.list:
        for tool, tail in calls:
            flags = " ".join(dict.fromkeys(FLAG.findall(tail))) or "—"
            print(f"  {tool:34s} {flags}")
        return 0

    if not calls:
        print("Makefile에서 도구 호출을 0개 읽었다. **그물이 비었다** (D-0230)", file=sys.stderr)
        return 1

    problems = check()
    if problems:
        print(f"주는 인자와 받는 인자가 어긋난 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    tools = len({tool for tool, _ in calls})
    print(f"인자 대조 검사 통과 · 호출 {len(calls)}종 · 도구 {tools}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
