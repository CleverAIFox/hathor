#!/usr/bin/env python3
"""`docs/DESIGN.md` 부록 A를 `docs/DECISIONS.md`에서 생성하고 어긋남을 검사한다.

### 왜 필요한가

부록 A는 41행짜리 손유지 요약표였고 **이미 어긋나 있었다** (D-0042).

- D-0003 결정 기록: "실존 가수의 음색 복제·보간은 **구현하지 않는다**"
  부록 A: "실존 가수 음색은 **식별 가능한 산출물만 금지**"
  → 안전 관련 항목인데 두 문장의 뜻이 다르다.
- D-0015의 MASTER.md 폐기가 부록 A에 없다. D-0008 행에 곁다리로 붙어 있을 뿐이다.
  D-0039를 쓰게 만든 그 누락이 부록 A에 그대로 남아 있었다.

**요약을 손으로 유지하면 반드시 어긋난다.** 어긋남은 조용하고, 부록 A만 본 사람이
잘못된 판단을 내린 뒤에야 드러난다.

### 무엇을 하는가

`## D-XXXX. 제목` 줄을 긁어 **제목 그대로** 표를 만든다. 요약하지 않는다.
요약하는 순간 다시 두 번째 진실 공급원이 생긴다. 부록 A는 이제 **색인**이지
요약이 아니다.

사용법:
    python tools/sync_decision_index.py           # 다시 쓴다
    python tools/sync_decision_index.py --check   # 어긋나면 1로 끝난다 (make check)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "DECISIONS.md"
DESIGN = ROOT / "docs" / "DESIGN.md"

HEADING = re.compile(r"^## (D-\d{4})\. (.+?)\s*$", re.MULTILINE)

BEGIN = "<!-- decision-index:begin -->"
END = "<!-- decision-index:end -->"

BLOCK = re.compile(
    re.escape(BEGIN) + r".*?" + re.escape(END),
    re.DOTALL,
)


def build_index(decisions_text: str) -> str:
    """결정 기록 제목을 표로 만든다. 번호 순서는 파일 등장 순서를 따른다."""
    entries = HEADING.findall(decisions_text)
    if not entries:
        raise SystemExit("결정 기록에서 `## D-XXXX. 제목`을 찾지 못했다")

    seen: set[str] = set()
    for identifier, _ in entries:
        if identifier in seen:
            raise SystemExit(f"결정 번호가 중복이다: {identifier}")
        seen.add(identifier)

    rows = "\n".join(f"| {identifier} | {title} |" for identifier, title in entries)
    return (
        f"{BEGIN}\n"
        f"<!-- 이 표는 tools/sync_decision_index.py가 생성한다. 손으로 고치지 않는다 (D-0042). -->\n"
        f"\n"
        f"| ID | 결정 |\n"
        f"|---|---|\n"
        f"{rows}\n"
        f"\n"
        f"{END}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="부록 A 결정 기록 색인 동기화")
    parser.add_argument("--check", action="store_true", help="쓰지 않고 어긋남만 검사한다")
    args = parser.parse_args()

    plan_text = DESIGN.read_text(encoding="utf-8")
    if not BLOCK.search(plan_text):
        print(f"{DESIGN}에 {BEGIN} ... {END} 표식이 없다", file=sys.stderr)
        return 2

    index = build_index(DECISIONS.read_text(encoding="utf-8"))
    updated = BLOCK.sub(lambda _: index, plan_text, count=1)

    if updated == plan_text:
        print(f"부록 A 색인 일치 ({index.count('| D-')}건)")
        return 0

    if args.check:
        print("부록 A 색인이 결정 기록과 어긋난다.", file=sys.stderr)
        print("  python tools/sync_decision_index.py 로 다시 쓴다.", file=sys.stderr)
        return 1

    DESIGN.write_text(updated, encoding="utf-8")
    print(f"부록 A 색인 갱신 ({index.count('| D-')}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
