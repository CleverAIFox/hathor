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

from decision_ledger import EVIDENCE, EVIDENCE_VALUES, Record

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
    if unknown > UNKNOWN_EVIDENCE:
        problems.append(f"`자료 불명`이 {unknown}건으로 천장 {UNKNOWN_EVIDENCE}건을 넘는다")
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


KEEPER = re.compile(r"^강제자  (.+)$", re.MULTILINE)
"""누가 이 판단을 지키나. **`강제자 없음 — 사유:` 꼴로 부재도 선언한다.**"""

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


def check_keepers(records: list[Record]) -> list[str]:
    """강제자가 가리키는 **시험 함수가 실재하는가** (O-58 닫힘 D-0288).

    **O-58 (닫힘 D-0291)이 적은 그 병이다** — *"강제자 `tests/test_x.py`처럼 파일까지만
    적으면, 그 파일이
    해당 함수를 안 봐도 초록이다."* D-0191이 그렇게 났다. 그 뒤로도 아무도 안 셌다.

    실측: 함수까지 적은 강제자 65건 중 **4건이 없는 함수를 가리키고 있었다.** 넷 다
    **내가 이름을 바꾼 것**이다 — D-0273이 배선 시험 둘을 새로 쓰고, D-0281이 계산 시험을
    쪼개면서 옛 이름이 기록에 남았다. **고치는 판마다 강제자를 안 따라갔다.**

    **파일까지만 적은 205건은 여기 안 걸린다.** 못은 구멍이 0인 데에만 박는다 (D-0134) —
    함수까지 적은 쪽은 넷을 고치니 0이고, 파일까지만 적은 쪽은 O-58 (닫힘 D-0291)이 계속 든다.
    """
    problems: list[str] = []
    for record in records:
        found = KEEPER.search(record.body)
        if found is None:
            continue
        for path_text, function in NODE.findall(found.group(1)):
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
    found = KEEPER.search(record.body)
    if found is None or found.group(1).startswith("없음"):
        return []
    return [
        f"{record.identifier}의 강제자가 시험 파일까지만 가리킨다: {path_text}. "
        f"`{path_text}::함수` 꼴로 적는다 — 그 파일이 그 함수를 안 봐도 초록이었다 "
        "(O-58 닫힘 D-0291)"
        for path_text, node in BARE.findall(found.group(1))
        if path_text.startswith(TEST_TREE) and not node
    ]
