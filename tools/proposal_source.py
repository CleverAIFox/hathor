#!/usr/bin/env python3
"""기획서의 정본을 `MASTER.md`에서 읽는다 (D-0221).

### 왜 따로 두나

기획서는 `MASTER.md` Part I ~ III를 **그대로** 밖에 내는 판이다. 빌드 도구
(`build_proposal.py`) · 그림 도구(`render_figures.py` · `render_charts.py`) · 대조 검사
(`docx_check.py`)가 **같은 자리를 같은 방식으로** 읽어야 한다. 네 곳이 제각기 자르면 한
곳만 경계를 바꾸는 날이 온다 — 그래서 자르는 법을 여기 한 곳에 둔다.

**표준 라이브러리만 쓴다.** `docx_check.py`가 CI에서 이것을 부르고, CI에는 pandoc ·
graphviz · matplotlib이 없다.

### 지문

빌드가 정본 구간의 sha256을 docx 속성에 적는다. `docx_check.py`가 지금 구간의 지문과
맞대어 **기획서가 `MASTER.md`보다 낡았는지** 본다. 숫자 몇 개가 아니라 **Part I ~ III
전체**가 대조 대상이 된다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = "docs/MASTER.md"

START = "## 취향 잠재 표현 기반 종단간 AI 음악 창작 시스템"
"""기획서가 시작하는 자리 — 표지 문구와 ※ 전제가 여기서부터다."""

END = "## 부록 A."
"""기획서가 끝나는 자리. 부록 · 작업 원칙 · 결정 대장은 안에서만 쓴다."""

FINGERPRINT = "hathor-source-sha256:"
"""docx 속성(`dc:description`)에 적는 머리말."""


class SourceError(LookupError):
    """정본의 모양이 도구의 기대와 다르다. **조용히 넘어가지 않는다.**"""


def master_text(root: Path = ROOT) -> str:
    return (root / MASTER).read_text(encoding="utf-8")


def source(root: Path = ROOT) -> str:
    """기획서가 되는 구간. 표지 문구부터 12절 끝까지."""
    text = master_text(root)
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0 or end <= start:
        raise SourceError(f"{MASTER}에서 `{START}` ~ `{END}` 구간을 못 찾았다")
    return text[start:end].rstrip() + "\n"


def fingerprint(root: Path = ROOT) -> str:
    return hashlib.sha256(source(root).encode("utf-8")).hexdigest()


def section(text: str, heading: str) -> str:
    """`heading`으로 시작하는 줄부터 **같거나 높은 단계의 다음 제목** 앞까지."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == heading.strip():
            level = len(line) - len(line.lstrip("#"))
            end = len(lines)
            for later in range(index + 1, len(lines)):
                match = re.match(r"^(#+) ", lines[later])
                if match and len(match.group(1)) <= level:
                    end = later
                    break
            return "\n".join(lines[index:end])
    raise SourceError(f"제목 `{heading}`이 없다")


@dataclass(frozen=True)
class Table:
    header: list[str]
    rows: list[list[str]]

    def column(self, name: str) -> list[str]:
        if name not in self.header:
            raise SourceError(f"표에 `{name}` 열이 없다 — 있는 열: {self.header}")
        index = self.header.index(name)
        return [row[index] for row in self.rows]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def tables(text: str) -> list[Table]:
    """마크다운 표 전부. 구분선(`|---|`)이 있어야 표로 본다."""
    found: list[Table] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        if lines[index].lstrip().startswith("|") and re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[index + 1]
        ):
            header = _cells(lines[index])
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                cells = _cells(lines[index])
                rows.append((cells + [""] * len(header))[: len(header)])
                index += 1
            found.append(Table(header, rows))
        else:
            index += 1
    return found


def table(heading: str, nth: int = 0, root: Path = ROOT) -> Table:
    """`heading` 절의 `nth`번째 표."""
    found = tables(section(source(root), heading))
    if len(found) <= nth:
        raise SourceError(f"`{heading}` 절에 표가 {nth + 1}개 없다")
    return found[nth]


def code_block(heading: str, root: Path = ROOT) -> str:
    """`heading` 절의 첫 코드 블록 본문."""
    match = re.search(r"```[a-z]*\n(.*?)\n```", section(source(root), heading), re.S)
    if not match:
        raise SourceError(f"`{heading}` 절에 코드 블록이 없다")
    return match.group(1)


def plain(cell: str) -> str:
    """표 칸의 마크다운 표기를 걷는다 — 굵게 · 백틱 · 취소선 · `<br>`."""
    cell = cell.replace("<br>", " ")
    return re.sub(r"\*\*|`|~~", "", cell).strip()


def number(cell: str) -> float:
    """칸에서 첫 수. `3.7/0.8/0.7%`는 3.7이다."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", plain(cell))
    if not match:
        raise SourceError(f"`{cell}`에 수가 없다")
    return float(match.group(0).replace(",", ""))


if __name__ == "__main__":
    print(f"{MASTER} 기획서 구간 · {len(source().splitlines())}줄 · 지문 {fingerprint()[:16]}")
