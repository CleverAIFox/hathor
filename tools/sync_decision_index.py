#!/usr/bin/env python3
"""결정 기록과 미해결표를 기계가 검사한다. 부록 A 색인도 여기서 생성한다.

### 왜 필요한가

부록 A는 41행짜리 손유지 요약표였고 **이미 어긋나 있었다** (D-0042).

- D-0003 결정 기록: "실존 가수의 음색 복제·보간은 **구현하지 않는다**"
  부록 A: "실존 가수 음색은 **식별 가능한 산출물만 금지**"
  → 안전 관련 항목인데 두 문장의 뜻이 다르다.
- D-0015의 MASTER.md 폐기가 부록 A에 없다. D-0008 행에 곁다리로 붙어 있을 뿐이다.
  D-0039를 쓰게 만든 그 누락이 부록 A에 그대로 남아 있었다.

**요약을 손으로 유지하면 반드시 어긋난다.** 어긋남은 조용하고, 부록 A만 본 사람이
잘못된 판단을 내린 뒤에야 드러난다.

### 색인만으로는 모자랐다 (D-0080)

색인은 표제를 긁어 표로 만들 뿐 **표제가 있어야 할 자리에 없는 것은 못 본다.**
`D-0077` 본문이 "D-0076에서 넣은…"이라고 참조하는데 `## D-0076.` 표제가 파일에
없었고, **78건이 쌓이는 동안 아무 검사도 그것을 보지 않았다.**

미해결표도 같았다. `O-23`이 두 행으로 중복돼 있었고 정렬이 깨져 있었으며 닫힌
항목이 활성표에 남아 있었다. 전부 눈으로만 유지되던 것이다.

**GR-0.8이 "검사할 수 없는 규약은 잊힌다"고 적어 두고 정작 결정 기록 자신의
규약에는 검사를 안 걸었다.** 여기서 건다.

### 무엇을 검사하는가

| 검사 | 무엇을 잡는가 |
|---|---|
| 색인 일치 | 부록 A가 손으로 고쳐졌거나 낡았다 |
| 번호 중복·결번 | D-0076처럼 번호가 조용히 비었다 |
| **참조 무결성** | 본문이 없는 번호를 가리킨다. **D-0076을 그 자리에서 잡았을 검사다** |
| 후보-선택 짝 | 후보를 적고 무엇을 골랐는지 안 적었다 |
| 갱신 배지 | 뒤에서 갱신했다고 선언했는데 대상 기록 앞에 표시가 없다 |
| 미해결표 | ID 중복·정렬 어긋남·닫힌 항목이 활성표에 남음 |
| **표기** | 표제 앞뒤 구분선·빈 줄, 표 열 수, 코드 펜스 태그, 줄 길이 |

### 표기는 전수 강제, 내용은 신규만 (D-0081)

처음에 이 둘을 뭉뚱그려 "옛 기록은 소급해 고치지 않는다"고 했다. **틀렸다.**

**표기**(구분선·빈 줄·표 열 수·펜스 태그·줄 길이·낡은 수치)는 고쳐도 **그때의
판단이 바뀌지 않는다.** 공식 문서이므로 맞춰야 하고, 소급 정규화한 뒤 전수로
강제한다. 정규화만 하고 검사를 안 걸면 다음 세션에 또 어긋난다.

**내용**(배경·후보·선택·결과)은 다르다. 없는 근거를 지금 채우면 **그때 하지 않은
판단을 사후에 지어내는 것**이고, 그것이 추가 전용(GR-0.2)이 막으려는 바로 그것이다.
내용 검사만 `FORMAT_ENFORCED_FROM` 이후에 건다. 상수를 코드에 두는 것은 **기준을
옮겼는지 나중에 알 수 있게** 하기 위한 것이다.

**굵은 글씨 밀도는 검사하지 않는다.** 밀도가 높은 것은 사실이나(본문 2.7줄당 1개)
숫자를 걸면 문체를 그 숫자에 맞추게 된다 — D-0058~D-0061에서 네 세션을 태운
"손잡이 돌리기"와 같은 형태다. 규약으로만 두고 검사하지 않으며, **검사하지 않기로
했다는 사실을 여기 적는다** (GR-0.8의 예외이므로 이유가 남아야 한다).

사용법:
    python tools/sync_decision_index.py           # 색인을 다시 쓰고 검사한다
    python tools/sync_decision_index.py --check   # 쓰지 않는다. 어긋나면 1로 끝난다
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "DECISIONS.md"
DECISIONS_DIR = ROOT / "docs" / "decisions"
DESIGN = ROOT / "docs" / "DESIGN.md"

PART_NAME = "D-{low:04d}-{high:04d}.md"
PART_FILE = re.compile(r"^D-(\d{4})-(\d{4})\.md$")


def part_path(name: str) -> Path:
    return DECISIONS_DIR / name


def merge_parts(parts: list[tuple[str, str]]) -> str:
    """조각을 번호 순으로 잇는다. **각 조각의 머리말은 버린다.**

    안 버리면 앞 조각 마지막 기록의 본문에 다음 조각의 머리말이 딸려 들어가고,
    본문을 보는 검사(절·갱신·참조)가 그것을 기록의 일부로 읽는다.
    """
    bodies: list[str] = []
    for _, text in parts:
        first = HEADING.search(text)
        bodies.append(text[first.start() :] if first else "")
    return "\n---\n\n".join(body for body in bodies if body)


def load_parts() -> list[tuple[str, str]]:
    """검사 대상 결정 기록을 (이름, 본문)으로 낸다. **번호 순서다.**

    조각이 있으면 조각만 읽는다. 없으면 `DECISIONS.md` 한 장을 읽는다 —
    **분할 전후 어느 쪽에서도 검사가 돌아야 한다.**
    """
    if DECISIONS_DIR.is_dir():
        parts = sorted(DECISIONS_DIR.glob("D-*.md"))
        if parts:
            return [(path.stem, path.read_text(encoding="utf-8")) for path in parts]
    return [("DECISIONS", DECISIONS.read_text(encoding="utf-8"))]

HEADING = re.compile(r"^## (D-\d{4})\. (.+?)\s*$", re.MULTILINE)
REFERENCE = re.compile(r"D-(\d{4})")
SUPERSEDES = re.compile(r"^- \*\*갱신\*\*: (D-\d{4})", re.MULTILINE)
BADGE = re.compile(r"^> \*\*갱신됨 — (D-\d{4})", re.MULTILINE)
CANDIDATES = re.compile(r"^- \*\*후보\*\*", re.MULTILINE)
CHOICE = re.compile(r"^- \*\*선택\*\*", re.MULTILINE)

BEGIN = "<!-- decision-index:begin -->"
END = "<!-- decision-index:end -->"
BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

OPEN_BEGIN = "<!-- open-issues:begin -->"
OPEN_END = "<!-- open-issues:end -->"
CLOSED_BEGIN = "<!-- closed-issues:begin -->"
CLOSED_END = "<!-- closed-issues:end -->"
ISSUE_ROW = re.compile(r"^\| (O-\d+) \|", re.MULTILINE)

FORMAT_ENFORCED_FROM = 80
"""**내용** 항목 검사를 거는 첫 결정 번호 (D-0080 · D-0081).

옛 기록 30건에 `- **결과**:` 절이 없다. **지금 채우면 그때 하지 않은 판단을 사후에
지어내는 것**이고 추가 전용이 막으려는 것이 정확히 그것이다.

**표기 검사는 여기 걸리지 않는다** — 전 기록에 건다 (D-0081). 표기는 고쳐도
판단이 바뀌지 않는다.

**이 숫자는 자의적이 아니다** — D-0080이 검사를 넣은 기록이므로 그 뒤부터다.
옮기면 여기서 드러난다.
"""

SPLIT_LINE_LIMIT = 6000
SPLIT_RECORD_LIMIT = 100
"""한 조각의 상한. **O-30이 정한 숫자를 그대로 옮긴 것이다** (D-0080).

조건을 문서에만 적어 두고 **검사를 안 걸었다.** 발동한 뒤로도 한참을 그냥 지났고
`DECISIONS.md`는 112건 7579줄까지 갔다 — 조건의 26% 초과다. GR-0.8이 "검사할 수
없는 규약은 잊힌다"고 적어 놓고 **정작 자기 파일 크기만 안 보고 있었다.**

**여기서 건다. 넘으면 `make split`이다.**
"""

RECORDS_PER_PART = 50
"""한 조각에 담는 건수. `SPLIT_RECORD_LIMIT`의 절반이다.

**상한에 딱 맞춰 나누면 다음 기록 하나에 바로 다시 빨개진다.** 절반으로 나누면
조각당 50건 · 최근 평균 88.3줄 기준 약 4400줄로 두 상한 모두에 여유가 남는다.
"""

LINE_LIMIT = 100
"""문서 줄 길이 상한. 코드(`ruff` line-length)와 같은 값으로 맞춘다.

표·코드 블록·URL은 접을 수 없으므로 검사에서 뺀다.
"""

REQUIRED_SECTIONS = ("배경", "결과")
"""신규 기록에 반드시 있어야 하는 절. **후보·선택은 짝으로만 검사한다** — 후보가
없는 결정(단순 결함 수정 기록)이 실재하며, 강제하면 채우기 위한 글이 나온다.
"""

BLANK_RECORD = "(결번)"
"""내용이 유실된 번호의 표제 표시. **번호를 조용히 비우지 않는다** (D-0080)."""


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


def check_numbering(records: list[Record]) -> list[str]:
    """번호가 중복이거나 비었는가. **D-0076이 이 검사에 걸렸을 것이다.**"""
    problems: list[str] = []
    seen: set[int] = set()
    for record in records:
        if record.number in seen:
            problems.append(f"결정 번호가 중복이다: {record.identifier}")
        seen.add(record.number)
    if not seen:
        return problems
    # **이어진 결번은 한 줄로 묶는다.** 오타 하나로 `D-0999`가 들어오면 낱개로는
    # 887줄이 쏟아진다. 검사가 옳아도 **읽을 수 없으면 안 잡은 것과 같다.**
    for low, high in _gaps(sorted(set(range(1, max(seen) + 1)) - seen)):
        span = f"D-{low:04d}" if low == high else f"D-{low:04d}~D-{high:04d} ({high - low + 1}건)"
        problems.append(
            f"{span}가 비어 있다. "
            f"내용이 유실됐으면 `## D-{low:04d}. {BLANK_RECORD} …` 표제를 남긴다"
        )
    return problems


def _gaps(numbers: list[int]) -> list[tuple[int, int]]:
    """이어진 정수를 (처음, 끝)으로 묶는다."""
    ranges: list[tuple[int, int]] = []
    for number in numbers:
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], number)
        else:
            ranges.append((number, number))
    return ranges


def check_references(records: list[Record]) -> list[str]:
    """본문이 가리키는 번호가 실재하는가.

    **이것이 D-0076을 그 자리에서 잡았을 검사다.** `D-0077`이 "D-0076에서 넣은…"을
    쓴 순간 걸렸어야 했다. 번호 연속성보다 이쪽이 본질이다 — 참조가 없으면 결번은
    그냥 건너뛴 번호이고, 참조가 있으면 잃어버린 기록이다.
    """
    known = {record.number for record in records}
    problems: list[str] = []
    for record in records:
        for raw in sorted({int(value) for value in REFERENCE.findall(record.body)}):
            if raw not in known:
                problems.append(f"{record.identifier}가 없는 기록을 가리킨다: D-{raw:04d}")
    return problems


def check_sections(records: list[Record]) -> list[str]:
    """신규 기록에 필수 절이 있고 후보-선택이 짝을 이루는가 (GR-0.2).

    **내용 검사이므로 `FORMAT_ENFORCED_FROM` 이후에만 건다** (D-0081). 옛 기록 30건에
    `- **결과**:`가 없는데, 지금 채우면 그때 하지 않은 판단을 사후에 지어내는 것이다.
    """
    problems: list[str] = []
    for record in records:
        if record.number < FORMAT_ENFORCED_FROM or BLANK_RECORD in record.title:
            # **결번 표시는 결정이 아니라 구멍의 표시다.** 배경·결과를 요구하면
            # 없는 판단을 지어내게 된다 (D-0081).
            continue
        for name in REQUIRED_SECTIONS:
            if not re.search(rf"^- \*\*{name}\*\*", record.body, re.MULTILINE):
                problems.append(f"{record.identifier}에 `- **{name}**` 절이 없다")
        has_candidates = CANDIDATES.search(record.body) is not None
        has_choice = CHOICE.search(record.body) is not None
        if has_candidates != has_choice:
            missing = "선택" if has_candidates else "후보"
            problems.append(f"{record.identifier}에 `- **{missing}**`이 없다. 둘은 짝이다")
    return problems


def check_layout(parts: list[tuple[str, str]]) -> list[str]:
    """표기 규약. **전 기록에 건다** (D-0081).

    표기는 고쳐도 그때의 판단이 바뀌지 않으므로 소급 정규화했고, 정규화만 하고
    검사를 안 걸면 **다음 세션에 또 어긋난다.** 실제로 표제 앞이 `---`인 것과 빈
    줄인 것이 49대 31로 섞여 있었다.
    """
    problems: list[str] = []
    for name, text in parts:
        lines = text.split("\n")
        for index, line in enumerate(lines):
            if not line.startswith("## D-"):
                continue
            if index >= 2 and not (lines[index - 1] == "" and lines[index - 2].strip() == "---"):
                problems.append(f"{name} {index + 1}행: 표제 앞이 `---` + 빈 줄이 아니다")
            if index + 1 < len(lines) and lines[index + 1] != "":
                problems.append(f"{name} {index + 1}행: 표제 뒤에 빈 줄이 없다")
        for record in scan_records(text):
            if not record.title.strip():
                problems.append(f"{record.identifier}에 제목이 없다")
    return problems


def check_split(parts: list[tuple[str, str]]) -> list[str]:
    """조각이 상한 안에 있고 이름이 범위를 정확히 덮는가 (O-30 · D-0080).

    **이름이 범위다.** `D-0051-0100.md`에 `D-0101`이 들어 있으면 `grep` 없이 파일을
    고를 수 없고, 그 순간 조각 나누기는 아무것도 벌어 주지 않는다.
    """
    problems: list[str] = []
    seen: set[int] = set()
    for name, text in parts:
        records = scan_records(text)
        lines = text.count("\n") + 1
        if lines > SPLIT_LINE_LIMIT:
            problems.append(
                f"{name}: {lines}줄로 상한 {SPLIT_LINE_LIMIT}줄을 넘는다. make split"
            )
        if len(records) > SPLIT_RECORD_LIMIT:
            problems.append(
                f"{name}: {len(records)}건으로 상한 {SPLIT_RECORD_LIMIT}건을 넘는다. make split"
            )
        match = PART_FILE.match(f"{name}.md")
        if match is None:
            continue
        low, high = int(match.group(1)), int(match.group(2))
        for record in records:
            if not low <= record.number <= high:
                problems.append(f"{name}: {record.identifier}이 이름의 범위 밖이다")
            if record.number in seen:
                problems.append(f"{name}: {record.identifier}이 다른 조각에도 있다")
            seen.add(record.number)
    return problems


def check_text_style(paths: dict[str, str]) -> list[str]:
    """줄 길이·코드 펜스 태그·표 열 수. 문서 4종 전부에 건다 (D-0081)."""
    problems: list[str] = []
    for name, text in paths.items():
        lines = text.split("\n")
        inside = False
        header_columns: int | None = None
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not inside and stripped == "```":
                    problems.append(f"{name} {index}행: 코드 펜스에 언어 태그가 없다")
                if inside and stripped != "```":
                    problems.append(f"{name} {index}행: 닫는 펜스에 언어 태그가 붙었다")
                inside = not inside
                continue
            if inside:
                continue
            if line.startswith("|"):
                # 표 안의 `\|`는 셀 구분이 아니라 이스케이프다. 세면 안 된다.
                columns = line.replace("\\|", "").count("|")
                if header_columns is None:
                    header_columns = columns
                elif columns != header_columns:
                    problems.append(
                        f"{name} {index}행: 표 열 수가 {columns}로 머리글 {header_columns}과 다르다"
                    )
                continue
            header_columns = None
            if len(line) > LINE_LIMIT and not line.startswith(("http", "  ")):
                problems.append(f"{name} {index}행: {len(line)}자로 {LINE_LIMIT}자를 넘는다")
        if inside:
            problems.append(f"{name}: 코드 펜스 짝이 맞지 않는다")
    return problems


def check_supersession(records: list[Record]) -> list[str]:
    """갱신 선언과 배지가 짝을 이루는가 (D-0080).

    **낡은 수치는 기록 맨 뒤가 아니라 맨 앞에서 알려야 한다.** D-0063의 표에
    K-K 대비 14.1%가 있고 갱신이 뒤에 붙어 있어, 위에서 아래로 읽는 사람은
    낡은 값을 먼저 본다. 실제로 결정 기록·코드 독스트링·DESIGN 표 세 곳이
    동시에 틀렸다 (O-28).

    **앞을 고치는 것이 아니라 표시하는 것이다.** 추가 전용은 깨지지 않는다.
    """
    by_number = {record.number: record for record in records}
    problems: list[str] = []
    for record in records:
        for target in SUPERSEDES.findall(record.body):
            superseded = by_number.get(int(target[2:]))
            if superseded is None:
                problems.append(f"{record.identifier}가 없는 기록을 갱신한다고 적었다: {target}")
                continue
            if record.identifier not in BADGE.findall(superseded.body):
                problems.append(
                    f"{target} 표제 아래에 `> **갱신됨 — {record.identifier}.** …` 배지가 "
                    f"없다. {record.identifier}가 갱신한다고 선언했다"
                )
    return problems


def _section(text: str, begin: str, end: str) -> str | None:
    start, stop = text.find(begin), text.find(end)
    return None if start < 0 or stop < start else text[start:stop]


def check_open_issues(design_text: str) -> list[str]:
    """미해결표가 중복 없이 정렬돼 있고 닫힌 항목이 섞여 있지 않은가 (D-0080).

    **닫힌 항목을 지우지 않는다.** DESIGN이 "해소되면 결정 기록으로 옮기고 여기서
    지운다"고 적어 두었으나, 지우면 "이건 왜 안 하기로 했지"를 다시 묻게 된다 —
    O-11과 O-23이 정확히 그 종류다. **지우는 대신 닫힘 절로 옮기고 한 줄만
    남긴다.** 규약을 어기는 대신 규약을 고친다.
    """
    problems: list[str] = []
    active = _section(design_text, OPEN_BEGIN, OPEN_END)
    closed = _section(design_text, CLOSED_BEGIN, CLOSED_END)
    if active is None or closed is None:
        return [f"DESIGN에 {OPEN_BEGIN}/{CLOSED_BEGIN} 표식이 없다"]

    for label, block in (("활성", active), ("닫힘", closed)):
        rows = ISSUE_ROW.findall(block)
        for name in sorted({name for name in rows if rows.count(name) > 1}):
            problems.append(f"{label} 미해결표에 {name}이 두 번 있다")
        numbers = [int(name[2:]) for name in rows]
        if numbers != sorted(numbers):
            problems.append(f"{label} 미해결표가 번호 순이 아니다: {rows}")

    for name in sorted(set(ISSUE_ROW.findall(active)) & set(ISSUE_ROW.findall(closed))):
        problems.append(f"{name}이 활성표와 닫힘표에 동시에 있다")

    for row in active.splitlines():
        if row.startswith("| O-") and ("~~" in row or "**해결" in row or "**닫힘" in row):
            problems.append(
                f"활성표의 {ISSUE_ROW.findall(row + chr(10))}이 닫힘 표시를 달고 있다. "
                "닫힘 절로 옮긴다"
            )
    return problems


def build_index(decisions_text: str) -> str:
    """결정 기록 제목을 표로 만든다. 번호 순서는 파일 등장 순서를 따른다."""
    records = scan_records(decisions_text)
    if not records:
        raise SystemExit("결정 기록에서 `## D-XXXX. 제목`을 찾지 못했다")
    rows = "\n".join(f"| {record.identifier} | {record.title} |" for record in records)
    return (
        f"{BEGIN}\n"
        "<!-- 이 표는 tools/sync_decision_index.py가 생성한다."
        " 손으로 고치지 않는다 (D-0042). -->\n"
        f"\n"
        f"| ID | 결정 |\n"
        f"|---|---|\n"
        f"{rows}\n"
        f"\n"
        f"{END}"
    )


def run_checks(parts: list[tuple[str, str]], design_text: str) -> list[str]:
    """전부 돌리고 문제를 모아 낸다. **첫 문제에서 멈추지 않는다** — 한 번에 다
    보여야 고치러 여러 번 오지 않는다.

    **번호·참조·갱신은 합쳐서 본다.** 조각을 갈랐다고 `D-0113`이 `D-0086`을 참조하지
    못하게 되면 나눈 대가로 검사를 잃는 것이다.
    """
    records = scan_records(merge_parts(parts))
    documents = {
        "DESIGN": design_text,
        "CONTRIBUTING": (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"),
        "README": (ROOT / "README.md").read_text(encoding="utf-8"),
        "DECISIONS": DECISIONS.read_text(encoding="utf-8"),
        **dict(parts),
    }
    return [
        *check_numbering(records),
        *check_references(records),
        *check_sections(records),
        *check_supersession(records),
        *check_open_issues(design_text),
        *check_layout(parts),
        *check_text_style(documents),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="결정 기록 검사 및 부록 A 색인 동기화")
    parser.add_argument("--check", action="store_true", help="쓰지 않고 어긋남만 검사한다")
    args = parser.parse_args()

    plan_text = DESIGN.read_text(encoding="utf-8")
    if not BLOCK.search(plan_text):
        print(f"{DESIGN}에 {BEGIN} ... {END} 표식이 없다", file=sys.stderr)
        return 2

    parts = load_parts()
    decisions_text = merge_parts(parts)
    problems = run_checks(parts, plan_text)
    if problems:
        print(f"결정 기록·미해결표에 문제가 {len(problems)}건 있다.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    index = build_index(decisions_text)
    updated = BLOCK.sub(lambda _: index, plan_text, count=1)

    if updated == plan_text:
        print(f"결정 기록 검사 통과 · 부록 A 색인 일치 ({index.count('| D-')}건)")
        return 0

    if args.check:
        print("부록 A 색인이 결정 기록과 어긋난다.", file=sys.stderr)
        print("  python tools/sync_decision_index.py 로 다시 쓴다.", file=sys.stderr)
        return 1

    DESIGN.write_text(updated, encoding="utf-8")
    print(f"부록 A 색인 갱신 ({index.count('| D-')}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
