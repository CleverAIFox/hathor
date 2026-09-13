#!/usr/bin/env python3
"""내보내도 되는가 — 푸시 전후를 한 줄로 잇는다 (D-0147).

    make ship              검사만 한다. 아무것도 안 바꾼다
    make ship PUSH=1       통과하면 push 하고 교두보까지 보낸다

### 왜 만들었나

도구는 열다섯이고 **파이프라인이 없었다.** `make check`가 여섯 단계를 묶는 것이
전부이고, 푸시 전후의 순서는 사람 머리에 있었다.

    make check  &&  git push  &&  make artifacts-push ONLY=keys

**손으로 기억하는 목록은 언젠가 하나를 빠뜨린다.** 이 세션만 해도 `make check` 없이
패치를 붙인 적이 있고, 교두보 보내기를 잊은 채 다음 작업으로 넘어간 적이 있다.

### 지우지 않는다

찌꺼기를 **세어서 보고만 한다.** 무엇이 쌓이는지 실측하지 않은 채 지우는 정책을
만들면 그것이 지어낸 규칙이다 (GR-0.5). `.backup/`과 `.o7-*/`는 D-0072가 없앤
유물이라 지금은 안 쌓여야 하고, **쌓여 있다면 그 사실이 소식이다.**

`--fix`는 `make clean`이 이미 하는 것만 한다 — 파이썬 바이트코드다.

### `make check`와 겹치지 않는다

| | 무엇을 보는가 |
|---|---|
| `make check` | **코드와 문서가 규약과 맞는가** |
| `make ship` | **내보내도 되는가** — 위 + git 상태 + 위생 + 산출물 |

`ship`이 `make check`를 부른다. **중복 구현하지 않는다.**
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
OFF = "\033[0m"

LEFTOVERS = (".backup", ".o7-*")
"""D-0072가 없앤 유물. **쌓여 있다면 그 사실이 소식이다.**"""


def _run(*command: str) -> tuple[int, str]:
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return done.returncode, (done.stdout + done.stderr).strip()


def _git(*arguments: str) -> str:
    code, text = _run("git", *arguments)
    return text if code == 0 else ""


def check_git() -> list[str]:
    """워킹트리 · 브랜치 · 미푸시 커밋. **깨끗하지 않으면 내보내지 않는다.**"""
    problems: list[str] = []
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        problems.append(f"워킹트리에 커밋 안 된 변경이 {len(dirty.splitlines())}개 있다")
    if not _git("rev-parse", "--abbrev-ref", "@{upstream}"):
        problems.append("upstream이 없다. `git push -u origin <브랜치>`")
    return problems


def count_leftovers() -> list[str]:
    """찌꺼기를 **센다. 지우지 않는다.**"""
    found: list[str] = []
    for pattern in LEFTOVERS:
        hits = [path for path in ROOT.glob(pattern) if path.exists()]
        if hits:
            found.append(f"{pattern}가 {len(hits)}개 있다. D-0072가 없앤 유물이다")
    caches = len(list(ROOT.rglob("__pycache__")))
    if caches > 0:
        found.append(f"`__pycache__` {caches}개. `make clean` 또는 `PUSH=1 FIX=1`")
    scripts = [path.name for path in ROOT.glob("*.sh")]
    if scripts:
        found.append(f"루트에 일회성 스크립트 {len(scripts)}개: {' · '.join(scripts[:3])}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="내보내도 되는가 (D-0147)")
    parser.add_argument("--push", action="store_true", help="통과하면 push하고 교두보로 보낸다")
    parser.add_argument("--fix", action="store_true", help="바이트코드를 지운다")
    parser.add_argument("--only", default="keys", help="교두보로 보낼 세트 (D-0119)")
    args = parser.parse_args()

    if args.fix:
        _run("find", ".", "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+")

    print(f"{DIM}── 규약 (make check){OFF}")
    code, text = _run("make", "check")
    if code != 0:
        print(f"{RED}   막힘{OFF}  {text.strip().splitlines()[-1] if text else ''}")
        print("\n`make check`를 먼저 초록으로 만든다.", file=sys.stderr)
        return 1
    print(f"{GREEN}   통과{OFF}")

    print(f"{DIM}── git{OFF}")
    problems = check_git()
    for line in problems:
        print(f"{RED}   막힘{OFF}  {line}")
    if not problems:
        ahead = _git("rev-list", "--count", "@{upstream}..HEAD")
        print(f"{GREEN}   통과{OFF}  미푸시 커밋 {ahead or '0'}개")

    print(f"{DIM}── 위생 (세기만 한다){OFF}")
    leftovers = count_leftovers()
    for line in leftovers or ["깨끗하다"]:
        print(f"{DIM}   {line}{OFF}")

    print(f"{DIM}── 산출물 (교두보){OFF}")
    code, text = _run("python3", "tools/sync_artifacts.py", "status")
    if code != 0:
        # **교두보가 없는 기기도 있다.** 막지 않고 알리기만 한다 (D-0068).
        print(f"{DIM}   교두보를 못 읽었다. `make setup`{OFF}")
    else:
        for line in text.splitlines()[-3:]:
            print(f"{DIM}   {line.strip()}{OFF}")

    if problems:
        return 1
    if not args.push:
        print("\n내보낼 준비가 됐다. `make ship PUSH=1`")
        return 0

    print(f"\n{DIM}── push{OFF}")
    code, text = _run("git", "push")
    print(text.strip().splitlines()[-1] if text else "")
    if code != 0:
        return 1
    code, text = _run("python3", "tools/sync_artifacts.py", "push", "--only", args.only)
    print(text.strip().splitlines()[-1] if text else "")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
