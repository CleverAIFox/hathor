#!/usr/bin/env python3
"""기획서가 정본과 어긋나지 않는가 (D-0220).

### 왜 필요한가

기획서는 문서 중 **유일하게 밖이 읽는 것**인데 시제 규칙 밖이라 강제자가 없기 쉽다.
fire-lane이 그렇게 낡았고 — *"대상 222구간"*을 고치라는 갱신표까지 같이 낡았다 — thoth는
그것을 보고 **첫 판부터 검사를 붙였다.** 여기도 첫 판부터 붙인다.

### 정본은 기획서가 아니다

숫자와 이름의 정본은 저장소다. 기획서가 그것과 다르면 **저장소가 옳다.**

| 검사 | 무엇 |
|---|---|
| PRESENT | 저장소에서 읽은 값이 기획서에 있는가 |
| RETIRED | 폐기된 옛 값 · 옛 서술이 남아 있는가 |

**있는지만 보면 옛 값과 새 값이 둘 다 있어도 통과한다.** 없어야 할 것을 따로 본다.

### 모든 숫자를 보지 않는다

결정 건수 · 줄 수 · 커버리지처럼 **커밋마다 움직이는 수는 안 본다.** 그것까지 걸면
결정 하나 쓸 때마다 기획서를 다시 뽑아야 하고, 그러면 검사를 끈다. **판이 바뀌어야 하는
사건**에만 건다 — 상업 불가 모델이 바뀌었다 · 엔진 재개 조건이 바뀌었다 · 코퍼스가 바뀌었다.

docx는 표준 라이브러리로 연다(zip + XML). 의존이 없다.

    python3 tools/docx_check.py            # 검사한다. 위반 1 · 도구 고장 2
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCX = "docs/proposal.docx"

RETIRED: list[tuple[str, str]] = [
    ("유닛 1/4", "P1 인제스트는 끝났다 (D-0203)"),
    ("docs/archive", "보관소를 없앴다 (D-0186)"),
    ("사업화를 전제하지 않는다", "목표가 제품으로 바뀌었다 (D-0215)"),
    ("휴면", "장비가 필요한 일만 멈춘다 (D-0218)"),
]
"""기획서에 남으면 안 되는 말. **값이 바뀌면 옛 값을 여기로 옮긴다.**"""


def text_of(path: Path) -> str:
    """문단마다 한 줄. 표 안 글자도 문단이므로 같이 나온다."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    return "\n".join(
        "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", paragraph)) for paragraph in paragraphs
    )


def _one(pattern: str, text: str, where: str) -> str:
    found = re.search(pattern, text)
    if not found:
        raise LookupError(f"{where}에서 `{pattern}`을 못 찾았다 — 정본의 모양이 바뀌었다")
    return found.group(1)


def truths(root: Path) -> list[tuple[str, str]]:
    """(기획서에 있어야 할 문자열, 출처). **손으로 적지 않고 저장소에서 읽는다.**"""
    master = (root / "docs/MASTER.md").read_text(encoding="utf-8")
    plan = (root / "docs/PLAN.md").read_text(encoding="utf-8")
    licenses = (root / "tools/check_model_licenses.py").read_text(encoding="utf-8")

    corpus = _one(r"개발자 개인 보유 음원 (\d+)곡", master, "MASTER 코퍼스 전제")
    m1_row = r"M1 앨범 검색 P@10 \| \*\*실측 [\d.]+ \(무작위 [\d.]+ 대비 ([\d.]+)배"
    m1 = _one(m1_row, master, "MASTER §10")
    vram = _one(r"재개 조건: NVIDIA · VRAM (\d+)GB 이상", plan, "PLAN §1")
    blocked = re.findall(r'"([\w./-]+)": \(\s*"([^"]+)",\s*"no"', licenses)
    if not blocked:
        raise LookupError("check_model_licenses.py에서 상업 불가 모델을 못 읽었다")

    found = [
        (f"{corpus}곡", "MASTER — 개발 코퍼스"),
        (f"{m1}배", "MASTER §10 — M1 앨범 검색"),
        (f"VRAM {vram}GB", "PLAN §1 — 엔진 재개 조건"),
    ]
    for name, license_name in blocked:
        short = name.split("/")[-1].split("-")[0]
        found.append((short, f"check_model_licenses — 상업 불가 {name}"))
        found.append((license_name, f"check_model_licenses — {name}의 라이선스"))
    return found


def check(root: Path = ROOT) -> list[str]:
    path = root / DOCX
    if not path.is_file():
        return [f"{DOCX}가 없다"]
    text = text_of(path)
    problems = [
        f"기획서에 `{value}`이 없다 — 출처: {source}"
        for value, source in truths(root)
        if value not in text
    ]
    problems += [
        f"기획서에 폐기된 말 `{value}`이 남았다 — {reason}"
        for value, reason in RETIRED
        if value in text
    ]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 ↔ 정본 대조 (D-0220)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.parse_args()
    try:
        problems = check()
    except (LookupError, KeyError, zipfile.BadZipFile) as error:
        print(f"기획서 검사 도구가 죽었다: {error}", file=sys.stderr)
        return 2
    if problems:
        print(f"기획서가 정본과 {len(problems)}곳 어긋난다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"기획서 검사 통과 · 정본 대조 {len(truths(ROOT))}건 · 폐기어 {len(RETIRED)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
