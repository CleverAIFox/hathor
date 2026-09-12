#!/usr/bin/env python3
"""문서 레이아웃 강제자 (D-0129).

### 왜 레이아웃만 보는가

세션마다 톤·용어를 말로 설명하는 대신 검사로 고정하려 했다. **후보를 전부 재 보니
대부분 못 건다.**

| 후보 | 실측 | 판정 |
|---|---|---|
| 건당 자수 | 기존 중앙 2,059 · 새 기록 2,200 | **기각.** 차이가 7%다. 없는 문제다 |
| 굵게 밀도 | 기존 중앙 13.1 · 최대 20.3 | **기각.** 새 기록이 전부 최대 아래다 |
| 1인칭 금지 | 정규식이 **"하나는"의 "나는"**을 잡았다 | **기각.** 진짜 1인칭도 기존에 있다 |
| 용어 통일 | `임계` 40 · `문턱` 18로 **둘 다 살아 있다** | **기각.** 아래 |
| **레이아웃** | 위반 4곳 | **채택** |

용어 통일이 안 되는 이유가 중요하다. **결정 기록은 소급 수정하지 않는다** (D-0081).
낡은 기록의 낱말을 지금 낱말로 갈아치우면 **그 세션이 실제로 무엇을 생각했는지가
사라진다.** 통일하려면 128건을 고쳐야 하고, 그것은 기록을 기록이 아니게 만든다.

**레이아웃은 다르다.** 줄 길이·행끝 공백·표 앞 빈 줄을 고쳐도 **주장이 한 글자도
안 바뀐다.** 그래서 소급해서 고쳐도 D-0081에 안 걸린다.

### 규칙 여섯

1. 행끝 공백 금지
2. 본문 줄 100자 이하 (표·코드·제목·인용은 안 본다)
3. 표가 산문이나 빈 줄로 끊기지 않을 것
4. 경어체 금지 — `-ㅂ니다` · `-습니다` · `해요` · `했어요`
5. 제목 계층 건너뛰기 금지 (`##` 다음에 `####`)
6. 결정 기록에 `- **배경**`

**넷은 이미 위반 0이었다.** 규칙을 새로 만든 것이 아니라 **지켜지고 있던 것을
적어 둔 것이다** — 그래서 다음 세션이 어길 때만 빨개진다.

`- **결과**`는 안 본다. 30건이 없고 **그 30건은 못 고친다** (D-0081).

    python3 tools/check_doc_style.py            # 검사한다
    python3 tools/check_doc_style.py --list     # 검사 대상을 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCUMENTS = ("README.md", "CONTRIBUTING.md", "docs/DESIGN.md", "docs/DECISIONS.md")
DOCUMENT_TREES = ("docs/decisions",)
"""`docs/archive`는 안 본다. **폐기 문서이며 고칠 것이 아니다** (D-0042)."""

WIDTH = 100
"""본문 줄 상한. 실측 중앙 48 · 90% 62 · 최대 103이라 **거의 지켜지고 있던 값이다.**"""

POLITE = ("해요", "했어요")
"""경어체 낱말. **`하세요`는 뺐다** — 사용자 발화 인용 안에 있고, 인용까지 막으면
기획서가 사용자의 말을 못 적는다."""

FINAL_B = 17
"""한글 종성 `ㅂ`의 자리. `(코드 - 0xAC00) % 28`로 얻는다.

**`-ㅂ니다`·`-습니다`를 낱말 나열 없이 판정한다.** `니다`만 보면 **`아니다`가 전부
잡힌다** — 실측 196곳이었다. 앞 음절의 종성이 `ㅂ`인지 보면 `합니다`·`맞습니다`·
`입니다`는 잡고 `아니다`·`않다`는 안 잡는다. 실측 위반 0건이다."""


INLINE_CODE = re.compile(r"`[^`]*`")
"""백틱 안. **예시로 적은 낱말은 경어체가 아니다** — 이 검사를 설명하는 기록이
`합니다`·`입니다`를 예로 드는데, 그것까지 막으면 규칙을 적을 수가 없다."""


def _polite(line: str) -> bool:
    """경어체가 있는가. **인라인 코드는 빼고 본다.**"""
    line = INLINE_CODE.sub("", line)
    if any(word in line for word in POLITE):
        return True
    for index in range(1, len(line) - 1):
        if line[index : index + 2] == "니다":
            code = ord(line[index - 1])
            if 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 == FINAL_B:
                return True
    return False

FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^(#{1,6}) ")
RECORD = re.compile(r"^## (D-\d{4})\.", re.M)


def targets() -> list[Path]:
    """검사할 문서. 정렬해 낸다 — **문제 순서가 기기마다 달라지면 못 읽는다.**"""
    found = [ROOT / name for name in DOCUMENTS if (ROOT / name).exists()]
    for tree in DOCUMENT_TREES:
        base = ROOT / tree
        if base.is_dir():
            found.extend(sorted(base.glob("*.md")))
    return found


def _above(lines: list[str], number: int) -> bool:
    """빈 줄 위쪽이 같은 표인가. **머리글 없는 조각이 되는 경우만 잡는다.**"""
    index = number - 2
    while index >= 0 and not lines[index].strip():
        index -= 1
    return index >= 0 and lines[index].startswith("|")


def check_layout(name: str, text: str) -> list[str]:
    """한 문서의 레이아웃. **첫 문제에서 멈추지 않는다.**"""
    problems: list[str] = []
    lines = text.splitlines()
    fenced = False
    level = 0
    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if line != line.rstrip():
            problems.append(f"{name}:{number}: 행끝에 공백이 있다")
        if fenced:
            continue

        heading = HEADING.match(line)
        if heading:
            found = len(heading.group(1))
            if level and found > level + 1:
                problems.append(f"{name}:{number}: 제목이 {level}단에서 {found}단으로 건너뛴다")
            level = found
        elif line.startswith("|"):
            previous = lines[number - 2] if number >= 2 else ""
            following = lines[number] if number < len(lines) else ""
            heads = bool(following.strip()) and set(following.strip()) <= set("|-: ")
            if previous.strip() and not previous.startswith("|"):
                problems.append(f"{name}:{number}: 산문이 표를 끊는다. 표를 붙이고 산문을 뺀다")
            elif not previous.strip() and not heads and _above(lines, number):
                problems.append(
                    f"{name}:{number}: 빈 줄이 표를 끊는다. 머리글이 없어 따로 렌더된다"
                )
        elif line.strip() and not line.startswith((">", "    ")) and len(line) > WIDTH:
            problems.append(f"{name}:{number}: 본문이 {len(line)}자다. {WIDTH}자 이하로 접는다")

        if _polite(line):
            problems.append(f"{name}:{number}: 경어체가 있다. 평서체로 쓴다")
    return problems


def check_records(name: str, text: str) -> list[str]:
    """결정 기록의 필수 절. **`- **결과**`는 안 본다** — 30건이 없고 못 고친다 (D-0081)."""
    problems: list[str] = []
    parts = RECORD.split(text)
    for index in range(1, len(parts), 2):
        number, body = parts[index], parts[index + 1]
        if "- **배경**" not in body:
            problems.append(f"{name}: {number}에 `- **배경**`이 없다")
    return problems


def check() -> list[str]:
    problems: list[str] = []
    for path in targets():
        name = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        problems.extend(check_layout(name, text))
        if name.startswith("docs/decisions/"):
            problems.extend(check_records(name, text))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="문서 레이아웃 강제자 (D-0129)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="검사 대상을 찍는다")
    args = parser.parse_args()

    if args.list:
        for path in targets():
            print(f"  {path.relative_to(ROOT).as_posix()}")
        return 0

    problems = check()
    if problems:
        print(f"문서 레이아웃 규약을 어긴 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"문서 레이아웃 검사 통과 · 문서 {len(targets())}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
