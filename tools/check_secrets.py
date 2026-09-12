#!/usr/bin/env python3
"""추적 중인 파일에 비밀정보가 들어갔는가 (D-0128).

### 왜 필요한가

`CONTRIBUTING` §5.5가 *"코드에 비밀정보 금지. `.env` + 환경 변수. **CI가 시크릿
스캔을 돌린다**"*라고 적었다. **CI에 그 단계가 없었다.** 열한 단계를 전부 확인했고
색인·조각·표기·길이·린트·타입·아키텍처·테스트·취약점·결정성뿐이다.

D-0126이 잡은 것과 같은 부류인데 한 칸 더 나쁘다.

| | 무엇이 없었나 |
|---|---|
| D-0121 | 검사가 있는데 안 불린다 |
| D-0126 | 규약이 있는데 검사가 없다 |
| **D-0128** | **규약이 "검사가 돈다"고 적었는데 그 검사가 없다** |

### 무엇을 보는가 — 둘뿐이다

1. **무시 목록에 있는 파일이 추적되고 있는가.** `.env`가 `.gitignore`에 있어도
   `git add -f`는 통과한다. `git ls-files`로 직접 본다.
2. **추적 중인 파일에 값이 채워진 자격증명이 있는가.** `.env.example`처럼 빈 값이나
   `change-me`는 통과시킨다 — **예시는 공유되라고 있는 것이다.**

### 무엇을 안 보는가

**범용 시크릿 스캐너가 아니다.** 고엔트로피 문자열 탐지는 오탐이 많고, 오탐이 많은
검사는 꺼진다 (D-0126에서 엄격 규칙을 기각한 것과 같은 이유). 여기서 잡는 것은
**이 저장소가 실제로 흘릴 수 있는 모양**이다.

이력(과거 커밋)은 안 본다. 그것은 훅과 `git filter-repo`의 일이고, 훅이 걸려 있는지는
`doctor`가 본다.

    python3 tools/check_secrets.py            # 검사한다
    python3 tools/check_secrets.py --list     # 추적 파일 수를 찍는다
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = (".env",)
"""이름만으로 추적을 금지하는 파일. **`.env.example`은 여기 안 걸린다** (정확히 비교한다)."""

PLACEHOLDER_PREFIXES = ("change-me", "changeme", "your-", "xxx", "<", "{")
"""값이 아닌 것들. `.env.example`이 `change-me-min-8-chars`처럼 쓰므로 **앞자리로 본다.**"""

ASSIGNMENT = re.compile(
    r"(?<!\$\{)\b([A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|API_?KEY|ACCESS_?KEY|PRIVATE_KEY)[A-Z0-9_]*)"
    r"\s*[=:]\s*[\"']?([^\s\"',;)]+)"
)
"""`PASSWORD=값` 꼴. **낱말이 아니라 대입을 본다** — 산문에서 \'비밀번호\'를 말하는 것은
비밀정보가 아니다.

**`TOKEN`은 뺐다.** 파서 코드의 `TOKEN_AND`·`value_token`을 전부 잡는다 — 실측 오탐이
1600곳이었다. **오탐이 많은 검사는 꺼진다** (D-0126에서 엄격 규칙을 기각한 이유와 같다).
대문자 이름만 보는 것도 같은 까닭이다.

**`${VAR:-기본값}`은 대입이 아니라 참조다.** `docker-compose.yml`이 그렇게 쓰고,
안 빼면 셋이 오탐으로 잡힌다."""

SKIP_SUFFIXES = (".patch", ".lock")
"""패치와 잠금 파일은 건너뛴다. 둘 다 다른 파일의 사본이며 원본 쪽에서 이미 본다."""

SKIP_TREES = ("core/tests/",)
"""검사 나무는 건너뛴다. **비밀정보 검사의 검사는 비밀정보 모양을 가질 수밖에 없다.**

`check_issue_mentions`가 같은 이유로 `core/tests`를 뺀다. **대가가 있다** — 검사에
진짜 값을 적으면 안 잡힌다. `.env` 추적 검사는 그대로 걸리므로 주된 새는 자리는 막힌다."""


def tracked() -> list[str]:
    """`git ls-files`. 저장소가 아니면 빈 목록이다."""
    try:
        done = subprocess.run(
            ("git", "ls-files"),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return done.stdout.split() if done.returncode == 0 else []


def check(names: list[str]) -> list[str]:
    """추적 목록을 본다. **첫 문제에서 멈추지 않는다.**"""
    problems: list[str] = []
    for name in names:
        if Path(name).name in FORBIDDEN:
            problems.append(f"{name}: 추적되고 있다. `git rm --cached {name}` 후 값을 갈아치운다")
    for name in names:
        path = ROOT / name
        if name.startswith(SKIP_TREES) or path.suffix in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for key, value in ASSIGNMENT.findall(line):
                low = value.lower()
                if value.startswith("$") or low.startswith(PLACEHOLDER_PREFIXES):
                    continue
                problems.append(f"{name}:{number}: {key}에 값이 박혀 있다. .env로 옮긴다")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="비밀정보 검사 (D-0128)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="추적 파일 수를 찍는다")
    args = parser.parse_args()

    names = tracked()
    if args.list:
        print(f"추적 파일 {len(names)}개")
        return 0
    if not names:
        print("git 추적 목록을 못 읽었다. 저장소가 아니거나 git이 없다", file=sys.stderr)
        return 1

    problems = check(names)
    if problems:
        print(f"비밀정보로 보이는 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"비밀정보 검사 통과 · 추적 {len(names)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
