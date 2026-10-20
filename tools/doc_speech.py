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

PROFANITY = re.compile(
    r"씨발|(?<![가-힣])시발|(?<![가-힣])졸라|존나|(?<![가-힣])구라"
    r"|개같|개많|병신|지랄|좆|(?<![가-힣])새끼"
)
"""**추적 파일 전체에서 0건이어야 하는 말** (D-0443).

### 왜 말투 검사와 따로인가

말투 검사는 **결정 기록의 인용 안**만 본다. 욕설은 **어디에 있든 안 된다** — 실측으로
사용자가 넷을 찾아 왔고 **그중 하나가 시험 파일**이었다. *«죄다 구라에 가짜에 Mock에»*가
`test_gate_types.py`의 머리말에 복사돼 있었고 내 검사는 `docs/`만 보고 있었다.

### 앞 글자를 본다

`동시발음`의 «시발» · `도구라면`과 `연구라도`의 «구라»가 오탐이다. 앞에 한글이 붙어
있으면 낱말이 아니다 — 실측 오탐 6건이 전부 그 꼴이고 경계로 0이 된다.

**탈출구가 없다.** 인용이든 아니든 정본에 안 적는다.
"""


SPEECH_OK = "<!--speech-ok-->"
"""**발화 원문이 자료인 자리**의 표지 (D-0443).

규칙 4의 `check_doc_style.ALLOW`를 같이 쓰다가 **표지 하나가 규칙 둘을 겸했다** —
경어체·명령형 때문에 붙인 표지가 발화 인용까지 덮었고, 실측으로 다섯 곳이 그렇게
빠져나갔다. **규칙마다 제 표지를 둔다.**
"""


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

SAID = re.compile(
    r"(사용자|그가|그는|사람이|판정자)[^«\"]{0,60}?"
    r"(말했다|물었다|짚었다|지적했다|했다|잘랐다|반대했다|뒤집었다|되물었다|덧붙였다"
    r"|보냈다|평했다|적었다|막았다|멈춰 세웠다|밀어붙였다|의 말|:|—)\s*$"
)
"""**인용 바로 앞**에 붙은 발화 서술. 말투가 격식이어도 발화를 옮긴 것은 막는다 (D-0443).

### 창을 쓰면 못 쓴다

D-0438은 이 분기를 **앞 70자를 훑는 꼴**로 써 보고 **50건 중 25건이 오탐**이라 버렸다 —
다른 절의 동사가 창에 들어왔고 짧은 명사구 인용까지 물었다. **줄 끝에 붙여** 다시 재니
**29건에 오탐 0**이다. 버릴 분기가 아니라 **잘못 쓴 분기였다.**

`그 기록이 적었다`는 안 걸린다 — 주체가 사람을 가리키는 꼴일 때만 본다.
"""


RECORD = re.compile(r"^## (D-\d{4})\.", re.M)

SKIP = re.compile(r"^(?:    |\t|```)")
"""안 보는 줄. **들여쓴 블록은 산문이 아니다** — `재현`·`강제자` 칸과 코드다."""


def _marked(line: str, allow: str) -> bool:
    """**인용이 시작하는 줄**에만 표지를 인정한다 (D-0443).

    걸친 줄을 전부 보면 **다음 인용을 위해 붙인 표지가 앞 인용까지 덮는다.** 실측으로
    D-0368이 그렇게 빠져나갔다 — 두 줄짜리 인용의 끝줄에 뒷인용의 표지가 있었다.
    """
    return allow in line


def speech(text: str, allow: str = SPEECH_OK) -> list[tuple[int, str]]:
    """`(줄 번호, 인용)`. **빈 목록이 통과다.**"""
    lines = text.splitlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    found: list[tuple[int, str]] = []
    for match in QUOTE.finditer(text):
        first = _line_of(starts, match.start())
        if SKIP.match(lines[first]) or _marked(lines[first], allow):
            continue
        quoted = " ".join(match.group(1).split())
        if re.search(SPOKEN, quoted):
            found.append((first + 1, quoted))
            continue
        # **말투가 격식이어도 발화를 그대로 옮긴 것은 막는다** (D-0443).
        if SAID.search(text[: match.start()].rsplit("\n", 1)[-1]):
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


SELF = "tools/doc_speech.py"
"""패턴을 든 파일. **여기만 뺀다** — 막을 말을 적으려면 그 말을 써야 한다.

`check_retired`는 보는 범위가 문서 셋이라 제 파일을 애초에 안 본다. 이 검사는 추적
파일 전부를 보므로 **한 파일을 이름으로 뺀다.** 그 파일의 시험은 글자를 쪼개 써서
예외 없이 돈다 — 예외가 둘이 되면 숨을 자리가 둘이 된다.
"""


def profanity(root: Path, tracked: list[str]) -> list[tuple[str, int, str]]:
    """`(경로, 줄, 걸린 말)`. **추적 파일 전부를 본다** (D-0443)."""
    found: list[tuple[str, int, str]] = []
    for name in tracked:
        if name == SELF:
            continue
        path = root / name
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            hit = PROFANITY.search(line)
            if hit:
                found.append((name, number, hit.group()))
    return found


def tracked_files(root: Path) -> list[str]:
    """`git ls-files`. **추적 안 되는 것은 정본이 아니다.**"""
    import subprocess

    done = subprocess.run(
        ("git", "ls-files"), cwd=root, capture_output=True, text=True, timeout=60, check=False
    )
    return [name for name in done.stdout.splitlines() if name]


def main() -> int:
    """홀로 돌 때. `make check`는 `check_doc_style`을 거쳐 부른다."""
    from check_doc_style import PAST

    text = (ROOT / PAST).read_text(encoding="utf-8")
    dirty = profanity(ROOT, tracked_files(ROOT))
    for name, number, word in dirty:
        print(f"  {name}:{number} 욕설·은어 — {word}", file=sys.stderr)

    problems = speech(text)
    for line, quoted in problems:
        print(f"  {record_of(text, line)} {PAST}:{line} — {quoted[:70]}", file=sys.stderr)
    if problems or dirty:
        if dirty:
            print(f"욕설·은어 {len(dirty)}곳. 정본에 안 적는다 (D-0443)", file=sys.stderr)
        if problems:
            print(f"구어체 인용 {len(problems)}곳. 간접 서술로 옮긴다 (D-0438)", file=sys.stderr)
        return 1
    print(f"구어체 인용 검사 통과 · 0건 · 욕설 0건 (추적 {len(tracked_files(ROOT))}개)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
