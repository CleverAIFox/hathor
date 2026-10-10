#!/usr/bin/env python3
"""**관문 전부가 작업 트리를 읽는다** (D-0380).

D-0379에서 `make apply`가 제출본을 다시 만들고 **커밋에 안 담았다.** 작업 트리는 맞고
커밋만 낡았는데 `make check`은 **초록이었다** — 관문 스물다섯이 전부 작업 트리를 읽기
때문이다. *«커밋된 산출물이 커밋된 정본과 맞는가»*를 보는 자리가 **하나도 없었다.**

### 더러운 트리를 막는 것으로는 모자라다

`ship.check_git()`이 커밋 안 된 변경을 막으므로, **트리가 깨끗하면 트리 = 커밋**이고
`make check`의 판정이 커밋에도 그대로 간다. 그 길은 이미 막혀 있다. 안 막힌 길:

| 길 | 왜 새나 |
|---|---|
| `git commit --no-verify` | 훅을 건너뛰고 아무거나 담는다 |
| `git add -p` · 부분 담기 | 트리는 깨끗한데 **담긴 조각만** 어긋난다 |
| 머지·리베이스가 낸 트리 | 어느 쪽도 안 본 조합이 생긴다 |
| `apply_patch`가 권하던 `git push` | `ship`을 건너뛰어 더러운 트리 검사가 안 돈다 |

그래서 **`HEAD`를 꺼내 거기서 돌린다.** 임시 작업 트리를 만들고 `ROOT`가 거기를
가리키게 한 뒤, 추적 파일만 읽는 관문을 돌린다.

### 왜 `make check`에 안 넣나

`make check`은 **커밋 전에** 도는 것이 정상이고, 그때 트리는 당연히 커밋과 다르다 —
넣으면 늘 빨갛고, 늘 빨간 관문은 사람이 끈다 (D-0129). 이것은 **내보내는 자리**의
관문이다. CI는 이미 커밋을 체크아웃해 도므로 같은 일을 한다 — 여기는 **밀기 전에**
같은 답을 준다.

    python3 tools/check_committed.py --check
    python3 tools/check_committed.py --check --rev HEAD~1
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GATES = (
    "tools/render_proposal.py",
    "tools/check_claims.py",
    "tools/measured.py",
    "tools/doc_fsck.py",
    "tools/check_decisions.py",
)
"""커밋된 트리에서 돌릴 관문. **추적 파일만 읽고 맨 `python3`으로 도는 것**이다.

`var/`를 읽는 관문은 못 넣는다 — git이 안 나르므로 꺼낸 트리에는 없다 (D-0369).
묶음이 필요한 것(ruff · mypy · pytest)도 못 넣는다. **늘리는 것이 목표다**: 여기
들어온 관문만 커밋을 본다.
"""

FLOOR_GATES = 4
"""돌릴 관문의 **바닥** (D-0230). 목록이 비면 「커밋도 맞다」가 거짓으로 참이 된다."""


def picked(rev: str, into: Path) -> str | None:
    """`rev`를 임시 작업 트리로 꺼낸다. 못 꺼내면 까닭."""
    done = subprocess.run(
        ["git", "worktree", "add", "-q", "--detach", str(into), rev],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if done.returncode != 0:
        return (
            (done.stderr or done.stdout).strip().splitlines()[-1:][0]
            if done.stderr
            else "까닭 모름"
        )
    return None


def dropped(into: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(into)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def judged(into: Path, gate: str) -> str | None:
    """꺼낸 트리에서 관문 하나를 돌린다. 통과면 `None`, 아니면 꼬리 한 줄.

    **꺼낸 트리의 도구를 쓴다** — 지금 작업 트리의 도구로 옛 커밋을 보면 그 커밋이
    몰랐던 규약으로 판정하게 된다.
    """
    done = subprocess.run(
        ["python3", str(into / gate), "--check"],
        cwd=into,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if done.returncode == 0:
        return None
    tail = [one for one in (done.stderr or done.stdout).strip().splitlines() if one.strip()]
    return tail[-1].strip() if tail else f"{gate}가 {done.returncode}을 냈다"


def check(rev: str = "HEAD") -> list[str]:
    if len(GATES) < FLOOR_GATES:
        return [f"돌릴 관문이 {len(GATES)}개다(바닥 {FLOOR_GATES}). **그물이 비었다**"]
    with tempfile.TemporaryDirectory() as box:
        into = Path(box) / "커밋"
        broken = picked(rev, into)
        if broken:
            return [f"`{rev}`를 못 꺼냈다 — {broken}"]
        try:
            return [
                f"커밋된 트리에서 `{gate}`가 운다: {said}"
                for gate in GATES
                if (said := judged(into, gate))
            ]
        finally:
            dropped(into)


def main() -> int:
    parser = argparse.ArgumentParser(description="커밋된 트리가 스스로 맞나 (D-0380)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--rev", default="HEAD", help="볼 커밋 (기본 HEAD)")
    args = parser.parse_args()

    problems = check(args.rev)
    if problems:
        print(f"커밋된 트리가 {len(problems)}곳 어긋난다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        print(
            "  → **작업 트리는 초록일 수 있다.** 커밋에 안 담긴 것이 있다: "
            "`git add -A && git commit --amend --no-edit` (D-0380)",
            file=sys.stderr,
        )
        return 1

    print(f"커밋 검사 통과 · `{args.rev}`를 꺼내 관문 {len(GATES)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
