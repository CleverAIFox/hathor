#!/usr/bin/env python3
"""프로파일별 메모리 상한 합계가 기기에 맞는가 (D-0262).

### 왜

D-0001이 *"core 프로파일 메모리 상한 합계 약 2.3GB → 약 2.8GB"*라고 적고 **그 수치를 내는
명령이 저장소에 없었다.** 그래서 그 결정의 «재현» 칸이 «불명»이었고, «강제자» 칸도
비어 있었다 — 선언은 `docker-compose.yml`에 실재하는데 **아무도 세지 않았다.**

세는 것과 막는 것이 같은 자리다. 합계를 찍으면 재현이 되고, 천장과 대조하면 강제가 된다.

### 8GB 노트북이 기준이다

D-0001의 판단 자체가 *"8GB RAM 노드에서"*였다. core는 늘 켜져 있고 `ml` · `obs`는 필요할
때만 올린다 — 그래서 **프로파일별로 따로 센다.** 셋을 다 켜면 8GB에 안 들어간다는 것이
그 설계의 요점이다.

### YAML을 안 읽는다

`pyyaml`은 `docs` 묶음에도 없고, 이 검사는 관문에 서므로 **맨 `python3`으로 돌아야 한다**
(D-0256). `mem_limit`과 `profiles`는 한 줄짜리라 정규식으로 충분하다.

    python3 tools/check_compose.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"

SERVICE = re.compile(r"^  ([a-z][\w-]*):\s*$")
MEM = re.compile(r"^\s+mem_limit:\s*(\d+)([gm])\s*$", re.I)
PROFILES = re.compile(r"^\s+profiles:\s*\[([^\]]*)\]\s*$")

CEILING = {"core": 2816, "ml": 2304, "obs": 768}
"""프로파일별 상한(MiB). **정본은 여기 하나다** (D-0223).

core 2816 = 2.75GB — D-0001이 *"약 2.3GB → 약 2.8GB"*로 받아들인 그 값이다.
8GB 노트북에서 core만 늘 켜 두고 나머지는 필요할 때 올린다는 전제가 이 수에 들어 있다.

늘리려면 **결정 기록이 필요하다.** 컨테이너 하나가 조용히 512m를 더 가져가는 것이
D-0001이 막으려던 일이다."""


def services(text: str) -> dict[str, tuple[int, str]]:
    """`서비스 → (MiB, 프로파일)`. 프로파일이 없으면 `core`다."""
    found: dict[str, tuple[int, str]] = {}
    name = ""
    mib = 0
    profile = "core"
    for line in text.splitlines():
        head = SERVICE.match(line)
        if head:
            if name and mib:
                found[name] = (mib, profile)
            name, mib, profile = head.group(1), 0, "core"
            continue
        if not name:
            continue
        size = MEM.match(line)
        if size:
            value = int(size.group(1))
            mib = value * 1024 if size.group(2).lower() == "g" else value
        seen = PROFILES.match(line)
        if seen:
            profile = seen.group(1).split(",")[0].strip().strip("\"'") or "core"
    if name and mib:
        found[name] = (mib, profile)
    return found


def totals(found: dict[str, tuple[int, str]]) -> dict[str, int]:
    sums: dict[str, int] = {}
    for mib, profile in found.values():
        sums[profile] = sums.get(profile, 0) + mib
    return sums


def verdict(sums: dict[str, int], ceiling: dict[str, int]) -> list[str]:
    """천장과 어긋난 것. **늘어도 줄어도 말한다** (D-0117)."""
    problems: list[str] = []
    for profile, top in ceiling.items():
        got = sums.get(profile, 0)
        if got > top:
            problems.append(f"{profile} 합계가 {got}MiB로 천장 {top}MiB를 넘는다")
        elif got < top:
            problems.append(f"{profile} 합계가 {got}MiB다. 천장 {top}MiB를 내려 박는다")
    for profile in sorted(set(sums) - set(ceiling)):
        problems.append(f"{profile} 프로파일에 천장이 없다 ({sums[profile]}MiB)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="compose 메모리 상한 합계 (D-0262)")
    parser.add_argument("--check", action="store_true")
    parser.parse_args()

    if not COMPOSE.exists():
        print(f"{COMPOSE}가 없다", file=sys.stderr)
        return 2

    found = services(COMPOSE.read_text(encoding="utf-8"))
    sums = totals(found)
    problems = verdict(sums, CEILING)
    if problems:
        print(f"compose 메모리 규약에 문제가 {len(problems)}건 있다.", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 1

    shown = " · ".join(f"{name} {sums[name] / 1024:.2f}GB" for name in sorted(sums))
    print(f"compose 메모리 검사 통과 · 서비스 {len(found)}개 · {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
