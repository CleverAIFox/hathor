#!/usr/bin/env python3
"""결정 대장을 **쓴다**. 판정하지 않는다 (D-0193 · D-0286).

### 왜 갈랐나

`check_decisions.py`가 *"결정 기록과 미해결표를 기계가 검사한다. **마스터의 결정
대장도 여기서 생성한다**"*라고 제 머리말에 적고 있었다. <!--voice-ok--> 「도」가 두
일이라는 자백이다 — **쓰는 것과 판정하는 것**이 한 파일에 있었고 600줄 상한이 그것을
드러냈다.

D-0280이 조성 분포에서 **수와 글자**를 가른 것과 같은 자리다. 가르면 *"대장에 무엇이
드는가"*를 시험이 직접 물을 수 있다.

### 무엇이 여기 있나

`강제자` 칸이 있는 기록만 골라 대장 표를 만든다. `자료` 칸의 규약도 여기 있다 —
**대장이 그 값을 싣기 때문이다.** 판정(`check_evidence`)은 저쪽에 남는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING = re.compile(r"^## (D-\d{4})\. (.+?)\s*$", re.MULTILINE)
"""`## D-XXXX. 제목` 한 줄. **긁는 자리가 하나다** (D-0286)."""


LEDGER_BEGIN = "<!-- decision-ledger:begin -->"
LEDGER_END = "<!-- decision-ledger:end -->"
"""마스터의 결정 대장 자리 (D-0193).

**색인과 다르다.** 색인은 같은 목록이 두 곳에 사는 구조라 D-0189가 없앴다. 대장은
*"지금 무엇이 효력이 있는가"*이며 **강제자가 있는 기록만** 든다 — `fire-lane` §16과
같은 자리다. 목록이 아니라 **선별**이므로 두 곳이 아니다.

**손으로 고치지 않는다.** D-0186이 *"도구가 다시 쓴다"*고 적어 놓고 그 도구를 안
만들어 **120행에서 멈춘 채 일곱이 빠졌다.** 검사도 못 잡았다.
"""


def build_ledger(text: str) -> str:
    """강제자를 적은 기록에서 대장을 뽑는다. **고르지 않는다.**

    **`자료` 칸을 같이 든다** (D-0265). 대장은 *"지금 무엇이 효력이 있는가"*를 묻는
    자리이고, 그 답에는 «그 판단이 무엇으로 뒷받침되나»가 들어가야 한다 — 합성에서 낸
    수로 선 판단과 1004곡에서 낸 수로 선 판단은 **같은 무게가 아니다.**
    """
    rows = []
    for identifier, title, body in records_with_body(text):
        found = re.search(r"^강제자  (\S.*)$", body, re.MULTILINE)
        if not found:
            continue
        keeper = found.group(1).strip().replace("`", "").split(" · ")[0]
        source = EVIDENCE.search(body)
        evidence = source.group(1).strip() if source else "—"
        rows.append(f"| {identifier} | {title.split(' — ')[0].strip()} | `{keeper}` | {evidence} |")
    head = ["| 결정 | 무엇이 효력을 갖는가 | 누가 지키나 | 자료 |", "|---|---|---|---|"]
    # **표식과 표 사이를 빈 줄로 띄운다.** HTML 주석은 표 머리로 안 읽히고,
    # `check_doc_style`이 *"산문이 표를 끊는다"*로 문다.
    return "\n".join([LEDGER_BEGIN, "", *head, *rows, "", LEDGER_END])


def records_with_body(text: str) -> list[tuple[str, str, str]]:
    """`(번호, 표제, 본문)`. **본문 길이를 재려고 쓴다** (D-0188)."""
    found: list[tuple[str, str, str]] = []
    marks = list(HEADING.finditer(text))
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        found.append((mark.group(1), mark.group(2), text[mark.start() : end]))
    return found


EVIDENCE = re.compile(r"^자료  (\S.*)$", re.MULTILINE)
"""기록이 **스스로 낸 수**의 출처 (D-0265).

`강제자`는 «누가 지키나», `재현`은 «어떻게 다시 내나»를 적는다. **«무엇으로 쟀나»를
적는 칸이 없었다** — 264건 중 0건이었다. 그래서 `P@10 0.47`이 1004곡 실물에서 나온
것인지 `default_rng(7)` 합성에서 나온 것인지 **산문을 읽어야 알았고 기계는 몰랐다.**

D-0132가 `강제자`·`재현`을 전수로 채운 것과 같은 자리다."""

EVIDENCE_VALUES = re.compile(r"^(합성|해당 없음|불명|실물 \S.*|합성 · 실물 \S.*)$")
"""쓸 수 있는 값. **넷뿐이다** (D-0265).

| 값 | 뜻 |
|---|---|
| `합성` | 지은 자료에서 냈다 — `default_rng` · 합성 파형 · 임시 나무 |
| `실물 <무엇>` | 실제 자료나 실제 기기에서 냈다. 무엇이었는지 적는다 |
| `합성 · 실물 <무엇>` | 둘 다 썼다 — 합성 귀무 대조 + 실물 측정 |
| `해당 없음` | **아무것도 안 쟀다.** 설계 판단 · 규약 · 도구 배선 |
| `불명` | 쟀는데 무엇으로 쟀는지 기록에 없고 알아낼 수 없다 |

**인용은 안 센다.** 남의 기록에서 가져온 수는 그 기록의 칸이 든다. 아직 안 잰
것(«실측 필요»)은 `해당 없음`이다 — 그 기준이 없으면 같은 기록이 세션마다 달리 분류된다."""


@dataclass(frozen=True)
class Record:
    number: int
    identifier: str
    title: str
    body: str


def scan_records(text: str) -> list[Record]:
    """`## D-XXXX. 제목` 단위로 자른다. 본문은 다음 표제 직전까지다."""
    found: list[Record] = []
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found.append(
            Record(
                number=int(match.group(1)[2:]),
                identifier=match.group(1),
                title=match.group(2),
                body=text[match.end() : end],
            )
        )
    return found
