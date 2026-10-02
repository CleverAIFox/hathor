#!/usr/bin/env python3
"""**지운 말이 근거 없이 살아 있나** (D-0349).

### 네 곳에서 살아 있었다

D-0189가 색인을 없애며 *"같은 목록이 두 곳에 사는 구조"*라 적었는데, `MASTER`는 **160판
뒤에도** 「부록 A. 결정 기록 색인」을 들고 *"`docs/DECISIONS.md`가 자기 색인을 든다"*고
적고 있었다. `make check` 목록에도 「색인 일치」가 남아 **없는 검사를 광고했다.**

`docx_check.RETIRED`가 **같은 일을 기획서에만** 하고 있었다. 기획서는 `MASTER` Part
I ~ III에서 빌드되므로 **그 밖의 자리는 아무도 안 봤다.**

### 왜 따로 사나

`check_doc_style`에 넣었더니 그 파일이 **668줄로 상한(600)을 넘었다.** `fire-lane`이
제 진단으로 적은 그 꼴이다 — *"세 번째까지는 「검사를 하나 더 만든다」로 대응했다.
그래서 강제자가 마흔아홉이 됐다."* **도구를 키우는 대신 가른다.**

### 지운 말을 「지웠다」고 쓰는 것은 정상이다

**같은 줄에 지운 결정 번호가 있으면 통과시킨다** — `check_issue_mentions`가 닫힌 질문에
쓰는 규칙과 같은 꼴이다 (D-0126). 그 규칙이 *"엄격하게 닫은 결정만 요구하는 안은
기각했다"*고 적었고 여기도 같다: **번호가 붙어 있으면 이력을 따라갈 수 있다.**

과거 축(`docs/DECISIONS.md`)은 **안 본다** — 그때는 살아 있던 말이고 소급 수정이
금지다 (D-0081). 기획서는 `docx_check`가 제 목록으로 본다.

    python3 tools/check_retired.py            # 검사한다
    python3 tools/check_retired.py --list     # 지운 말을 찍는다
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LIVING = ("README.md", "docs/PLAN.md", "docs/MASTER.md")
"""보는 문서. **과거 축과 기획서는 각자 다른 자가 본다.**"""

ALLOW = "<!--voice-ok-->"
"""일부러 인용한 줄. `check_doc_style`과 같은 표식이다 (D-0187)."""

RETIRED_WORDS: tuple[tuple[str, str, str], ...] = (
    ("결정 기록 색인", "D-0189", "색인을 없앴다 — 같은 목록이 두 곳에 살면 반드시 어긋난다"),
    ("전체 색인", "D-0189", "같은 목록이 두 곳에 살면 반드시 어긋난다"),
    ("자기 색인", "D-0189", "같은 목록이 두 곳에 살면 반드시 어긋난다"),
    ("색인 일치", "D-0189", "그런 검사가 없다"),
    # deadcheck: ok 없어야 할 말이라 실물이 없는 것이 맞다 (`docx_check.RETIRED`와 같다)
    ("docs/archive", "D-0186", "보관소를 없앴다"),
    # deadcheck: ok 같음
    ("docs/DESIGN.md", "D-0189", "`docs/MASTER.md`가 흡수했다"),
    ("MASTER.md 뿌리", "D-0189", "뿌리 사본이 없다"),
)
"""**살아 있는 문서에 남으면 안 되는 말.** 지운 뒤에도 기어들어온다 (D-0349).

### 네 곳에서 살아 있었다

D-0189가 색인을 없애며 *"같은 목록이 두 곳에 사는 구조"*라 적었는데, `MASTER`는
**160판 뒤에도** 「부록 A. 결정 기록 색인」을 들고 *"`docs/DECISIONS.md`가 자기 색인을
든다"*고 적고 있었다. `make check` 목록에도 「색인 일치」가 남아 **없는 검사를 광고했다.**

`docx_check.RETIRED`가 **같은 일을 기획서에만** 하고 있었다. 기획서는 `MASTER` Part
I ~ III에서 빌드되므로 **그 밖의 자리는 아무도 안 봤다.**

### 지운 말을 「지웠다」고 쓰는 것은 정상이다

그래서 **같은 줄에 지운 결정 번호가 있으면 통과시킨다** —
`check_issue_mentions`가 닫힌 질문에 쓰는 규칙과 같은 꼴이다 (D-0126). 그 규칙이
*"엄격하게 닫은 결정만 요구하는 안은 기각했다"*고 적었고 여기도 같다: **번호가 붙어
있으면 쓰는 사람이 이력을 따라갈 수 있다.**

과거 축(`docs/DECISIONS.md`)은 **안 본다** — 그때는 살아 있던 말이고 소급 수정이
금지다 (D-0081).
"""


def check_retired_words(name: str, text: str) -> list[str]:
    """지운 말이 근거 없이 남아 있는 자리 (D-0349)."""
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW in line:
            continue
        for word, decision, why in RETIRED_WORDS:
            if word in line and decision not in line:
                problems.append(
                    f"{name}:{number}: «{word}»는 {decision}이 지웠다 — {why}. "
                    f"이력을 적을 자리면 같은 줄에 `{decision}`을 적는다"
                )
    return problems


def targets() -> list[Path]:
    """볼 문서. **없는 것을 목록에 두면 조용히 지나간다** (D-0349)."""
    return [ROOT / name for name in LIVING]


def check() -> list[str]:
    problems: list[str] = []
    for path in targets():
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT).as_posix()}: 검사 대상인데 없다")
            continue
        name = path.relative_to(ROOT).as_posix()
        problems.extend(check_retired_words(name, path.read_text(encoding="utf-8")))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="지운 말이 살아 있나 (D-0349)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="지운 말을 찍는다")
    args = parser.parse_args()

    if args.list:
        for word, decision, why in RETIRED_WORDS:
            print(f"  {decision}  «{word}» — {why}")
        return 0

    if not RETIRED_WORDS:
        print("지운 말이 0개다. **그물이 비었다** (D-0230)", file=sys.stderr)
        return 1

    problems = check()
    if problems:
        print(f"지운 말이 근거 없이 남은 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"지운 말 검사 통과 · 문서 {len(targets())}개 · 지운 말 {len(RETIRED_WORDS)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
