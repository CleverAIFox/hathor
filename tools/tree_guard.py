#!/usr/bin/env python3
"""**시험이 실물 저장소의 코드를 고쳤나** (D-0398).

    python3 tools/tree_guard.py --snapshot   # 시험 전 지문
    python3 tools/tree_guard.py --check      # 시험 후 대조

### 무엇이 있었나

`test_mutate_gate`가 `ROOT`를 안 바꾼 채 `cut_wiring()`을 불러 **실물 `tools/tidy.py`를
「# 잘렸다」로 덮었다.** `finally`가 되돌리지만 그 창에서 끊기면 파일이 빈다 — 그가
**190줄이 비워진 트리**를 받았고 `make ship`이 막혔다. `make check`은 **전부 초록이었다.**

D-0386이 같은 부류를 막았는데 **`git` 쓰기만** 봤다. 파일 쓰기는 그물 밖이었고,
**정적으로는 안 보인다** — 쓰는 자가 시험이 아니라 **시험이 부른 도구**다.

### 왜 pytest 훅이 아닌가

처음에 `pytest_runtest_teardown`에서 터뜨렸다. **`xdist`가 무너졌다** —
*«previous item was not torn down properly»*가 줄줄이 나고 `dsession`이 INTERNALERROR로
죽는다. 시험 하나하나를 범인으로 지목하려다 **달리는 자를 망가뜨린 것**이고, 그러면
수가 아니라 잡음이 나온다 (GR-0.8).

그래서 **바깥에 선다.** 범인 이름은 못 주지만 *«무엇이 고쳐졌나»*는 정확하고,
`ONLY=`로 좁혀 다시 돌리면 사람이 찾는다. **막는 것이 먼저다.**

### 되돌리지 않는다

고치는 것은 사람의 일이다. 여기서 되돌리면 *«무엇이 쓰는가»*가 조용해진다 (GR-0.5).
`git restore <경로>`가 그 자리를 복구한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WATCHED = ("tools", "core/hathor")
"""**시험이 건드려선 안 되는 나무.**

`core/tests`는 뺀다 — `test_mutate_gate`가 빨간 시험을 **일부러 심고 지운다** (D-0359).
문서도 뺀다 — `--fix` 계열이 고치는 자리이며 `git` 쪽이 이미 본다. 그 차집합을 여기
적는 것이 선언이다 (D-0219)."""

FLOOR = 150
"""지켜보는 파일 수의 **바닥** (D-0230). 실측 `tools` 63 + `core/hathor` 154 = 217 —
경로가 틀리면 **0개를 지켜보며 「아무것도 안 바뀌었다」**를 내놓는다."""


def fingerprint() -> dict[str, list[int]]:
    """지켜보는 파일마다 (크기, mtime). **내용을 안 읽는다** — 쓰기 자체가 결함이므로
    되돌려 놓아도 걸려야 한다."""
    found: dict[str, list[int]] = {}
    for folder in WATCHED:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            stat = path.stat()
            found[path.relative_to(ROOT).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return found


def changed(before: dict[str, list[int]], after: dict[str, list[int]]) -> list[str]:
    """바뀐 · 생긴 · 사라진 파일. **빈 목록이 통과다.**"""
    names = sorted(set(before) | set(after))
    return [name for name in names if before.get(name) != after.get(name)]


def where() -> Path:
    """지문을 두는 자리. **저장소 안에 안 쓴다** — 새 파일이 `ship`의 위생에 센다."""
    stamp = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"hathor-tree-{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="시험이 실물 저장소를 고쳤나 (D-0398)")
    parser.add_argument("--snapshot", action="store_true", help="시험 전 지문을 뜬다")
    parser.add_argument("--check", action="store_true", help="시험 후 대조한다")
    args = parser.parse_args()

    found = fingerprint()
    if len(found) < FLOOR:
        print(
            f"지켜보는 파일이 {len(found)}개다(바닥 {FLOOR}). `WATCHED`가 가리키는 "
            f"자리가 비었다 (D-0230)",
            file=sys.stderr,
        )
        return 2

    if not args.check:
        where().write_text(json.dumps(found), encoding="utf-8")
        print(f"나무 지문 {len(found)}개")
        return 0

    path = where()
    if not path.exists():
        print(f"지문이 없다: {path} — `--snapshot`을 먼저 돈다 (D-0398)", file=sys.stderr)
        return 2
    before = json.loads(path.read_text(encoding="utf-8"))
    broken = changed(before, found)
    if broken:
        print(f"**시험이 실물 저장소의 파일 {len(broken)}개를 고쳤다** (D-0398):", file=sys.stderr)
        for name in broken[:10]:
            print(f"  - {name}", file=sys.stderr)
        print(
            "  → `git status`로 보고 `git restore`로 되돌린다. 쓴 자를 찾으려면 "
            "시험 파일 하나씩 돌린다 (`ONLY=` 아니라 `pytest <파일>`)",
            file=sys.stderr,
        )
        return 1
    print(f"나무 검사 통과 · 지켜본 파일 {len(found)}개 · 고쳐진 것 0개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
