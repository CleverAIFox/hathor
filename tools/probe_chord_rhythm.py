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

**반감점이 곡마다 갈리는가.** 갈리지 않으면 귀무선도 판정 규칙도 뜻이 없다.
갈린 뒤에야 self/other 하네스(D-0112 · D-0113)를 얹는다.

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

BUNDLES = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64)
"""묶음 길이(창 수). **촘촘한 격자다.**

`1,2,4,8`처럼 성기면 반감점이 네 값 중 하나로 뭉쳐 곡이 안 갈린다. 보간을 쓰더라도
격자가 성기면 보간 오차가 신호보다 커진다.
"""


def spikiness(series: np.ndarray) -> float:
    """창별 크로마의 **뾰족함 평균.** 균등이면 1/12, 한 음이면 1.

    정규화한 크로마의 최댓값이다. 화음이 섞이면 질량이 퍼져 내려간다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    totals = stacked.sum(axis=1, keepdims=True)
    safe = np.where(totals > 0.0, totals, 1.0)
    return float((stacked / safe).max(axis=1).mean())


def bundle(series: np.ndarray, size: int) -> np.ndarray:
    """짧은 창 `size`개를 평균해 `size`배 긴 창으로 (D-0104).

    **크로마는 시간 평균이므로 정확히 `size`배 긴 창이다.** 남는 꼬리는 버린다 —
    길이가 다른 창을 섞으면 뾰족함이 창 길이만으로 달라진다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    usable = len(stacked) // size * size
    if usable < size:
        return stacked[:0]
    return stacked[:usable].reshape(-1, size, stacked.shape[1]).mean(axis=1)


def curve(series: np.ndarray, bundles: tuple[int, ...] = BUNDLES) -> list[tuple[int, float]]:
    """묶음 길이별 뾰족함. 창이 모자라 빈 묶음은 뺀다."""
    points: list[tuple[int, float]] = []
    for size in bundles:
        grouped = bundle(series, size)
        if len(grouped) < 2:
            break
        points.append((size, spikiness(grouped)))
    return points


def limit_spikiness(series: np.ndarray) -> float:
    """`k`를 무한히 늘렸을 때의 뾰족함. **곡 전체를 한 창으로 본 값이다.**

    묶을수록 곡의 평균 크로마로 수렴하므로 이것이 바닥이고, **닫힌 꼴로 구한다.**

    **격자의 마지막 점을 바닥으로 쓰면 안 된다.** 화음이 격자보다 길면 거기서
    아직 안 내려왔고, 그러면 반감점이 눌린다 — 자기 검사에서 16창짜리가 8창보다
    낮게 나왔다. D-0079가 "극한 열이 상한이다"라고 적은 것과 같은 자리다.
    """
    stacked = np.asarray(series, dtype=np.float64)
    if stacked.size == 0:
        return 0.0
    return spikiness(stacked.mean(axis=0, keepdims=True))


def half_fall(points: list[tuple[int, float]], floor: float) -> float | None:
    """뾰족함이 **극한까지 절반 내려오는 묶음 길이.** 로그 격자에서 보간한다.

    바닥은 `limit_spikiness`가 낸 `k → 무한` 값이다. 상수를 박지 않는다 (O-25).

    격자 안에서 반을 안 지나면 `None`이다 — **없는 것을 있는 척하지 않는다** (GR-0.5).
    """
    if len(points) < 3:
        return None
    top = points[0][1]
    if top - floor <= 1e-9:
        return None
    target = floor + (top - floor) / 2.0

    for (left_k, left_v), (right_k, right_v) in pairwise(points):
        if left_v >= target > right_v:
            if left_v - right_v <= 1e-12:
                return float(left_k)
            share = (left_v - target) / (left_v - right_v)
            span = math.log(right_k) - math.log(left_k)
            return float(math.exp(math.log(left_k) + share * span))
    return None


def self_transition_rate(series: np.ndarray) -> float:
    """`argmax` 열이 이어지는 비율. **진단이다. 판정에 쓰지 않는다** (D-0083 계열)."""
    stacked = np.asarray(series, dtype=np.float64)
    if len(stacked) < 2:
        return 0.0
    picked = np.argmax(stacked, axis=1)
    return float((picked[:-1] == picked[1:]).mean())


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
    print("\n통과" if ok else "\n실패 — 지표가 화음 길이를 못 따라간다")
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


def report(folder: Path, stem_set: str, window_seconds: float) -> int:
    songs = load_series(folder, stem_set)
    if not songs:
        print(f"{folder.name}에 {stem_set} 시계열이 없다", file=sys.stderr)
        return 1

    values: list[float] = []
    rates: list[float] = []
    missing = 0
    for _, series in songs:
        value = half_fall(curve(series), limit_spikiness(series))
        if value is None:
            missing += 1
            continue
        values.append(value)
        rates.append(self_transition_rate(series))

    print(f"{folder.name} · {stem_set} · {len(songs)}곡 · 창 {window_seconds:g}초\n")
    if not values:
        print("반감점이 하나도 안 나왔다. 시계열이 너무 짧거나 평평하다")
        return 1

    array = np.asarray(values) * window_seconds
    quantiles = np.quantile(array, [0.05, 0.25, 0.5, 0.75, 0.95])
    print("반감점 (초)")
    print(
        f"  5% {quantiles[0]:.2f} · 25% {quantiles[1]:.2f} · 중앙 {quantiles[2]:.2f} "
        f"· 75% {quantiles[3]:.2f} · 95% {quantiles[4]:.2f}"
    )
    print(
        f"  평균 {array.mean():.2f} · 표준편차 {array.std(ddof=1):.2f} "
        f"· 사분위폭 {quantiles[3] - quantiles[1]:.2f}"
    )
    print(f"  반감점 없음 {missing}곡")

    # **이것이 이 탐침의 판정이다.** 서로 다른 값이 몇 개인지 본다 —
    # 격자 위 정수로 뭉치면 곡이 안 갈리고, 그러면 O-37은 다른 지표가 필요하다.
    distinct = len(np.unique(np.round(array, 2)))
    print(f"\n서로 다른 값 {distinct}개 / {len(array)}곡 ({distinct / len(array):.1%})")
    spread = float(quantiles[3] - quantiles[1]) / max(float(quantiles[2]), 1e-9)
    print(f"사분위폭 / 중앙값 = {spread:.3f}")
    verdict = distinct >= len(array) * 0.5 and spread >= 0.2
    print(
        "\n판정: "
        + ("갈린다 — self/other 하네스로 간다" if verdict else "안 갈린다 — 지표를 다시 고른다")
    )

    print(f"\n진단 (판정에 쓰지 않는다) 자기 전이율 중앙 {np.median(rates):.3f}")
    print("뾰족함 곡선 — 중앙값")
    stacked = [curve(series) for _, series in songs]
    longest = max((len(c) for c in stacked), default=0)
    for index in range(longest):
        column = [c[index][1] for c in stacked if len(c) > index]
        if len(column) < len(songs) * 0.5:
            break
        print(
            f"  {BUNDLES[index] * window_seconds:>5.1f}초  {np.median(column):.4f}"
            f"  ({len(column)}곡)"
        )
    return 0 if verdict else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="화성 리듬 탐침 (O-37)")
    parser.add_argument("--stem-set", default="other", help="기본 other (D-0074)")
    parser.add_argument("--window-seconds", type=float, default=1.0, help="창 길이 (D-0104)")
    parser.add_argument("--self-test", action="store_true", help="합성 회수 검사")
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
    return report(folder, args.stem_set, args.window_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
