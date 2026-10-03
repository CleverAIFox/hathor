#!/usr/bin/env python3
"""**래칫을 느슨하게 박은 자리를 세는 자가 없었다** (D-0352 · D-0350에서 넘어온 빚).

### 느슨해진 래칫은 초록으로 위장한다

`check_sight`가 *"`--update --loosen`에는 결정 기록이 필요하다"*고 화면에 적는다.
**규약이고, 아무도 안 셌다.** 못을 내려 박고 기록을 안 쓰면 그 판은 영원히 초록이다 —
`fire-lane`은 커버리지 래칫이 14인데 실물이 그 아래인 것을 **나흘 몰랐다.**

### 세는 법 — 부모 커밋과 대조한다

못의 값은 소스에 산다. 그러니 **직전 판의 값과 비교하면** 어느 쪽으로 움직였는지
기계가 안다. 느슨해졌는데 그 커밋이 `docs/DECISIONS.md`를 안 건드렸으면 **막는다.**
(`check_patch`가 쓰는 것과 같은 길이고, CI는 `fetch-depth: 2`로 받는다.)

### 어떤 상수가 못인가 — 이름으로 가린다

정수 상수 74개를 세어 보니 대부분 **시험 치수**(`DIM` · `DEGREES` · `SR`)였다. 눈으로
골랐으면 다음 판에 또 골라야 하고 빠뜨린다. 그래서 **이름 어휘**로 가린다 — `FLOOR` ·
`CEILING` · `UNTESTED` · `UNTYPED` · `UNKNOWN` · `…_FROM`. 어휘에 걸린 이름은 **반드시
`NAILS`에 방향이 선언돼 있어야 한다** (`check_sight`가 상수에 하는 것과 같다).

`check_sight.PINNED`는 여기서 안 본다 — **정본은 하나다** (D-0117). 그쪽은 저 자신이
방향을 알고 `--loosen`을 막는다.

    python3 tools/check_ratchets.py            # 부모와 대조한다
    python3 tools/check_ratchets.py --list     # 못과 방향을 찍는다
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAST = "docs/DECISIONS.md"

VOCABULARY = ("FLOOR", "CEILING", "UNTESTED", "UNTYPED", "UNKNOWN")
"""못임을 알리는 이름 조각. 끝이 `_FROM`인 것도 못이다 (강제 시작점)."""

OWNED_ELSEWHERE = ("check_sight.PINNED",)
"""저 자신이 방향을 알고 `--loosen`을 막는 것. **정본은 하나다** (D-0117)."""

NAILS = {
    "허용": "천장",
    "천장": "천장",
    "바닥": "바닥",
    "강제 시작": "천장",
}
"""부류 → 느슨해지는 방향. **「천장」은 오르면 느슨하고, 「바닥」은 내리면 느슨하다.**

`강제 시작`(`…_FROM`)이 천장인 것이 헷갈린다 — **늦게 강제하면 덜 강제한다.**
`FORMAT_ENFORCED_FROM = 80`을 81로 올리면 기록 하나가 형식 검사 밖으로 빠진다.
"""

KINDS = {
    "FLOOR": "바닥",
    "CEILING": "천장",
    "UNTESTED": "천장",
    "UNTYPED": "천장",
    "UNKNOWN": "천장",
}
"""이름 조각 → 부류. `_FROM`은 아래에서 따로 붙인다."""

SOURCES = ("tools/*.py", "core/tests/unit/test_*.py")


def kind(name: str) -> str | None:
    """그 상수가 어느 부류의 못인가. 못이 아니면 `None`."""
    for piece, which in KINDS.items():
        if piece in name:
            return which
    return "강제 시작" if name.endswith("_FROM") else None


def nails(text: str) -> dict[str, int]:
    """한 파일의 못. 정수는 그 값, 정수 묶음은 **키마다 한 못**이다.

    **`ast`로 읽는다** — 임포트하면 그 파일의 부작용이 돈다 (`check_sight`와 같은 규율).
    """
    found: dict[str, int] = {}
    for node in ast.parse(text).body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for one in targets:
            if not isinstance(one, ast.Name) or not one.id.isupper() or not kind(one.id):
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, int):
                found[one.id] = value.value
            elif isinstance(value, ast.Dict):
                for key, item in zip(value.keys, value.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and isinstance(item, ast.Constant)
                        and isinstance(item.value, int)
                    ):
                        found[f"{one.id}[{key.value}]"] = item.value
    return found


def here_text(path: str) -> str:
    """지금 작업 트리에서 읽는다."""
    return (ROOT / path).read_text(encoding="utf-8")


def measure(read: Callable[[str], str] = here_text) -> dict[str, int]:
    """저장소 전체의 못. 키는 `모듈.상수`다.

    `read`를 주면 그것으로 파일을 읽는다 — 부모 커밋을 같은 코드로 재는 데 쓴다.
    """
    opened = read
    found: dict[str, int] = {}
    for pattern in SOURCES:
        for path in sorted(ROOT.glob(pattern)):
            short = path.relative_to(ROOT).as_posix()
            try:
                text = opened(short)
            except (OSError, subprocess.CalledProcessError):
                continue
            for name, value in nails(text).items():
                found[f"{path.stem}.{name}"] = value
    return {key: value for key, value in found.items() if key not in OWNED_ELSEWHERE}


def at(commit: str) -> dict[str, int]:
    """그 커밋의 못. **지금의 파일 목록으로 훑는다** — 새 파일은 부모에 없으니 건너뛴다."""

    def read(path: str) -> str:
        return subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        ).stdout

    return measure(read)


def loosened(before: dict[str, int], after: dict[str, int]) -> list[str]:
    """느슨해진 자리. **사라진 못은 늘 느슨해지는 쪽이다** (D-0349)."""
    report: list[str] = []
    for key, was in sorted(before.items()):
        name = key.split(".", 1)[1].split("[", 1)[0]
        which = NAILS[kind(name) or "천장"]
        now = after.get(key)
        if now is None:
            report.append(f"{key}: {was} → **사라졌다**")
        elif which == "천장" and now > was:
            report.append(f"{key}: 천장 {was} → {now} (올랐다)")
        elif which == "바닥" and now < was:
            report.append(f"{key}: 바닥 {was} → {now} (내렸다)")
    return report


def git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    return done.stdout


def touched(commit: str) -> set[str]:
    """그 커밋이 건드린 파일."""
    listed = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    return {one for one in listed.split("\n") if one}


def pending() -> set[str]:
    """아직 커밋 안 된 변경. 추적 안 된 파일까지 (D-0222의 그 자리)."""
    return {
        line[3:].strip('"') for line in git("status", "--porcelain", "-uall").split("\n") if line
    }


def commit(which: str) -> str | None:
    found = git("rev-parse", "--verify", "-q", f"{which}^{{commit}}").strip()
    return found or None


def against() -> tuple[str | None, set[str], str]:
    """**무엇과 비교하고, 기록을 어디서 찾는가.**

    짝을 틀리면 검사가 거짓이 된다 — 첫 판이 작업 트리를 `HEAD`의 **부모**와 비교하면서
    기록은 `HEAD`의 커밋에서 찾았다. 둘이 다른 판이다.

    | | 비교 상대 | 기록을 찾는 곳 |
    |---|---|---|
    | 작업 트리가 더럽다 (`make check` · 커밋 훅) | `HEAD` | 커밋 안 된 변경 |
    | 깨끗하다 (CI · 머지 뒤) | `HEAD^` | `HEAD`가 건드린 파일 |
    """
    dirty = pending()
    if dirty:
        return commit("HEAD"), dirty, "작업 트리 ↔ HEAD"
    return commit("HEAD~1"), touched("HEAD"), "HEAD ↔ 부모"


def check() -> tuple[list[str], str]:
    """느슨해진 자리와 **무엇을 쟀는지**. 못 쟀으면 그렇게 말한다 (GR-0.5)."""
    here = measure()
    if len(here) < FLOOR_NAILS:
        return (
            [f"못을 {len(here)}개 읽었다(바닥 {FLOOR_NAILS}). **그물이 비었다** (D-0230)"],
            "못 쟀다",
        )
    older, changed, how = against()
    if older is None:
        return [], "비교 상대 없음 · **안 돌렸다**"
    slack = loosened(at(older), here)
    if slack and PAST in changed:
        return [], f"{how} · 느슨 {len(slack)}곳 · 기록 있다"
    if slack:
        return (
            [
                *slack,
                f"**느슨해진 래칫은 초록으로 위장한다.** `{PAST}`에 무엇을 왜 내려 박았는지"
                " 쓴다 (D-0352 · D-0118의 `GROW=1`과 같은 규율)",
            ],
            f"{how} · 느슨 {len(slack)}곳 · **기록 없다**",
        )
    return [], f"{how} · 조였거나 그대로"


FLOOR_NAILS = 25
"""읽어야 하는 못의 **바닥** (D-0230). 실측 29개 — 어휘가 망가지면 0이 되고 통과한다."""


def main() -> int:
    parser = argparse.ArgumentParser(description="래칫이 느슨해진 자리 (D-0352)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="못과 방향을 찍는다")
    args = parser.parse_args()

    here = measure()
    if args.list:
        for key, value in sorted(here.items()):
            name = key.split(".", 1)[1].split("[", 1)[0]
            print(f"  {key:46s} {NAILS[kind(name) or '천장']:4s} {value}")
        print(f"  못 {len(here)}개")
        return 0

    problems, what = check()
    if problems:
        print(f"래칫이 느슨해졌다 — {what}", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"래칫 검사 통과 · 못 {len(here)}개 · {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
