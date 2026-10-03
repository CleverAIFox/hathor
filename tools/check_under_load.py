#!/usr/bin/env python3
"""**부하가 걸린 자리에서 관문을 돌려 본다** (D-0355 · D-0354에서 넘어온 빚).

### 한 갈래로는 안 보이는 결함이 있다

D-0354가 그랬다. `make_patch.sh`가 `git show … | grep -q`로 대장을 봤는데, `grep -q`가
일치하자마자 끝내고 `git show`가 아직 쓰고 있으면 `SIGPIPE`로 죽는다 — `set -o pipefail`이
그것을 실패로 읽는다. **한가하면 `git`이 먼저 끝나서 안 보인다.**

| | |
|---|---|
| 관문 하나씩 차례로 (`make check`) | 통과 |
| 시험 한 갈래 | 통과 |
| 시험 네 갈래 | **3/3 실패** |

**사용자 기기에서 터져서야 알았다.** 그때까지 이 저장소에는 **일부러 부하를 주고 관문을
도는 자리가 없었다** — `make check`은 하나씩 차례로 돌고, CI도 단계마다 하나씩 돈다.

### 어떻게

`Makefile`에서 `--check`를 받는 관문을 전부 찾아 **여러 판을 한꺼번에** 돌린다. 하나라도
빨개지면 그 관문은 부하에서 거짓 실패를 낸다 — **거짓 경보는 진짜 경보를 죽인다**
(GR-0.8). 이 부류는 더 나쁘다: **바쁜 날에만 막고 다시 돌리면 통과한다.**

    python3 tools/check_under_load.py              # 4판 · 열여섯 갈래
    python3 tools/check_under_load.py --rounds 8
    python3 tools/check_under_load.py --list
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"

GATE = re.compile(r"(?m)^\tpython3 (tools/[a-z_0-9]+\.py) --check$")
"""`make check` 사슬에서 `--check`를 받는 관문. **레시피 줄만** 본다."""

FLOOR = 15
"""읽어야 하는 관문의 **바닥** (D-0230). 실측 19개 — 정규식이 망가지면 0을 돌고 통과한다."""

WORKERS = 16
"""동시에 돌리는 갈래. D-0354는 **넷**에서 났다 — 열여섯이면 더 잘 난다."""

MINE = "check_under_load.py"
"""저 자신은 안 돈다. **제가 저를 부르면 갈래가 제곱으로 는다.**"""


def gates() -> list[str]:
    """`make check`이 부르는 관문 전부."""
    found = GATE.findall(MAKEFILE.read_text(encoding="utf-8"))
    return sorted({one for one in found if not one.endswith(MINE)})


def once(tool: str) -> tuple[str, int, str]:
    """관문 하나를 돌린다. (도구, 종료코드, 마지막 줄)."""
    done = subprocess.run(
        ["python3", tool, "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    spoke = (done.stderr or done.stdout).strip().splitlines()
    return tool, done.returncode, spoke[-1] if spoke else ""


def sweep(rounds: int, workers: int = WORKERS) -> list[tuple[str, str]]:
    """관문 전부를 `rounds`판, 한꺼번에. 빨개진 것을 돌려준다."""
    jobs = [one for _ in range(rounds) for one in gates()]
    bad: list[tuple[str, str]] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for tool, code, tail in pool.map(once, jobs):
            if code != 0:
                bad.append((tool, tail))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description="부하에서 관문이 거짓 실패하나 (D-0355)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="돌릴 관문을 찍는다")
    parser.add_argument("--rounds", type=int, default=4, help="몇 판 돌릴까 (기본 4)")
    args = parser.parse_args()

    found = gates()
    if args.list:
        for one in found:
            print(f"  {one}")
        print(f"  관문 {len(found)}개")
        return 0

    if len(found) < FLOOR:
        print(
            f"관문을 {len(found)}개 읽었다(바닥 {FLOOR}). **그물이 비었다** (D-0230)",
            file=sys.stderr,
        )
        return 1

    bad = sweep(args.rounds)
    if bad:
        print(
            f"부하에서 빨개진 관문이 {len(bad)}곳이다 — **한가할 때는 안 보인다** (D-0354).",
            file=sys.stderr,
        )
        for tool, tail in bad:
            print(f"  - {tool}: {tail}", file=sys.stderr)
        return 1

    print(f"부하 검사 통과 · 관문 {len(found)}개 x {args.rounds}판 · 갈래 {WORKERS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
