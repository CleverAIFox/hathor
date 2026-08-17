#!/usr/bin/env python3
"""가사 코퍼스의 언어 구성을 실측한다. 신경망 인코더 선택 근거다 (D-0044).

### 왜 필요한가

한국어 단일이면 한국어 특화 모델이, 영어가 상당히 섞였으면 다국어 모델이 맞다.
**추측으로 고르면 나중에 "모델 성능 문제인지 언어 불일치 문제인지" 구분되지 않는다**
(GR-0.5). 스템을 MERT에 넣었을 때와 같은 종류의 혼입이다.

### 무엇을 재는가

`lyrics extract`가 실제로 쓰는 것과 **같은 경로**로 읽는다 — 스캔 산출물의 USLT
원문을 `split_segments`로 자른 뒤 문자를 센다. 여기서 다른 경로를 쓰면 측정 대상이
파이프라인과 달라진다.

문자 분류는 유니코드 블록 기준이며 **표기 문자만 센다** (공백·구두점·숫자 제외).
구두점을 포함하면 언어 비율이 희석돼 판단이 흐려진다.

사용법:
    cd core && uv run python ../tools/lyrics_language_profile.py --out var/ingest
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from hathor.domain.services.lyrics_segmentation import split_segments
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore


def classify(char: str) -> str | None:
    """표기 문자 하나를 언어 계열로 분류한다. 비표기 문자는 None."""
    category = unicodedata.category(char)
    if category[0] in {"Z", "C", "P", "S"} or category == "Nd":
        return None
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F:
        return "한글"
    if 0x3040 <= code <= 0x30FF:
        return "일본어 가나"
    if 0x4E00 <= code <= 0x9FFF:
        return "한자"
    if code < 0x0250:
        return "라틴"
    return "기타"


def main() -> int:
    parser = argparse.ArgumentParser(description="가사 언어 구성 실측")
    parser.add_argument("--out", default="var/ingest", help="스캔 산출물 루트")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="곡을 '주로 그 언어'로 분류하는 문자 비율 기준",
    )
    args = parser.parse_args()

    store = JsonlScanStore(Path(args.out))
    total: Counter[str] = Counter()
    per_track_primary: Counter[str] = Counter()
    mixed_tracks = 0
    tracks_with_lyrics = 0
    segment_count = 0
    skipped = 0

    for track in store.read_tracks():
        segments = split_segments(track.tags.lyrics_text)
        if len(segments) < 2:
            skipped += 1
            continue
        tracks_with_lyrics += 1
        segment_count += len(segments)

        counts: Counter[str] = Counter()
        for segment in segments:
            for char in segment:
                label = classify(char)
                if label:
                    counts[label] += 1
        total.update(counts)

        chars = sum(counts.values())
        if not chars:
            continue
        primary = counts.most_common(1)[0][0]
        per_track_primary[primary] += 1
        # 두 번째 계열이 10%를 넘으면 혼재로 본다. 영어 후렴 한 줄과
        # 절반이 영어인 곡은 인코더 선택에서 의미가 다르다.
        rest = [c for label, c in counts.items() if label != primary]
        if rest and max(rest) / chars >= 0.10:
            mixed_tracks += 1

    if not tracks_with_lyrics:
        print("가사가 있는 곡이 없다. --out 경로를 확인한다.", file=sys.stderr)
        return 1

    grand = sum(total.values())
    print(f"곡 {tracks_with_lyrics}개 (구간 2개 미만 제외 {skipped}) / 구간 {segment_count}개")
    print(f"표기 문자 {grand:,}자\n")

    print("문자 비율 (전체 코퍼스 합산)")
    for label, count in total.most_common():
        print(f"  {label:<10} {count:>10,}  {count / grand:>7.2%}")

    print("\n곡별 주 언어")
    for label, count in per_track_primary.most_common():
        print(f"  {label:<10} {count:>5}곡  {count / tracks_with_lyrics:>7.2%}")

    ratio = mixed_tracks / tracks_with_lyrics
    print(f"\n혼재 곡 (2순위 계열 10% 이상)  {mixed_tracks}곡  {ratio:.2%}")

    print("\n--- 읽는 법 ---")
    print("한글 90% 이상 + 혼재 20% 미만  → 한국어 특화 인코더")
    print("라틴 20% 이상 또는 혼재 40% 이상 → 다국어 인코더")
    print("그 사이  → 다국어 인코더. 한국어 특화는 영어 구간에서 무너진다")
    print("\n이 수치는 리포트로 저장하지 않는다. 판단 근거는 DECISIONS.md에 적는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
