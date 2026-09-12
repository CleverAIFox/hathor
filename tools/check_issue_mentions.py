#!/usr/bin/env python3
"""닫힌 미해결 질문을 코드가 **열린 것처럼** 적고 있는가 (D-0126).

### 왜 필요한가

`O-38`은 D-0114가 닫았다. 그런데 `sweep_self_transition`과 `harmony_generator`의
문서 문자열이 *"안 움직이면 짐작이 틀린 것이고 O-38(닫힘 D-0114)은 다른 원인을 찾아야 한다"*고
**살아 있는 질문처럼 적고 있었다.**

D-0125 세션이 그것을 읽고 O-38을 두 판 끌었다. **미해결표를 안 보고 코드 문서
문자열을 봤다.** 기획서에는 닫혔다고 적혀 있었고 코드에는 안 적혀 있었다.

### 규약은 이미 있었다

닫힌 질문 열셋 중 일곱은 코드에서 `(O-31 · D-0083)`처럼 **닫은 결정을 같이 적는다.**
지키는 자리가 다수였고 O-38(D-0114)만 안 지켰다. **적혀 있는데 안 지켜지는 규약이 GR-0.8이
말한 그것이다** — D-0117의 `main.py` 4161줄과 같은 부류다.

### 규칙

**닫힌 질문 번호를 적으면 같은 줄에 그 질문을 닫은 결정 번호를 적는다.**

- 닫힌 질문과 그 결정 번호는 `docs/DESIGN.md`의 닫힘표에서 읽는다. **여기 손으로
  적지 않는다** — 두 곳이 어긋난다 (D-0043).
- **열린 질문은 안 본다.** 열린 질문에는 닫은 결정이 없다.
- **결정 번호면 무엇이든 통과시킨다.** 닫은 결정을 콕 집어 요구하는 안은 기각했다 —
  `evaluate_degree_restriction.py`가 `(O-31 · D-0083)`이라 적는데 D-0083은 그 모듈을
  **만든** 결정이고 닫은 것은 D-0088이다. **둘 다 참이고 출처 쪽이 더 쓸모 있다.**
  엄격 규칙은 옳게 적은 줄 24곳을 잡았다. 막으려는 것은 **맨몸 참조**다.

### 무엇을 안 보는가

`docs/`는 안 본다. 결정 기록은 **닫히기 전 시점을 그대로 적는 문서**이고, 거기에
사후 번호를 달게 하면 기록이 기록이 아니게 된다 (D-0081의 *"소급해서 고치지 않는다"*).

    python3 tools/check_issue_mentions.py            # 검사한다
    python3 tools/check_issue_mentions.py --list     # 닫힌 질문과 결정을 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLOSED_BEGIN = "<!-- closed-issues:begin -->"
CLOSED_END = "<!-- closed-issues:end -->"

TREES = ("core/hathor", "tools")
"""훑을 코드 나무. **`core/tests`는 뺀다** — 검사 이름이 질문 번호를 갖는 것은 정상이다."""

DOCUMENTS = ("README.md", "CONTRIBUTING.md")
"""훑을 문서. **`docs/`는 안 본다** — 결정 기록은 그 시점을 그대로 적는다."""

ISSUE = re.compile(r"O-\d+")
DECISION = re.compile(r"D-(\d{4})")
ROW = re.compile(r"^\|\s*(O-\d+)\s*\|")


def closed_issues(design_text: str) -> dict[str, set[int]]:
    """닫힌 질문 → 그 행이 가리키는 결정 번호들.

    **닫힘표가 정본이다.** 이 파일에 목록을 적지 않는다.
    """
    if CLOSED_BEGIN not in design_text or CLOSED_END not in design_text:
        return {}
    block = design_text.split(CLOSED_BEGIN)[1].split(CLOSED_END)[0]
    found: dict[str, set[int]] = {}
    for row in block.splitlines():
        match = ROW.match(row)
        if match:
            found[match.group(1)] = {int(value) for value in DECISION.findall(row)}
    return found


def targets() -> list[Path]:
    """훑을 파일. 정렬해 낸다 — **문제 순서가 기기마다 달라지면 못 읽는다.**"""
    found: list[Path] = []
    for tree in TREES:
        base = ROOT / tree
        if base.is_dir():
            found.extend(
                path
                for path in sorted(base.rglob("*.py"))
                if "__pycache__" not in path.parts
            )
    found.extend(ROOT / name for name in DOCUMENTS if (ROOT / name).exists())
    return found


def check(design_text: str) -> list[str]:
    """규칙을 어긴 자리를 전부 낸다. **첫 문제에서 멈추지 않는다.**"""
    table = closed_issues(design_text)
    if not table:
        return [f"DESIGN에 {CLOSED_BEGIN} 표식이 없다"]
    problems: list[str] = []
    for path in targets():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            annotated = bool(DECISION.search(line))
            for issue in dict.fromkeys(ISSUE.findall(line)):
                closers = table.get(issue)
                if closers is None or annotated:
                    continue
                wanted = " · ".join(f"D-{value:04d}" for value in sorted(closers))
                problems.append(
                    f"{name}:{number}: {issue}은 닫혔는데 맨몸으로 적혀 있다. "
                    f"같은 줄에 결정을 적는다 (닫힘표: {wanted})"
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="닫힌 질문 표기 검사 (D-0126)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="닫힌 질문과 결정을 찍는다")
    args = parser.parse_args()

    design_text = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    if args.list:
        for issue, closers in closed_issues(design_text).items():
            joined = " · ".join(f"D-{value:04d}" for value in sorted(closers))
            print(f"  {issue}  {joined}")
        return 0

    problems = check(design_text)
    if problems:
        print(f"닫힌 질문을 열린 것처럼 적은 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"닫힌 질문 표기 검사 통과 · 닫힘 {len(closed_issues(design_text))}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
