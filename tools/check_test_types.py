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

PINNED = {
    "arg-type": 19,
    "no-untyped-def": 15,
    "list-item": 8,
    "index": 7,
    "no-any-return": 6,
    "attr-defined": 4,
    "union-attr": 3,
    "operator": 2,
    "call-overload": 1,
    "valid-type": 1,
}
"""**부류별로** 못을 박는다 (D-0151).

D-0150이 합계를 박았고 다음 기기에서 `assignment`가 하나 나왔는데 **총 67이라는
것만 알 수 있었다.** 부류별로 박으면 어긋난 순간 **어느 줄을 봐야 하는지가 나온다.**

늘리려면 `--update --allow-growth`와 결정 기록이 필요하다 (D-0118).
**손이 한 번 멈추는 것이 요점이다.**"""


def total(counts: dict[str, int]) -> int:
    return sum(counts.values())


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


def _report(counts: dict[str, int], raw: str) -> None:
    """**어긋난 부류의 실제 줄까지 찍는다.** 부류만 보면 또 한 판 물어야 한다."""
    codes = sorted(set(counts) | set(PINNED))
    print(f"타입 오류가 {total(counts)}건으로 못 박은 {total(PINNED)}건과 다르다.", file=sys.stderr)
    for code in codes:
        now, pinned = counts.get(code, 0), PINNED.get(code, 0)
        mark = "" if now == pinned else ("  ←늘" if now > pinned else "  ←줄")
        print(f"  {code:<20}{now:>4} / {pinned:<4}{mark}", file=sys.stderr)
    for code in codes:
        if counts.get(code, 0) > PINNED.get(code, 0):
            for line in raw.splitlines():
                if line.rstrip().endswith(f"[{code}]"):
                    print(f"    {line.strip()}", file=sys.stderr)


def _rewrite(counts: dict[str, int]) -> None:
    """못을 다시 박는다. **정렬해 쓴다** — 차례가 기기마다 달라지면 못 읽는다."""
    path = Path(__file__)
    text = path.read_text(encoding="utf-8")
    head = text.index("PINNED = {")
    tail = text.index("}", head) + 1
    body = "\n".join(
        f'    "{code}": {count},'
        for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )
    path.write_text(text[:head] + "PINNED = {\n" + body + "\n}" + text[tail:], encoding="utf-8")


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

    grown = any(count > PINNED.get(code, 0) for code, count in counts.items())
    if args.update:
        if grown and not args.allow_growth:
            _report(counts, raw)
            print("줄이거나 `--allow-growth`와 결정 기록을 함께 낸다 (D-0118).", file=sys.stderr)
            return 1
        _rewrite(counts)
        print(f"못을 {total(PINNED)} → {found}로 다시 박았다.")
        return 0

    if counts != PINNED:
        _report(counts, raw)
        print(
            "새로 쓴 검사의 타입을 맞춘다." if grown else "`--update`로 못을 내려 박는다.",
            file=sys.stderr,
        )
        return 1
    print(f"검사 코드 타입 래칫 통과 · {found}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
