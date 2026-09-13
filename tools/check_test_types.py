#!/usr/bin/env python3
"""검사 코드의 타입 오류 래칫 (D-0149).

### 왜 래칫인가

`core/tests`가 `mypy` 밖이었다 (D-0146이 남긴 자리). 걸어 보니 **`--strict`에서
1421건**이고 그중 **1111건이 `-> None` 없음**이다. 테스트 함수 1100개에 반환형을
붙이는 것은 기계적이지만 **값이 그만큼이 아니다** — 테스트는 돌려서 검증된다.

주석 요구를 빼면 **75건**이며 이쪽은 값이 있다. 실제로 제품 코드의 거짓말을 짚었다 —
`beat_period`·`phase_profile`이 `Sequence[float]`이라 선언하고 언제나 `ndarray`로
불리고 있었고, 그 서명을 고쳐 여섯 건이 사라졌다.

- **한 번에 고치면** 25파일에 걸친 큰 차이가 되고 테스트 뜻이 바뀔 위험이 있다.
- **안 걸면** 다음 세션이 76번째를 더한다.

**래칫이 그 사이다.** D-0117이 파일 길이에 쓴 것을 타입 검사에 그대로 쓴다 —
늘면 빨개지고 줄이면 못을 내려 박는다.

### 주석은 요구하지 않는다

`--allow-untyped-defs` · `--allow-untyped-calls`로 돈다. **`-> None` 1111개는 잡음이고
잡음이 많으면 검사를 끈다** (D-0126 · D-0129에서 되풀이해 확인한 것이다).

    python3 tools/check_test_types.py            # 검사한다
    python3 tools/check_test_types.py --update   # 못을 다시 박는다
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"

PINNED = 66
"""지금 못 박힌 오류 수. **늘면 빨개진다.**

이 수를 올리려면 `--update --allow-growth`와 결정 기록이 필요하다 — D-0118이 파일
길이에서 세운 규율과 같다. **손이 한 번 멈추는 것이 요점이다.**"""

COMMAND = (
    "mypy",
    "tests",
    "--explicit-package-bases",
    "--allow-untyped-defs",
    "--allow-untyped-calls",
)

CODE = re.compile(r"error: .*\[([a-z-]+)\]\s*$")

VOLATILE = frozenset({"import-not-found", "import-untyped", "unused-ignore"})
"""기기마다 생겼다 없어지는 부류. **세지 않는다** (D-0150).

첫 못이 75였는데 다른 기기에서 76이 나왔다. **같은 코드에서 수가 다르면 래칫이
아니다.** `unused-ignore`는 스텁이 깔렸는지에 따라 달라지고 `import-not-found`는
`MYPYPATH`에 따라 달라진다.

**세는 것이 흔들리면 그 수로 한 판단도 흔들린다** — D-0148에서 `.venv`를 찌꺼기로
센 것과 같은 부류다."""


def measure() -> int | None:
    """오류 수. 못 재면 `None`이다 — **0으로 넘기지 않는다** (GR-0.5)."""
    raw = _mypy()
    return None if raw is None else sum(tally(raw).values())


def _mypy() -> str | None:
    """`mypy` 출력 그대로."""
    try:
        done = subprocess.run(
            ("uv", "run", *COMMAND),
            cwd=CORE,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout + done.stderr


def tally(text: str) -> dict[str, int]:
    """부류별 오류 수. **어긋났을 때 어디가 다른지 바로 보이게 한다.**"""
    found: dict[str, int] = {}
    for line in text.splitlines():
        match = CODE.search(line)
        if match and match.group(1) not in VOLATILE:
            found[match.group(1)] = found.get(match.group(1), 0) + 1
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="검사 코드 타입 래칫 (D-0149)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--update", action="store_true", help="못을 다시 박는다")
    parser.add_argument("--allow-growth", action="store_true", help="늘어도 박는다 (D-0118)")
    args = parser.parse_args()

    raw = _mypy()
    if raw is None:
        print("타입 검사를 못 돌렸다. `cd core && uv sync --group dev`", file=sys.stderr)
        return 1
    counts = tally(raw)
    found = sum(counts.values())

    if args.update:
        if found > PINNED and not args.allow_growth:
            print(f"{found}건으로 못 박은 {PINNED}건보다 늘었다.", file=sys.stderr)
            print("줄이거나 `--allow-growth`와 결정 기록을 함께 낸다 (D-0118).", file=sys.stderr)
            return 1
        path = Path(__file__)
        text = path.read_text(encoding="utf-8")
        fixed = text.replace(f"PINNED = {PINNED}", f"PINNED = {found}", 1)
        path.write_text(fixed, encoding="utf-8")
        print(f"못을 {PINNED} → {found}로 다시 박았다.")
        return 0

    if found != PINNED:
        direction = "늘었다" if found > PINNED else "줄었다"
        print(f"타입 오류가 {found}건으로 못 박은 {PINNED}건보다 {direction}.", file=sys.stderr)
        for code, count in sorted(counts.items(), key=lambda item: -item[1]):
            print(f"  {code:<20}{count:>4}", file=sys.stderr)
        hint = (
            "새로 쓴 검사의 타입을 맞춘다." if found > PINNED else "`--update`로 못을 내려 박는다."
        )
        print(hint, file=sys.stderr)
        return 1
    print(f"검사 코드 타입 래칫 통과 · {found}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
