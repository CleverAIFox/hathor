#!/usr/bin/env python3
"""**CI가 git이 안 나르는 자리를 읽으면 거기서만 터진다** (D-0369).

D-0368이 배포 잡에 `cp var/proposal/figures/*.png _site/figures/`를 넣었다. `var/`는
`.gitignore`에 있다 — **내 기기에는 있고 러너에는 없다.** `make check`은 초록이었고
배포만 빨갰다. 이 부류는 **로컬에서 영원히 안 보인다.**

### 무엇을 보나

워크플로의 `run:` 줄에 나오는 저장소 경로 중 **`.gitignore`가 덮는 자리**를 찾고,
**같은 잡이 그것을 만들지 않으면** 문제로 든다. 만드는 자리는 `--out` · `-o` ·
`mkdir` · `>` 뒤에 그 경로가 나오는 것으로 본다 — `_site/`처럼 **그 잡이 짓고 그
잡이 읽는** 자리가 정상이기 때문이다.

**순서는 안 본다.** 같은 잡 안에 만드는 줄이 있으면 통과시킨다 — 순서까지 따지면
`run: |` 블록 안의 여러 줄을 세어야 하고, 그 정교함이 거짓 경보를 낳는다 (GR-0.8).

### 왜 따로 사나

`check_args.py`가 이미 워크플로를 읽지만 **570줄이라 상한(600)이 가깝다.**
`check_retired`를 가른 그 까닭과 같다 — **도구를 키우는 대신 가른다** (D-0349).

    python3 tools/check_workflow_paths.py --check
    python3 tools/check_workflow_paths.py --list     # 덮인 자리와 만드는 자리를 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = ROOT / ".gitignore"
FLOWS = ROOT / ".github" / "workflows"

FLOOR_ROOTS = 5
"""`.gitignore`가 덮는 최상위 디렉터리의 **바닥** (D-0230).

목록이 비면 **아무것도 안 걸러도 「전부 맞다」가 된다.** 실측 16개다.
"""

TOKEN = re.compile(r"[A-Za-z0-9_][\w./*-]*/[\w./*-]+")
MAKES = re.compile(r"(?:--out|-o|mkdir(?:\s+-\w+)*|>)[ \t]+(\S+)")
"""만드는 자리. `>`는 리다이렉션이고, YAML의 접힘 표시(`run: >`)는 줄 끝이라 안 걸린다."""


def ignored_roots() -> list[str]:
    """`.gitignore`가 덮는 **최상위 디렉터리** 이름.

    `var/`처럼 슬래시로 끝나고 안쪽 경로가 아닌 줄만 센다 — `notebooks/.ipynb_checkpoints/`
    같은 안쪽 자리는 그 위가 추적되므로 **읽어도 된다.**
    """
    found = []
    for line in GITIGNORE.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#") or not name.endswith("/"):
            continue
        body = name.removeprefix("/").removesuffix("/")
        if "/" not in body:
            found.append(body + "/")
    return sorted(set(found))


def jobs(text: str) -> list[str]:
    """워크플로를 **잡 단위로** 자른다. 들여쓰기 두 칸이 잡 이름이다."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^  \w[\w-]*:\s*$", line)]
    if not starts:
        return [text]
    return ["\n".join(lines[a:b]) for a, b in zip(starts, [*starts[1:], len(lines)], strict=True)]


def shell_text(job: str) -> str:
    """잡 안에서 **셸로 도는 줄만** 모은다 — `uses:`나 주석은 뺀다."""
    kept, inside = [], False
    for line in job.splitlines():
        bare = line.strip()
        if bare.startswith("#"):
            continue
        if re.match(r"^\s*(?:-\s*)?run:", line):
            inside = True
            kept.append(line)
            continue
        if inside and (not bare or line.startswith(" " * 10)):
            kept.append(line)
            continue
        inside = False
    return "\n".join(kept)


def reads(job: str, roots: list[str]) -> set[str]:
    """그 잡이 **덮인 자리에서 읽는** 경로."""
    body = shell_text(job)
    return {
        token
        for token in TOKEN.findall(body)
        if any(token.removeprefix("../").startswith(root) for root in roots)
    }


def writes(job: str) -> set[str]:
    """그 잡이 **만드는** 경로. 순서는 안 본다."""
    return {one.strip("'\"") for one in MAKES.findall(shell_text(job))}


def covered(path: str, made: set[str]) -> bool:
    """만든 자리 **아래**면 통과. `_site/figures`를 만들고 `_site/figures/a.png`를 읽는다."""
    bare = path.removeprefix("../")
    return any(bare.startswith(one.removeprefix("../").rstrip("/")) for one in made)


def check() -> list[str]:
    roots = ignored_roots()
    problems: list[str] = []
    if len(roots) < FLOOR_ROOTS:
        return [f"`.gitignore`가 덮는 최상위가 {len(roots)}개다(바닥 {FLOOR_ROOTS}). 그물이 비었다"]
    for path in sorted(FLOWS.glob("*.yml")):
        where = path.relative_to(ROOT).as_posix()
        for job in jobs(path.read_text(encoding="utf-8")):
            made = writes(job)
            problems += [
                f"{where}: `{one}`은 `.gitignore`가 덮는다 — "
                "git이 안 나르므로 **러너에는 없다.** 같은 잡이 만들거나 경로를 바꾼다 (D-0369)"
                for one in sorted(reads(job, roots))
                if not covered(one, made)
            ]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="워크플로가 읽는 자리를 git이 나르나 (D-0369)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="덮인 자리와 만드는 자리를 찍는다")
    args = parser.parse_args()

    roots = ignored_roots()
    if args.list:
        print(f"덮는 최상위 {len(roots)}개: {roots}")
        for path in sorted(FLOWS.glob("*.yml")):
            for job in jobs(path.read_text(encoding="utf-8")):
                seen = reads(job, roots)
                if seen:
                    print(f"  {path.name:<16} 읽음 {sorted(seen)} · 만듦 {sorted(writes(job))}")
        return 0

    problems = check()
    if problems:
        print(f"워크플로가 안 날아가는 자리를 {len(problems)}곳 읽는다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1

    flows = len(list(FLOWS.glob("*.yml")))
    print(f"워크플로 경로 검사 통과 · 워크플로 {flows}개 · 덮는 최상위 {len(roots)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
