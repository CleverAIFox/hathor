#!/usr/bin/env python3
"""화성 리듬 탐침 — 곡별 **반감점**을 잰다 (O-37 · D-0104).

### 무엇을 재는가

크로마 시계열을 `k`창씩 묶으면 뾰족함이 떨어진다. **참 화음 길이를 넘는 순간
급락한다** — D-0104가 창 길이 기준 (3)을 기각하다가 관측한 것이고, 그 꺾임점이
곡마다 다르다(발라드와 댄스곡). **그것이 화성 리듬이다.**

`반감점`은 뾰족함이 `k=1` 값에서 가장 긴 묶음 값까지 **절반 내려오는 지점**이다.
로그 격자에서 보간하므로 **연속값이다** — 격자 위 정수로 뭉치지 않는다.

### 왜 자기 전이율이 아닌가

`argmax` 열의 자기 전이율이 더 싸지만 **창 길이가 그 값을 정한다.** D-0103이
대각선을 버린 근거가 통째로 그것이다. 1초 창을 0.5초로 다시 뽑으면 전부 오른다.
반감점은 초 단위이고 **곡의 성질이지 격자의 성질이 아니다.**

자기 전이율은 함께 찍되 **판정에 쓰지 않는다** — D-0083의 순위상관과 같은 지위다.

### 이 탐침이 답하는 것은 하나다

**반감점이 시간 순서에서 오는가.**

퍼지는 것만으로는 아무것도 안 나온다 — 곡마다 잡음 수준이 다르기만 해도 퍼진다.
**귀무선은 곡 안에서 창 순서를 뒤섞은 것이다.** 크로마 분포는 그대로고 시간 구조만
죽으므로, 묶음 평균이 곡 전체 평균으로 바로 가 반감점이 1 근처로 내려앉아야 한다.
**실측이 그보다 크면 그 초과분이 화음 지속이다.**

판정은 곡 단위 짝지은 차이다 (D-0113). **곡마다 실측과 뒤섞음을 같은 곡에서 잰다.**

### 서로 다른 값 세기는 판정이 아니다

첫 판에서 `서로 다른 값 45.9%`를 "뭉친다"로 읽었는데 **그 숫자는 반올림 격자가
정한다.** 폭 2.21~7.52초를 0.01로 반올림하면 칸이 531개고, 1002번 뽑으면 생일
충돌로 451개(45.0%)가 기대값이다. **완전 연속 분포와 구분되지 않는다.**

O-25 (4) — 판정 규칙을 적었으면 **귀무 자료에서 먼저 돌려 본다.** 안 돌렸다.

사용법:
    python tools/probe_chord_rhythm.py                 # 저장된 시계열 전부
    python tools/probe_chord_rhythm.py --stem-set mix
    python tools/probe_chord_rhythm.py --self-test     # 합성으로 회수되는지
"""

from __future__ import annotations

import argparse
import math
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEGREE_COUNT = 12

sys.path.insert(0, str(ROOT / "core"))

from hathor.domain.services.chord_rhythm import (
    BUNDLES,
    curve,
    half_fall,
    limit_spikiness,
    measure,
    self_transition_rate,
    shuffled,
)

# ------------------------------------------------------------------ 합성


def synth(chord_windows: int, total: int, noise: float, seed: int) -> np.ndarray:
    """`chord_windows`창마다 화음이 바뀌는 시계열. **회수되는지 보는 용도다.**"""
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    current = rng.integers(0, DEGREE_COUNT)
    for index in range(total):
        if index % chord_windows == 0 and index:
            current = (current + rng.integers(1, DEGREE_COUNT)) % DEGREE_COUNT
        row = np.full(DEGREE_COUNT, noise, dtype=np.float64)
        for offset in (0, 4, 7):  # 장3화음
            row[(current + offset) % DEGREE_COUNT] += 1.0
        rows.append(np.maximum(row + rng.normal(0.0, noise, DEGREE_COUNT), 0.0))
    return np.asarray(rows)


def self_test() -> int:
    """합성에서 **참 화음 길이가 회수되는가.** 아니면 나머지 숫자를 읽지 않는다."""
    print("합성 회수 검사 — 참 화음 길이 대 반감점\n")
    print(f"{'참 길이(창)':>10} {'반감점':>8} {'자기전이':>8}   판정")
    ok = True
    measured: list[tuple[int, float]] = []
    for truth in (2, 4, 8, 16):
        got = []
        for seed in range(8):
            series = synth(truth, 960, noise=0.25, seed=seed)
            value = half_fall(curve(series), limit_spikiness(series))
            if value is not None:
                got.append(value)
        if not got:
            print(f"{truth:>10} {'없음':>8}")
            ok = False
            continue
        median = float(np.median(got))
        rate = self_transition_rate(synth(truth, 480, 0.25, 0))
        # **순서만 본다.** 반감점이 참 길이와 같아야 할 이유는 없고, 참 길이가
        # 길수록 반감점도 길면 그 축을 잰 것이다.
        print(f"{truth:>10} {median:>8.2f} {rate:>8.3f}")
        measured.append((truth, median))
    if len(measured) >= 2:
        truths = [t for t, _ in measured]
        values = [v for _, v in measured]
        rising = all(left < right for left, right in pairwise(values))
        corr = float(np.corrcoef(np.log(truths), np.log(values))[0, 1])
        print(f"\n단조 증가: {'예' if rising else '아니오'} · 로그 상관 {corr:.4f}")
        ok = ok and rising and corr > 0.95
    if not ok:
        print("\n실패 — 지표가 화음 길이를 못 따라간다")
        return 1

    # **귀무 하네스가 질 수 있는가** (O-25 (2)). 화음이 안 이어지는 합성에서
    # 실측이 뒤섞음보다 크면 하네스가 고장이므로 나머지 숫자를 읽지 않는다.
    print("\n\n귀무 대조 — 실측 대 창 순서 뒤섞음\n")
    print(f"{'참 길이(창)':>10} {'실측':>7} {'뒤섞음':>7} {'차이':>8} {'t':>8} {'승률':>7}")
    for truth in (1, 2, 4, 8, 16):
        left, right = [], []
        for seed in range(40):
            series = synth(truth, 960, noise=0.25, seed=seed)
            got, shaken = measure(series), measure(shuffled(series, seed=100 + seed))
            if got is not None and shaken is not None:
                left.append(got)
                right.append(shaken)
        arr_l, arr_r = np.asarray(left), np.asarray(right)
        gap = arr_l - arr_r
        stat = float(gap.mean() / (gap.std(ddof=1) / math.sqrt(gap.size)))
        print(
            f"{truth:>10} {np.median(arr_l):>7.2f} {np.median(arr_r):>7.2f} "
            f"{gap.mean():>+8.2f} {stat:>8.1f} {(arr_l > arr_r).mean():>7.1%}"
        )
        if truth == 1 and stat > 0:
            ok = False

    print(
        "\n통과 — 화음이 안 이어지면 진다"
        if ok
        else "\n실패 — 화음이 안 이어지는데도 이긴다. 하네스가 고장이다"
    )
    return 0 if ok else 1


# ------------------------------------------------------------------ 실측


def load_series(folder: Path, stem_set: str) -> list[tuple[str, np.ndarray]]:
    found: list[tuple[str, np.ndarray]] = []
    for path in sorted(folder.glob(f"*-{stem_set}.npz")):
        with np.load(path, allow_pickle=False) as data:
            found.append((str(data["source_key"]), np.asarray(data["series"], dtype=np.float64)))
    return found


def find_folder(stem_set: str) -> Path | None:
    ingest = ROOT / "var" / "ingest"
    if not ingest.is_dir():
        return None
    for path in sorted(ingest.glob("keys-*.series"), reverse=True):
        if any(path.glob(f"*-{stem_set}.npz")):
            return path
    return None


def report(folder: Path, stem_set: str, window_seconds: float, seed: int) -> int:
    songs = load_series(folder, stem_set)
    if not songs:
        print(f"{folder.name}에 {stem_set} 시계열이 없다", file=sys.stderr)
        return 1

    real: list[float] = []
    null: list[float] = []
    rates: list[float] = []
    missing = 0
    for _, series in songs:
        got = measure(series)
        shaken = measure(shuffled(series, seed))
        if got is None or shaken is None:
            missing += 1
            continue
        real.append(got)
        null.append(shaken)
        rates.append(self_transition_rate(series))

    print(f"{folder.name} · {stem_set} · {len(songs)}곡 · 창 {window_seconds:g}초 · 시드 {seed}\n")
    if len(real) < 2:
        print("반감점이 거의 안 나왔다. 시계열이 너무 짧거나 평평하다")
        return 1

    left = np.asarray(real) * window_seconds
    right = np.asarray(null) * window_seconds
    quantiles = np.quantile(left, [0.05, 0.25, 0.5, 0.75, 0.95])
    print("반감점 (초) — 실측")
    print(
        f"  5% {quantiles[0]:.2f} · 25% {quantiles[1]:.2f} · 중앙 {quantiles[2]:.2f} "
        f"· 75% {quantiles[3]:.2f} · 95% {quantiles[4]:.2f}"
    )
    print(f"  뒤섞음 중앙 {np.median(right):.2f} · 반감점 없음 {missing}곡")

    # **곡 단위 짝지은 차이다** (D-0113). 같은 곡에서 둘을 재므로 곡 고유 잡음이 빠진다.
    gap = left - right
    error = float(gap.std(ddof=1) / math.sqrt(gap.size))
    stat = float(gap.mean() / error) if error > 0 else 0.0
    win = float((left > right).mean())
    ratio = float(np.median(left) / max(float(np.median(right)), 1e-9))

    print(f"\n실측 - 뒤섞음  {gap.mean():+.3f}초 · t {stat:.2f} · 곡승률 {win:.1%}")
    print(f"중앙값 비  {ratio:.2f}배 · 표본 {gap.size}곡")

    # **사전 등록한 판정 규칙이다** (GR-6.5 · D-0112).
    verdict = gap.mean() > 0.0 and stat > 3.0 and win > 0.5
    print(
        "\n판정: "
        + (
            "시간 순서에서 온다 — self/other 하네스로 간다"
            if verdict
            else "순서에서 오지 않는다 — 지표를 다시 고른다"
        )
    )

    spread = float(quantiles[3] - quantiles[1]) / max(float(quantiles[2]), 1e-9)
    print("\n진단 (판정에 쓰지 않는다)")
    print(f"  사분위폭 / 중앙값 {spread:.3f} · 자기 전이율 중앙 {np.median(rates):.3f}")
    print("  뾰족함 곡선 중앙값")
    stacked = [curve(series) for _, series in songs]
    longest = max((len(c) for c in stacked), default=0)
    for index in range(longest):
        column = [c[index][1] for c in stacked if len(c) > index]
        if len(column) < len(songs) * 0.5:
            break
        print(f"    {BUNDLES[index] * window_seconds:>5.1f}초  {np.median(column):.4f}")
    return 0 if verdict else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="화성 리듬 탐침 (O-37 · D-0123)")
    parser.add_argument("--stem-set", default="other", help="기본 other (D-0074)")
    parser.add_argument("--window-seconds", type=float, default=1.0, help="창 길이 (D-0104)")
    parser.add_argument("--self-test", action="store_true", help="합성 회수 검사")
    parser.add_argument("--seed", type=int, default=7, help="뒤섞기 시드")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    folder = find_folder(args.stem_set)
    if folder is None:
        print(
            f"var/ingest에 {args.stem_set} 시계열 폴더가 없다. make artifacts-pull 을 먼저 본다",
            file=sys.stderr,
        )
        return 1
    return report(folder, args.stem_set, args.window_seconds, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
