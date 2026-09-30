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
        text_found = keeper_text(body)
        if not text_found:
            continue
        keeper = text_found.replace("`", "").split(" · ")[0]
        source = EVIDENCE.search(body)
        evidence = source.group(1).strip() if source else "—"
        rows.append(f"| {identifier} | {title.split(' — ')[0].strip()} | `{keeper}` | {evidence} |")
    head = ["| 결정 | 무엇이 효력을 갖는가 | 누가 지키나 | 자료 |", "|---|---|---|---|"]
    # **표식과 표 사이를 빈 줄로 띄운다.** HTML 주석은 표 머리로 안 읽히고,
    # `check_doc_style`이 *"산문이 표를 끊는다"*로 문다.
    return "\n".join([LEDGER_BEGIN, "", *head, *rows, "", LEDGER_END])


KEEPER_HEAD = re.compile(r"^강제자(?:  (.+))?$", re.MULTILINE)
"""`강제자` 칸의 머리. **같은 줄 뒤가 비어 있어도 잡는다** (D-0304).

빈 채로 두고 다음 줄들을 들여쓰는 꼴을 쓸 수 있는데, 셋 다 그것을 못 읽었다 — 대장은
행을 버리고 `check_doc_style`은 경로 존재를 안 보고 `check_keepers`는 함수를 안 봤다.
**네 판이 그 상태로 초록이었다.**
"""


def keeper_text(body: str) -> str | None:
    """`강제자` 칸의 내용 한 덩어리. 칸이 없으면 `None`이다 (D-0304).

    두 꼴을 다 읽는다 — 한 줄(`강제자  A · B`)과 **머리만 두고 들여쓴 여러 줄**. 시험을
    아홉 개 적으면 한 줄이 100자를 넘으므로 여러 줄 꼴이 필요하다 (D-0081의 줄 길이).

    **파서를 한 자리에 둔다.** 세 군데가 각자 정규식을 들고 있었고 **셋 다 다르게 틀렸다.**
    """
    found = KEEPER_HEAD.search(body)
    if found is None:
        return None
    parts = [found.group(1).strip()] if found.group(1) else []
    lines = body[found.end() :].splitlines()
    for line in lines[1:] if lines and not lines[0].strip() else lines:
        if not line.startswith(("    ", "\t")):
            break
        if stripped := line.strip():
            parts.append(stripped)
    return " · ".join(parts) if parts else ""


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

NOT_PROMOTED = re.compile(r"\(D-(\d{4}) 승격 아님\)")
"""**뒤 판이 이 판의 자료를 안 올린다**는 판단 (D-0323).

`(D-xxxx 확인)`의 짝이다. 뒤에 온 판이 실물로 쟀다고 해서 앞 판이 승격되는 것은
아니다 — **결함을 찾았거나 판정을 뒤집었으면 승격 대상이 아니다.** 그 판단을 적어
두지 않으면 `decision_evidence.payable`의 명단에 영원히 남고, **「아니다」로만 찬
명단은 아무도 안 읽는다.**
"""

OVERTURNED = re.compile(r"\(D-(\d{4}) 뒤집힘\)")
"""**뒤 판이 이 판의 판정을 뒤집었다** (D-0328).

`(D-xxxx 확인)`의 반대다. 뒤에 온 판이 실물로 쟀는데 **결과가 반대로 나왔으면**
「확인」이 아니다 — 확인으로 적으면 **기각을 통과로 읽는다.**

실제로 두 줄이 그랬다. D-0091은 «단조 차용이 실재한다»가 D-0327에서 기각됐는데
`(D-0327 확인)`이었고, D-0104는 천장을 30~60배 넘겨 **깨졌는데** `(D-0322 확인)`이었다.
**같은 판에서 PLAN에는 「확인이 아니다」라고 적어 놓고 대장에는 확인으로 적었다.**
"""

REVERSAL = re.compile(r"기각|깨졌|폐기|파기|뒤집(?:었|혔)다")
"""갱신 배지가 **뒤집었다고 말하는** 자리. `확인` 꼬리표와 함께 서면 안 된다.

**동사만 본다.** 처음에 낱말 `뒤집`을 넣었더니 D-0169가 걸렸는데, 거기 있는
*"박 뒤집힘이 4/39에서 1/39로 줄었다"*는 **지표 이름**이고 그 판은 진짜 확인이었다.
셋 중 하나가 거짓이면 **그 검사는 안 읽힌다** (GR-0.8 · fire-lane MASTER §18-13).

그래서 `뒤집었다`·`뒤집혔다`만 받는다. **놓치는 쪽을 고른다** — 이 검사는 막는 것이
아니라 잡는 것이고, 거짓 경보 하나가 진짜 둘을 죽인다.
"""


EVIDENCE_VALUES = re.compile(
    r"^(합성(?: \(D-\d{4} 승격 아님\))?|해당 없음|불명|실물 \S.*|합성 · 실물 \S.*)$"
)
"""쓸 수 있는 값. **넷뿐이다** (D-0265).

| 값 | 뜻 |
|---|---|
| `합성` | 지은 자료에서 냈다 — `default_rng` · 합성 파형 · 임시 나무 |
| `실물 <무엇>` | 실제 자료나 실제 기기에서 냈다. 무엇이었는지 적는다 |
| `합성 · 실물 <무엇>` | 둘 다 썼다 — 합성 귀무 대조 + 실물 측정 |
| `해당 없음` | **아무것도 안 쟀다.** 설계 판단 · 규약 · 도구 배선 |
| `불명` | 쟀는데 무엇으로 쟀는지 기록에 없고 알아낼 수 없다 |
| `합성 (D-xxxx 승격 아님)` | 합성인데 **뒤 판이 승격시키지 않는다**고 판단했다 (D-0323) |
| `... (D-xxxx 뒤집힘)` | 뒤 판이 **판정을 뒤집었다.** 「확인」이 아니다 (D-0328) |

**인용은 안 센다.** 남의 기록에서 가져온 수는 그 기록의 칸이 든다. 아직 안 잰
것(«실측 필요»)은 `해당 없음`이다 — 그 기준이 없으면 같은 기록이 세션마다 달리 분류된다."""


def evidence_base(value: str) -> str:
    """`자료` 값에서 **꼬리표를 뗀 몸통** (D-0323).

    `합성 (D-0315 승격 아님)` → `합성`. **꼬리표는 판단이지 자료가 아니다** — 세는 쪽은
    몸통만 봐야 빚 수가 안 흔들린다.

    **한 자리에 둔다.** 이 식이 `doc_fsck`와 `decision_evidence` 두 곳에 생겼고, 두 벌이
    되면 한쪽만 고치는 날이 온다 (D-0317이 같은 자리에서 겪었다).
    """
    return value.split(" (")[0].strip()


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
