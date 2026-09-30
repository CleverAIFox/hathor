#!/usr/bin/env python3
"""기록이 **무엇으로 서 있는가**를 본다 (D-0288).

`check_decisions.py`에서 셋을 떼어 왔다. 셋이 같은 물음의 세 갈래다.

| 칸 | 묻는 것 | 결정 |
|---|---|---|
| `자료` | **무엇으로 쟀나** — 합성인가 실물인가 | D-0265 |
| 논거 | 판단을 사람에게 돌렸으면 **그 사람의 말**이 있나 | D-0133 · D-0285 |
| `강제자` | 지키는 시험이 **실재하나** | O-58 · D-0288 |

**판정만 한다.** 대장을 쓰는 것은 `decision_ledger.py`이고, 번호·참조·표기는 저쪽이다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from decision_ledger import (
    EVIDENCE,
    EVIDENCE_VALUES,
    NOT_PROMOTED,
    Record,
    evidence_base,
    keeper_text,
)

ROOT = Path(__file__).resolve().parent.parent


UNKNOWN_EVIDENCE = 0
"""`자료 불명`의 천장 (D-0265). **지금 0이다.**

264건을 전수로 채우면서 하나도 `불명`이 안 나왔다 — **«재현 불명»과 «자료 불명»은
다르다.** 명령이 사라진 11건도 무엇으로 쟀는지는 적고 있었다. 산출물은 없어졌지만
자료의 정체는 남아 있다.

늘리려면 결정 기록이 필요하다 (D-0118). **모르는 것을 «해당 없음»으로 숨기는 쪽이
훨씬 쉬우므로** 이 천장이 그 길을 막는다."""


def check_evidence(records: list[Record]) -> list[str]:
    """기록마다 `자료` 칸이 있고 값이 규약 안인가 (D-0265).

    **전 기록에 건다.** `FORMAT_ENFORCED_FROM` 뒤로 미루지 않는다 — 264건을 읽어 전수로
    채웠으므로 구멍이 0이고, **구멍이 0일 때 못 박는다** (D-0134 · D-0261).
    """
    problems: list[str] = []
    unknown = 0
    for record in records:
        found = EVIDENCE.search(record.body)
        if found is None:
            problems.append(
                f"{record.identifier}에 `자료` 칸이 없다. 값은 {EVIDENCE_VALUES.pattern}"
            )
            continue
        value = found.group(1).strip()
        if not EVIDENCE_VALUES.match(value):
            problems.append(f"{record.identifier}의 `자료` 값이 규약 밖이다: {value!r}")
        if value == "불명":
            unknown += 1
        problems.extend(_confirmation(record, value))
    if unknown > UNKNOWN_EVIDENCE:
        problems.append(f"`자료 불명`이 {unknown}건으로 천장 {UNKNOWN_EVIDENCE}건을 넘는다")
    return problems


CONFIRMED_BY = re.compile(r"\(D-(\d{4}) 확인\)")
"""`자료` 칸을 **뒤에 온 판이 갱신했다**는 표식 (D-0301).

`자료`는 표기 칸이라 소급 갱신 대상이다 (GR-0.2 *"표기는 소급해 맞추고 내용은 안
맞춘다"* · D-0081) — D-0265가 264건을 전수로 채운 것이 그 근거다. **그런데 고칠 수
있게 된 순간 조용히 고쳐질 수 있다.** 갱신한 판의 번호를 칸에 적게 하고, 그 번호가
자기보다 **뒤**인지 본다. 앞 번호를 적으면 *"나중 실측이 확인했다"*가 거짓이다.

참조가 실존하는지는 `check_decisions`의 참조 무결성이 이미 본다.
"""


def _confirmation(record: Record, value: str) -> list[str]:
    """`(D-xxxx 확인)`과 `(D-xxxx 승격 아님)`이 **자기보다 뒤 번호**인가 (D-0301 · D-0323)."""
    problems: list[str] = []
    for label, pattern in (("확인됐다", CONFIRMED_BY), ("승격 아니라고 판단됐다", NOT_PROMOTED)):
        for mark in pattern.finditer(value):
            number = int(mark.group(1))
            if number <= record.number:
                problems.append(
                    f"{record.identifier}의 `자료`가 D-{number:04d}로 {label}는데 "
                    f"자기보다 앞 번호다. 뒤에 온 판만 앞 판의 자료를 갱신한다"
                )
    return problems


ATTRIBUTION = re.compile(
    r"사용자[가는]?\s*[^\n]{0,20}?(반대했|골랐|정했|택했|판정했|지시했|승인했|거부했|요구했|물었|짚었|시켰)"
)
"""판단을 **사람에게 귀속시킨 자리** (D-0133 · D-0285).

D-0133이 *"결정의 근거는 사람이 아니라 논거다"*라고 적고 **세는 것을 안 만들었다.** <!--voice-ok-->
PLAN은 그 뒤로 «25곳»이라고 적어 뒀는데 실측은 **26건 귀속 · 근거 없는 것 0건**이다 —
갚혀 있는 빚을 두 해 가까이 장부에 남겨 둔 셈이다."""

QUOTED = re.compile(r'\*"[^"]+"\*|«[^»]+»|"[^"]{4,}"')
"""그 사람의 말이 기록 안에 남아 있는가.

**줄이 아니라 기록 단위로 본다.** 표제(«사용자가 전제를 짚었다»)에서 귀속하고 본문에서
인용하는 꼴이 실재하며, 그것은 잘못이 아니다 — 읽는 사람이 **무엇이 판단을 움직였는지**
그 기록 안에서 확인할 수 있으면 된다."""


def check_attribution(records: list[Record]) -> list[str]:
    """사람에게 귀속시킨 기록이 그 사람의 말을 같이 들고 있는가 (D-0285).

    **전 기록에 건다.** `FORMAT_ENFORCED_FROM` 뒤로 미루지 않는다 — 실측으로 구멍이
    0이고, **구멍이 0일 때 못 박는다** (D-0134).

    D-0133이 «소급 안 한다»고 적은 것은 **근거를 지어내지 않기 위해서**였다. 이 검사는
    근거를 지어내라고 하지 않는다 — **그때 그 사람이 한 말**이 남아 있기를 요구할 뿐이고,
    실측상 전 기록이 이미 그렇다.
    """
    problems: list[str] = []
    for record in records:
        if ATTRIBUTION.search(record.body) and not QUOTED.search(record.body):
            problems.append(
                f"{record.identifier}이 판단을 사람에게 귀속시키면서 그 사람의 말이 없다. "
                "무엇이 판단을 움직였는지 그 자리에 적는다 (D-0133 · D-0285)"
            )
    return problems


NODE = re.compile(r"`([\w./-]+\.py)::([\w가-힣_]+)`")
"""`파일::함수`까지 적은 강제자. **파일까지만 적은 것은 여기 안 걸린다** — 그쪽은 `BARE`가 든다."""

BARE = re.compile(r"`([\w./가-힣-]+\.py)(::[\w가-힣_]+)?`")
"""강제자가 든 경로 하나. **함수 부분은 있을 수도 없을 수도 있다.**"""


def _functions(path: Path) -> set[str] | None:
    """그 파일이 정의한 함수 이름. 파일이 없으면 `None`이다."""
    if not path.exists():
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


NODE_FROM = 270
"""**시험 강제자에 함수까지 적기 시작한 번호** (O-58 닫힘 D-0291).

O-58 (닫힘 D-0291)이 *"강제자가 파일까지만 가리킨다 — 검사도 파일이 있는지만
본다"*고 적었다. <!--voice-ok-->
D-0191이 그렇게 났다 — 적은 파일이 그 함수를 안 보는데도 초록이었다.

**소급하지 않는다.** 옛 156건에 함수를 지금 붙이면 «그때 무엇이 지켰나»가 아니라
«지금 무엇이 지키나»가 되고, 그것은 추가 전용이 막으려는 것이다 (GR-0.2 · D-0081).
`FORMAT_ENFORCED_FROM`과 같은 꼴로 **번호를 끊는다.**

**실측으로 270을 골랐다.** D-0270부터 D-0290까지 시험 강제자 중 함수가 없는 것이
**0건**이다 — 그 뒤로 이미 그렇게 쓰고 있었고 **아무도 그것을 세지 않았다.**
구멍이 0인 자리에 못을 박는다 (D-0134)."""

TEST_TREE = "core/tests/"
"""여기를 가리키면 함수까지 묻는다.

**도구를 가리키는 강제자 44건은 다른 꼴이다** — `tools/check_file_size.py`가 강제자면
**래칫 자체가 지키는 것**이고 그 안에 함수가 따로 없다. 그것까지 묻으면 오탐이고,
오탐은 사람이 검사를 끄게 만든다."""


def check_keeper_text(records: list[Record]) -> list[str]:
    """`강제자` 칸이 **비어 있지 않은가** (D-0304).

    머리만 두고 들여쓰기를 잊으면 `keeper_text`가 빈 문자열을 낸다. 그러면 대장에서 행이
    빠지고 함수 실재도 안 보게 되는데 **아무 검사도 그것을 안 봤다** — 네 판이 그 상태로
    열일곱 관문을 통과했다.

    **전 기록에 건다.** 지금 빈 칸이 0이므로 못을 박는다 (D-0134).
    """
    return [
        f"{record.identifier}의 `강제자` 칸이 비어 있다. 같은 줄에 두 칸 뒤로 적거나 "
        "다음 줄들을 네 칸 들여쓴다 — 비면 대장에서 조용히 빠진다 (D-0304)"
        for record in records
        if keeper_text(record.body) == ""
    ]


def check_keepers(records: list[Record]) -> list[str]:
    """강제자가 가리키는 **시험 함수가 실재하는가** (O-58 닫힘 D-0288).

    **O-58 (닫힘 D-0291)이 적은 그 병이다** — *"강제자 `tests/test_x.py`처럼 파일까지만
    적으면, 그 파일이
    해당 함수를 안 봐도 초록이다."* D-0191이 그렇게 났다. 그 뒤로도 아무도 안 셌다.

    실측: 함수까지 적은 강제자 65건 중 **4건이 없는 함수를 가리키고 있었다.** 넷 다
    **내가 이름을 바꾼 것**이다 — D-0273이 배선 시험 둘을 새로 쓰고, D-0281이 계산 시험을
    쪼개면서 옛 이름이 기록에 남았다. **고치는 판마다 강제자를 안 따라갔다.**

    **강제자 읽기는 `decision_ledger.keeper_text`가 든다** (D-0304). 여기에도 정규식이
    있었고 `^강제자  (.+)$`였다 — 머리만 두고 들여쓴 꼴을 못 읽어 **네 판의 함수 실재를
    조용히 안 봤다.** 대장과 `check_doc_style`도 각자 다르게 틀렸다.

    **파일까지만 적은 205건은 여기 안 걸린다.** 못은 구멍이 0인 데에만 박는다 (D-0134) —
    함수까지 적은 쪽은 넷을 고치니 0이고, 파일까지만 적은 쪽은 O-58 (닫힘 D-0291)이 계속 든다.
    """
    problems: list[str] = []
    for record in records:
        found = keeper_text(record.body)
        if not found:
            continue
        for path_text, function in NODE.findall(found):
            known = _functions(ROOT / path_text)
            if known is None:
                problems.append(f"{record.identifier}의 강제자가 없는 파일을 가리킨다: {path_text}")
            elif function not in known:
                problems.append(
                    f"{record.identifier}의 강제자가 없는 함수를 가리킨다: "
                    f"{path_text}::{function} (O-58 닫힘 D-0288)"
                )
        problems += _bare_files(record)
    return problems


def _bare_files(record: Record) -> list[str]:
    """`NODE_FROM` 뒤의 기록이 시험 파일을 **함수 없이** 가리키는가 (O-58 닫힘 D-0291)."""
    if record.number < NODE_FROM:
        return []
    found = keeper_text(record.body)
    if not found:
        return []
    return [
        f"{record.identifier}의 강제자가 시험 파일까지만 가리킨다: {path_text}. "
        f"`{path_text}::함수` 꼴로 적는다 — 그 파일이 그 함수를 안 봐도 초록이었다 "
        "(O-58 닫힘 D-0291)"
        for path_text, node in BARE.findall(found)
        if path_text.startswith(TEST_TREE) and not node
    ]


UPDATED_BY = re.compile(r"갱신됨 — D-(\d{4})")
"""«갱신됨 — D-XXXX» 머리. **본문 맨 위 인용 블록에만 쓰인다** (D-0043의 서술 규약)."""


def payable(records: list[Record]) -> list[str]:
    """**빚이 이미 갚였을지 모르는 기록**을 센다 (D-0317).

    ### 왜 이것이 필요했나

    D-0313이 합성 강제자 넷을 *"도구는 섰고 실측만 남았다"*로 묶었다. **둘은 그 도구가
    재는 것이 아니었고**(D-0169 · D-0170은 대역과 사건 길이이며 `eval onsets`는 포락선
    자기상관만 본다) **그 둘은 이미 D-0171이 실물 39곡으로 확인해 놓은 상태였다.**
    146개 기록이 지나도록 아무도 `자료` 칸을 안 옮겼다.

    D-0301이 `(D-xxxx 확인)` 규약을 세운 것이 바로 그 자리인데 **소급 적용을 안 했다.**

    ### 명단은 **비워지는 것**이다 (D-0323)

    **전부가 갚을 것은 아니다.** 승격 조건은 *"뒤 판이 실물로 쟀다"*가 아니라 **"뒤 판이
    그 주장을 확인했다"*이고, 둘은 다르다 — 결함을 찾았거나 판정을 뒤집었으면 승격 대상이
    아니다.

    **그 판단을 `자료` 칸에 적으면 명단에서 나간다.** `합성 (D-xxxx 승격 아님)`이며
    `(D-xxxx 확인)`의 짝이다. 안 적으면 「아니다」가 쌓이고, **「아니다」로만 찬 명단은
    아무도 안 읽는다** — 첫 판에서 다섯이던 것이 두 판 만에 일곱이 됐다.

    그래서 **못을 안 박는다.** 명단이 0인 것이 목표가 아니라 **모든 줄이 판단을 기다리는
    줄인 것**이 목표다. 0으로 박으면 「아니다」를 승격으로 바꾸게 되고, 그러면 거짓
    경보가 되고 **거짓 경보는 진짜 경보를 죽인다** (`fire-lane` MASTER §18-13).

    `make ship`이 이 수를 찍는다 — 보는 자리에 두는 것이 이 함수의 전부다.
    """
    source = {
        record.identifier: hit.group(1).strip()
        for record in records
        if (hit := EVIDENCE.search(record.body))
    }
    rows: list[str] = []
    for record in records:
        value = source.get(record.identifier, "")
        if evidence_base(value) != "합성" or NOT_PROMOTED.search(value):
            continue
        later = [
            f"D-{number}"
            for number in sorted(set(UPDATED_BY.findall(record.body)))
            if "실물" in source.get(f"D-{number}", "")
        ]
        if later:
            rows.append(f"{record.identifier} ← {' · '.join(later)}")
    return rows
