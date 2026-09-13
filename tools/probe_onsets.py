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
    peaks,
    phase_profile,
)
from hathor.infrastructure.onset_store import SUFFIX  # noqa: E402


def _resolve(value: str) -> Path:
    """상대 경로는 **저장소 루트 기준**이다 (D-0069)."""
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


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


WINDOW_SECONDS = 30.0
"""구간별로 다시 재는 창. **드리프트를 가르는 자다** (D-0154).

곡 전체로 한 번 재면 빠르기 변화와 추정 오차가 섞인다. **구간마다 따로 재서 값이
고르면 추정은 되는데 위상만 밀리는 것이고, 들쭉날쭉하면 포락선이 나쁜 것이다.**"""


def diagnose(song: tuple[str, np.ndarray, float]) -> int:
    """곡 하나를 뜯는다. **포락선이 나쁜가 추정이 나쁜가를 가른다.**"""
    key, envelope, hop = song
    print(f"\n곡 · {key}")
    print(f"  길이 {envelope.size * hop:.1f}초 · 칸 {envelope.size}")

    centred = envelope - envelope.mean()
    peak = float(np.abs(centred).max())
    print("\n포락선 선명도")
    print(f"  최대/중앙 {peak / max(float(np.median(np.abs(centred))), 1e-9):.1f}배")
    above = int((centred > peak * 0.3).sum())
    print(f"  최대의 30%를 넘는 칸 {above} ({above / envelope.size:.1%})")

    whole = beat_period(envelope, hop)
    if whole is not None:
        print(f"\n곡 전체 · {whole.tempo_bpm:.2f}BPM · 격차 {whole.margin:.3f}")

    if whole is not None:
        beat_frames = whole.period_seconds / hop
        apart = max(1, int(beat_frames / PHASE_BINS / 2))
        print(f"\n봉우리 · 박 하나가 {beat_frames:.1f}칸 · 한 칸 {apart}칸")
        for label, picked in (
            ("이웃만", peaks(envelope)),
            ("해상도 한 칸", peaks(envelope, apart=apart)),
        ):
            share = len(picked) / envelope.size
            gap = float(np.median(np.diff([i for i, _ in picked]))) if len(picked) > 1 else 0.0
            times = beat_frames / gap if gap else 0.0
            print(
                f"  {label:<12}{len(picked):>6}개 ({share:5.1%})"
                f" · 간격 중앙 {gap:5.1f}칸 · 박의 {times:5.1f}배"
            )
        print("  **`phase_profile`이 쓰는 것은 아래 줄이다** (D-0157)")
        print("\n이 곡의 박 안 위상")
        print(
            "  "
            + " · ".join(f"{v:.3f}" for v in phase_profile(envelope, whole.period_seconds, hop))
        )

    span = int(WINDOW_SECONDS / hop)
    found: list[float] = []
    for start in range(0, envelope.size - span, span):
        piece = beat_period(envelope[start : start + span], hop)
        if piece is not None:
            found.append(piece.tempo_bpm)
    if found:
        print(f"\n{WINDOW_SECONDS:g}초 구간별 · {len(found)}구간")
        print(f"  {quantiles(found)}")
        spread = statistics.pstdev(found) if len(found) > 1 else 0.0
        print(f"  표준편차 {spread:.2f}BPM")
        print(
            "  **구간이 고르면 추정은 되고 위상만 밀린 것이다.** "
            "들쭉날쭉하면 포락선이 나쁘다 (D-0154)"
        )
    return 0


def table(songs: list[tuple[str, np.ndarray, float]]) -> int:
    """곡마다 한 줄. **전체 분포가 못 가르는 것을 여기서 본다** (D-0160).

    주기를 반으로 볼 때 또렷해지는 곡이 7 / 20이었다. **과반이 아니므로 절반 오류가
    지배적이지 않은데, 그 일곱은 나아졌다** — 곡마다 사정이 다르다는 뜻이다.
    """
    print(f"\n{'곡':<34}{'BPM':>8}{'격차':>7}{'배수격차':>9}{'집중':>7}{'반주기':>8}  판정")
    for key, envelope, hop in songs:
        beat = beat_period(envelope, hop)
        if beat is None:
            print(f"{key[:32]:<34}{'못 고름':>8}")
            continue
        now = max(phase_profile(envelope, beat.period_seconds, hop))
        half = max(phase_profile(envelope, beat.period_seconds / 2.0, hop))
        mark = "←반으로" if half > now else ("" if now > 1.5 / PHASE_BINS else "고름")
        print(
            f"{key[:32]:<34}{beat.tempo_bpm:>8.1f}{beat.margin:>7.3f}"
            f"{beat.octave_margin:>9.3f}{now:>7.3f}{half:>8.3f}  {mark}"
        )
    print("\n**배수 격차가 낮은 곡이 곧 반으로 볼 곡인지 보면 판정자가 생긴다** (D-0160)")
    return 0


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
    # **저장소 루트 기준으로 푼다** (D-0069 · D-0153). `cd core`에서 돌리므로 현재
    # 디렉터리 기준으로 두면 `core/var/ingest`를 찾는다 — 실제로 그렇게 틀렸다.
    parser.add_argument("--out", type=_resolve, default=ROOT / "var" / "ingest", help="산출물 루트")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한")
    parser.add_argument("--diagnose", type=int, default=None, help="곡 하나를 뜯는다 (0부터)")
    parser.add_argument("--table", action="store_true", help="곡별로 한 줄씩 찍는다")
    args = parser.parse_args()

    picked = folders(args.out)
    if not picked:
        print(f"{args.out.resolve()}에 포락선 폴더가 없다.", file=sys.stderr)
        print("`ingest onsets`를 먼저 돌리거나 `--out`을 확인한다 (D-0153).", file=sys.stderr)
        return 1
    folder = picked[-1]
    songs = load(folder, args.limit)
    if not songs:
        print(f"{folder}가 비어 있다.", file=sys.stderr)
        return 1

    print(f"{folder} · {len(songs)}곡")
    if args.diagnose is not None:
        return diagnose(songs[args.diagnose])
    if args.table:
        return table(songs)
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

    # **곡마다 박의 원점이 다르다** (D-0143 · D-0158). 그대로 평균 내면 상쇄돼
    # 언제나 균등이 나온다 — 실측 `0.260 · 0.250 · 0.239 · 0.251`이 그것이었다.
    print("\n박 안 위상 집중도 (곡별 최대 칸)")
    tops = [max(profile) for profile in profiles]
    print(f"  {quantiles(tops)}")
    flat = sum(1 for value in tops if value < 1.5 / PHASE_BINS)
    print(f"  고른 곡 {flat} / {len(profiles)} · 균등이면 {1 / PHASE_BINS:.3f}")

    # **절반 템포인가.** 박을 절반으로 잡으면 진짜 박 둘이 한 박에 들어가 0번과
    # 2번 칸이 함께 솟는다 — 실측 모양이 그랬다. 주기를 반으로 보고 다시 재면
    # 갈린다 (D-0159).
    doubled: list[float] = []
    for _, envelope, hop in songs:
        beat = beat_period(envelope, hop)
        if beat is not None:
            doubled.append(max(phase_profile(envelope, beat.period_seconds / 2.0, hop)))
    if doubled:
        print("\n주기를 반으로 보면 (= 빠르기 두 배)")
        print(f"  집중도 {quantiles(doubled)}")
        better = sum(1 for now, half in zip(tops, doubled, strict=False) if half > now)
        print(f"  더 또렷해진 곡 {better} / {len(doubled)}")
        print("  **과반이 또렷해지면 박을 절반으로 잡고 있는 것이다** (D-0159)")

    print("\n가장 센 칸을 맞춰 포갠 모양")
    rolled = [
        tuple(
            profile[(index + profile.index(max(profile))) % PHASE_BINS]
            for index in range(PHASE_BINS)
        )
        for profile in profiles
    ]
    shape = [statistics.mean(profile[index] for profile in rolled) for index in range(PHASE_BINS)]
    print("  " + " · ".join(f"{value:.3f}" for value in shape))
    print("  **원점을 맞춰야 모양이 보인다.** 셋째 칸이 크면 뒤박이 있다는 뜻이다")

    gap = statistics.median(abs(value - 96.0) for value in tempos)
    print(f"\n`--tempo` 기본값 96과의 차이\n  중앙 {gap:.1f}BPM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
