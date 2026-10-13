#!/usr/bin/env python3
"""코퍼스 템포 전수 — **`--emit`이 실측 정본의 `[onset.counts]`를 다시 쓴다** (D-0397).

    cd core && uv run python ../tools/probe_tempo.py           # 수를 찍는다
    cd core && uv run python ../tools/probe_tempo.py --emit    # 정본을 갈아 넣는다
    cd core && uv run python ../tools/probe_tempo.py --split   # 반쪽 나누기 (O-77)
    make measure                                               # 셋 다 + 거울

**맨 `python3`으로는 안 돈다** — `numpy`와 `hathor`가 프로젝트 묶음에 있다 (D-0367).

### 왜 이 도구가 생겼나

기본 템포 126은 **D-0206이 손으로 옮긴 수**였고, 같은 측정 하나를 두고 수가 네 곳에서
달랐다 (D-0397):

| 어디 | 전수 | 못 읽은 곡 | 접은 중앙 |
|---|---|---|---|
| 실측 (2026-10-12 · 홉 0.01) | 1004 | **0** | **130** |
| D-0206 기록 | 1004 | 1 | 126 |
| `DEFAULT_TEMPO_BPM` 독스트링 | **1003** · 「200곡 중 없음」 | 0 | 126 |

옮겨 적은 수는 낡는다 (GR-0.7). 이제 **도구가 세고 상수가 정본과 대조된다.**

### 접는 법을 두 벌로 안 만든다

`from_envelopes`가 **생성 경로가 쓰는 바로 그 함수**다 (D-0392). 여기서 다시 접으면
엔진이 접는 법을 바꿀 때 정본이 조용히 낡는다 (D-0117) — 그래서 판정에서 `folded`를
받아 사분위만 여기서 낸다.

### 자에 홉이 들어간다

같은 코퍼스가 홉 0.01에서 130, D-0206의 측정에서 126이었다. **홉은 자의 일부다**
(D-0145) — `RULER`에 적고, 다른 홉 폴더가 최신이 되면 `measured --check`가
*«세는 법이 바뀌었고 다시 안 쟀다»*로 운다 (D-0374).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

import measured  # noqa: E402 — sys.path 조작 뒤라야 한다

from hathor.application.corpus_rhythm import (  # noqa: E402
    peaked,
    phase_spread,
    split_half,
    spread,
)
from hathor.application.reference_tempo import from_envelopes  # noqa: E402
from hathor.infrastructure.onset_store import SUFFIX, find_envelope_root  # noqa: E402

SECTION = "onset"
"""갈아 넣을 정본 블록."""

RULER = "2026-10-12 · 홉 0.01 · 곡마다 접고 중앙 · 박/마디 4등분 (D-0401)"
"""`[onset.counts]`를 낸 자의 이름 (D-0374). **홉과 접는 법이 둘 다 자다.**"""

EMITS = (
    "beat_read",
    "beat_missing",
    "bpm_raw_median",
    "bpm_folded_median",
    "bpm_folded_q1",
    "bpm_folded_q3",
    "phase_bar_q1_permille",
    "phase_bar_top_permille",
    "phase_bar_q3_permille",
    "phase_bar_max_permille",
    "phase_beat_q1_permille",
    "phase_beat_top_permille",
    "phase_beat_q3_permille",
    "phase_beat_max_permille",
    "phase_flat",
)
"""`[onset.counts]`에 넣는 수. **전부 정수다** — 곡명·경로·곡별 행은 안 나간다 (D-0366).

**한 벌로 적는다** (D-0401). 처음에 `(*PHASE, …)`로 펼쳤더니 `measured.emitted()`가 이
묶음을 **글자로 읽어** 따옴표 안의 이름만 세므로 **아홉이 안 보였다** — 상류 검사가
*«아무도 안 센다»*로 울었다. 도구를 임포트하면 `numpy`가 딸려 와 관문에 못 넣는다
(D-0256), 그래서 **읽는 쪽이 글자인 한 선언도 글자여야 한다.**

비율은 **천분율 정수**다 — 정본은 정수만 들고 거울이 `28.9%`로 찍는다 (D-0043)."""

PHASE = tuple(one for one in EMITS if one.startswith("phase_"))
"""발음 집중도 — **O-46의 비교선** (D-0399 → D-0401). **`EMITS`에서 끌어낸다** — 두
벌로 적으면 어긋난다 (D-0043).

**마디 읽기와 박 읽기를 둘 다 든다.** D-0206의 28.2%가 어느 쪽이었는지 실측이 갈랐다:
마디 **28.9%** · 박 38.6%. **기록의 말이 옳았고 내 추정이 틀렸다** (D-0401)."""


SPLIT = (
    "split_read",
    "split_same_mid_permille",
    "split_other_mid_permille",
    "split_turned_mid_permille",
    "split_peaked_read",
    "split_peaked_same_q1_permille",
    "split_peaked_same_mid_permille",
    "split_peaked_same_q3_permille",
    "split_peaked_self_q1_permille",
    "split_peaked_self_mid_permille",
    "split_peaked_self_q3_permille",
    "split_peaked_mean_q1_permille",
    "split_peaked_mean_mid_permille",
    "split_peaked_mean_q3_permille",
    "split_peaked_turned_q1_permille",
    "split_peaked_turned_mid_permille",
    "split_peaked_turned_q3_permille",
    "split_peaked_wins_permille",
    "split_peaked_gain_q1_permille",
    "split_peaked_gain_mid_permille",
    "split_peaked_gain_q3_permille",
)
"""반쪽 나누기가 내는 수 — **아직 정본에 없다** (O-77 · D-0406 ~ D-0408).

`EMITS`와 **일부러 갈라 둔다.** 정본에 키를 넣으면 `measured --check`가 그 수를
찾는데, 그 수는 **그의 기기에서만 나온다** (D-0015). D-0399가 같은 자리에서
차례를 둘로 나눴다 — 먼저 찍고, 수를 받아서 정본을 짓는다 (D-0401이 그 둘째였다).

거리는 **총변동거리**라 0~1이고, 천분율 정수로 적으면 거울이 `49.7%`로 찍는다.

**판정은 `peaked_wins`와 `peaked_gain`이다** (D-0409) — 곡마다 짝지어 견준
*«관례 빼기 참조»*이고, 승률 500이면 동전 던지기다. `peaked_mean` ↔ `peaked_self`의
중앙값 차는 **짝을 안 지은 수**라 참고로만 든다 — *«참조곡이 관례를 이기나»*.
나머지는 그 판정이 무엇을 걷어냈는지 보이려고 함께 든다: 원점(D-0407이 123천분율로
쟀다) · 봉우리 없는 곡 · 무작위 한 곡이라는 틀린 귀무(D-0408)."""


def parted(loaded: list[tuple[np.ndarray, float]]) -> dict[str, int]:
    """반쪽 나누기 전수 (O-77 · D-0406 ~ D-0408).

    **예측자 셋을 같은 자로 잰다** — 제 앞 절반(참조곡의 천장) · 코퍼스 평균(관례) ·
    다른 곡 하나. 셋 다 돌려서 재므로 **원점 차이가 안 섞인다.**

    고른 곡은 뺀다 — 베낄 리듬이 없다 (`peaked` · D-0401의 45.9%).
    사분위는 `corpus_rhythm.spread` **한 자**가 낸다 (D-0043).
    """
    whole = split_half(loaded)
    only = split_half(peaked(loaded))
    found = {"split_read": whole.read, "split_peaked_read": only.read}
    for name, values in (
        ("same", whole.same),
        ("other", whole.other),
        ("turned", whole.turned),
    ):
        found[f"split_{name}_mid_permille"] = round(spread(values)[1] * 1000)
    found["split_peaked_wins_permille"] = round(only.wins / only.read * 1000)
    for name, values in (
        ("gain", only.gain),
        ("same", only.same),
        ("self", only.turned_self),
        ("mean", only.turned_mean),
        ("turned", only.turned),
    ):
        low, mid, high, _top = spread(values)
        found[f"split_peaked_{name}_q1_permille"] = round(low * 1000)
        found[f"split_peaked_{name}_mid_permille"] = round(mid * 1000)
        found[f"split_peaked_{name}_q3_permille"] = round(high * 1000)
    return found


def envelopes(folder: Path) -> list[tuple[np.ndarray, float]]:
    """그 폴더의 포락선 전부. **곡 이름은 안 들고 나온다** (D-0015 · D-0134)."""
    found: list[tuple[np.ndarray, float]] = []
    for path in sorted(folder.glob("*.npz")):
        with np.load(path, allow_pickle=False) as bundle:
            found.append(
                (
                    np.asarray(bundle["envelope"], dtype=np.float64),
                    float(bundle["hop_seconds"]),
                )
            )
    return found


def explored(loaded: list[tuple[np.ndarray, float]]) -> dict[str, int]:
    """발음 집중도 — **O-46의 비교선** (D-0399 · D-0401).

    **두 번 걷는다.** 한 번에 하려면 템포 판정이 위상까지 들고 와야 하고, 그러면
    **생성 경로가 쓰는 함수**(`from_envelopes`)가 코퍼스 집계 꼴로 비틀린다. 1004곡에
    자가상관을 두 번 돌리는 값이고, 이 도구는 `make measure`에서만 돈다.
    """
    phase = phase_spread(loaded)
    found: dict[str, int] = {"phase_flat": phase.flat}
    for name, values in (("bar", phase.bar_top), ("beat", phase.beat_top)):
        low, mid, high, top = phase.spread(values)
        found[f"phase_{name}_q1_permille"] = round(low * 1000)
        found[f"phase_{name}_top_permille"] = round(mid * 1000)
        found[f"phase_{name}_q3_permille"] = round(high * 1000)
        found[f"phase_{name}_max_permille"] = round(top * 1000)
    return found


def counted(folder: Path) -> dict[str, int]:
    """그 폴더에서 낸 정본의 수. **못 읽은 곡도 수로 든다** (GR-0.5)."""
    loaded = envelopes(folder)
    verdict = from_envelopes(loaded)
    if verdict.bpm is None or verdict.raw_median is None:
        raise LookupError(f"{folder.name}에서 박을 하나도 못 읽었다 — 낼 수가 없다")
    cut = statistics.quantiles(sorted(verdict.folded), n=4)
    return {
        "beat_read": verdict.read,
        "beat_missing": verdict.asked - verdict.read,
        "bpm_raw_median": round(verdict.raw_median),
        "bpm_folded_median": verdict.bpm,
        "bpm_folded_q1": round(cut[0]),
        "bpm_folded_q3": round(cut[2]),
        **explored(loaded),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="코퍼스 템포 전수 (D-0397)")
    parser.add_argument("--emit", action="store_true", help="실측 정본의 counts를 다시 쓴다")
    parser.add_argument("--out", type=Path, default=None, help="포락선 폴더를 직접 준다")
    parser.add_argument("--split", action="store_true", help="반쪽 나누기로 O-77을 잰다")
    args = parser.parse_args()

    folder = args.out or find_envelope_root(ROOT)
    if folder is None or not folder.is_dir():
        print(
            f"포락선 폴더가 없다 (`var/ingest/keys-*{SUFFIX}`). "
            "`ingest onsets`를 먼저 돌린다 (D-0153)",
            file=sys.stderr,
        )
        return 2
    if args.split:
        try:
            parts = parted(envelopes(folder))
        except LookupError as error:
            print(f"{error}", file=sys.stderr)
            return 2
        print(f"{folder.name} · 반쪽을 낸 곡 {parts['split_read']}개")
        for key in SPLIT:
            print(f"  {key:<26} {parts[key]}")
        raw = parts["split_other_mid_permille"] - parts["split_same_mid_permille"]
        turn = parts["split_turned_mid_permille"] - parts["split_same_mid_permille"]
        apart = parts["split_peaked_turned_mid_permille"] - parts["split_peaked_self_mid_permille"]
        beats = parts["split_peaked_gain_mid_permille"]
        wins = parts["split_peaked_wins_permille"]
        print(f"\n  곡마다 다른가 · 안 돌림     {raw} 천분율  (원점 차이가 섞여 있다)")
        print(f"  곡마다 다른가 · 돌림       {turn} 천분율")
        print(f"  곡마다 다른가 · 봉우리만    {apart} 천분율  (귀무가 **다른 곡 하나**다)")
        print(f"\n  참조가 이긴 곡           {wins} 천분율  ← **500이면 동전 던지기다**")
        print(f"  관례 - 참조 · 차의 중앙    {beats} 천분율  ← **판정은 이 둘이다**")
        print("**0에 가까우면 코퍼스 평균이 참조곡만큼 좋다** — 쪼갬을 관례로 둔다 (O-77)")
        return 0

    try:
        counts = counted(folder)
    except LookupError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    print(f"{folder.name} · 곡 {counts['beat_read'] + counts['beat_missing']}개")
    for key in EMITS:
        mark = "  (천분율)" if key.endswith("_permille") else ""
        print(f"  {key:<26} {counts[key]}{mark}")

    if not args.emit:
        print("\n정본에 넣으려면 `--emit`. **자의 이름이 바뀌면 거울도 다시 찍는다** (D-0374)")
        return 0

    changed = measured.emit(SECTION, counts)
    print(f"\n정본 갱신 · 바뀐 수 {len(changed)}개")
    for line in changed:
        print(f"  {line}")
    print("거울은 `make docs-fix`가 찍는다 (D-0288 — 관문은 문서를 안 고친다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
