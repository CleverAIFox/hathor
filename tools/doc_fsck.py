#!/usr/bin/env python3
"""문서가 가리키는 것이 실물로 있는가 (D-0189).

    python3 tools/doc_fsck.py

### 왜 생겼나

강제자가 여덟인데 **전부 문서 ↔ 문서**였다. 색인이 기록과 맞는가, 표기가 규약과
맞는가, 레이아웃이 맞는가. **문서 ↔ 실물을 보는 것이 하나도 없었다.**

`fire-lane`의 `doc_fsck.py`가 같은 자리에서 생겼고 거기 적힌 말이 그대로 맞는다 —
*"읽으면 보이는데 아무도 안 읽었다."* 이 저장소에서도 같은 일이 났다.

| 실제로 난 일 | 언제 |
|---|---|
| `PLAN §1`이 없는 `tools/probe_keys.py`를 가리켰다 | D-0182 |
| 탐침이 `find_keys_store`에 엉뚱한 인자를 넘겼다 | D-0180 |
| 재현 절이 `cd core` 기준 상대 경로를 적어 빈손이 됐다 | D-0153이 검사를 만든 뒤에도 |

### 무엇을 보나

| | 무엇 |
|---|---|
| 경로 | 문서가 적은 `tools/x.py` · `core/...`가 실재하는가 |
| 명령 | `재현` 절의 `python3 tools/x.py`가 실재하는가 |
| 도구 | `tools/*.py`가 문서 어디서든 불리는가 (죽은 도구) |

### 무엇을 안 보나

**자연어 모순은 안 잡는다.** *"A 문서와 B 문서가 다른 말을 한다"*를 기계가 판정하려면
두 서술의 의미를 비교해야 하고 그것은 이 도구의 범위가 아니다. 여기서 보는 것은
**구조뿐이다** — 판단이 아니라 대조다.

**결정 기록 본문의 옛 경로는 안 잡는다.** 기록은 그때를 적는 문서이고 소급해서
고치지 않는다 (GR-0.2 · D-0081). 지금을 말하는 문서만 본다.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIVING = ("README.md", "docs/MASTER.md", "docs/PLAN.md")
"""**지금을 말하는 문서만 본다.** `DECISIONS.md`는 과거라 옛 경로가 정상이다."""

PATH_LIKE = re.compile(r"`((?:tools|core|docs|web|infra|docker)/[\w./\-]+\.\w+)`")
"""백틱 안의 저장소 경로. **백틱 밖은 안 본다** — 산문의 예시와 구분이 안 된다."""

SKIP_SUFFIXES = (".mp3", ".mid", ".npz", ".jsonl", ".json", ".patch")
"""산출물은 `.park` 뒤에 있어 없는 것이 정상이다 (D-0075)."""


def living_documents() -> list[Path]:
    return [ROOT / name for name in LIVING if (ROOT / name).exists()]


def check_paths() -> list[str]:
    """문서가 적은 경로가 실재하는가."""
    problems: list[str] = []
    for path in living_documents():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in dict.fromkeys(PATH_LIKE.findall(line)):
                if found.endswith(SKIP_SUFFIXES):
                    continue
                if not (ROOT / found).exists():
                    problems.append(f"{name}:{number}: `{found}`가 없다")
    return problems


def check_commands() -> list[str]:
    """문서가 적은 `python3 tools/x.py`가 실재하는가."""
    runner = re.compile(r"python3?\s+(?:\.\./)?(tools/[\w./\-]+\.py)")
    problems: list[str] = []
    for path in living_documents():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in dict.fromkeys(runner.findall(line)):
                if not (ROOT / found).exists():
                    problems.append(f"{name}:{number}: 명령이 부르는 `{found}`가 없다")
    return problems


def check_orphan_tools() -> list[str]:
    """문서 어디서도 안 불리는 도구가 있는가.

    **`DECISIONS.md`까지 센다.** 도구는 과거 기록이 부르기만 해도 살아 있다 —
    *"왜 만들었나"*가 거기 있기 때문이다.
    """
    blob = "".join(
        path.read_text(encoding="utf-8")
        for path in [*living_documents(), ROOT / "docs" / "DECISIONS.md", ROOT / "Makefile"]
        if path.exists()
    )
    problems: list[str] = []
    for tool in sorted((ROOT / "tools").glob("*.py")):
        if tool.name not in blob:
            problems.append(f"tools/{tool.name}: 문서 어디서도 안 불린다. 쓰이는가")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="문서 ↔ 실물 대조 (D-0189)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.parse_args()

    problems = check_paths() + check_commands() + check_orphan_tools()
    if problems:
        print(f"문서가 없는 것을 가리키는 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        f"문서 대조 검사 통과 · 문서 {len(living_documents())}개 · 도구 "
        f"{len(list((ROOT / 'tools').glob('*.py')))}개"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
