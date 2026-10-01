"""**어휘를 넓히면 새 정보가 오는가** — 날퍼짐이 아니라 잔차를 본다 (O-73 · D-0333).

### 왜 이 파일이 있나

D-0095가 `cell_spread`(곡 간 로그 표준편차)를 만들며 *"두 표준편차가 비슷하면 어휘를
넓혀도 이득이 없다"*고 적었다. **역이 안 선다** (D-0327).

| | 차용 칸 퍼짐 | 대조 칸 퍼짐 | 어휘 이득 |
|---|---|---|---|
| 합성 양성 | 0.8730 | 0.5837 | **+0.0666** (t +5.16) |
| **실물 1004곡** | **0.7788** | **0.5642** | **+0.0011** (t +0.20) |

**퍼짐 차이가 같은 크기인데 이득이 60배 다르다.** 날퍼짐은 필요조건이지 충분조건이
아니다.

### 묻는 것은 «`base`가 이미 아는가»다

`mixture`와 `control`은 둘 다 **`base` 6도수 위에** 세 칸을 얹는다. 그러니 물어야 할 것은
*"차용 칸이 흔들리는가"*가 아니라 **"그 흔들림이 `base`가 이미 담은 것과 겹치는가"**다.

차용 칸의 곡 간 변동을 **온음계 6칸으로 회귀하고 남는 잔차의 퍼짐**을 잰다. 대조 칸도
같은 자로 재서 견준다 — **회귀 대상이 `base`의 칸이어야 하는 이유가 이것이다.**

### 잔차가 이득을 예측한다 — 눈금 세 점 (O-25 (4)·(6))

1000곡 5회씩. **마지막 줄이 이 자의 값이다.**

| 코퍼스 | 날퍼짐 | 잔차 | 차이 | 어휘 이득 |
|---|---|---|---|---|
| 음성 — 안 흔들린다 | 0.5616 / 0.5609 | 0.5440 / 0.5430 | **+0.001** | -0.0035 (t -0.34) |
| 양성 — 고유 변동 | 0.8770 / 0.5862 | 0.8443 / 0.5854 | **+0.259** | **+0.0609** (t +5.30) |
| 이웃 비례 — `base`가 안다 | 0.5398 / 0.5742 | **0.1478** / 0.5305 | **-0.383** | +0.0036 |

(왼쪽이 차용 칸, 오른쪽이 대조 칸이다.)

셋째 줄에서 차용 칸 날퍼짐의 **73%가 온음계로 설명되고 0.1478만 남으며, 이득은 0이다.**
**날퍼짐으로는 그 줄과 음성 줄이 안 갈린다** (0.5398 대 0.5616) — 흔들리는데 `base`가
아는 경우를 «안 흔들린다»로 읽는다. 잔차는 가른다.

**「따라간다」를 공통 인자로 만들면 안 된다.** 12칸 중 9칸을 같이 올리면 합도 같이 올라
정규화에서 상쇄되고 설명된 몫이 4.3%에 그쳤다. 누설이라면 **이웃 온음계 칸에 비례**하고,
그 비례만이 로그 비율에 남는다.

**실물은 이 셋 중 어느 모양도 아니다** — 날퍼짐이 양성 쪽(0.7788/0.5642)인데 이득은 0이다.
그 조합을 내는 합성은 못 만들었고, 더 만지면 *"실물에 맞을 때까지 합성을 조정하는 것"*이
되므로 멈췄다 (D-0058 계열).

### 사전 등록 — 실물을 재기 전에 적는다

- 차이가 **음성 쪽(≈0)**이면: 차용 칸의 흔들림이 `base`에 이미 있다. 이득 0이 설명된다.
- 차이가 **양성 쪽(≈0.26)**이면: **가설이 틀렸다.** 새 정보가 있는데도 출력이 안 갈린
  것이므로 원인은 사전이 아니라 **생성기나 지표**에 있다.
- 그 사이면 **둘 다 아니다** — 그때는 수를 적고 다음 판으로 넘긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.engines.compose.harmony_generator import (
    BORROWED_ROOT_SEMITONES,
    CONTROL_ROOT_SEMITONES,
    DIATONIC_ROOT_SEMITONES,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hathor.application.evaluate_harmony_output import ReferencePrior
    from hathor.domain.value_objects.key import Mode

FLOOR = 1e-12
"""로그를 씌우기 전 바닥. 0인 칸이 `-inf`가 되면 회귀가 통째로 죽는다."""

NEGATIVE_GAP = 0.001
"""음성 눈금 — 차용 칸이 안 흔들릴 때의 잔차 차이 (1000곡 5회).

**이보다 작은 것, 음수까지가 「`base`가 안다」다.** 이웃 비례 코퍼스는 **-0.383**을 냈고
거기서도 이득이 0이었다 — 음수는 더 약한 증거가 아니라 **더 강한 증거**다.
"""

POSITIVE_GAP = 0.259
"""양성 눈금 — 차용 칸만 고유하게 흔들릴 때. 거기서 이득 +0.0609 (t +5.30)."""


@dataclass(frozen=True, slots=True)
class CellNovelty:
    """한 칸 묶음이 `base` 위에 **새로 얹는** 변동."""

    name: str
    raw_spread: float
    """날것의 곡 간 로그 표준편차. D-0095의 `cell_spread`와 같은 양이다."""
    residual_spread: float
    """온음계 6칸으로 회귀하고 **남은** 퍼짐. 이것이 «새 정보»다."""

    @property
    def explained(self) -> float:
        """`base`가 설명한 몫. **1에 가까우면 어휘를 넓힐 자리가 없다.**"""
        if self.raw_spread <= 0.0:
            return 0.0
        return 1.0 - (self.residual_spread / self.raw_spread)


def _log_table(references: Sequence[ReferencePrior]) -> np.ndarray:
    stacked = np.asarray([item.prior for item in references], dtype=np.float64)
    return np.log(np.maximum(stacked, FLOOR))


def residual_spread(
    references: Sequence[ReferencePrior], cells: Sequence[int], mode: Mode
) -> float:
    """그 칸들이 **온음계로 설명되지 않는** 곡 간 퍼짐 (O-73).

    **회귀 대상은 `base`의 칸이다.** 「나머지 반음계」로 회귀하면 다른 것을 재게 된다 —
    묻는 것은 «`mixture`가 `base` 위에 새 것을 얹는가»이기 때문이다.
    """
    table = _log_table(references)
    diatonic = list(DIATONIC_ROOT_SEMITONES[mode])
    if table.shape[0] <= len(diatonic) + 1:
        raise ValueError(f"회귀에 곡이 모자란다: {table.shape[0]}곡 · 설명 변수 {len(diatonic)}개")
    design = np.column_stack([np.ones(table.shape[0]), table[:, diatonic]])
    left: list[float] = []
    for cell in cells:
        target = table[:, cell]
        coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
        residual = target - design @ coefficients
        left.append(float(residual.std(ddof=design.shape[1])))
    return float(np.mean(left)) if left else 0.0


def novelty(
    references: Sequence[ReferencePrior], cells: Sequence[int], mode: Mode, name: str
) -> CellNovelty:
    """한 묶음의 날퍼짐과 잔차 퍼짐."""
    table = _log_table(references)
    raw = float(np.mean(table[:, list(cells)].std(axis=0, ddof=1))) if cells else 0.0
    return CellNovelty(
        name=name, raw_spread=raw, residual_spread=residual_spread(references, cells, mode)
    )


def compare_cells(
    references: Sequence[ReferencePrior], mode: Mode
) -> tuple[CellNovelty, CellNovelty]:
    """차용 칸과 대조 칸을 **같은 자로** 잰다. 앞이 차용, 뒤가 대조다."""
    return (
        novelty(references, BORROWED_ROOT_SEMITONES[mode], mode, "차용"),
        novelty(references, CONTROL_ROOT_SEMITONES[mode], mode, "대조"),
    )


def gap_of(borrowed: CellNovelty, control: CellNovelty) -> float:
    """두 잔차의 차이. **눈금 두 점 사이 어디인지**가 판정이다."""
    return borrowed.residual_spread - control.residual_spread


def reading(gap: float) -> str:
    """사전 등록한 읽는 법 (D-0333). **셋 중 하나만 낸다.**"""
    midpoint = (NEGATIVE_GAP + POSITIVE_GAP) / 2
    if gap <= midpoint / 2:
        # **음수도 여기다.** 이웃 비례 코퍼스가 -0.383을 냈고 이득은 0이었다.
        return "**base가 이미 안다** — 차용 칸의 흔들림이 온음계로 설명된다"
    if gap >= POSITIVE_GAP - midpoint / 2:
        return "**가설이 틀렸다** — 새 정보가 있는데 출력이 안 갈렸다. 생성기나 지표를 본다"
    return f"**둘 다 아니다** — 눈금 {NEGATIVE_GAP} ~ {POSITIVE_GAP} 사이다"
