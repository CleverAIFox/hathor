#!/usr/bin/env python3
"""**빚을 한 축만 세고 있었다** (D-0328).

### 왜 이 파일이 있나

`make ship`이 *"갚을 수 있는 빚 **없다**"*를 찍는 동안 이것들이 서 있었다.

| 무엇 | 실제 |
|---|---|
| `README.md`가 없는 폴더를 명령으로 준다 | `var/ingest/mert-layers` — D-0203이 없앴다 |
| `README.md`가 자기 안에서 모순된다 | 114행 «PDF로 굽는다» 대 242행 «브라우저가 그대로 그린다» |
| `MASTER` §10이 기각된 판정을 옛 수로 든다 | M8 «단조 차용이 실재한다» — D-0327이 기각 |
| `PLAN`에 끝난 항목이 산다 | O-39(기획서 배포)는 완료다 (D-0222) |
| 기획서가 15판 뒤처졌다 | D-0312에서 멈췄다 |

**하나도 「빚」으로 안 세어졌다.** 세던 축이 「합성으로만 선 판단」 하나뿐이었기
때문이다 (D-0317). 한 축이 0이 되자 **화면이 「빚 없다」고 말했고 그것은 거짓이었다.**

### 거짓 침묵은 거짓 경보보다 나쁘다

`fire-lane` MASTER §18-13이 *"거짓 경보는 진짜 경보를 죽인다"*고 적었다. 이 판은 그
뒤집힌 짝이다 — **안 세는 것은 0으로 보이고, 0은 다 끝난 것으로 읽힌다.** D-0134가
*"구멍이 0일 때 못 박는다"*고 한 것도 같은 자리다.

### 막지 않고 찍기만 한다

`make check`에 걸지 않는다. 걸면 결정 하나 쓸 때마다 `README`를 손봐야 하고,
**그러면 검사를 끈다** (D-0220이 기획서에서 같은 이유로 수를 안 보기로 한 자리).
`make ship`이 **수를 찍는다** — 위생 구역과 같은 취급이다.

### 신선도는 git이 센다

문서가 **몇 판 뒤처졌나**는 「마지막으로 그 파일을 바꾼 커밋이 어느 결정이었나」다.
git이 없으면 **「모름」을 낸다** — 0이 아니다 (GR-0.5).

    python3 tools/debts.py           # 축마다 몇 건인지 찍는다
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import decision_evidence  # noqa: E402
import decision_ledger  # noqa: E402

OPEN_ISSUE = re.compile(r"^\| (O-\d+) \|", re.MULTILINE)
DEBT_ROW = re.compile(r"^\| (D-\d{4}) \|", re.MULTILINE)
PATCH_DECISION = re.compile(r"D-?(\d{4})")

WATCHED = ("README.md", "docs/MASTER.md", "docs/PLAN.md")
"""신선도를 보는 문서. **`DECISIONS.md`는 안 본다** — 판마다 바뀌므로 늘 0이다.

**`docs/proposal.docx`도 뺐다** (D-0348). 그것은 `MASTER` Part I ~ III **지문 구간이
바뀔 때만** 움직이는데 이 축은 **모든 결정**과 견준다 — 결정 기록만 쌓는 날이 열 번
이어지면 **멀쩡한 기획서가 「뒤처졌다」고 찍힌다.** D-0343이 *"정상이다"*라고 적어 두고
고치지는 않았고, 이 판의 직전에 **9**까지 올라와 있었다.

**`docx_check`가 sha256 지문으로 이미 더 정확히 본다.** 같은 것을 **더 나쁜 자로**
또 세면 거짓 경보만 는다 (GR-0.8).
"""

STALE_FLOOR = 10
"""몇 판 뒤처지면 화면에 드는가.

**0으로 두면 매 판 네 줄이 뜬다.** 그러면 그 줄을 안 읽게 되고, 그것이 이 파일이
막으려는 바로 그 병이다. 10판은 *"한 세션어치"*다 — 한 세션이 통째로 지나도록
입구 문서가 안 바뀌었으면 그것은 사건이다.
"""


@dataclass(frozen=True, slots=True)
class Axis:
    """빚 한 축. **0도 찍는다** — 안 찍으면 「안 센다」와 「없다」가 안 갈린다."""

    name: str
    count: int
    note: str = ""
    summed: bool = True
    """합계에 더하는가. **다른 축의 부분집합이면 거짓이다** (D-0342).

    「PLAN 조건 걸린 질문」 6건은 전부 「PLAN 열린 질문」 33건 **안에 있다** — 같은
    블록의 같은 줄을 한 번은 전부, 한 번은 표식이 달린 것만 센다. 그런데 합계가 둘을
    더해 **34를 40으로 찍었다.**

    **수가 틀리면 그 수를 안 믿게 된다** (GR-0.8). 이 도구가 생긴 이유가
    *"안 세는 것은 0으로 보인다"*인데, **부풀린 수도 같은 자리에서 신뢰를 깎는다.**
    """

    def line(self) -> str:
        mark = "" if self.summed else "  ↳"
        tail = f"  {self.note}" if self.note else ""
        return f"{mark}{self.name:<{24 - len(mark)}} {self.count:>4}{tail}"


def _read(name: str) -> str:
    path = ROOT / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _section(text: str, begin: str, end: str) -> str:
    if begin not in text or end not in text:
        return ""
    return text.split(begin, 1)[1].split(end, 1)[0]


def synthetic_only() -> Axis:
    """합성으로만 선 판단 중 **갚을 수 있는 것** (D-0317). 기존 축이다."""
    rows = decision_evidence.payable(decision_ledger.scan_records(_read("docs/DECISIONS.md")))
    return Axis("합성으로만 선 판단", len(rows))


def plan_open_issues() -> Axis:
    """PLAN의 열린 질문. **항목 그 자체가 빚이다.**

    닫힌 질문은 여기 없어야 하고 `check_issue_mentions`가 그것을 본다. 남은 수는
    **아직 답이 없는 것의 개수**이며, 그것이 미래 문서의 무게다.
    """
    block = _section(
        _read("docs/PLAN.md"), "<!-- open-issues:begin -->", "<!-- open-issues:end -->"
    )
    return Axis("PLAN 열린 질문", len(OPEN_ISSUE.findall(block)))


CONDITION_MET = "**조건 충족**"
"""재개·착수 조건이 **이미 걸린** 질문의 표식 (D-0336).

«P5 착수 때» · «Part III가 800줄을 넘으면» 같은 조건을 적어 두고 **아무도 안 세면
영원히 잠긴다** (D-0126). 실제로 여섯이 그랬다 — O-17의 조건은 **283건 전**에 걸렸다.

**기계가 세려면 글자가 있어야 한다.** 조건이 걸렸다고 판단한 사람이 이 표식을 달고,
그 수가 화면에 뜬다.
"""


def plan_unblocked() -> Axis:
    """조건이 걸렸는데 **아직 안 움직인** 질문 (D-0336).

    열린 질문 수(35)에 섞여 있으면 안 보인다 — **「아직 못 한다」와 「지금 할 수 있다」는
    다른 빚이다.**
    """
    block = _section(
        _read("docs/PLAN.md"), "<!-- open-issues:begin -->", "<!-- open-issues:end -->"
    )
    rows = [line for line in block.splitlines() if CONDITION_MET in line]
    # **합계에 안 더한다** (D-0342). 이 줄들은 「열린 질문」과 같은 블록의 같은 줄이다.
    return Axis(
        "PLAN 조건 걸린 질문",
        len(rows),
        "지금 할 수 있다" if rows else "",
        summed=False,
    )


def plan_settled_rows() -> Axis:
    """§3.1에서 **이미 판결이 난** 행 (D-0328).

    「승격 아님」은 *"더 갚을 것이 없다"*는 뜻이다. 그것이 미래 문서에 남아 있으면
    **미래 문서가 과거를 이고 간다** (MASTER의 갚은 빚 규약).
    """
    table = _section(_read("docs/PLAN.md"), "### 3.1 합성으로만 선 판단", "\n## ")
    settled = [
        line for line in table.splitlines() if line.startswith("| D-") and "승격 아님" in line
    ]
    return Axis("PLAN 판결 난 행", len(settled), "미래 문서가 과거를 인다" if settled else "")


SECURITY_SETUP = {
    "SECURITY.md": "취약점을 어디에 보고하나",
    ".github/workflows/codeql.yml": "코드 수준 결함을 아무도 안 본다",
}
"""GitHub 보안 탭에서 **파일로 확인할 수 있는 것** (D-0329).

«비공개 취약점 보고»는 저장소 설정이라 파일이 없다 — **여기서 못 센다.** 세는 척하면
0이 「켜져 있다」로 읽히므로 아예 축에서 뺀다 (GR-0.5). `make gh-setup`이 든다.
"""


def security_setup() -> Axis:
    """보안 설정 중 **빠진 것**. 0이면 파일 쪽은 다 있다는 뜻이다."""
    missing = [name for name in SECURITY_SETUP if not (ROOT / name).is_file()]
    note = " · ".join(f"{name}: {SECURITY_SETUP[name]}" for name in missing)
    return Axis("보안 설정 빠짐", len(missing), note)


def plan_open_rows() -> Axis:
    """§3.1에서 **아직 안 갚은** 행 (D-0335).

    D-0328이 「판결 난 행」만 셌다. 그래서 **갚을 것이 남은 행은 아무 데도 안 세어졌고**,
    화면이 「합계 35」를 찍는 동안 넷이 서 있었다 — **같은 병의 세 번째다**
    (D-0328 · D-0329).
    """
    table = _section(_read("docs/PLAN.md"), "### 3.1 합성으로만 선 판단", "\n## ")
    rows = [line for line in table.splitlines() if line.startswith("| D-")]
    open_rows = [line for line in rows if "승격 아님" not in line and "뒤집힘" not in line]
    return Axis("PLAN 안 갚은 행", len(open_rows))


CLOSED_ISSUE = re.compile(r"^\| (O-\d+) \|", re.MULTILINE)
RECORD_TITLE = re.compile(r"^## (D-\d{4})\. (.+)$", re.MULTILINE)
TITLE_ISSUE = re.compile(r"O-\d+")


def _closed_issues() -> set[str]:
    """`MASTER`의 닫힌 미해결 표. **표식 사이만 읽는다** — 열린 표도 같은 꼴이다."""
    return set(
        CLOSED_ISSUE.findall(
            _section(
                _read("docs/MASTER.md"),
                "<!-- closed-issues:begin -->",
                "<!-- closed-issues:end -->",
            )
        )
    )


def plan_closed_question_rows() -> Axis:
    """§3.1의 행이 **이미 닫힌 질문**을 가리키나 (D-0338).

    ### 이 축이 없어서 하루를 썼다

    D-0337이 D-0064의 자를 지었다. **그 질문은 D-0065가 272판 전에 기각했다** —
    창별 중앙값의 달성 가능 폭이 0.0198이고 사전 등록 기준 0.031에 못 미쳤다.
    D-0062도 같다: 판정 장치가 **D-0063에서 실물 200곡으로 돌았고** O-21이 닫혔다.

    **왜 안 보였나.** §3.1 표는 **손으로 쓴다.** `payable()`은 대장을 읽어 명단을
    내는데 **그 명단은 비어 있었다** — 두 행 중 어느 것도 거기 없었다. 손 표와 대장이
    서로 다른 것을 세고 **둘을 맞춰 보는 코드가 없었다.** 그래서 손 표가 이겼다.

    ### 제목이 근거다

    기록 제목에 `(O-27 (b))`(닫힘 D-0074)처럼 질문 번호가 박혀 있다. `MASTER`의 닫힌
    표에 그 번호가 있으면 **그 행은 닫힌 질문을 막고 있다고 말하는 것**이다.

    **제목에 번호가 없는 행은 안 센다** — D-0199(WSL 파서)·D-0337(자 자체)이 그렇고,
    그 둘은 질문이 아니라 기기와 도구를 기다린다. 못 세는 것을 세는 척하지 않는다
    (GR-0.5).
    """
    table = _section(_read("docs/PLAN.md"), "### 3.1 합성으로만 선 판단", "\n## ")
    titles = dict(RECORD_TITLE.findall(_read("docs/DECISIONS.md")))
    closed = _closed_issues()
    hit: list[str] = []
    for line in table.splitlines():
        if not line.startswith("| D-"):
            continue
        identifier = line.split("|")[1].strip()
        shut = [name for name in TITLE_ISSUE.findall(titles.get(identifier, "")) if name in closed]
        if shut:
            hit.append(f"{identifier}→{'·'.join(shut)}")
    return Axis("PLAN 닫힌 질문 행", len(hit), " ".join(hit))


def dependabot_alerts() -> Axis:
    """열린 Dependabot 경보 (D-0335).

    **`gh`가 없거나 로그인 안 됐으면 0이 아니라 「모름」이다** (GR-0.5). 0으로 내면
    「경보가 없다」로 읽히고, 그것이 이 파일이 막으려는 병이다.

    `tidy`가 봇 **브랜치**를 치우고 `gh_ops.bot`이 봇 **PR**을 닫는다 — **열린 경보를
    읽는 코드는 한 줄도 없었다.** 2026-10-01에 다섯이 떴고 `make ship`은 「합계 35」만
    찍었다.
    """
    unknown = Axis("Dependabot 열린 경보", 0, "**모름** — `gh`를 못 읽었다. 0이 아니다")
    try:
        done = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/dependabot/alerts?state=open", "--jq", "length"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        # **`gh`가 아예 없으면 터진다.** 터지는 것은 0을 내는 것보다 낫지만,
        # 빚을 세다가 죽으면 **나머지 축도 안 보인다** — 여기서 잡는다.
        return unknown
    counted = done.stdout.strip()
    if done.returncode != 0 or not counted.isdigit():
        return unknown
    return Axis("Dependabot 열린 경보", int(counted))


def _last_decision_of(name: str) -> int | None:
    """그 파일을 마지막으로 바꾼 커밋의 결정 번호. **못 읽으면 `None`이다.**"""
    done = subprocess.run(
        ["git", "log", "-1", "--format=%s", "--", name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        return None
    found = PATCH_DECISION.search(done.stdout)
    return int(found.group(1)) if found else None


def latest_decision() -> int | None:
    found = decision_ledger.HEADING.findall(_read("docs/DECISIONS.md"))
    return max(int(identifier.removeprefix("D-")) for identifier, _ in found) if found else None


def staleness() -> list[Axis]:
    """문서마다 몇 판 뒤처졌나. **`STALE_FLOOR` 밑은 안 든다.**"""
    newest = latest_decision()
    if newest is None:
        return [Axis("문서 신선도", 0, "결정 기록을 못 읽었다")]
    found: list[Axis] = []
    for name in WATCHED:
        seen = _last_decision_of(name)
        if seen is None:
            found.append(Axis(f"{name} 뒤처짐", 0, "git을 못 읽었다 — 0이 아니라 **모름**이다"))
            continue
        gap = newest - seen
        if gap >= STALE_FLOOR:
            found.append(Axis(f"{name} 뒤처짐", gap, f"D-{seen:04d}에서 멈췄다"))
    return found


def survey() -> list[Axis]:
    """모든 축. **순서가 뜻을 갖는다** — 갚을 수 있는 것이 먼저다."""
    return [
        synthetic_only(),
        plan_open_issues(),
        plan_unblocked(),
        plan_settled_rows(),
        plan_open_rows(),
        plan_closed_question_rows(),
        security_setup(),
        dependabot_alerts(),
        *staleness(),
    ]


def report(axes: list[Axis]) -> list[str]:
    """**부분집합인 축은 합계에서 뺀다** (D-0342). 두 번 세면 수가 부푼다."""
    total = sum(axis.count for axis in axes if axis.summed)
    lines = [axis.line() for axis in axes]
    lines.append(f"{'합계':<24} {total:>4}" + ("" if total else "  **정말 없다**"))
    return lines


def main() -> int:
    for line in report(survey()):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
