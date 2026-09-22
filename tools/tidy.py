#!/usr/bin/env python3
"""로컬 찌꺼기를 센다. `--yes`일 때만 치운다 (D-0225).

### 왜 필요한가

Dependabot이 PR마다 `dependabot/...` 브랜치를 만든다. PR이 닫히면 원격에서는 지워져도
**로컬에는 추적 참조가 남고,** `git fetch`마다 새 것이 딸려 온다. 패치 폴더에는 이미 적용한
`D0xxx.patch`가 쌓인다. 둘 다 **조용히 틀린 것을 부르는** 자리다 — fire-lane의 `tidy.py`가
세 번의 사고로 생긴 이유와 같다(옛 스크립트를 같은 이름으로 다시 돌렸다 · 지워진 원격을 따라가
`pull`이 실패했다).

| 무엇 | 판정 | `--yes` |
|---|---|---|
| 원격이 사라진 로컬 브랜치 (`[gone]`) | 따라갈 곳이 없다 | `git branch -D` |
| 봇 브랜치 추적 참조 (`origin/dependabot/*`) | 로컬에 둘 이유가 없다 | `git branch -rd` |
| 봇 브랜치를 받아 오는 설정 | 다음 fetch가 또 가져온다 | 음수 refspec을 건다 |
| 끊긴 작업 트리 | 폴더가 사라졌다 | `git worktree prune` |
| 적용된 패치 (`HATHOR_PATCH_DIR`) | 제목이 로그에 있다 | `applied/`로 옮긴다 · **안 지운다** |

### 무엇을 안 건드리나

**`var/` · `.venv/` · 작업 트리의 파일.** 산출물은 찌꺼기가 아니다 (D-0067).
**GitHub의 원격 브랜치.** 닫힌 봇 PR의 브랜치는 Dependabot이 지운다 — 사람이 머지한 PR의
브랜치는 저장소 설정 «Automatically delete head branches»가 지운다. 여기서 원격에 쓰지 않는다.

    python3 tools/tidy.py          # 센다 (기본). 망을 안 탄다
    python3 tools/tidy.py --yes    # 치운다. `git fetch --prune`을 먼저 한다
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOT_PREFIX = "dependabot/"
BOT_REFSPEC = "^refs/heads/dependabot/*"
PATCH_ENV = "HATHOR_PATCH_DIR"
APPLIED = "applied"
COMMIT_MARK = "# hathor-commit:"


@dataclass(frozen=True)
class Finding:
    kind: str
    items: tuple[str, ...]
    fix: tuple[tuple[str, ...], ...]
    """치우는 명령. 비었으면 파이썬이 직접 한다(패치 옮기기)."""


def git(*arguments: str, stderr: bool = False) -> list[str]:
    """줄 목록. 실패하면 빈 목록. `worktree prune --dry-run`은 표준 오류로 말한다."""
    done = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        return []
    text = done.stdout + (done.stderr if stderr else "")
    return [line for line in text.splitlines() if line.strip()]


def dotenv(name: str) -> str | None:
    """셸이 이긴다. 없으면 `.env`에서 읽는다 (D-0066)."""
    if os.environ.get(name):
        return os.environ[name]
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.strip().partition("=")
        if key.strip() == name and value.strip():
            return value.strip().strip("\"'")
    return None


def gone_branches(rows: list[str], current: str) -> list[str]:
    """`이름 [gone]` 행에서 이름만. **지금 선 브랜치는 뺀다** — 지울 수 없고 지우면 안 된다."""
    return [row.split()[0] for row in rows if row.endswith("[gone]") and row.split()[0] != current]


def bot_refs(rows: list[str]) -> list[str]:
    return [row for row in rows if row.split("/", 1)[-1].startswith(BOT_PREFIX)]


def patch_subject(path: Path) -> str | None:
    """패치 첫 줄의 커밋 제목. 표식이 없으면 이 저장소의 패치가 아니다."""
    try:
        first = path.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
    except OSError:
        return None
    return first.removeprefix(COMMIT_MARK).strip() if first.startswith(COMMIT_MARK) else None


def applied_patches(folder: Path, subjects: set[str]) -> list[Path]:
    """제목이 커밋 로그에 있는 패치. **폴더 맨 위만 본다** — `applied/` 안은 이미 옮긴 것이다."""
    return sorted(path for path in folder.glob("*.patch") if patch_subject(path) in subjects)


def survey() -> list[Finding]:
    found: list[Finding] = []
    current = next(iter(git("rev-parse", "--abbrev-ref", "HEAD")), "")
    gone = gone_branches(
        git("for-each-ref", "--format=%(refname:short) %(upstream:track)", "refs/heads"),
        current,
    )
    if gone:
        found.append(
            Finding("원격이 사라진 브랜치", tuple(gone), (("git", "branch", "-D", *gone),))
        )
    bots = bot_refs(git("for-each-ref", "--format=%(refname:short)", "refs/remotes"))
    if bots:
        found.append(
            Finding("봇 브랜치 추적 참조", tuple(bots), (("git", "branch", "-rd", *bots),))
        )
    remotes = git("remote")
    if "origin" in remotes and BOT_REFSPEC not in git("config", "--get-all", "remote.origin.fetch"):
        found.append(
            Finding(
                "봇 브랜치를 받아 오는 설정",
                ("remote.origin.fetch에 음수 refspec이 없다",),
                (("git", "config", "--add", "remote.origin.fetch", BOT_REFSPEC),),
            )
        )
    stale = git("worktree", "prune", "--dry-run", "--verbose", stderr=True)
    if stale:
        names = tuple(line.removeprefix("Removing ").split(":", 1)[0] for line in stale)
        found.append(Finding("끊긴 작업 트리", names, (("git", "worktree", "prune"),)))
    folder = dotenv(PATCH_ENV)
    if folder and Path(folder).is_dir():
        subjects = set(git("log", "--format=%s", "-n", "2000"))
        done = applied_patches(Path(folder), subjects)
        if done:
            found.append(Finding("적용된 패치", tuple(path.name for path in done), ()))
    return found


def sweep(finding: Finding) -> None:
    for command in finding.fix:
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
    if finding.kind == "적용된 패치":
        folder = Path(dotenv(PATCH_ENV) or "")
        (folder / APPLIED).mkdir(exist_ok=True)
        for name in finding.items:
            (folder / name).replace(folder / APPLIED / name)


def report(found: list[Finding]) -> list[str]:
    """`make ship`도 이 줄을 찍는다 — 세는 규칙이 두 곳에 살지 않는다."""
    lines: list[str] = []
    for finding in found:
        head = " · ".join(finding.items[:3])
        more = f" 외 {len(finding.items) - 3}" if len(finding.items) > 3 else ""
        lines.append(f"{finding.kind} {len(finding.items)}: {head}{more}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="로컬 찌꺼기 (D-0225)")
    parser.add_argument("--yes", action="store_true", help="치운다. 없으면 세기만 한다")
    args = parser.parse_args()

    if args.yes and "origin" in git("remote"):
        subprocess.run(["git", "fetch", "--prune", "origin"], cwd=ROOT, check=False)
    found = survey()
    if not found:
        print("깨끗하다")
        return 0
    for line in report(found):
        print(f"  {line}")
    if not args.yes:
        print("세기만 했다. 치우려면 `make tidy YES=1`")
        return 0
    failed = 0
    for finding in found:
        # **첫 실패에서 멈추지 않는다.** 하나가 막혀도 나머지는 치운다.
        try:
            sweep(finding)
        except (subprocess.CalledProcessError, OSError) as error:
            print(f"{finding.kind}를 못 치웠다: {error}", file=sys.stderr)
            failed += 1
    print(f"치웠다 · {len(found) - failed}종 · 실패 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
