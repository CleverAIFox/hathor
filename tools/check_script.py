#!/usr/bin/env python3
"""**화면의 스크립트를 보는 관문** (D-0368).

fire-lane의 협업 방침 화면은 JS를 안 쓴다. 까닭이 *«이 페이지의 스크립트를 보는 검사가
없으므로 여기 스크립트가 들어가면 검사 밖에서 자란다»*였다 — **JS가 나쁘다는 말이
아니라 관문이 없다는 말이다.**

기획서 화면은 2단 절 22개에 표 78개 · 그림 28장이 담긴 164KB짜리라 **찾기**와 **지금
보는 절 표시**가 필요하다. 둘 다 CSS로는 안 된다. 그래서 JS를 쓰고 **관문을 같이 둔다.**

`node`가 없는 기기에서는 **안 쟀다고 적는다** (GR-0.5 · `check_patch`의 `--no-live`와
같은 규율). 못 잰 것을 통과로 적으면 그것이 거짓 초록이다.

    python3 tools/check_script.py --check
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ("site/proposal.js",)
"""문법을 보는 스크립트. **늘면 여기 적는다** — 목록이 한 벌이다."""

FLOOR = 1
"""봐야 하는 스크립트의 **바닥** (D-0230). 목록이 비면 「전부 맞다」가 거짓이 된다."""


def targets() -> list[Path]:
    return [ROOT / name for name in SCRIPTS]


def missing() -> list[str]:
    return [name for name in SCRIPTS if not (ROOT / name).is_file()]


def syntax(path: Path) -> str | None:
    """`node --check`. 통과면 `None`, 깨지면 까닭."""
    done = subprocess.run(
        ["node", "--check", str(path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if done.returncode == 0:
        return None
    tail = (done.stderr or done.stdout).strip().splitlines()
    return tail[0] if tail else "까닭 모름"


def embedded() -> list[str]:
    """**화면에 박힌 스크립트가 그 파일과 같은가** (D-0043).

    렌더러가 파일을 통째로 박으므로 두 벌이 아니다. 다만 **박는 쪽을 누가 고치면**
    화면만 바뀐다 — 그것을 본다.
    """
    screen = ROOT / "site" / "proposal.html"
    if not screen.is_file():
        return ["site/proposal.html이 없다 — 생성물을 커밋한다"]
    body = screen.read_text(encoding="utf-8")
    return [
        f"{name}의 본문이 화면에 박혀 있지 않다 — 렌더러가 다른 것을 넣었다"
        for name in SCRIPTS
        if (ROOT / name).is_file() and (ROOT / name).read_text(encoding="utf-8") not in body
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="화면 스크립트 문법 (D-0368)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.parse_args()

    problems = [f"{name}가 없다" for name in missing()]
    if len(SCRIPTS) < FLOOR:
        problems.append(f"볼 스크립트가 {len(SCRIPTS)}개다(바닥 {FLOOR}). **그물이 비었다**")
    problems += embedded()

    where = shutil.which("node")
    if where and not problems:
        problems += [
            f"{path.relative_to(ROOT).as_posix()}: 문법이 깨졌다 — {said}"
            for path in targets()
            if (said := syntax(path))
        ]

    if problems:
        print(f"화면 스크립트에 문제가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1

    # **못 잰 것을 통과로 적지 않는다** (GR-0.5).
    ran = "문법 실측" if where else "문법 **안 쟀다**(node 없음)"
    print(f"화면 스크립트 검사 통과 · {len(SCRIPTS)}개 · {ran}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
