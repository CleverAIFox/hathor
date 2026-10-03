#!/usr/bin/env python3
"""요구사항 정의서가 **자기 규약을 지키나** (D-0350).

### 규약을 적어 두고 아무도 안 셌다

`MASTER` Part II가 제 규약을 세 줄로 적는다 — ID 꼴 · 우선순위 · 상태 집합. 그리고
**MVP 경계**를 못 박는다:

> *"우선순위 M은 P4까지의 범위에 한정한다. P5 이후 요구사항은 최대 S를 부여한다.
> 이는 미완 시 MVP 판정에 영향을 주지 않기 위한 장치다."*

**아홉 건이 그것을 어기고 있었고 세는 자가 없었다.** D-0126이 적은 그 문장이다 —
***조건을 적어 두고 아무도 안 세면 영원히 잠긴다.***

### 아홉을 S로 내리는 것이 답이 아니다

재 보니 아홉이 **셋으로 갈린다.**

| 부류 | 왜 단계와 무관하게 M인가 |
|---|---|
| 안전·법적 | `REQ-QUA-001`이 **D-0003**이다 — 음색 차단. 내리면 **제품이 아니라 위험**이다 |
| 재현성 | `REQ-GEN-009` · `REQ-EVL-005`는 **D-0009**다. 못 믿는 결과는 결과가 아니다 |
| 엔진 관문 | `REQ-EVL-007` · `REQ-EVL-008`은 **D-0217**이 착수 전에 적은 관문이다 |

**규칙이 블런트했던 것이고 행이 틀린 것이 아니다.** 그래서 **예외를 선언하고 센다** —
`fire-lane`의 *"선언되지 않은 차집합을 묻는다"* 꼴이다 (`gate_parity.py`). 예외마다
사유가 붙고, **사유 없는 예외는 그냥 구멍이다.**

### 완료인데 근거가 없으면 무엇이 완료시켰는지 모른다

`REQ-INF-002` · `REQ-INF-004`가 **완료**인데 비고가 비어 있었다. D-0132가 강제자에
대해 적은 규율과 같다 — **없다는 사실 자체가 기록이어야 한다.** 끝난 것은 **무엇이
끝냈는지**를 적는다.

    python3 tools/check_requirements.py            # 검사한다
    python3 tools/check_requirements.py --list     # 실측을 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "docs" / "MASTER.md"

ROW = re.compile(
    r"(?m)^\|\s*(REQ-([A-Z]{2,3})-(\d{3}))\s*\|(.*?)\|\s*([MSC])\s*\|\s*(P\d)\s*\|\s*(\S+)\s*\|(.*?)\|\s*$"
)
"""요구사항 한 행.

**비고가 비어도 잡는다.** 첫 판이 `\\| (.*?) \\|$`였고 `| |`(한 칸)을 떨어뜨려
**97행 중 72행만 셌다** — 빈 비고 23건이 통째로 안 보였고 그중 둘이 이 판의 결함이다.
**세는 자 자신이 빈 그물이었다** (D-0230).
"""

TREE = re.compile(r"(?m)^[├└]─ REQ-([A-Z]{2,3})\s")
"""체계도의 그룹 코드. **`REQ-UI`는 두 글자다** — `[A-Z]{3}`으로 훑으면 빠진다."""

STATES = ("미착수", "진행", "부분", "완료", "강제", "설계", "보류", "변경", "폐기")
"""쓸 수 있는 상태. **정본은 Part II의 ID 체계 표다** — 늘리면 그 표도 같이 고친다."""

DONE = ("완료", "강제")
"""끝난 상태. **무엇이 끝냈는지를 비고가 들어야 한다** (D-0132의 규율)."""

MVP_PHASE = 4
"""우선순위 M의 단계 상한. **정본은 Part II의 「MVP 경계」 문단이다.**"""

MVP_EXEMPT = {
    "REQ-GEN-009": "재현성 — D-0009. 못 믿는 결과는 결과가 아니다",
    "REQ-EVL-005": "재현성 — D-0009. CI 재현성 잡이 든다",
    "REQ-EVL-007": "엔진 관문 — D-0112 · D-0217이 착수 전에 적었다",
    "REQ-EVL-008": "엔진 관문 — D-0217의 G0 ~ G3",
    "REQ-LYR-003": "법적 — 기존 가사 복제 금지. 내리면 제품이 아니라 위험이다",
    "REQ-VOC-003": "안전 — D-0003. G2 음색 누설 관문이 대신한다 (D-0217)",
    "REQ-QUA-001": "안전 — **D-0003 실존 가수 음색 차단.** 이 저장소의 금지 1호다",
    "REQ-QUA-002": "안전 — 위 판정 기준. 문턱을 뒤에 고르면 그것이 D-0058이다",
    "REQ-UI-006": "제출 요건 — 설치 없이 보이는 판이 없으면 심사에서 못 돈다",
}
"""**단계와 무관하게 M인 것.** 사유를 같이 적는다 (D-0350).

**늘리면 `check_sight`가 운다** — 이름이 `MVP_`로 시작해 바닥이지만, 늘어난 수는
`doc_fsck`의 축이 든다. **예외가 조용히 자라면 규칙이 꺼진 것과 같다.**

`fire-lane`의 역검증도 같이 걸었다 (`test_requirements.py`) — **예외에 있는데 이미
규칙을 지키고 있으면 줄을 지운다.** 낡은 면제는 사각지대가 된다.
"""


class Row:
    """요구사항 한 행. **읽는 자리가 하나다** (D-0272의 규율)."""

    def __init__(self, raw: tuple[str, ...]) -> None:
        self.rid, self.group, number, title, self.rank, phase, self.state, note = raw
        self.number = int(number)
        self.phase = int(phase[1:])
        self.title = title.strip()
        self.note = note.strip()


def rows() -> list[Row]:
    return [Row(raw) for raw in ROW.findall(MASTER.read_text(encoding="utf-8"))]


def declared_groups() -> set[str]:
    return set(TREE.findall(MASTER.read_text(encoding="utf-8")))


def check(
    found: list[Row],
    groups: set[str],
    exempt: dict[str, str] | None = None,
) -> list[str]:
    """어긴 자리를 **전부** 낸다. 첫 문제에서 멈추지 않는다.

    `exempt`는 시험이 넣는 자리다 — 합성 표에 실물 예외를 들이대면 **낡은 면제**로
    전부 운다. **정본은 `MVP_EXEMPT` 하나이고** 안 주면 그것을 쓴다 (D-0223).
    """
    if not found:
        return ["요구사항 행을 0개 읽었다. **그물이 비었다** — `ROW`를 본다 (D-0230)"]
    if not groups:
        return ["체계도에서 그룹을 0개 읽었다. **그물이 비었다** — `TREE`를 본다"]

    waived = MVP_EXEMPT if exempt is None else exempt
    problems: list[str] = []
    seen: defaultdict[str, list[int]] = defaultdict(list)
    for row in found:
        seen[row.group].append(row.number)
        if row.state not in STATES:
            problems.append(
                f"{row.rid}: 상태 «{row.state}»가 규약 밖이다 (쓸 수 있는 것: {STATES})"
            )
        if row.group not in groups:
            problems.append(f"{row.rid}: 그룹 `REQ-{row.group}`이 체계도에 없다")
        if row.state in DONE and not row.note:
            problems.append(
                f"{row.rid}: **{row.state}**인데 비고가 비었다 — "
                f"**무엇이 끝냈는지**를 적는다 (D-0132의 규율)"
            )
        if row.rank == "M" and row.phase > MVP_PHASE and row.rid not in waived:
            problems.append(
                f"{row.rid}: 우선 **M**인데 P{row.phase}다. MVP 경계는 P{MVP_PHASE}까지다 — "
                f"S로 내리거나 `MVP_EXEMPT`에 **사유와 함께** 적는다"
            )

    problems.extend(
        f"`REQ-{group}`이 체계도에 있는데 표에 0행이다" for group in sorted(groups - set(seen))
    )
    for group in sorted(seen):
        numbers = sorted(seen[group])
        repeated = sorted(one for one, count in Counter(numbers).items() if count > 1)
        problems.extend(
            f"REQ-{group}-{one:03d}이 두 번 있다. **번호는 재사용하지 않는다**" for one in repeated
        )
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        problems.extend(
            f"REQ-{group}-{one:03d}이 결번이다. 폐기했으면 **「폐기」 행으로 남긴다** — "
            f"지우면 번호가 재사용될 수 있다"
            for one in missing
        )
    problems.extend(
        f"{rid}이 `MVP_EXEMPT`에 있는데 표에 없다. **낡은 면제는 사각지대다** — 줄을 지운다"
        for rid in sorted(waived)
        if rid not in {row.rid for row in found}
    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="요구사항 정의서 규약 검사 (D-0350)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="실측을 찍는다")
    args = parser.parse_args()

    found = rows()
    groups = declared_groups()
    if args.list:
        print(f"  요구사항 {len(found)}행 · 그룹 {len(groups)}개")
        print(f"  우선   {dict(Counter(row.rank for row in found))}")
        print(f"  상태   {dict(Counter(row.state for row in found))}")
        print(f"  단계   {dict(sorted(Counter(row.phase for row in found).items()))}")
        print(f"  MVP 예외 {len(MVP_EXEMPT)}건")
        for rid, why in sorted(MVP_EXEMPT.items()):
            print(f"    {rid}  {why}")
        return 0

    problems = check(found, groups)
    if problems:
        print(f"요구사항 규약을 어긴 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(
        f"요구사항 검사 통과 · {len(found)}행 · 그룹 {len(groups)}개 · MVP 예외 {len(MVP_EXEMPT)}건"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
