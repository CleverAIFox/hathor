#!/usr/bin/env python3
"""참조곡 스템에서 **층이 무엇을 가져올 수 있나** 실측 탐침 (O-51 · D-0214).

    cd core
    uv run python ../tools/probe_stems.py
    uv run python ../tools/probe_stems.py --match "강남스타일" --match "허전해"

**판정하지 않는다.** 분포를 낼 뿐이고 무엇을 제품에 쓸지는 보고 나서 결정 기록으로
정한다 — 탐침이 판정하면 그 자리에서 값이 생긴다 (D-0058).

### 묶음이 줄 수 있는 것과 없는 것

| 묻는 것 | 묶음에 있나 | 어디서 |
|---|---|---|
| 가락·베이스의 **음역** | 있다 | `pitch/vocals` · `pitch/bass` (pyin, Hz) |
| 가락·베이스가 **얼마나 쉬나** | 있다 | pyin 무성 판정(`NaN`). **우리 문턱이 아니다** |
| 곡 전체의 **쉼** | 있다 | `silence/mixture` · 문턱은 manifest의 `silence_floor` |
| 층의 **음량 비** | **없다** | `onset/*`는 스펙트럼 선속이라 음량이 아니다 (D-0206) |
| **무슨 악기인가** | **없다** | 스템은 역할(`other`)이지 악기가 아니다. 기타인지 신스인지 모른다 |

**아래 두 줄이 O-51의 한계다.** 악기 번호를 참조곡에서 «가져오는» 길은 이 묶음으로는
없다 — 있는 척하지 않으려고 표에 적는다.

### 옥타브 오류

pyin은 옥타브를 틀린다. 코러스·더블링이 있는 보컬 스템에서 특히 그렇다. **곡마다
10·50·90분위를 따로 찍어** 한 곡의 폭이 두 옥타브를 넘으면 그 곡을 의심한다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from hathor.infrastructure.track_bundle_store import (  # noqa: E402 — sys.path 조작 뒤라야 한다
    BUNDLE_DIRNAME,
    TrackBundleStore,
)

PITCH_STEMS = ("vocals", "bass")
PREFIXES = ("pitch/", "silence/")


def midi(hertz: np.ndarray) -> np.ndarray:
    """Hz → MIDI 번호. **무성(`NaN`)은 뺀다.**"""
    voiced = hertz[np.isfinite(hertz) & (hertz > 0)]
    return 69.0 + 12.0 * np.log2(voiced / 440.0)


def song_row(arrays: dict[str, np.ndarray], manifest: dict[str, object]) -> dict[str, float]:
    row: dict[str, float] = {}
    for stem in PITCH_STEMS:
        track = arrays.get(f"pitch/{stem}")
        if track is None or track.size == 0:
            continue
        notes = midi(np.asarray(track, dtype=np.float64))
        row[f"{stem}_voiced"] = notes.size / track.size
        if notes.size:
            low, mid, high = np.percentile(notes, (10, 50, 90))
            row[f"{stem}_p10"], row[f"{stem}_p50"], row[f"{stem}_p90"] = low, mid, high
    silence = arrays.get("silence/mixture")
    floor = manifest.get("silence_floor")
    if silence is not None and silence.size and isinstance(floor, int | float):
        row["mix_silent"] = float((silence < float(floor)).mean())
    if "vocals_p50" in row and "bass_p50" in row:
        row["gap"] = row["vocals_p50"] - row["bass_p50"]
    return row


def name_of(number: float) -> str:
    if not math.isfinite(number):
        return "-"
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    rounded = round(number)
    return f"{names[rounded % 12]}{rounded // 12 - 1}"


def spread(values: list[float]) -> str:
    if not values:
        return "(없다)"
    low, mid, high = np.percentile(values, (10, 50, 90))
    return f"10% {low:6.1f} · 중앙 {mid:6.1f} · 90% {high:6.1f}   ({len(values)}곡)"


FIELDS = (
    ("vocals_p50", "가락 음높이 중앙 (MIDI)", False),
    ("vocals_p10", "가락 아래 10%", False),
    ("vocals_p90", "가락 위 90%", False),
    ("vocals_voiced", "가락이 소리 내는 몫", True),
    ("bass_p50", "베이스 음높이 중앙 (MIDI)", False),
    ("bass_voiced", "베이스가 소리 내는 몫", True),
    ("gap", "가락 - 베이스 (반음)", False),
    ("mix_silent", "곡 전체가 무음인 몫", True),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="var/ingest", help="산출물 루트 (저장소 기준)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--match", action="append", default=[], help="곡별로 찍을 곡 이름 조각")
    args = parser.parse_args()

    out = Path(args.out)
    store = TrackBundleStore((out if out.is_absolute() else ROOT / out) / BUNDLE_DIRNAME)
    rows: list[tuple[str, dict[str, float]]] = []
    for index, (source_key, path, manifest) in enumerate(store.manifests()):
        if args.limit is not None and index >= args.limit:
            break
        rows.append((source_key, song_row(store.read(path, PREFIXES), manifest)))
    if not rows:
        print(f"묶음이 없다: {store.root}", file=sys.stderr)
        return 1

    print(f"곡 {len(rows)}개 · {store.root}\n")
    for field, label, share in FIELDS:
        values = [row[field] for _, row in rows if field in row]
        text = spread([value * 100 for value in values] if share else values)
        print(f"  {label:<24}{text}{' (%)' if share else ''}")
        if field == "vocals_p50" and values:
            print(f"  {'':<24}중앙은 {name_of(float(np.median(values)))}")

    wide = sum(
        1 for _, row in rows if row.get("vocals_p90", 0.0) - row.get("vocals_p10", 0.0) > 24.0
    )
    print(f"\n  가락 폭이 두 옥타브를 넘는 곡 {wide} — **옥타브 오류를 의심한다**")

    for needle in args.match:
        for source_key, row in rows:
            if needle.lower() not in source_key.lower():
                continue
            picked = {
                key: (
                    round(value, 3) if "voiced" in key or key == "mix_silent" else round(value, 1)
                )
                for key, value in row.items()
            }
            print(f"\n{source_key}\n  {json.dumps(picked, ensure_ascii=False)}")
            if "vocals_p50" in row:
                print(
                    f"  가락 중앙 {name_of(row['vocals_p50'])}"
                    f" · 베이스 중앙 {name_of(row.get('bass_p50', math.nan))}"
                )

    print(
        "\n--- 읽는 법 ---\n"
        "생성기의 층 음역과 **나란히 놓는다.** 멀면 음역을 참조곡에서 가져올 근거다.\n"
        "소리 내는 몫이 100%에서 멀면 **쉼(O-50)을 참조곡에서 가져올 근거다.**\n"
        "악기 번호와 층 음량 비는 이 묶음에 없다 — 표를 보고 적었다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
