#!/usr/bin/env python3
"""발화 인용 검사 — **결정 기록은 구어를 그대로 담지 않는다** (D-0438).

### 왜 레이아웃 검사에 못 붙이는가

`check_doc_style`은 **줄 하나**를 본다. 발화 인용은 줄을 넘는다 — 실측 49건 중 14건이
두 줄 이상이었다. 줄 단위로 보면 *«아니 왜 소급을 안 해??»* 는 잡고 이어지는
*«소급해야 할 것 같은데»* 는 놓친다. **인용 덩어리가 단위다.**

### 무엇을 막는가

둘이다. **구어체 낱말**과 **사람 발화를 그대로 옮긴 인용**이다.

1. 인용 안에 `SLANG`의 낱말이 있다 — `;;` · `거야` · `잖아` 같은 것들.
2. 인용 바로 앞 `WINDOW`자 안에 **사람**(`SPEAKER`)과 **발화 동사**(`SAID`)가 같이
   있다 — *«사용자가 물었다 — "…"»* 꼴이다.

둘째가 있어야 하는 이유: 구어체 낱말이 하나도 없는 발화도 정본에 그대로 들어간다.
D-0437의 표가 그랬다 — *«잘 잡은 것 같다»* 에는 걸릴 낱말이 없다. **말투가 아니라
«사람 말을 그대로 옮겼다»가 문제다.**

### 기록을 인용하는 것은 막지 않는다

`D-0094가 *"지표가 목표가 된다"*고 적었다`는 **정당한 인용이다.** 그래서 `SPEAKER`를
`그가`·`사용자`처럼 **사람을 가리키는 꼴로만** 둔다. `그 기록이`는 안 걸린다.

### 탈출구 — 발화가 자료인 자리

**귀 판정은 원문이 측정값이다.** *«왠지 모르겠는데 별로»*를 «판정자가 부정적으로
평했다»로 옮기면 **자료가 사라진다** — D-0213이 그 한 줄로 판정 하네스의 구멍을
짚었다. 그런 자리는 `check_doc_style.ALLOW` 표지를 단다.

표지가 붙은 실측 6건은 전부 **귀 판정과 사용자가 친 입력**이다 (D-0063 · D-0213 둘 ·
D-0214 · D-0404 · D-0422).

### 소급 바닥이 없다

이 검사에는 `*_FROM` 바닥이 없다. **전수 0건이다** — D-0438이 D-0042부터 D-0437까지
43곳을 간접 서술로 고쳤다. 바닥을 두면 *«과거는 안 본다»*가 되고, 그러면 다음 세션이
옛 기록을 손볼 때 다시 구어가 들어온다 (D-0117).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPOKEN = (
    # 채팅 기호
    r";;|ㅋ|ㅠ|ㅡㅡ|\?\?|\?!"
    # 해체 의문 — **평어체 의문은 안 잡는다** (`~는가?`·`~인가?`)
    r"|(?<![가-힣])(?:맞아|맞지|되지|하지|할래|그치|뭐야|뭐지|뭔데|어때)\s*\?"
    r"|아니야\?|거야\?|건데\?|인데\?|는데\?|냐\?|니\?|맞나\?"
    # 해체 종결
    r"|거야|거임|거네|잖아|는걸|했어|했네|하네(?![가-힣])|이네|싫어|주든가|만들어줘"
    r"|더라(?![가-힣])"
    # 구어 의문
    r"|아니냐|않나|아님\?|하자고|니까\?|뭔[말소]"
    # 은어·비속어
    r"|옆그레이드|개엉망|완전 개"
)
"""인용 안에서 막는 꼴. **후보를 다섯 갈래로 나눠 전수로 쟀다** (D-0438).

| 갈래 | 실측 | 오탐 |
|---|---|---|
| 채팅 기호 | 8 | 0 |
| 해체 의문 | 24 | 0 |
| 해체 종결 | 22 | **2** — `하네스`가 `하네`에 걸렸다. 경계를 붙여 0 |
| 구어 의문 | 16 | 0 |
| 은어 | 5 | 0 |

**`?` 하나는 안 막는다.** 기록은 평어체로 묻는다 — *«왜 두 벌이 되는가?»*는 정상이고
*«이게 어딜 말하는 거야?»*가 아니다. `??`·`?!`와 **해체 종결만** 구어다.

**발화 동사로는 안 잡는다.** *«사용자가 물었다 — "…"»* 꼴을 세어 봤더니 50건 중 25건이
오탐이었다 — 기록 인용·화면 문구·오류 메시지·내가 개념에 붙인 이름까지 물었다.
**경보가 반이 거짓이면 끈다** (GR-0.8). 말투로만 가른다."""

QUOTE = re.compile(r'\*?[«"]([^»"\n]{2,}(?:\n[^»"\n]*){0,4}?)[»"]\*?')
"""인용 덩어리. **네 줄까지 넘는다** — 실측 최대가 세 줄이다."""

RECORD = re.compile(r"^## (D-\d{4})\.", re.M)

SKIP = re.compile(r"^(?:    |\t|```)")
"""안 보는 줄. **들여쓴 블록은 산문이 아니다** — `재현`·`강제자` 칸과 코드다."""


def _marked(lines: list[str], first: int, last: int, allow: str) -> bool:
    """인용이 걸친 줄 가운데 하나라도 탈출구 표지를 달았는가."""
    return any(allow in lines[index] for index in range(first, last + 1))


def speech(text: str, allow: str) -> list[tuple[int, str]]:
    """`(줄 번호, 인용)`. **빈 목록이 통과다.**"""
    lines = text.splitlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    found: list[tuple[int, str]] = []
    for match in QUOTE.finditer(text):
        first = _line_of(starts, match.start())
        last = _line_of(starts, match.end() - 1)
        if SKIP.match(lines[first]) or _marked(lines, first, last, allow):
            continue
        quoted = " ".join(match.group(1).split())
        if re.search(SPOKEN, quoted):
            found.append((first + 1, quoted))
    return found


def _line_of(starts: list[int], position: int) -> int:
    """글자 자리 → 0부터 세는 줄 번호."""
    low, high = 0, len(starts) - 1
    while low < high - 1:
        middle = (low + high) // 2
        if starts[middle] <= position:
            low = middle
        else:
            high = middle
    return low


def record_of(text: str, line: int) -> str:
    """그 줄이 속한 결정 기록 번호. **어느 판인지 안 적으면 못 찾는다** (D-0203)."""
    lines = text.splitlines()
    for index in range(min(line, len(lines)) - 1, -1, -1):
        match = RECORD.match(lines[index])
        if match:
            return match.group(1)
    return "(머리말)"


def main() -> int:
    """홀로 돌 때. `make check`는 `check_doc_style`을 거쳐 부른다."""
    from check_doc_style import ALLOW, PAST

    text = (ROOT / PAST).read_text(encoding="utf-8")
    problems = speech(text, ALLOW)
    for line, quoted in problems:
        print(f"  {record_of(text, line)} {PAST}:{line} — {quoted[:70]}", file=sys.stderr)
    if problems:
        print(f"구어체 인용 {len(problems)}곳. 간접 서술로 옮긴다 (D-0438)", file=sys.stderr)
        return 1
    print("구어체 인용 검사 통과 · 0건")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
