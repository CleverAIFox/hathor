"""일회성 조사: ID3 프레임 전수 히스토그램. 프로덕션 코드 아님."""
from __future__ import annotations

import os
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError

DATE_FRAMES = ("TDRC", "TDRL", "TDOR", "TYER", "TDAT", "TORY")


def main() -> int:
    root = Path(os.environ.get("HATHOR_LIBRARY_ROOT", "/mnt/d/노래/노래"))
    if not root.is_dir():
        print(f"경로 없음: {root}")
        return 1

    files = sorted(p for p in root.rglob("*.mp3") if p.is_file())
    frame_counter: Counter[str] = Counter()
    date_counter: Counter[str] = Counter()
    nfd_names = 0
    has_isrc = 0
    has_uslt = 0
    has_sylt = 0
    has_any_date = 0
    failures: list[tuple[str, str]] = []

    for path in files:
        name = path.name
        if unicodedata.normalize("NFC", name) != name:
            nfd_names += 1
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            frame_counter["<NO_ID3_HEADER>"] += 1
            continue
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            continue

        keys = set(tags.keys())
        prefixes = {k.split(":")[0] for k in keys}
        for prefix in prefixes:
            frame_counter[prefix] += 1
        if "TSRC" in prefixes:
            has_isrc += 1
        if "USLT" in prefixes:
            has_uslt += 1
        if "SYLT" in prefixes:
            has_sylt += 1
        found = [f for f in DATE_FRAMES if f in prefixes]
        if found:
            has_any_date += 1
            date_counter["+".join(found)] += 1

    total = len(files)
    print(f"총 파일: {total}")
    print(f"읽기 실패: {len(failures)}")
    print(f"파일명 NFD(비정규화): {nfd_names}")
    print()
    print("=== 핵심 지표 ===")
    for label, count in (
        ("발매일 프레임 보유", has_any_date),
        ("ISRC(TSRC)", has_isrc),
        ("가사 USLT", has_uslt),
        ("동기가사 SYLT", has_sylt),
    ):
        pct = (count / total * 100) if total else 0.0
        print(f"{label:22s} {count:5d} / {total}  ({pct:5.1f}%)")
    print()
    print("=== 발매일 프레임 조합 ===")
    for combo, count in date_counter.most_common():
        print(f"  {combo:28s} {count:5d}")
    print()
    print("=== 전체 프레임 히스토그램 ===")
    for frame, count in frame_counter.most_common():
        pct = (count / total * 100) if total else 0.0
        print(f"  {frame:12s} {count:5d}  ({pct:5.1f}%)")
    if failures:
        print()
        print("=== 실패 샘플(최대 10) ===")
        for name, detail in failures[:10]:
            print(f"  {name}: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
