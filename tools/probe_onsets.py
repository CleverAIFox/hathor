#!/usr/bin/env python3
"""박·온셋 실측 탐침 (O-46 · D-0152).

    cd core
    uv run python ../tools/probe_onsets.py
    uv run python ../tools/probe_onsets.py --hop 0.01 --limit 50

**합성이 아니라 곡에서 잰다.** D-0143이 12판, D-0144가 합성 음원에서 관통을
확인했고 **실제 곡에는 리버브도 스윙도 박자 변화도 있다.**

### 무엇을 보는가

| | 무엇 |
|---|---|
| 빠르기 | 곡별 BPM 분포. **`--tempo` 기본값 96이 얼마나 틀렸는지** |
| 격차 | 봉우리 1등과 2등. 낮으면 못 고른 것이다 |
| 배수 격차 | 절반·두 배와의 차이. **낮으면 사람도 갈릴 자리다** (D-0054) |
| 위상 | 발음이 박 안 어디에 떨어지는가. **반주 리듬의 재료다** |

### 판정하지 않는다

이 탐침은 **분포를 낼 뿐이다.** 무엇을 제품에 쓸지는 보고 나서 결정 기록으로
정한다 — 탐침이 판정하면 그 자리에서 값이 생긴다 (D-0058).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from hathor.domain.services.onset import (  # noqa: E402 — sys.path 조작 뒤라야 한다
    PHASE_BINS,
    beat_period,
    phase_profile,
)
from hathor.infrastructure.onset_store import SUFFIX  # noqa: E402


def folders(out: Path) -> list[Path]:
    """`keys-*.onsets` 전부. **홉이 다른 폴더가 섞이면 안 된다** (D-0145)."""
    return sorted(out.glob(f"keys-*{SUFFIX}"))


def load(folder: Path, limit: int | None) -> list[tuple[str, np.ndarray, float]]:
    found: list[tuple[str, np.ndarray, float]] = []
    for path in sorted(folder.glob("*.npz"))[:limit]:
        with np.load(path, allow_pickle=False) as bundle:
            found.append(
                (
                    str(bundle["source_key"]),
                    np.asarray(bundle["envelope"], dtype=np.float64),
                    float(bundle["hop_seconds"]),
                )
            )
    return found


def quantiles(values: list[float]) -> str:
    ordered = sorted(values)
    if len(ordered) < 4:
        return " · ".join(f"{value:.2f}" for value in ordered)
    cut = statistics.quantiles(ordered, n=20)
    return (
        f"5% {cut[0]:.2f} · 25% {cut[4]:.2f} · 중앙 {statistics.median(ordered):.2f} "
        f"· 75% {cut[14]:.2f} · 95% {cut[18]:.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="박·온셋 실측 (D-0152)")
    parser.add_argument("--out", type=Path, default=Path("var/ingest"), help="산출물 루트")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한")
    args = parser.parse_args()

    picked = folders(args.out)
    if not picked:
        print(f"{args.out}에 포락선 폴더가 없다. `ingest onsets`를 먼저 돌린다.", file=sys.stderr)
        return 1
    folder = picked[-1]
    songs = load(folder, args.limit)
    if not songs:
        print(f"{folder}가 비어 있다.", file=sys.stderr)
        return 1

    print(f"{folder.name} · {len(songs)}곡")
    tempos: list[float] = []
    margins: list[float] = []
    octaves: list[float] = []
    profiles: list[tuple[float, ...]] = []
    missing = 0
    for _, envelope, hop in songs:
        beat = beat_period(envelope, hop)
        if beat is None:
            missing += 1
            continue
        tempos.append(beat.tempo_bpm)
        margins.append(beat.margin)
        octaves.append(beat.octave_margin)
        profiles.append(phase_profile(envelope, beat.period_seconds, hop))

    if not tempos:
        print("박을 하나도 못 골랐다.", file=sys.stderr)
        return 1

    print(f"\n빠르기 (BPM)\n  {quantiles(tempos)}")
    print(f"  못 고른 곡 {missing}")
    print(f"\n격차\n  {quantiles(margins)}")
    print(f"\n배수 격차\n  {quantiles(octaves)}")
    low = sum(1 for value in octaves if value < 0.10)
    print(f"  0.10 미만 {low}곡 — **사람도 갈릴 자리다** (D-0054)")

    print("\n박 안 위상 (평균)")
    mean = [statistics.mean(profile[index] for profile in profiles) for index in range(PHASE_BINS)]
    print("  " + " · ".join(f"{value:.3f}" for value in mean))
    flat = sum(1 for profile in profiles if max(profile) < 1.5 / PHASE_BINS)
    print(f"  고른 곡 {flat} / {len(profiles)} — 고르면 **정박에 안 몰린다는 뜻이다**")

    gap = statistics.median(abs(value - 96.0) for value in tempos)
    print(f"\n`--tempo` 기본값 96과의 차이\n  중앙 {gap:.1f}BPM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
