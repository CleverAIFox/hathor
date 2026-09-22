#!/usr/bin/env python3
"""결정 기록에서 릴리스를 낸다 — 태그 이름과 본문 (D-0223).

### 왜 결정 번호인가

hathor는 main에 바로 푸시하고, 한 번의 푸시가 결정 하나(가끔 둘)를 싣는다. **판이 바뀌는
단위가 결정이다.** 그래서 태그를 결정 번호로 단다 — `D-0223`. 날짜나 semver를 따로 매기면
두 번호 체계가 생기고 한쪽이 낡는다.

본문은 **그 결정의 표제와 «결과» · «남기는 것»**이다. 새로 쓰지 않는다 — 결정 기록이 이미
그것을 적는다.

    python3 tools/release_notes.py --tag             # 가장 최근 결정의 태그 이름
    python3 tools/release_notes.py --since D-0221    # D-0221 뒤의 결정들로 본문
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "DECISIONS.md"
HEADING = re.compile(r"^## (D-(\d{4}))\. (.+)$", re.M)


def records(text: str) -> list[tuple[str, str, str]]:
    """(번호, 표제, 본문) — 문서 순서대로."""
    found = list(HEADING.finditer(text))
    out = []
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        out.append((match.group(1), match.group(3).strip(), text[match.end() : end]))
    return out


def latest(text: str) -> str:
    numbered = records(text)
    if not numbered:
        raise LookupError("결정 기록에 표제가 없다")
    return max(numbered, key=lambda record: int(record[0][2:]))[0]


def _part(body: str, marker: str) -> str:
    """`- **결과**:` 줄부터 다음 `- **`/`###`/`재현` 앞까지."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(marker):
            chunk = [line]
            for later in lines[index + 1 :]:
                if later.startswith(("- **", "### ", "재현", "강제자", "---")):
                    break
                chunk.append(later)
            return "\n".join(chunk).strip()
    return ""


def _lessons(body: str) -> str:
    """`### 남기는 것` 절 — `재현` · `강제자` 줄 앞까지."""
    _, found, rest = body.partition("### 남기는 것")
    if not found:
        return ""
    kept = []
    for line in rest.splitlines():
        if line.startswith(("재현", "강제자", "---", "## ")):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def notes(text: str, since: str | None = None) -> str:
    """`since`보다 뒤의 결정들. 없으면 가장 최근 하나."""
    numbered = records(text)
    floor = int(since[2:]) if since else int(latest(text)[2:]) - 1
    picked = [record for record in numbered if int(record[0][2:]) > floor]
    if not picked:
        raise LookupError(f"{since} 뒤에 결정이 없다")
    parts = []
    for number, title, body in sorted(picked, key=lambda record: record[0]):
        section = [f"## {number}. {title}"]
        result = _part(body, "- **결과**")
        if result:
            section.append(result)
        lesson = _lessons(body)
        if lesson:
            section.append("**남기는 것**\n\n" + lesson)
        parts.append("\n\n".join(section))
    parts.append("전문은 `docs/DECISIONS.md` — 결정 번호로 찾는다.")
    return "\n\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="결정 기록에서 릴리스 (D-0223)")
    parser.add_argument("--tag", action="store_true", help="가장 최근 결정의 태그 이름")
    parser.add_argument("--title", action="store_true", help="가장 최근 결정의 «번호. 표제»")
    parser.add_argument("--since", help="이 태그 뒤의 결정들로 본문을 낸다")
    args = parser.parse_args()
    text = DECISIONS.read_text(encoding="utf-8")
    try:
        if args.tag:
            print(latest(text))
        elif args.title:
            number = latest(text)
            print(next(f"{n}. {title}" for n, title, _ in records(text) if n == number))
        else:
            print(notes(text, args.since), end="")
    except LookupError as error:
        print(f"릴리스를 낼 수 없다: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
