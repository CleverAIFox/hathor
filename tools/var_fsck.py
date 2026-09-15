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
    """이 묶음이 무엇인가. **추측이면 추측이라고 적는다.**"""
    manifests = sorted(path.glob(f"*{MANIFEST_SUFFIX}"))
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
    groups: dict[str, list[Path]] = {}
    for item in files:
        groups.setdefault(item.name.split("-")[0], []).append(item)
    for prefix, members in sorted(groups.items()):
        if len(members) > 1:
            total = sum(item.stat().st_size for item in members)
            print(f"  {prefix:<14} {len(members)}개 · {human(total)}  ← 같은 접두사가 여럿이다")

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
