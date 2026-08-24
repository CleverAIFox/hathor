#!/usr/bin/env python3
"""결정 기록을 번호대별 파일로 나눈다 (O-30 · D-0080).

### 왜 필요한가

O-30이 **분할 조건을 6000줄 또는 100건**으로 정해 두었다. 조건은 조건일 뿐
**검사가 없어 아무도 보지 않았고**, 발동한 뒤에도 한참을 그냥 지났다.
GR-0.8이 "검사할 수 없는 규약은 잊힌다"고 적은 그 자리다.

검사는 `sync_decision_index.py`가 진다. **이 도구는 검사가 빨갛게 떴을 때
초록으로 되돌리는 손이다.**

### 나누는 규칙

`RECORDS_PER_PART`건씩 번호대로 자른다. 조각 이름이 곧 범위다 —
`docs/decisions/D-0001-0050.md`. **어느 번호가 어느 파일인지 이름만 보고 안다.**

`docs/DECISIONS.md`는 지우지 않고 **조각 목록만 담은 진입 문서로 남긴다.**
README·DESIGN·CONTRIBUTING·PR 서식이 그 경로를 가리키고 있고, 링크를 한꺼번에
고치는 것은 이 분할과 다른 작업이다.

### 다시 돌려도 안전하다

조각이 이미 있으면 **조각을 다시 읽어 합친 뒤 다시 나눈다.** 기록이 100건에서
150건이 될 때도 같은 명령이다 — 일회성 이주 도구가 아니라 유지 도구다.

**내용은 한 글자도 바꾸지 않는다.** 표제 앞뒤 구분선과 빈 줄만 규약대로 다시
쓴다 (D-0081의 표기 정규화와 같은 범위다). 추가 전용(GR-0.2)은 깨지지 않는다.

사용법:
    python tools/split_decisions.py          # 나눠 쓴다
    python tools/split_decisions.py --check  # 쓰지 않는다. 달라지면 1로 끝난다
"""

from __future__ import annotations

import argparse
import sys

from sync_decision_index import (
    DECISIONS,
    DECISIONS_DIR,
    PART_NAME,
    RECORDS_PER_PART,
    load_parts,
    merge_parts,
    part_path,
    scan_records,
)

HEADER = """# 결정 기록 {first} ~ {last} (GR-0.2)

> **문서 4종** (D-0043) — 규약 `CONTRIBUTING.md` · 기획 `docs/DESIGN.md` ·
> 결정 `docs/DECISIONS.md` · 진입 `README.md`. **현재 문서: 결정.**

형식: 배경 / 후보 / 선택 / 근거 / 결과

<!-- 이 파일은 tools/split_decisions.py가 나눈 조각이다. 전체 색인은 부록 A. -->
"""

STUB = """# 결정 기록 (GR-0.2)

> **문서 4종** (D-0043) — 규약 `CONTRIBUTING.md` · 기획 `docs/DESIGN.md` ·
> 결정 `docs/DECISIONS.md` · 진입 `README.md`. **현재 문서: 결정.**

형식: 배경 / 후보 / 선택 / 근거 / 결과

**본문은 번호대별 조각에 있다** (O-30 · D-0080). 한 파일이 6000줄 또는 100건을
넘으면 `make split`이 다시 나눈다. **전체 색인은 `docs/DESIGN.md` 부록 A**이며
`tools/sync_decision_index.py`가 조각 전부를 긁어 생성한다.

<!-- 이 목록은 tools/split_decisions.py가 생성한다. 손으로 고치지 않는다. -->

| 조각 | 범위 | 건수 |
|---|---|---|
{rows}

찾기:

```bash
grep -rn "D-0086" docs/decisions/
```
"""


def _body(text: str) -> str:
    """기록 본문에서 **뒤따라온 구분선을 뗀다.**

    구분선은 다음 표제의 것이지 이 기록의 것이 아니다. 안 떼면 다시 나눌 때마다
    `---`가 한 줄씩 늘고, 표기 검사는 그것을 통과시킨다 — **조용히 자란다.**
    """
    body = text.rstrip()
    while body.endswith("---"):
        body = body[: -len("---")].rstrip()
    return body


def _blocks(text: str) -> list[str]:
    """조각 본문을 표제 단위로 다시 조립한다. **표기만 규약대로 맞춘다.**"""
    return [
        f"---\n\n## {record.identifier}. {record.title}\n{_body(record.body)}\n"
        for record in scan_records(text)
    ]


def render() -> dict[str, str]:
    """써야 할 파일 전부를 경로별 본문으로 낸다. **쓰지는 않는다.**"""
    merged = merge_parts(load_parts())
    records = scan_records(merged)
    if not records:
        raise SystemExit("결정 기록에서 `## D-XXXX. 제목`을 찾지 못했다")

    numbers = [record.number for record in records]
    if numbers != sorted(numbers):
        raise SystemExit("번호가 오름차순이 아니다. 먼저 make docs로 어긋남을 본다")

    blocks = _blocks(merged)
    planned: dict[str, str] = {}
    rows: list[str] = []
    for start in range(0, len(records), RECORDS_PER_PART):
        chunk = records[start : start + RECORDS_PER_PART]
        # **번호대는 건수가 아니라 자리로 끊는다.** 결번이 있어도 이름이 범위를
        # 정확히 덮어야 `grep` 없이 파일을 고를 수 있다.
        low = (chunk[0].number - 1) // RECORDS_PER_PART * RECORDS_PER_PART + 1
        high = low + RECORDS_PER_PART - 1
        name = PART_NAME.format(low=low, high=high)
        body = HEADER.format(first=chunk[0].identifier, last=chunk[-1].identifier)
        planned[name] = body + "\n" + "\n".join(blocks[start : start + len(chunk)])
        span = f"{chunk[0].identifier}~{chunk[-1].identifier}"
        rows.append(f"| [`{name}`](decisions/{name}) | {span} | {len(chunk)}건 |")

    planned["__stub__"] = STUB.format(rows="\n".join(rows))
    return planned


def main() -> int:
    parser = argparse.ArgumentParser(description="결정 기록을 번호대별로 나눈다")
    parser.add_argument("--check", action="store_true", help="쓰지 않고 차이만 본다")
    args = parser.parse_args()

    planned = render()
    stub = planned.pop("__stub__")

    changed: list[str] = []
    for name, body in planned.items():
        path = part_path(name)
        if not path.exists() or path.read_text(encoding="utf-8") != body:
            changed.append(name)
    for path in sorted(DECISIONS_DIR.glob("D-*.md")) if DECISIONS_DIR.exists() else []:
        if path.name not in planned:
            changed.append(f"{path.name} (지움)")
    if DECISIONS.read_text(encoding="utf-8") != stub:
        changed.append(DECISIONS.name)

    if not changed:
        print(f"조각 {len(planned)}개가 이미 맞다.")
        return 0

    if args.check:
        print("결정 기록 조각이 어긋난다:", file=sys.stderr)
        for name in changed:
            print(f"  - {name}", file=sys.stderr)
        print("  make split 으로 다시 쓴다.", file=sys.stderr)
        return 1

    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(DECISIONS_DIR.glob("D-*.md")):
        if path.name not in planned:
            path.unlink()
    for name, body in planned.items():
        part_path(name).write_text(body, encoding="utf-8")
    DECISIONS.write_text(stub, encoding="utf-8")

    print(f"조각 {len(planned)}개를 썼다 · {DECISIONS.name}은 진입 문서로 남겼다.")
    print("다음:  make docs  &&  make check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
