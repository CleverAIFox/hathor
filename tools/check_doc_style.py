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
4. 경어체·명령형 금지. 의도한 인용은 줄 끝에 `<!--voice-ok-->`
5. 제목 계층 건너뛰기 금지 (`##` 다음에 `####`)
6. 결정 기록에 `- **배경**`
7. 살아 있는 문서 하위 절의 `**강조**`가 열여섯을 넘지 않을 것
8. 결정 기록에 `강제자` (D-0131 이후분)
9. **여섯 번째 문서 금지** — `docs/`에 축 셋 말고 다른 문서가 생기지 않는가

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

DOCUMENTS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/PLAN.md",
    "docs/DESIGN.md",
    "docs/DECISIONS.md",
)
DOCUMENT_TREES = ("docs/decisions",)
"""`docs/archive`는 안 본다. **폐기 문서이며 고칠 것이 아니다** (D-0042)."""

WIDTH = 100
"""본문 줄 상한. 실측 중앙 48 · 90% 62 · 최대 103이라 **거의 지켜지고 있던 값이다.**"""

ALLOW = "<!--voice-ok-->"
"""문체 검사 탈출구 (D-0131).

**인용을 위반으로 세면 회고를 쓸 수 없다.** 기획서는 사용자의 말을, 결정 기록은
폐기한 문언을 그대로 적어야 한다. 막으면 사람이 검사를 끈다.

특수 사례로 때우지 않는다 — D-0129는 인라인 코드만 예외로 뒀고, 그래서 백틱 밖에서
인용해야 하는 자리가 나오자 막혔다. **일반 표지가 맞다.**"""

IMPERATIVE = (
    r"(?:[가-힣]지\s*(?:마라|말라)|해라|하라|봐라|보라|써라|쳐라|둬라|들어라|물어라"
    r"|적어라|지워라|옮겨라|받아라|만들어라|정해라|고쳐라|넣어라|빼라|걸어라|돌려라)"
    r"(?![가-힣])"
)
"""명령형. 실측 5건이며 **전부 인용문 안이라 표지를 달았다.**

`~라` 종결만 본다. 청유형(`~하자`)은 연결어미(`추가하자 잡혔다`)와 구분이 안 돼
오탐이 크다 — **검사가 시끄러우면 끈다.**"""

BOLD_LIMIT = 16
"""살아 있는 문서 하위 절 하나가 가질 수 있는 `**강조**` 수 (D-0131).

실측 56절 중앙 3 · 90% 9 · 그다음 15 · **최대 33.** 16은 그 틈이다.

**넘으면 강조가 과한 것이 아니라 절이 너무 큰 것이다.** 강조를 지우지 말고 절을
쪼갠다. **결정 기록에는 안 건다** — 덧붙이기만 하는 문서라 못 고친다 (D-0081).

이 규칙은 D-0129가 *"굵게 밀도는 없는 문제"*라며 기각했던 것을 되살린 것이다.
그때는 **저자 간 드리프트**로 봤고 7% 차이라 근거가 없었다. 여기서는 **절 크기의
냄새**로 쓴다 — 용도가 다르고 실측이 뒷받침한다."""

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


def _voice(line: str) -> str | None:
    """문체 위반이 있으면 종류를, 없으면 `None`.

    안 보는 것 셋이다 — 인라인 코드 · 탈출구 표지 · **4칸 들여쓴 블록.**

    **들여쓴 블록은 산문이 아니다.** 결정 기록은 폐기한 문언을 증거로 인용하고
    이 기록 자신이 그렇게 적혔다. **인용을 위반으로 세면 회고를 쓸 수 없다.**
    """
    if ALLOW in line or line.startswith("    "):
        return None
    line = INLINE_CODE.sub("", line)
    if re.search(IMPERATIVE, line):
        return "명령형"
    return "경어체" if _polite(line) else None


def _polite(line: str) -> bool:
    """경어체가 있는가."""
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

        if kind := _voice(line):
            problems.append(
                f"{name}:{number}: {kind} 표현이 있다. 평서체 3인칭으로 쓴다. "
                f"의도한 인용이면 줄 끝에 {ALLOW}"
            )
    return problems


BOLD = re.compile(r"\*\*[^*]+\*\*")
SECTION = ("## ", "### ", "#### ")


def check_bold_density(name: str, text: str) -> list[str]:
    """하위 절 하나가 강조를 몇 개 다는가 (D-0131).

    **세는 단위는 하위 절이다.** 상위 절에서 세면 절 크기가 아니라 하위 절 개수를
    재게 된다. 표 줄은 안 센다 — 표의 강조는 행의 강조이지 절의 강조가 아니다.
    """
    problems: list[str] = []
    heading, count, size, line_number = None, 0, 0, 0
    fenced = False

    def close() -> None:
        if heading and size > 200 and count > BOLD_LIMIT:
            problems.append(
                f"{name}:{line_number}: 하위 절의 강조가 {count}개다. "
                f"{BOLD_LIMIT}을 넘으면 절이 너무 큰 것이니 쪼갠다"
            )

    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith(SECTION):
            close()
            heading, count, size, line_number = line, 0, 0, number
            continue
        if line.startswith("|"):
            continue
        count += len(BOLD.findall(line))
        size += len(line)
    close()
    return problems


def check_records(name: str, text: str) -> list[str]:
    """결정 기록의 필수 절.

    `강제자`는 **D-0131 이후분에만 요구한다.** 앞의 130건을 고치는 것은 소급 수정이며
    D-0081이 막는다. **무엇을 요구하는지는 지금 정하고, 적용은 앞으로부터다.**
 **`- **결과**`는 안 본다** — 30건이 없고 못 고친다 (D-0081)."""
    problems: list[str] = []
    parts = RECORD.split(text)
    for index in range(1, len(parts), 2):
        number, body = parts[index], parts[index + 1]
        if "- **배경**" not in body:
            problems.append(f"{name}: {number}에 `- **배경**`이 없다")
        if int(number[2:]) >= ENFORCER_FROM and "강제자" not in body:
            problems.append(
                f"{name}: {number}에 `강제자` 기술이 없다. "
                "`강제자  tools/xxx.py` 또는 `강제자 없음 — 사유: …`"
            )
    return problems


ENFORCER_FROM = 131
"""`강제자` 기술을 요구하기 시작하는 결정 번호 (D-0131).

**"누가 이것을 지키는가"를 적는 칸이다.** 이 저장소가 반복해 맞은 사고가 한 형태다 —
규약은 문서나 주석에 있고 강제하는 검사가 없다. D-0121 · D-0126 · D-0128이 전부
그것이었고 **한 세션에 셋을 맞았다.**

형식은 둘이다.

    강제자  tools/check_doc_style.py · core/tests/unit/test_doc_style.py
    강제자 없음 — 사유: 자료만으로 닫는다. 고정할 동작이 없다

**없다는 사실 자체가 기록이어야 한다.** 비워 두면 보이지 않는다."""

AXES = ("PLAN.md", "DESIGN.md", "DECISIONS.md")
"""`docs/` 바로 아래에 허용되는 문서. **미래·현재·과거 세 시제가 다 찼다** (D-0130)."""

ALLOWED_TREES = ("decisions", "archive")
"""하위 폴더. `decisions/`는 조각(O-30 · D-0080)이고 `archive/`는 폐기 문서다 (D-0042).
**`archive/`는 PLAN §3이 든 빚이다** — 지우면 이 목록에서도 뺀다."""


def check_sixth_document() -> list[str]:
    """축 셋 말고 다른 문서가 `docs/`에 생겼는가 (D-0130).

    **한 항목은 한 문서에만 산다.** 넷째 축을 만들면 그 순간 어느 시제인지 모르는
    항목이 생기고, 같은 항목이 두 곳에 살기 시작한다. 새 문서를 만들고 싶으면
    **그것은 셋 중 하나의 절이다.**

    하위 폴더까지 본다. `docs/_patch/` 같은 자리가 두 검사 사이로 빠져나가는 것이
    이 검사가 막는 일이다.
    """
    base = ROOT / "docs"
    if not base.is_dir():
        return []
    problems: list[str] = []
    for path in sorted(base.rglob("*.md")):
        parts = path.relative_to(base).parts
        if len(parts) == 1 and parts[0] in AXES:
            continue
        if len(parts) > 1 and parts[0] in ALLOWED_TREES:
            continue
        name = path.relative_to(ROOT).as_posix()
        problems.append(
            f"{name}: 여섯 번째 문서다. 미래(PLAN) · 현재(DESIGN) · 과거(DECISIONS) 중 "
            "어디의 절인지 정해 옮긴다"
        )
    return problems


def check() -> list[str]:
    problems: list[str] = list(check_sixth_document())
    for path in targets():
        name = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        problems.extend(check_layout(name, text))
        if not name.startswith("docs/decisions/"):
            problems.extend(check_bold_density(name, text))
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
