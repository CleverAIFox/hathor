#!/usr/bin/env python3
"""파일 길이 래칫. **양방향이다** (D-0117).

### 왜 필요한가

`import-linter`는 임포트 **방향**만 본다. 로직이 어느 계층에 **얼마나** 있는가는
아무도 안 봤고, 그 결과 `interfaces/cli/main.py`가 4161줄이 됐다 — 프로덕션 코드의
31%, 미커버 구문의 67%가 한 파일이었다 (D-0116).

GR-2.2가 "interfaces에 로직 금지"라 적혀 있고 `main.py` 첫 줄에도 그렇게 쓰여 있다.
**검사할 수 없는 규약은 잊힌다** (GR-0.8). 4161줄이 그 증거다.

### 왜 양방향인가

상한만 걸면 예외값에 영원히 머문다. `main.py`를 3866으로 못 박고 상한만 보면
3865줄이 되어도 아무 일도 안 일어나고, 다음 세션에 3866까지 도로 붇는다.

**줄었을 때도 실패시켜 예외값을 낮추게 한다.** 톱니가 한 칸씩 내려가고 되돌아갈 수
없다. `--cov-fail-under`를 75에서 83으로 올린 것과 같은 규율이며, 그것은 손으로
하고 있었으나 여기서는 도구가 시킨다.

### 무엇을 세는가

**빈 줄과 주석을 포함한 전체 줄이다.** 유효 줄만 세면 문서 문자열을 지워 통과할 수
있고, 이 저장소는 근거를 문서 문자열에 적는다 — 그것을 벌하면 안 된다.

    python3 tools/check_file_size.py            # 검사한다
    python3 tools/check_file_size.py --update   # 예외표를 현재 값으로 다시 쓴다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

LIMITS = {
    "code": 600,
    "test": 700,
}
"""기본 상한. **예외표에 없는 파일에 걸린다.**

실측에서 고른 값이다 (D-0117). 이 상한에서 예외가 코드 3개·테스트 0개였다.
더 조이면 예외표가 길어져 표 자체가 규약이 되고, 더 풀면 아무것도 안 잡는다.
"""

TREES = {
    "code": ("core/hathor", "tools"),
    "test": ("core/tests",),
}

# ---------------------------------------------------------------- 예외표 시작
EXCEPTIONS: dict[str, int] = {
    "core/hathor/application/evaluate_harmony_output.py": 663,
    "core/hathor/domain/services/key_estimation.py": 760,
    "core/hathor/interfaces/cli/main.py": 3880,
}
# ---------------------------------------------------------------- 예외표 끝
"""넘고 있는 파일을 **현재 줄 수로 못 박은 것**이다. 상한이 아니라 래칫이다.

늘면 실패한다. **줄어도 실패한다** — `--update`로 낮추라고 시킨다. 소급해서
쪼개지 않는다 (D-0081의 "표기는 전수, 내용은 신규만"과 같은 규율).

새 파일은 여기 없으므로 기본 상한이 걸린다. **예외를 손으로 더하지 않는다** —
`--update`만이 이 표를 쓴다.
"""

BLOCK = re.compile(r"(# -+ 예외표 시작\nEXCEPTIONS: dict\[str, int\] = \{\n)(.*?)(\})", re.DOTALL)


def kind_of(path: str) -> str | None:
    """그 파일이 어느 상한을 받는가. 대상 밖이면 `None`."""
    for kind, trees in TREES.items():
        if any(path.startswith(f"{tree}/") for tree in trees):
            return kind
    return None


def measure() -> dict[str, int]:
    """대상 파일의 `상대경로 → 줄 수`. **경로 구분자는 항상 `/`다.**

    윈도우에서 `\\`가 나오면 예외표가 기기마다 다르게 읽힌다 (D-0009).
    """
    found: dict[str, int] = {}
    for kind, trees in TREES.items():
        del kind
        for tree in trees:
            base = ROOT / tree
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                name = path.relative_to(ROOT).as_posix()
                found[name] = path.read_text(encoding="utf-8").count("\n") + 1
    return found


def check(sizes: dict[str, int]) -> list[str]:
    """상한과 래칫을 본다. **첫 문제에서 멈추지 않는다.**"""
    problems: list[str] = []

    for name in sorted(set(EXCEPTIONS) - set(sizes)):
        problems.append(f"예외표에 없는 파일이 있다: {name}. --update로 지운다")

    for name, lines in sorted(sizes.items()):
        kind = kind_of(name)
        if kind is None:
            continue
        pinned = EXCEPTIONS.get(name)
        if pinned is None:
            if lines > LIMITS[kind]:
                problems.append(
                    f"{name}: {lines}줄로 {kind} 상한 {LIMITS[kind]}줄을 넘는다. 쪼갠다"
                )
            continue
        if lines > pinned:
            problems.append(
                f"{name}: {lines}줄로 못 박은 {pinned}줄보다 늘었다. 되돌리거나 쪼갠다"
            )
        elif lines < pinned:
            problems.append(
                f"{name}: {lines}줄로 {pinned}줄에서 줄었다. --update로 래칫을 내린다"
            )
    return problems


def render(sizes: dict[str, int]) -> str:
    """예외표를 다시 그린다. 기본 상한 아래로 내려온 파일은 표에서 사라진다."""
    rows = {
        name: lines
        for name, lines in sizes.items()
        if (kind := kind_of(name)) is not None and lines > LIMITS[kind]
    }
    body = "".join(f'    "{name}": {lines},\n' for name, lines in sorted(rows.items()))
    return body


def update(allow_growth: bool) -> int:
    """예외표를 현재 값으로 쓴다. **올리는 것은 기본으로 막는다** (D-0118).

    막지 않으면 래칫이 아니다 — "늘었다"가 떠도 `make resize` 한 번이면 사라지고,
    그것은 상한만 있는 것과 같다. **올리려면 이유를 결정 기록에 적고 `--allow-growth`를
    준다.** 손이 한 번 멈추는 것이 요점이다.
    """
    sizes = measure()
    grown = {
        name: (pinned, sizes[name])
        for name, pinned in EXCEPTIONS.items()
        if name in sizes and sizes[name] > pinned
    }
    if grown and not allow_growth:
        print("예외값을 올리려 한다. 래칫은 기본으로 이것을 막는다.", file=sys.stderr)
        for name, (pinned, now) in sorted(grown.items()):
            print(f"  - {name}: {pinned} -> {now} (+{now - pinned})", file=sys.stderr)
        print("\n  쪼개서 되돌리거나, 이유를 결정 기록에 적고:", file=sys.stderr)
        print("  python3 tools/check_file_size.py --update --allow-growth", file=sys.stderr)
        return 1

    text = SELF.read_text(encoding="utf-8")
    found = BLOCK.search(text)
    if found is None:
        print("예외표 표식을 찾지 못했다", file=sys.stderr)
        return 2
    SELF.write_text(
        text[: found.start(2)] + render(sizes) + text[found.end(2) :], encoding="utf-8"
    )
    print(f"예외표 갱신 ({len(render(sizes).splitlines())}건)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="파일 길이 래칫 (D-0117)")
    parser.add_argument("--update", action="store_true", help="예외표를 현재 값으로 다시 쓴다")
    parser.add_argument(
        "--allow-growth", action="store_true", help="예외값을 올린다. 결정 기록에 이유를 적는다"
    )
    args = parser.parse_args()

    if args.update:
        return update(args.allow_growth)

    problems = check(measure())
    if problems:
        print(f"파일 길이 규약에 문제가 {len(problems)}건 있다.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"파일 길이 검사 통과 · 예외 {len(EXCEPTIONS)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
