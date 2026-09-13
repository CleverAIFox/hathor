"""가락 (D-0141).

### 무엇이 없었나

D-0140이 처음 듣고 *"그냥 반주다"*로 판정했다. **전경이 통째로 없었다.**

### 어디서 가져오는가 — 새로 만들지 않는다

가락은 손잡이가 사방에 있는 자리다 — 리듬 · 도약 폭 · 프레이즈 길이 · 어느 화음음을
짚을지. **하나라도 실험으로 고르면 D-0058이다.**

그래서 **이미 있는 것만 쓴다.**

| 무엇 | 어디서 | 새 값인가 |
|---|---|---|
| 발음 자리 | **박 격자** (`TICKS_PER_BEAT`) | 아니다. 마디가 4박인 것은 이미 상수다 |
| 고를 음 | 그 마디 **화음의 구성음** | 아니다. 화음이 이미 정했다 |
| 가중치 | 참조곡 **전이 행렬** · 없으면 **도수 사전** | 아니다. `generate_harmony`가 쓴다 |
| 옥타브 | 화음 **위** | 베이스가 아래인 것과 같은 근거다 (D-0139) |

**화음은 마디 격자를 쓰고 가락은 박 격자를 쓴다.** 둘 다 이미 있는 격자이며 새로
정한 눈금이 아니다.

### 도약을 막지 않는다

*"도약이 크면 버린다"*가 곧아 보이지만 **문턱이 생긴다** — 몇 반음부터 큰가.
D-0137이 병행 5도에서 내린 판단과 같다. **도약 폭은 고르는 값이 아니라 재는 값이고**,
귀가 거슬린다고 하면 그때 근거가 생긴다 (O-45).

### 왜 전이 행렬인가

도수 사전만 쓰면 매 박이 서로 독립이라 **가락이 아니라 점의 나열**이 된다. 전이
행렬은 *직전에 무엇이 왔는가*를 담고 있고 그것이 곡의 움직임이다. **O-32(D-0113)가 화음
배열에서 쓴 것을 가락에서 다시 쓴다** — 새 자료가 아니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from hathor.domain.services.midi_writer import (
    DEGREE_INDEX,
    MAJOR_SCALE,
    MINOR_SCALE,
    TICKS_PER_BEAT,
)
from hathor.domain.value_objects.key import Key, Mode

OCTAVE = 12
TRIAD_STEPS = (0, 2, 4)
"""3화음은 음계에서 한 칸 건너뛰기 셋이다. `chord_pitches`와 같은 규칙이다."""


def chord_positions(degree: str) -> tuple[int, ...]:
    """화음 구성음의 **음계 자리**. 음높이가 아니라 자리다."""
    index = DEGREE_INDEX.get(degree.lower())
    if index is None:
        raise ValueError(f"알 수 없는 도수: {degree}")
    return tuple((index + step) % 7 for step in TRIAD_STEPS)


def _weights(
    positions: Sequence[int],
    before: int | None,
    prior: Sequence[float] | None,
    transition: Sequence[Sequence[float]] | None,
) -> tuple[float, ...]:
    """구성음 각각의 가중치. **없으면 균등이다** — 지어내지 않는다 (GR-0.5)."""
    if transition is not None and before is not None:
        row = np.asarray(transition[before % len(transition)], dtype=np.float64)
        picked = np.maximum([row[position % len(row)] for position in positions], 0.0)
    elif prior is not None:
        vector = np.asarray(prior, dtype=np.float64)
        picked = np.maximum([vector[position % len(vector)] for position in positions], 0.0)
    else:
        picked = np.ones(len(positions), dtype=np.float64)
    total = float(picked.sum())
    if total <= 0.0:
        return tuple(1.0 / len(positions) for _ in positions)
    return tuple(float(value) for value in picked / total)


def _place(position: int, key: Key, floor: int) -> int:
    """음계 자리를 `floor` 이상의 가장 낮은 음높이로 놓는다."""
    scale = MAJOR_SCALE if key.mode is Mode.MAJOR else MINOR_SCALE
    pitch_class = (key.tonic_pitch_class + scale[position]) % OCTAVE
    return floor + (pitch_class - floor) % OCTAVE


def sing(
    seed: int,
    spans: Sequence[tuple[str, int]],
    key: Key,
    *,
    ceiling: int,
    beats_per_bar: int,
    prior: Sequence[float] | None = None,
    transition: Sequence[Sequence[float]] | None = None,
) -> list[tuple[int, int, int]]:
    """`(시작 틱, 길이 틱, 음높이)` 목록. **시드가 같으면 같다.**

    `spans`는 `(도수, 마디 수)`이며 `arrange`가 이어 붙인 화음 그대로다. 가락은
    **화음이 끄는 동안에도 박마다 움직인다** — 그것이 전경과 배경의 차이다.
    """
    if beats_per_bar < 1:
        raise ValueError("마디당 박은 1 이상이어야 한다")

    rng = np.random.default_rng(seed)
    found: list[tuple[int, int, int]] = []
    before: int | None = None
    beat = 0
    for degree, repeats in spans:
        positions = chord_positions(degree)
        for _ in range(repeats * beats_per_bar):
            weights = _weights(positions, before, prior, transition)
            position = int(rng.choice(len(positions), p=weights))
            before = positions[position]
            found.append((beat * TICKS_PER_BEAT, TICKS_PER_BEAT, _place(before, key, ceiling)))
            beat += 1
    return found
