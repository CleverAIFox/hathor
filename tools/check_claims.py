#!/usr/bin/env python3
"""**기획서가 제 수치 규약을 적어 놓고 아무도 안 셌다** (D-0378).

정본 §전제가 이렇게 적는다:

> **※ 수치 표기 원칙**: 본 문서의 수치는 인제스트·분석 산출물에서 코드로 재산출한
> 값이며 **결정 기록마다 `재현` 명령이 붙는다** (D-0135).

그 문장이 참인지 **한 번도 안 셌다.** 내가 센 척한 적은 있다 — D-0371이 *«약 127줄»*,
D-0372가 *«345줄»*이라 적었고 **둘 다 안 센 수**였다. 345는 `REQ-ING-007` · `D-0174` ·
`R-8` · `2026-08-10` 같은 **식별자를 수로 센** 것이다 (GR-0.5를 두 판 연속 어겼다).

### 무엇을 세나

표 본문 줄에서 **코드 조각과 식별자·날짜를 지우고도 수가 남으면** 그 줄은 수치를
주장한다. 그 주장마다 상류를 묻는다 — **자에게 직접 묻는다**:

| 상류 | 누가 답하나 |
|---|---|
| 거울 | `measured.present()` — 그 표식 안의 줄 |
| 축 | `doc_counts.COUNTED` — 그 정규식이 무는 줄 (`doc_fsck`가 실물과 맞댄다) |
| 기록 | 줄이 — 또는 **그 표의 머리말이** — `D-XXXX`를 들고, 그 표제가 대장에 있다 |

머리말까지 보는 까닭: 표 한 장의 상류는 보통 **그 표 위 제목**에 한 번 적힌다
(`### □ 레이어 곡선 — 검색축 (D-0027)`). 줄마다 번호를 반복하면 사람이 안 읽는다.
**위로 열두 줄까지**, 다른 표를 만나면 멈춘다 — 그보다 멀면 읽는 사람도 못 잇는다.

어디에도 안 걸리면 **상류가 없다.** 그 수에 천장을 박는다 (D-0117 · D-0257) — 줄면
못을 조이고, 늘면 빨개진다.

천장은 **`check_ratchets`가 조인다** — `doc_fsck.UNENFORCED_CEILING`과 같은 꼴이다.
**정본은 하나다** (D-0117): 여기에 `--update`를 두면 조이는 자가 둘이 된다.

**차집합은 선언으로만 존재한다** (D-0219). 여기서 세는 것은 *«아직 아무도 안 보는 수가
몇 개인가»*이고, **그 수를 눈앞에 둔다** (D-0269).

    python3 tools/check_claims.py --check
    python3 tools/check_claims.py --list    # 상류 없는 줄을 찍는다
    python3 tools/check_ratchets.py --update    # 줄었으면 못을 조인다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import doc_counts  # noqa: E402
import measured  # noqa: E402
from proposal_source import source  # noqa: E402

MASTER = ROOT / "docs" / "MASTER.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"

NUMBER = re.compile(r"(?<![A-Za-z0-9])-?\d[\d,]*(?:\.\d+)*%?")
"""한 **건**. 줄이 아니라 수를 센다.

`| fp16 · 120초 곡 | 확산 68초 · 옮기기 189초 뒤 NaN |`은 **한 줄에 세 건**이다.
줄로 세면 빚이 작아 보인다 — **빚은 건수로 센다.**

판 번호(`8.0.1`)는 **한 건**이다. 점을 끝까지 먹는다 — 안 그러면 `ffmpeg 8.0.1` 하나가
두 건이 되고 천장이 부푼다 (GR-0.8).

**글자에 바로 붙은 수는 이름이다** — `fp16` · `layer03`은 안 센다. 뒤에 붙는 단위는
그대로 센다(`44.1kHz`는 한 건) — 앞이 글자냐 뒤가 글자냐로 가른다.
"""

UNSOURCED_CEILING = 35
"""상류가 없는 수치 **건수**의 천장 (D-0378).

실측으로 박는다. 늘면 빨개진다 — 새 표를 손으로 적으면 여기서 걸린다.

**0이 목표가 아니다**: 외부 논문·환경 사실처럼 저장소가 재산출할 수 없는 것이 있다.
목표는 **아무도 모르는 사이에 늘지 않는 것**이다.
"""

IDENTS = (
    r"\b(?:REQ|NFR|TST|OPS)-[A-Z]{2,4}-\d{3}\b",
    r"\bD-\d{4}\b",
    r"\bGR-\d+\.\d+\b",
    r"\b[ORCGMPTS]-?\d{1,2}\b",
    r"\bP@\d+\b",
    r"\b\d{4}-\d{2}(?:-\d{2})?\b",
)
"""**수로 세면 안 되는 것** — 이름과 날짜다.

`REQ-ING-007`의 007은 수치가 아니다. 이것을 안 지운 탓에 D-0372가 345를 적었다.
"""

IDENT_FLOOR = 5
"""지워야 하는 꼴의 **바닥** (D-0230). 목록이 비면 모든 줄이 「주장」이 되고 천장이 뜻을 잃는다."""

INDEX = re.compile(r"^\s*\|\s*\**\d+(?:\.\d+)?\**\s*\.?\s*(?=[|\s])")
"""표의 **첫 칸 번호**. `| 3 | 인제스트 파이프라인 | …`의 3은 수치가 아니라 **차례**다.

`| 09 | 0.1725 | …`처럼 뒤에 진짜 수가 있으면 그 줄은 그대로 주장으로 남는다 — 첫 칸
하나만 지운다.
"""

CODE = re.compile(r"`[^`]*`")
SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
CITES = re.compile(r"\bD-(\d{4})\b")


LOOKBACK = 12
"""표 머리말을 찾아 올라가는 **최대 줄 수**. 그보다 멀면 읽는 사람도 표와 못 잇는다."""


def rows() -> list[str]:
    """정본 표의 **본문 줄**. 머리와 구분선은 뺀다."""
    return [
        line
        for line in source().splitlines()
        if line.lstrip().startswith("|") and not SEPARATOR.match(line)
    ]


def captions() -> dict[str, set[str]]:
    """표 본문 줄 → **그 표 머리말이 인용한** 결정 번호.

    머리말은 표 바로 위의 제목이나 한 문단이다. 위로 `LOOKBACK`줄까지 보고, **다른
    표를 만나면 멈춘다** — 거기부터는 앞 표의 머리말이다.
    """
    lines = source().splitlines()
    found: dict[str, set[str]] = {}
    carry: set[str] = set()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        if index == 0 or not lines[index - 1].lstrip().startswith("|"):
            carry = set()
            for back in range(index - 1, max(-1, index - 1 - LOOKBACK), -1):
                above = lines[back]
                if above.lstrip().startswith("|"):
                    break
                carry |= set(CITES.findall(above))
                if above.lstrip().startswith("#"):
                    break
        if carry and not SEPARATOR.match(line):
            found[line.strip()] = carry
    return found


def stripped(line: str) -> str:
    """코드 조각 · 첫 칸 차례 · 식별자를 지운 나머지. **여기 남는 수가 주장이다.**"""
    bare = INDEX.sub("| ", CODE.sub(" ", line))
    for pattern in IDENTS:
        bare = re.sub(pattern, " ", bare)
    return bare


def tally(lines: list[str]) -> int:
    """**건수.** 줄 하나가 수 넷을 들 수 있다 — 줄로 세면 빚이 작아 보인다."""
    return sum(len(NUMBER.findall(stripped(line))) for line in lines)


def claims(table_rows: list[str]) -> list[str]:
    """수치를 **주장하는** 줄. 코드 조각과 식별자를 지우고도 수가 남는 것."""
    # **`claims()`와 `tally()`가 같은 자를 쓴다** (D-0381). 갈려 있던 동안 `mp3`의 3을
    # 주장으로 세고 건수는 0으로 세서, 목록에 **0건짜리 줄 셋**이 떠 있었다.
    return [line for line in table_rows if NUMBER.search(stripped(line))]


def mirrored() -> set[str]:
    """`measured`의 표식 안에 사는 줄. **자가 정본에서 다시 만든다.**"""
    text = MASTER.read_text(encoding="utf-8")
    inside: set[str] = set()
    for name in measured.BLOCKS:
        body = measured.present(text, name)
        if body is None:
            continue
        inside |= {line.strip() for line in body.splitlines() if line.lstrip().startswith("|")}
    return inside


def axled() -> set[str]:
    """`doc_fsck`의 축이 무는 줄. **그 자가 수를 실물과 맞댄다.**

    `check_requirements`는 덮는 자가 **아니다** (D-0381). 그것은 ID·우선순위·상태를
    보고 **수는 안 본다** — `REQ-ANL-006`의 `해시 8192`도 `REQ-ING-008`의 `78.5%`도
    그 자의 눈 밖이다. 덮개로 세었더니 **열 건을 과대 신용**했다.
    """
    return {
        line.strip()
        for line in rows()
        if any(pattern.search(line) for _name, pattern, _count in doc_counts.COUNTED)
    }


def recorded() -> set[str]:
    """대장에 **실제로 있는** 결정 번호. 없는 번호를 인용하면 상류가 아니다."""
    return set(re.findall(r"(?m)^## D-(\d{4})\.", DECISIONS.read_text(encoding="utf-8")))


def sort(found: list[str]) -> dict[str, list[str]]:
    """주장마다 상류를 묻는다. **먼저 무는 자가 가져간다** — 한 줄은 한 번만 센다."""
    mirror, rule, ledger, heads = mirrored(), axled(), recorded(), captions()
    out: dict[str, list[str]] = {
        "거울": [],
        "축": [],
        "기록": [],
        "상류 없음": [],
        "헛인용": [],
    }
    for line in found:
        bare = line.strip()
        cited = CITES.findall(bare) or sorted(heads.get(bare, ()))
        if bare in mirror:
            out["거울"].append(line)
        elif bare in rule:
            out["축"].append(line)
        elif cited and all(one in ledger for one in cited):
            out["기록"].append(line)
        elif cited:
            out["헛인용"].append(line)
        else:
            out["상류 없음"].append(line)
    return out


def check() -> list[str]:
    table = rows()
    if len(IDENTS) < IDENT_FLOOR:
        return [f"지울 식별자 꼴이 {len(IDENTS)}개다(바닥 {IDENT_FLOOR}). **그물이 비었다**"]
    if not table:
        return ["정본에서 표를 한 줄도 못 읽었다 — 자르는 법이 깨졌다"]

    groups = sort(claims(table))
    problems = [f"대장에 없는 결정을 인용한다: {line.strip()[:70]}" for line in groups["헛인용"]]
    loose = tally(groups["상류 없음"])
    if loose > UNSOURCED_CEILING:
        problems.append(
            f"상류 없는 수치가 {loose}건이다(천장 {UNSOURCED_CEILING}). "
            "표를 손으로 늘렸다 — 자를 붙이거나 결정 기록을 인용한다 (D-0378)"
        )
    elif loose < UNSOURCED_CEILING:
        problems.append(
            f"상류 없는 수치가 {loose}건이다(천장 {UNSOURCED_CEILING}). "
            "`python3 tools/check_ratchets.py --update`로 못을 조인다 (D-0257)"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 수치의 상류 (D-0378)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="상류 없는 줄을 찍는다")
    args = parser.parse_args()

    table = rows()
    groups = sort(claims(table))
    loose = tally(groups["상류 없음"])

    if args.list:
        for line in groups["상류 없음"]:
            print(f"  {tally([line])}건  {line.strip()[:150]}")
        print(
            f"상류 없는 수치 {loose}건 · 줄 {len(groups['상류 없음'])} · 천장 {UNSOURCED_CEILING}"
        )
        return 0

    problems = check()
    if problems:
        print(f"기획서 수치의 상류가 {len(problems)}곳 어긋난다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1

    said = sum(len(one) for one in groups.values())
    print(
        f"기획서 수치 검사 통과 · 표 줄 {len(table)} · 주장 {said} · "
        f"거울 {len(groups['거울'])} · 축 {len(groups['축'])} · "
        f"기록 {len(groups['기록'])} · "
        f"**상류 없음 {loose}건**/{len(groups['상류 없음'])}줄(천장 {UNSOURCED_CEILING})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
