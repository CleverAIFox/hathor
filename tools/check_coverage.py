#!/usr/bin/env python3
"""커버리지 바닥 래칫. **숫자는 한 곳에만 산다** (D-0223).

### 왜 필요한가

바닥 `83`이 Makefile과 `ci.yml` **두 곳에 손으로** 적혀 있었다. fire-lane이 똑같은 모양으로
«로컬 초록 · CI 빨강»을 겪었다 — 한쪽만 고친 날이다. 그리고 실측이 88%대인데 바닥이 83이라
**5%p가 놀고 있었다.** 그 사이로 시험 없는 코드가 조용히 들어올 수 있다.

### 두 방향으로 본다

| 방향 | 규칙 |
|---|---|
| 아래 | 실측 < 바닥 → pytest가 빨개진다 (`fail_under`) |
| 위 | 실측 ≥ 바닥 + `SLACK` → 여기서 빨개진다. `make cov-bump`로 바닥을 올린다 |

파일 길이 래칫(D-0117)과 같은 규율이다 — **톱니가 한 칸씩 올라가고 되돌아가지 않는다.**
`SLACK`을 두는 것은 기기마다 실측이 1%p 안팎 갈리기 때문이다(GPU 묶음 유무로 건너뛰는
시험이 다르다). 바닥은 **실측 - 1**로 올린다.

바닥의 정본은 `core/pyproject.toml`의 `[tool.coverage.report] fail_under` 하나다.

    python3 tools/check_coverage.py            # pytest --cov 뒤에 부른다
    python3 tools/check_coverage.py --update   # 바닥을 실측 - 1로 올린다
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "core" / "pyproject.toml"
SLACK = 3.0
FLOOR = re.compile(r"^(fail_under\s*=\s*)(\d+(?:\.\d+)?)\s*$", re.M)


def floor(text: str) -> float:
    found = FLOOR.search(text)
    if not found:
        raise LookupError("core/pyproject.toml에 `fail_under`가 없다 — 바닥의 정본이 사라졌다")
    return float(found.group(2))


def measured() -> float:
    """마지막 `pytest --cov`가 남긴 `.coverage`의 총합."""
    result = subprocess.run(
        ["uv", "run", "--no-sync", "coverage", "report", "--format=total", "--precision=2"],
        cwd=ROOT / "core",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise LookupError(
            f"커버리지 자료가 없다. pytest --cov를 먼저 돌린다 ({result.stderr.strip()})"
        )
    return float(result.stdout.strip())


def verdict(actual: float, bottom: float) -> str | None:
    """문제가 있으면 문장, 없으면 `None`."""
    if actual < bottom:
        return f"커버리지 {actual:.2f}%가 바닥 {bottom:g}%보다 낮다"
    if actual >= bottom + SLACK:
        return (
            f"커버리지 {actual:.2f}%가 바닥 {bottom:g}%보다 {SLACK:g}%p 이상 높다 — "
            "`make cov-bump`로 바닥을 올린다"
        )
    return None


def bumped(text: str, actual: float) -> str:
    return FLOOR.sub(lambda m: f"{m.group(1)}{math.floor(actual) - 1}", text, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="커버리지 바닥 래칫 (D-0223)")
    parser.add_argument("--update", action="store_true", help="바닥을 실측 - 1로 올린다")
    args = parser.parse_args()
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        bottom, actual = floor(text), measured()
    except LookupError as error:
        print(f"커버리지 래칫 도구가 죽었다: {error}", file=sys.stderr)
        return 2
    if args.update:
        new = bumped(text, actual)
        if floor(new) <= bottom:
            print(f"바닥 {bottom:g}%를 내리지 않는다. 실측 {actual:.2f}%")
            return 0
        PYPROJECT.write_text(new, encoding="utf-8")
        print(f"바닥 {bottom:g}% → {floor(new):g}% (실측 {actual:.2f}%)")
        return 0
    problem = verdict(actual, bottom)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    print(f"커버리지 래칫 통과 · 실측 {actual:.2f}% · 바닥 {bottom:g}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
