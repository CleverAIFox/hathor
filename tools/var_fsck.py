#!/usr/bin/env python3
"""산출물이 무엇인지 찍는다 (D-0203).

### 왜 있나

`var/`가 1.9GB까지 갔고 **무엇이 현역인지 아무도 몰랐다.** 정리하려고
손으로 열 번 넘게 `du`·`head`·`json.tool`을 쳤고, 그 끝에 `mert-layers`가
**정본**이라는 것을 겨우 알아냈다 — `stem_names`에 `layer03`이 들어 있는 것을
보고 추측한 것이며 하마터면 지울 뻔했다.

**그 대화를 다시 하지 않으려고 만든다.** `doc_fsck`가 문서 ↔ 실물을 보듯
이것은 **산출물 ↔ 정체**를 본다.

### 판정하지 않는다

무엇을 지울지 여기서 정하지 않는다. 사람이 보고 정한다 — **자동으로 지우는
도구는 언젠가 정본을 지운다.** 찍기만 하는 것이 규약이다.

사용법:
    python3 tools/var_fsck.py
    python3 tools/var_fsck.py --root var/ingest
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "var" / "ingest"

MANIFEST_SUFFIX = ".manifest.json"
"""D-0203 이후 산출물이 자기를 설명하는 자리."""

LEGACY_INDEX = "index.features.jsonl"
"""옛 묶음. **아무것도 안 든다** — `stem_names`로 정체를 추측해야 한다."""


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "K", "M", "G"):
        if value < 1024 or unit == "G":
            return f"{value:.0f}{unit}"
        value /= 1024
    return f"{value:.0f}G"


def folder_size(path: Path) -> tuple[int, int]:
    total = count = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
            count += 1
    return total, count


def describe(path: Path) -> str:
    """이 묶음이 무엇인가. **추측이면 추측이라고 적는다.**

    **manifest는 한 단계 아래에도 있다** (D-0244). `NpzFeatureStore`는 `<루트>/features/`에
    쓰므로 `clap/clap.manifest.json`이 아니라 `clap/features/clap.manifest.json`이다.
    옛 판은 manifest를 `glob`으로, 옛 인덱스를 `rglob`으로 찾았다 — **그 비대칭 때문에
    D-0233이 manifest를 쓰기 시작한 뒤에도 «자기를 설명하지 않는다»가 그대로 떴다.**
    """
    manifests = sorted(path.rglob(f"*{MANIFEST_SUFFIX}"))
    if manifests:
        found = json.loads(manifests[0].read_text(encoding="utf-8"))
        layers = found.get("layers") or []
        return (
            f"manifest {len(manifests)}건 · 층 {len(layers)}개"
            f" · dtype {found.get('dtype', '?')} · rev {found.get('revision', '?')}"
        )
    legacy = next(path.rglob(LEGACY_INDEX), None)
    if legacy is not None:
        first = legacy.read_text(encoding="utf-8").splitlines()[:1]
        if first:
            record = json.loads(first[0])
            names = record.get("stem_names") or []
            kind = "층" if any(str(n).startswith("layer") for n in names) else "스템"
            return f"**manifest 없음** · {kind} {names} · {record.get('feature_dim')}차 (추측)"
    return "**manifest 없음** · 정체 불명"


STAMP = re.compile(r"^(?P<name>[\w.-]*?)-?(?P<stamp>\d{8}T\d{6}Z)(?P<rest>\..*)?$")
"""`scan-20260915T133016Z.jsonl` 꼴에서 이름과 시각을 가른다."""


def runs(files: list[Path]) -> dict[str, tuple[set[str], int]]:
    """이름별 `(실행 시각 집합, 총 바이트)` (D-0209).

    **한 실행이 낸 파일들을 한 묶음으로 센다.** `scan-*`는 한 번 돌면
    `.jsonl` · `.failures.jsonl` · `.summary.json` **셋**이 나온다. 접두사만 보고
    세면 **정상을 «여럿»으로 찍고**, 그 경고가 매번 뜨면 사람이 읽기를 그만둔다 —
    **정상을 잔해로 부르는 검사는 진짜 잔해를 가린다.**

    시각이 둘 이상일 때가 진짜 잔해다. 시각이 없는 파일은 한 실행으로 센다.
    """
    table: dict[str, tuple[set[str], int]] = {}
    for item in files:
        found = STAMP.match(item.name)
        name = (found["name"] or item.stem) if found else item.stem
        stamp = found["stamp"] if found else ""
        stamps, size = table.get(name, (set(), 0))
        table[name] = (stamps | {stamp}, size + item.stat().st_size)
    return table


def report(root: Path) -> int:
    if not root.exists():
        print(f"산출물 루트가 없다: {root}", file=sys.stderr)
        return 2
    folders = sorted(item for item in root.iterdir() if item.is_dir())
    files = sorted(item for item in root.iterdir() if item.is_file())

    print(f"{root}\n")
    print(f"{'묶음':<34}{'크기':>8}{'파일':>8}  정체")
    print("-" * 100)
    unnamed = 0
    for folder in folders:
        size, count = folder_size(folder)
        text = describe(folder)
        unnamed += "manifest 없음" in text
        print(f"{folder.name:<34}{human(size):>8}{count:>8}  {text}")

    print(f"\n낱개 파일 {len(files)}개")
    stale = 0
    for label, (stamps, size) in sorted(runs(files).items()):
        mark = ""
        if len(stamps) > 1:
            stale += 1
            mark = "  ← **옛 실행이 남았다**"
        print(f"  {label:<22} 실행 {len(stamps)}회 · {human(size):>6}{mark}")

    if stale:
        print(f"\n**{stale}개 이름에 실행이 여럿 남았다.** 최신만 남긴다 (O-62).")
    if unnamed:
        print(f"\n**{unnamed}개 묶음이 자기를 설명하지 않는다.** 정체를 추측해야 한다 (D-0203).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="산출물 정체 검사 (D-0203)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="산출물 루트")
    args = parser.parse_args()
    return report(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
