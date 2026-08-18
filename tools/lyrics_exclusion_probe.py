#!/usr/bin/env python3
"""가사 구간 분할에서 제외된 곡의 원인을 밝힌다 (D-0048).

### 왜 필요한가

`BIGBANG (빅뱅) - 멍청한 사랑`이 "구간 2개 미만"으로 제외됐다. 제외 사유가
"가사 없음"이 아니므로 **태그는 존재한다.** 그런데 `split_segments`에는 빈 줄이
없을 때 4줄씩 묶는 폴백이 있어, 가사가 길면 제외될 이유가 없어 보인다.

**원인을 추측으로 채우지 않는다 (GR-0.5).** 후보는 셋이며 서로 처방이 다르다.

| 후보 | 처방 |
|---|---|
| 줄바꿈이 없는 한 줄짜리 태그 | 문장 부호로 나누는 2차 폴백 |
| 모든 줄이 `[Verse]` 같은 구조 표기 | 표기 제거를 구간 판정 **전에** 하지 않도록 순서 변경 |
| 모든 블록이 8자 미만 | `MIN_SEGMENT_CHARS` 재검토 |

한 곡짜리 문제로 보이지만 **조용한 데이터 손실 범주**다. 코퍼스가 바뀌면
같은 이유로 여러 곡이 사라질 수 있고, 그때도 제외 수만 찍힐 뿐 원인은 안 보인다.

사용법:
    cd core && uv run python ../tools/lyrics_exclusion_probe.py --out var/ingest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from hathor.domain.services.lyrics_segmentation import (
    BLANK_LINE,
    BRACKETED,
    MIN_SEGMENT_CHARS,
    normalize_lyrics,
    split_segments,
)
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore


def diagnose(text: str) -> dict[str, object]:
    """분할이 실패한 지점을 단계별로 짚는다. `split_segments`의 순서를 따른다."""
    normalized = normalize_lyrics(text)
    lines = [line for line in normalized.split("\n") if line.strip()]
    blocks = [block for block in BLANK_LINE.split(normalized) if block.strip()]
    bracketed = [line for line in lines if BRACKETED.match(line.strip())]
    return {
        "chars": len(normalized),
        "lines": len(lines),
        "blank_line_blocks": len(blocks),
        "bracketed_lines": len(bracketed),
        "longest_line": max((len(line) for line in lines), default=0),
        "segments": len(split_segments(text)),
    }


def verdict(facts: dict[str, object]) -> str:
    lines = int(facts["lines"])
    chars = int(facts["chars"])
    if lines <= 1 and chars > 200:
        return "한 줄짜리 태그 — 줄바꿈이 없어 4줄 폴백이 블록 하나만 낸다"
    if int(facts["bracketed_lines"]) >= lines:
        return "모든 줄이 구조 표기 — 정리 단계에서 전부 버려진다"
    if lines <= 4:
        return f"줄이 {lines}개뿐 — 폴백 단위(4줄)로 블록 하나다"
    return f"원인 불명 — 줄 {lines}개인데 구간이 {facts['segments']}개다. 원문을 직접 본다"


def main() -> int:
    parser = argparse.ArgumentParser(description="가사 제외 곡 진단")
    parser.add_argument("--out", default="var/ingest", help="스캔 산출물 루트")
    parser.add_argument("--show", type=int, default=300, help="원문 앞부분을 몇 자 보일지")
    args = parser.parse_args()

    excluded: list[tuple[str, str, dict[str, object]]] = []
    total = 0
    no_lyrics = 0

    for track in JsonlScanStore(Path(args.out)).read_tracks():
        total += 1
        text = track.tags.lyrics_text
        if not text or not text.strip():
            no_lyrics += 1
            continue
        if len(split_segments(text)) >= 2:
            continue
        excluded.append((track.source_key, text, diagnose(text)))

    print(f"곡 {total}개 / 가사 없음 {no_lyrics} / 태그는 있으나 제외 {len(excluded)}\n")
    if not excluded:
        print("제외된 곡이 없다.")
        return 0

    for key, text, facts in excluded:
        print("=" * 70)
        print(key)
        print(
            f"  문자 {facts['chars']} · 줄 {facts['lines']} · 빈줄블록 {facts['blank_line_blocks']} "
            f"· 구조표기줄 {facts['bracketed_lines']} · 최장줄 {facts['longest_line']} "
            f"· 구간 {facts['segments']} (기준 최소 {MIN_SEGMENT_CHARS}자)"
        )
        print(f"  판정: {verdict(facts)}")
        print("  원문 앞부분:")
        preview = normalize_lyrics(text)[: args.show]
        for line in preview.split("\n"):
            print(f"    | {line}")
        if len(text) > args.show:
            print("    | ...")
    print("\n이 결과를 근거로 처방을 고른다. 추측으로 고치지 않는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
