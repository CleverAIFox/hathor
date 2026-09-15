"""배음 감산 강도를 **선법으로 나눠** 훑는다 (O-57 · D-0197).

### 왜 나눠야 하나

D-0059가 배음 감산을 **전체 기준으로** 기각했다. 코퍼스가 장조 745 · 단조 259라
**전체 지표는 장조가 든다** — 단조에서 무슨 일이 나든 4분의 1 무게로 희석된다.

D-0191이 `--harmonic 0.3`에서 단조 애매가 36.7% → 30.8%로 내려가는 것을 봤고,
전체 무작위 바닥 32.5%와 대어 *"바닥 아래로 내려갔다"*고 읽었다. **그 읽기가
틀렸다.**

### 셋을 함께 내지 않으면 못 읽는다

| 내는 것 | 없으면 |
|---|---|
| **선법별 무작위 바닥** | 전체 바닥(32.2%)을 단조(29.4%)에 대게 된다 |
| **선법 구성비** | 분모가 강도마다 달라지는 것을 못 본다 |
| **고정 집합** | 강도끼리 **다른 곡 집합**을 비교하게 된다 |

셋째가 가장 조용하다. 강도를 올리면 **경계에 있던 곡이 선법을 갈아탄다.**
귀무 자료에서 0.0 → 0.3에 장→단 114곡 · 단→장 39곡이 움직였고, **넘어온 곡의
93.9%가 애매했다.** 갈아탄 곡은 원래 애매한 곡이므로 선법별 애매율은 **실력이
아니라 이동으로도 움직인다.**

그래서 **선법이 전 강도에서 한 번도 안 바뀐 곡**만 따로 낸다. 그 집합에서는
분모가 고정이므로 강도끼리 비교가 성립한다. O-25 (1)이 요구하는 *"무엇과
비교할지"*의 답이며, 그 비교선은 **질 수 있다** — O-25 (2).

### 왜 강도마다 따로 돌리지 않는가

`--harmonic`을 강도마다 손으로 돌리면 위 셋 중 **하나도 안 나온다.** 바닥은
전체만 나오고, 구성비는 표에 남지 않으며, 고정 집합은 강도 전부를 한 번에
쥐고 있어야 정의된다. **한 번에 도는 표가 아니면 잴 수 없는 양이다.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.key_estimation import (
    KEY_MARGIN_FLOOR,
    PROFILE_KRUMHANSL,
    KeyEstimate,
    estimate_key,
    random_baseline_by_mode,
    relative_key,
    subtract_harmonics,
)
from hathor.domain.value_objects.key import Mode

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_STRENGTHS: tuple[float, ...] = (0.0, 0.3, 0.5, 0.7, 1.0)
"""훑는 강도. D-0060이 고른 다섯을 그대로 쓴다."""


@dataclass(frozen=True)
class ModeCell:
    """한 강도 · 한 선법의 실측."""

    mode: Mode
    count: int
    share: float
    ambiguous: float
    floor: float
    """같은 강도 · 같은 선법의 무작위 애매율. **전체 바닥이 아니다.**"""
    relative_in_ambiguous: float
    stable_count: int
    stable_ambiguous: float
    """선법이 전 강도에서 안 바뀐 곡만 본 애매율. **분모가 고정이다.**"""

    @property
    def excess(self) -> float:
        """바닥 대비 초과(%p). **양수면 무작위보다 나쁘다.**"""
        return (self.ambiguous - self.floor) * 100


@dataclass(frozen=True)
class SweepRow:
    strength: float
    cells: tuple[ModeCell, ...]
    moved: int
    """강도 0에서 선법이 바뀐 곡 수."""

    def cell(self, mode: Mode) -> ModeCell:
        for item in self.cells:
            if item.mode is mode:
                return item
        raise KeyError(mode)


@dataclass(frozen=True)
class ModeSweep:
    rows: tuple[SweepRow, ...]
    song_count: int
    stable_count: int
    profile: str

    @property
    def stable_share(self) -> float:
        return self.stable_count / self.song_count if self.song_count else 0.0


def sweep_harmonic_modes(
    chromas: Sequence[Sequence[float]],
    *,
    profile: str = PROFILE_KRUMHANSL,
    strengths: tuple[float, ...] = DEFAULT_STRENGTHS,
) -> ModeSweep:
    """강도마다 조성을 다시 추정해 선법으로 나눈 표를 낸다.

    **크로마만 읽으므로 음원도 GPU도 필요 없다** — `--replay`가 싼 이유다.
    """
    if not strengths:
        raise ValueError("강도를 하나 이상 준다")

    # **못 쓰는 곡을 `None`으로 끼워 두지 않는다.** 자리 표시자가 들어가면 이후
    # 모든 읽기가 `None` 검사를 달고 다니고, 그 검사 하나를 빠뜨리면 조용히 센다.
    layers: list[dict[int, KeyEstimate]] = []
    for strength in strengths:
        layer: dict[int, KeyEstimate] = {}
        for index, item in enumerate(chromas):
            vector = subtract_harmonics(np.asarray(item, dtype=np.float64), strength)
            total = float(vector.sum())
            if total <= 0:
                continue
            layer[index] = estimate_key(
                np.asarray(vector / total, dtype=np.float32), profile=profile
            )
        layers.append(layer)

    usable = sorted(set.intersection(*(set(layer) for layer in layers)))
    # **선법이 한 번도 안 바뀐 곡만 고정 집합이다.** 갈아탄 곡은 강도끼리
    # 분모를 흔들어 비교를 깬다.
    stable = {index for index in usable if len({layer[index].key.mode for layer in layers}) == 1}

    first = layers[0]
    rows: list[SweepRow] = []
    for strength, layer in zip(strengths, layers, strict=True):
        floors = random_baseline_by_mode(profile=profile, harmonic=strength)
        picked = [layer[index] for index in usable]
        cells: list[ModeCell] = []
        for mode in (Mode.MAJOR, Mode.MINOR):
            members = [item for item in picked if item.key.mode is mode]
            ambiguous = [item for item in members if item.margin < KEY_MARGIN_FLOOR]
            held = [layer[index] for index in sorted(stable) if layer[index].key.mode is mode]
            held_ambiguous = sum(1 for item in held if item.margin < KEY_MARGIN_FLOOR)
            cells.append(
                ModeCell(
                    mode=mode,
                    count=len(members),
                    share=len(members) / len(picked) if picked else 0.0,
                    ambiguous=len(ambiguous) / len(members) if members else 0.0,
                    floor=floors[mode][1],
                    relative_in_ambiguous=(
                        sum(1 for item in ambiguous if relative_key(item.key) == item.runner_up)
                        / len(ambiguous)
                        if ambiguous
                        else 0.0
                    ),
                    stable_count=len(held),
                    stable_ambiguous=held_ambiguous / len(held) if held else 0.0,
                )
            )
        moved = sum(1 for index in usable if layer[index].key.mode is not first[index].key.mode)
        rows.append(SweepRow(strength=strength, cells=tuple(cells), moved=moved))

    return ModeSweep(
        rows=tuple(rows),
        song_count=len(usable),
        stable_count=len(stable),
        profile=profile,
    )
