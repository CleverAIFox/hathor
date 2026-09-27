#!/usr/bin/env python3
"""결정이 **금지한 것**이 코드에 들어왔는가 (D-0261).

### 왜 필요한가

§3에 «설계 판단 **13건**에 강제 수단이 없다»가 오래 적혀 있었다. 그중 D-0003은
문서 표가 *"어기면 가장 나쁜 것"*으로 이름을 부른 둘 중 하나이고, 짝인 D-0015는
D-0134가 `check_egress`로 이미 못 박았다.

**첫 삽에 걸렸다.** `tools/step0_check.py`의 VRAM 계획표에 *"RVC v2 학습 — 가창 음색
변환"*이 6GB 항목으로 앉아 있었다. D-0003이 **구현하지 않는다**고 적은 바로 그것이
장비 계획에 남아 있었고, 검사가 없어서 아무도 안 봤다.

### 구멍이 0일 때 못 박는다

`check_egress`와 같은 모양이다 (D-0134). 지금 위반이 0이므로 **지금 박으면 앞으로 못
들어온다.** 위반이 쌓인 뒤에 박으려면 래칫이 필요하고, 래칫은 «0이어야 하는 것»에는
맞지 않는다.

### 문자열로 막을 수 있는 것만 막는다

«실존 가수 음색을 복제하지 않는다»는 판단이고 기계가 못 읽는다. 그러나 그 판단을
어기려면 **부르는 이름이 있다** — `rvc` · `so-vits` · `speaker_encoder`. 이름을 막는
것은 판단을 막는 것이 아니지만, **판단을 어기는 가장 흔한 길을 막는다.**

    python3 tools/check_forbidden.py --check
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREES = ("core/hathor", "tools")
"""**제품 코드와 도구만 본다.** 결정 기록은 금지어를 설명하느라 그 낱말을 쓴다."""

FORBIDDEN: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "음색 복제": (
        "D-0003",
        "실존 가수의 음색 복제·보간은 구현하지 않는다. 화자 공간은 라이선스가 명확한 "
        "공개 다화자 DB로만 만들고 보간은 익명 화자 공간 안에서만 한다",
        (
            r"\brvc\b",
            r"so[-_]?vits",
            r"\bxtts\b",
            r"openvoice",
            r"\bvall-?e\b",
            r"speaker[_-]?(embedding|encoder)",
            r"voiceprint",
            r"\b[dx]-vector\b",
        ),
    ),
    "호칭": (
        "D-0012",
        "취향 웜스타트는 Bradley-Terry를 임베딩 공간 위에서 적합하는 것이다. "
        "«랜덤 포레스트»라고 부르지 않는다 — 이름이 틀리면 설계를 오해한다",
        (r"랜덤\s*포레스트", r"RandomForest"),
    ),
    "DrvFs 복사": (
        "D-0120 · D-0122",
        "DrvFs 경계를 넘는 복사는 메타데이터를 보존하지 않는다. `copy2`는 거기서 "
        "죽는다 — D-0120이 함수 하나를 고쳤고 D-0122가 «모든 복사가 같은 자리»라고 "
        "부류를 지목했다",
        (r"shutil\.copy2", r"shutil\.copytree"),
    ),
}
"""금지한 것 · 그 결정 · 사유 · 찾을 꼴.

**사유를 적는 자리가 표 안에 있다.** 검사가 빨개졌을 때 사람이 «왜 막혔나»를 결정
기록까지 가서 찾아야 하면, 그 사람은 패턴을 지우는 쪽을 고른다."""

SELF = Path(__file__).name
"""**자기 자신은 안 본다** (D-0261).

금지할 이름을 적어 두는 자리가 바로 여기다. 처음에 이 예외가 없었고 — 파일이 커밋되기
전에는 `git ls-files`에 없어 보이지 않다가, **커밋되자마자 자기 패턴 여덟 줄에 걸렸다.**
`check_secrets`가 자기 정규식에 걸리지 않는 것과 같은 자리다."""

ALLOW = "# forbidden-ok:"
"""줄 끝에 이 표식과 사유가 있으면 넘어간다. **선언 없는 면제는 없다** (D-0219)."""


def tracked() -> list[Path]:
    """git이 아는 파일만. 추적 안 되는 찌꺼기까지 보면 잡음이 된다."""
    done = subprocess.run(
        ["git", "ls-files", *TREES], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        return [path for tree in TREES for path in (ROOT / tree).rglob("*.py") if path.name != SELF]
    return [
        ROOT / name
        for name in done.stdout.split()
        if name.endswith((".py", ".toml", ".md")) and Path(name).name != SELF
    ]


def hits(text: str, patterns: tuple[str, ...]) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW in line:
            continue
        for pattern in patterns:
            if re.search(pattern, line, re.I):
                found.append((number, line.strip()[:90]))
                break
    return found


def survey() -> list[str]:
    problems: list[str] = []
    for path in sorted(tracked()):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name, (decision, reason, patterns) in FORBIDDEN.items():
            for number, line in hits(text, patterns):
                where = path.relative_to(ROOT)
                problems.append(f"{where}:{number} [{name} · {decision}] {line}\n      {reason}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="결정이 금지한 것을 막는다 (D-0261)")
    parser.add_argument("--check", action="store_true")
    parser.parse_args()

    problems = survey()
    if problems:
        print(f"결정이 금지한 것이 {len(problems)}곳 있다.", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        print(f"\n  뜻이 있어 남긴다면 줄 끝에 `{ALLOW} <사유>`", file=sys.stderr)
        return 1
    print(f"금지 검사 통과 · 부류 {len(FORBIDDEN)}개 · 파일 {len(tracked())}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
