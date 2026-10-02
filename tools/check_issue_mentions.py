#!/usr/bin/env python3
"""닫힌 미해결 질문을 코드가 **열린 것처럼** 적고 있는가 (D-0126).

### 왜 필요한가

`O-38`은 D-0114가 닫았다. 그런데 `sweep_self_transition`과 `harmony_generator`의
문서 문자열이 *"안 움직이면 짐작이 틀린 것이고 O-38(닫힘 D-0114)은 다른 원인을 찾아야 한다"*고
**살아 있는 질문처럼 적고 있었다.**

D-0125 세션이 그것을 읽고 O-38을 두 판 끌었다. **미해결표를 안 보고 코드 문서
문자열을 봤다.** 기획서에는 닫혔다고 적혀 있었고 코드에는 안 적혀 있었다.

### 규약은 이미 있었다

닫힌 질문 열셋 중 일곱은 코드에서 `(O-31 · D-0083)`처럼 **닫은 결정을 같이 적는다.**
지키는 자리가 다수였고 O-38(D-0114)만 안 지켰다. **적혀 있는데 안 지켜지는 규약이 GR-0.8이
말한 그것이다** — D-0117의 `main.py` 4161줄과 같은 부류다.

### 규칙

**닫힌 질문 번호를 적으면 같은 줄에 그 질문을 닫은 결정 번호를 적는다.**

- 닫힌 질문과 그 결정 번호는 `docs/MASTER.md`의 닫힘표에서 읽는다. **여기 손으로
  적지 않는다** — 두 곳이 어긋난다 (D-0043).
- **열린 질문은 안 본다.** 열린 질문에는 닫은 결정이 없다.
- **결정 번호면 무엇이든 통과시킨다.** 닫은 결정을 콕 집어 요구하는 안은 기각했다 —
  `evaluate_degree_restriction.py`가 `(O-31 · D-0083)`이라 적는데 D-0083은 그 모듈을
  **만든** 결정이고 닫은 것은 D-0088이다. **둘 다 참이고 출처 쪽이 더 쓸모 있다.**
  엄격 규칙은 옳게 적은 줄 24곳을 잡았다. 막으려는 것은 **맨몸 참조**다.

### 무엇을 안 보는가

`docs/`는 안 본다. 결정 기록은 **닫히기 전 시점을 그대로 적는 문서**이고, 거기에
사후 번호를 달게 하면 기록이 기록이 아니게 된다 (D-0081의 *"소급해서 고치지 않는다"*).

    python3 tools/check_issue_mentions.py            # 검사한다
    python3 tools/check_issue_mentions.py --list     # 닫힌 질문과 결정을 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLOSED_BEGIN = "<!-- closed-issues:begin -->"
CLOSED_END = "<!-- closed-issues:end -->"
OPEN_BEGIN = "<!-- open-issues:begin -->"
OPEN_END = "<!-- open-issues:end -->"
PLAN = "docs/PLAN.md"

TREES = ("core/hathor", "tools", "core/tests")
"""훑을 코드 나무. **`core/tests`도 본다** (D-0146).

D-0126은 *"검사 이름이 질문 번호를 갖는 것은 정상"*이라며 뺐다. **전수로 훑으니
25곳이 나왔고 전부 산문이었다** — 문서 문자열과 주석이며 제품 코드와 같은 부류다.
`O-38·D-0114이 닫혔는데 열린 것처럼 적혀 있다`는 위험이 검사 파일이라고 달라지지 않는다.

**나무를 빼는 대신 파일 하나를 뺀다.**"""

SKIP_FILES = (
    "core/tests/unit/test_issue_mentions.py",
    "core/tests/unit/test_check_decisions.py",
)
"""검사에서 빼는 파일. **둘 다 가짜 자료를 들고 있다.**

앞의 것은 이 검사의 검사다 — **맨몸 참조를 일부러 담는다**. 잡히는지 보는 자료다.

뒤의 것은 색인 도구를 합성한 열림·닫힘표로 시험한다 (D-0183). 거기 적힌 질문 번호는
**참조가 아니라 자료**이며, 결정 번호를 붙이면 시험이 시험이 아니게 된다.

나무를 통째로 빼면 사각지대가 되고, 파일 하나를 빼면 그 파일만 사각지대다."""

DOCUMENTS = (
    "README.md",
    "docs/PLAN.md",
    "docs/MASTER.md",
    "docs/DECISIONS.md",
)
"""훑을 문서. **축 셋과 진입 전부다** (D-0145).

D-0126은 `docs/`를 통째로 뺐고 사유는 *"결정 기록은 그 시점을 그대로 적는다"*였다.
**그 사유는 `docs/DECISIONS.md`에만 맞는다** — 과거 축이라 소급 수정이 금지다 (D-0081).

**`PLAN`과 `MASTER`는 현재와 미래이며 고칠 수 있고 고쳐야 한다.**

**뿌리 `MASTER.md`는 없다** (D-0189가 흡수했다). 사장 항목이 `exists()`에 걸려
조용히 지나고 있었다 — 지웠다 (D-0349).
"""

FLOOR = {"문서": 3, "코드": 250}
"""**시야 바닥. 줄면 실패한다** (D-0349 — 시야 못).

`deadcheck`의 `CEILING`과 같은 규율이다 (D-0117 · D-0223). 저쪽은 **죽은 검사가 늘면**
울고 여기는 **보는 것이 줄면** 운다.

### 카나리아로는 늦다

`SKIP_TREES`가 `("",)`로 비면서 문서 축이 통째로 죽었을 때, 카나리아는 **다음에 돌릴
때** 그것을 잡는다. **못은 바꾸는 그 판에 잡는다.** 둘이 막는 것이 다르다.

| | 무엇을 잡나 |
|---|---|
| 카나리아 | 시야는 그대로인데 **잡는 능력**을 잃었다 |
| **시야 못** | **시야 자체**가 조용히 줄었다 |

**코드 바닥은 느슨하다** — 파일이 생기고 사라지는 것은 정상이고, 막는 것은
**나무 하나가 통째로 빠지는 것**이다. 실측 302에 50을 뺐다. 문서 셋은 **정확히
셋이어야 한다** — 늘거나 줄면 축이 바뀐 것이고 그때는 이 수도 같이 고친다.
"""

SKIP_TREES = ("docs/DECISIONS.md",)
"""안 보는 나무. **과거 축은 그 시점을 적는다.**

**`("",)`였다** (D-0349). `name.startswith("")`는 **늘 참**이므로 `DOCUMENTS` 전부가
떨어져 나갔고, **문서 축이 한 줄도 안 보였다.** 위 독스트링에 **빈 백틱**이 남아
있던 것이 흔적이다 — 이름을 지우면서 상수까지 비웠다.

**302개 대상이 전부 코드였다.** D-0145가 *"축 셋과 규약과 진입 전부다"*라고 만든
검사가 **아무것도 안 보고 초록을 찍고 있었다** (GR-0.8).
"""

SKIP_NUMBERS = {
    59: "저장소 전수에 흔적이 한 줄도 없다. 번호가 났는지조차 모른다 — **조사 불가**",
}
"""**두 표 어디에도 없어도 되는 번호.** 사유를 같이 적는다 (D-0349).

**늘리면 못이 운다** (`check_sight.py` — `SKIP_` 머리는 천장이다). 조이려면 `check_sight.py
--update`를 돌려야 하고 그러면 결정 기록에 한 줄이 남는다. **이 목록이 조용히
자라면 전수 검사가 꺼진 것과 같다.**

번호를 접은 것은 여기 안 적는다 — **닫힘표에 행으로 적는다.** O-61(D-0202)이 그
꼴이다: O-10과 같은 질문이라 접었다. 숨은 목록보다 찾아지는 행이 낫다.
"""

ISSUE = re.compile(r"O-\d+")
DECISION = re.compile(r"D-(\d{4})")
ROW = re.compile(r"^\|\s*(O-\d+)\s*\|")


def open_issues(plan_text: str) -> set[str]:
    """열린 질문 번호. **열린표가 정본이다** — 여기 목록을 적지 않는다."""
    if OPEN_BEGIN not in plan_text or OPEN_END not in plan_text:
        return set()
    block = plan_text.split(OPEN_BEGIN)[1].split(OPEN_END)[0]
    found: set[str] = set()
    for row in block.splitlines():
        match = ROW.match(row)
        if match:
            found.add(match.group(1))
    return found


def closed_issues(design_text: str) -> dict[str, set[int]]:
    """닫힌 질문 → 그 행이 가리키는 결정 번호들.

    **닫힘표가 정본이다.** 이 파일에 목록을 적지 않는다.
    """
    if CLOSED_BEGIN not in design_text or CLOSED_END not in design_text:
        return {}
    block = design_text.split(CLOSED_BEGIN)[1].split(CLOSED_END)[0]
    found: dict[str, set[int]] = {}
    for row in block.splitlines():
        match = ROW.match(row)
        if match:
            found[match.group(1)] = {int(value) for value in DECISION.findall(row)}
    return found


def targets() -> list[Path]:
    """훑을 파일. 정렬해 낸다 — **문제 순서가 기기마다 달라지면 못 읽는다.**"""
    found: list[Path] = []
    for tree in TREES:
        base = ROOT / tree
        if base.is_dir():
            found.extend(
                path
                for path in sorted(base.rglob("*.py"))
                if "__pycache__" not in path.parts
                and path.relative_to(ROOT).as_posix() not in SKIP_FILES
            )
    found.extend(
        ROOT / name
        for name in DOCUMENTS
        if (ROOT / name).exists() and not name.startswith(SKIP_TREES)
    )
    return found


def check(design_text: str, plan_text: str = "") -> list[str]:
    """규칙을 어긴 자리를 전부 낸다. **첫 문제에서 멈추지 않는다.**"""
    table = closed_issues(design_text)
    if not table:
        return [f"DESIGN에 {CLOSED_BEGIN} 표식이 없다"]
    living = open_issues(plan_text)
    problems: list[str] = []
    for path in targets():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            annotated = bool(DECISION.search(line))
            for issue in dict.fromkeys(ISSUE.findall(line)):
                closers = table.get(issue)
                if closers is None:
                    # **두 표 어디에도 없으면 고아다** (D-0183). 닫힘표에 있는 번호만
                    # 보던 동안 `O-1(D-0019)` · `O-7` · `O-8` · `O-9`가 27자리에서 조용히
                    # 불리고 있었다 — 닫혔는데 표에 소급 등록이 안 된 것들이다.
                    if living and issue not in living:
                        problems.append(
                            f"{name}:{number}: {issue}이 열린표에도 닫힘표에도 없다. "
                            f"닫혔으면 DESIGN 닫힘표에 적는다"
                        )
                    continue
                if annotated:
                    continue
                wanted = " · ".join(f"D-{value:04d}" for value in sorted(closers))
                problems.append(
                    f"{name}:{number}: {issue}은 닫혔는데 맨몸으로 적혀 있다. "
                    f"같은 줄에 결정을 적는다 (닫힘표: {wanted})"
                )
    return problems


def census(design_text: str, plan_text: str, past_text: str = "") -> list[str]:
    """**번호 전수.** 1부터 최대까지 **두 표 중 정확히 한 곳**에 있어야 한다 (D-0349).

    D-0346이 *"`MASTER` 닫힌 미해결 표에 셋. 번호 자리에 넣었다"*라고 적었는데
    **들어간 것은 O-55 하나였다** (D-0346). O-6 · O-14(D-0349가 넣었다)는 **두 표
    어디에도 없는 고아**로 남았고 **348판이 통과했다.**

    기존 검사는 **코드가 부르는 번호**만 봤다 — 아무도 안 부르는 고아는 안 걸린다.
    D-0126이 적은 그 문장이다: ***조건을 적어 두고 아무도 안 세면 영원히 잠긴다.***

    **겹침도 본다.** 한 번호가 두 표에 다 있으면 닫혔는지 열렸는지 알 수 없고,
    `debts`의 합계가 그것을 두 번 센다 (D-0346의 그 꼴).

    ### 천장을 두 표에서 읽으면 안 된다

    처음 안은 `max(두 표)`까지 봤다. **그러면 맨 윗 행을 지우는 것이 안 걸린다** —
    천장이 같이 내려가서 구멍이 메워진 것처럼 보인다. 시험이 그것을 잡았다.

    **천장은 과거 축에서 읽는다** (`docs/DECISIONS.md`). 추가만 하는 문서라 줄지
    않고, 번호가 난 판이 거기 적혀 있다 (D-0081).
    """
    closed = {int(key.removeprefix("O-")) for key in closed_issues(design_text)}
    opened = {int(key.removeprefix("O-")) for key in open_issues(plan_text)}
    if not closed or not opened:
        return ["두 표 중 한쪽이 비었다 — 표식(`closed-issues` · `open-issues`)을 본다"]
    ever = {int(found.removeprefix("O-")) for found in ISSUE.findall(past_text)}
    problems = [
        f"O-{number}이 닫힘표와 열림표에 **둘 다** 있다. 한 곳에만 있어야 한다"
        for number in sorted(closed & opened)
    ]
    problems.extend(
        f"O-{number}이 두 표 어디에도 없다. **고아다** — 닫혔으면 `MASTER` 닫힘표에, "
        f"살았으면 `PLAN` 열림표에 적는다. 번호가 안 났다면 `SKIP_NUMBERS`에 사유를 적는다"
        for number in sorted(set(range(1, max(closed | opened | ever) + 1)) - closed - opened)
        if number not in SKIP_NUMBERS
    )
    return problems


def shortfall(seen: list[Path]) -> list[str]:
    """**시야가 바닥 밑으로 내려간 축**을 전부 낸다 (D-0349 — 시야 못).

    `deadcheck.CEILING`과 같다 — **정본은 여기 하나이고 손으로 조인다** (D-0223).
    저쪽은 늘면 울고 여기는 **줄면** 운다.
    """
    counted = {
        "문서": sum(1 for path in seen if path.suffix == ".md"),
        "코드": sum(1 for path in seen if path.suffix == ".py"),
    }
    return [
        f"{axis} 시야가 {counted[axis]}개다. 바닥은 {floor}개였다 — "
        f"상수가 비었는지 본다(`DOCUMENTS` · `TREES` · `SKIP_TREES`). "
        f"줄인 것이 맞다면 `FLOOR['{axis}']`를 같이 내린다"
        for axis, floor in FLOOR.items()
        if counted[axis] < floor
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="닫힌 질문 표기 검사 (D-0126)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="닫힌 질문과 결정을 찍는다")
    args = parser.parse_args()

    design_text = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    plan_text = (ROOT / PLAN).read_text(encoding="utf-8") if (ROOT / PLAN).exists() else ""
    if args.list:
        for issue, closers in closed_issues(design_text).items():
            joined = " · ".join(f"D-{value:04d}" for value in sorted(closers))
            print(f"  {issue}  {joined}")
        return 0

    # **그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230 · D-0349).
    # 이 검사는 `SKIP_TREES` 하나가 비면서 **문서를 한 줄도 안 보는 채로** 초록을
    # 찍고 있었다. 「닫힘 42 · 열림 30」은 **표의 수**이지 **읽은 파일 수**가 아니라
    # 아무도 못 알아챘다. **자기가 몇 개를 봤는지 찍고, 0이면 실패한다.**
    seen = targets()
    papers = [path for path in seen if path.suffix == ".md"]
    empty = shortfall(seen)
    if empty:
        print(f"시야가 바닥 밑으로 내려갔다. {len(empty)}축이다.", file=sys.stderr)
        for text in empty:
            print(f"  - {text}", file=sys.stderr)
        return 1

    past_text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    problems = census(design_text, plan_text, past_text) + check(design_text, plan_text)
    if problems:
        print(f"닫힌 질문을 열린 것처럼 적은 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(
        f"닫힌 질문 표기 검사 통과 · 닫힘 {len(closed_issues(design_text))}건"
        f" · 열림 {len(open_issues(plan_text))}건"
        f" · 훑은 것 {len(seen)}개(문서 {len(papers)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
