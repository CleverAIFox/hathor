#!/usr/bin/env python3
"""코퍼스 템포 전수 — **`--emit`이 실측 정본의 `[onset.counts]`를 다시 쓴다** (D-0397).

    cd core && uv run python ../tools/probe_tempo.py           # 수를 찍는다
    cd core && uv run python ../tools/probe_tempo.py --emit    # 정본을 갈아 넣는다
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

from hathor.application.reference_tempo import from_envelopes  # noqa: E402
from hathor.infrastructure.onset_store import SUFFIX, find_envelope_root  # noqa: E402

SECTION = "onset"
"""갈아 넣을 정본 블록."""

RULER = "2026-10-12 · 홉 0.01 · 곡마다 접고 중앙 (D-0392)"
"""`[onset.counts]`를 낸 자의 이름 (D-0374). **홉과 접는 법이 둘 다 자다.**"""

EMITS = (
    "beat_read",
    "beat_missing",
    "bpm_raw_median",
    "bpm_folded_median",
    "bpm_folded_q1",
    "bpm_folded_q3",
)
"""`[onset.counts]`에 넣는 수. **전부 정수다** — 곡명·경로·곡별 행은 안 나간다 (D-0366)."""


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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="코퍼스 템포 전수 (D-0397)")
    parser.add_argument("--emit", action="store_true", help="실측 정본의 counts를 다시 쓴다")
    parser.add_argument("--out", type=Path, default=None, help="포락선 폴더를 직접 준다")
    args = parser.parse_args()

    folder = args.out or find_envelope_root(ROOT)
    if folder is None or not folder.is_dir():
        print(
            f"포락선 폴더가 없다 (`var/ingest/keys-*{SUFFIX}`). "
            "`ingest onsets`를 먼저 돌린다 (D-0153)",
            file=sys.stderr,
        )
        return 2
    try:
        counts = counted(folder)
    except LookupError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    print(f"{folder.name} · 곡 {counts['beat_read'] + counts['beat_missing']}개")
    for key in EMITS:
        print(f"  {key:<18} {counts[key]}")

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
