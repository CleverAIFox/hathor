"""곡마다 다른 **시간 변화**가 실재하는지 잰다 (O-32 게이트 · D-0098).

### 왜 게이트가 먼저인가

순서 조건화에는 크로마 **시계열**이 필요하다. 저장된 것은 곡 전체 평균뿐이므로
1004곡을 다시 돌아야 하고, **스템 캐시가 없어 Demucs를 처음부터 다시 돈다.**

**게이트 없이 전량을 다시 도는 것은 D-0058 계열의 형태다.** 그 전에 값싼 표본으로
"시간 축에 곡 고유 정보가 있는가"를 판정한다.

### 버린 설계 — 비율은 상한이지 추정치가 아니다

처음에는 `곡 내 head-tail 거리 / 곡 간 거리`를 보려 했다. **탐색에서 기각됐다** —
시간 변화가 **전혀 없어도** 반쪽 추정 잡음만으로 비율이 0.448까지 올랐다.
낮게 나오면 멈출 근거가 되지만 높게 나오면 아무것도 모른다. **한쪽으로만 강한 것을
쓰려면 그 강한 쪽이 필요한 방향이어야 하는데 여기서는 아니다.**

### 쓰는 설계 — 두 독립 관측이 같은 방향을 가리키는가

같은 곡에 **관측이 둘** 있다. 전체 믹스와 스템이다. 각각의 변화 벡터를 만든다.

```text
d_mix   = log(tail_mix)   - log(head_mix)
d_stem  = log(tail_stem)  - log(head_stem)
```

**크로마 추정 잡음은 두 출처에서 상당히 갈리고 진짜 시간 변화는 둘 다에 나타난다.**
그러니 곡 간 상관이 양수면 **곡마다 다른 시간 변화가 실재한다.**

귀무선은 **곡 짝을 뒤섞은 것**이다. 곡 짝짓기만 없애므로 잡음 구조와 코퍼스 공통
성분은 그대로 남는다. **음원 재처리 없이 판정이 선다** — 표본만 다시 뽑으면 된다.

### 코퍼스 공통 변화는 쓸모가 없다

모든 곡이 뒷반쪽에서 똑같이 변한다면 참조곡을 볼 이유가 없다. 뒤섞은 귀무선이
그 몫을 그대로 갖고 있으므로 **초과분만 곡 고유한 시간 변화다.**

### 문턱을 높게 잡는다

`t > 3`이다. **자의적이지만 이유가 있다** — 이 게이트가 통과하면 전량 재추출과
시계열 파이프라인이라는 큰 작업을 승인한다. **승인 문턱은 관측 문턱보다 높아야
한다.** D-0095에서 승률 51%를 통과로 읽을 뻔한 뒤 정한 규율이다.

### 이 게이트가 못 가르는 것

두 출처가 **같은 오디오**를 공유한다. 뒷반쪽이 그냥 더 시끄러운 식의 **곡별
인공물**이 있으면 둘 다에 나타난다. 그것도 시간 변화이긴 하나 **화성이 아니다.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.application.evaluate_harmony_output import Histogram
from hathor.domain.services.harmony_prior import DEGREE_COUNT

DEFAULT_NULL_REPEATS = 20
DEFAULT_BOOTSTRAP = 40
GATE_T = 3.0
"""게이트 통과 문턱. **관측 문턱(2)보다 높다** — 큰 작업을 승인하기 때문이다."""


@dataclass(frozen=True, slots=True)
class DriftObservation:
    """곡 하나의 두 출처 변화 벡터. **이미 으뜸음으로 회전돼 있다.**"""

    source_key: str
    left: tuple[float, ...]
    right: tuple[float, ...]

    def __post_init__(self) -> None:
        for vector in (self.left, self.right):
            if len(vector) != DEGREE_COUNT:
                raise ValueError(f"변화 벡터는 12차원이어야 한다: {len(vector)}")


def drift_vector(head: Sequence[float], tail: Sequence[float]) -> tuple[float, ...]:
    """`log(tail) - log(head)`. **로그를 쓰는 이유는 크기가 아니라 방향을 보기 위해서다.**

    반쪽마다 전체 세기가 다를 수 있고 그것은 화성이 아니다. 로그 차는 비율을 재므로
    세기의 곱셈 성분이 상수로 빠진다.
    """
    left = np.maximum(np.asarray(head, dtype=np.float64), 1e-12)
    right = np.maximum(np.asarray(tail, dtype=np.float64), 1e-12)
    changed = np.log(right) - np.log(left)
    return tuple(float(value) for value in changed - changed.mean())


def _cell_correlation(left: Histogram, right: Histogram) -> float:
    """칸별 곡 간 상관의 평균. 흔들리지 않는 칸은 뺀다."""
    found: list[float] = []
    for cell in range(DEGREE_COUNT):
        a, b = left[:, cell], right[:, cell]
        if a.std() == 0.0 or b.std() == 0.0:
            continue
        found.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(found)) if found else 0.0


def _positive_cells(left: Histogram, right: Histogram, null: float) -> float:
    """칸 몇 개에서 귀무선을 넘는가. **평균 한 점의 우연이 아님을 본다.**"""
    wins = 0
    total = 0
    for cell in range(DEGREE_COUNT):
        a, b = left[:, cell], right[:, cell]
        if a.std() == 0.0 or b.std() == 0.0:
            continue
        total += 1
        if float(np.corrcoef(a, b)[0, 1]) > null:
            wins += 1
    return wins / total if total else 0.0


@dataclass(frozen=True, slots=True)
class DriftReport:
    label: str
    song_count: int
    observed: float
    null: float
    standard_error: float
    cell_share: float

    @property
    def excess(self) -> float:
        return self.observed - self.null

    @property
    def t_statistic(self) -> float:
        return self.excess / self.standard_error if self.standard_error > 0 else 0.0

    @property
    def time_drift_is_song_specific(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0098 · GR-6.5). 결과를 보고 고치지 않는다.

        1. 뒤섞은 귀무선을 넘는다.
        2. `t > 3` — **관측 문턱보다 높다.** 이 게이트가 큰 작업을 승인한다.
        3. **칸 과반**에서 귀무선을 넘는다.

        셋 다 넘으면 곡마다 다른 시간 변화가 실재하며 순서 조건화에 근거가 선다.
        넘지 못하면 **전량 재추출을 하지 않는다.**
        """
        return self.excess > 0.0 and self.t_statistic > GATE_T and self.cell_share > 0.5


class EvaluateTimeDrift:
    """두 출처의 변화 벡터가 곡 단위로 맞물리는지 잰다."""

    def __init__(
        self,
        seed: int = 20260822,
        null_repeats: int = DEFAULT_NULL_REPEATS,
        bootstrap: int = DEFAULT_BOOTSTRAP,
    ) -> None:
        if null_repeats < 1 or bootstrap < 1:
            raise ValueError("반복 수는 1 이상이어야 한다")
        self._seed = seed
        self._null_repeats = null_repeats
        self._bootstrap = bootstrap

    def run(self, observations: Sequence[DriftObservation], label: str) -> DriftReport:
        if len(observations) < 10:
            raise ValueError(f"곡이 10개 이상 필요하다: {len(observations)}")
        left = np.asarray([item.left for item in observations], dtype=np.float64)
        right = np.asarray([item.right for item in observations], dtype=np.float64)

        def stream(line: int, repeat: int = 0) -> np.random.Generator:
            """**선마다 흐름이 따로다** (D-0087)."""
            return np.random.default_rng([self._seed, line, repeat])

        def null_of(a: Histogram, b: Histogram, line: int) -> float:
            drawn = []
            for index in range(self._null_repeats):
                order = stream(line, index).permutation(len(a))
                drawn.append(_cell_correlation(a, b[order]))
            return float(np.mean(drawn))

        observed = _cell_correlation(left, right)
        null = null_of(left, right, 1)

        resample = stream(9)
        spread: list[float] = []
        for _ in range(self._bootstrap):
            picked = resample.integers(0, len(left), len(left))
            spread.append(
                _cell_correlation(left[picked], right[picked])
                - null_of(left[picked], right[picked], 2)
            )

        return DriftReport(
            label=label,
            song_count=len(observations),
            observed=observed,
            null=null,
            standard_error=float(np.std(spread, ddof=1)) if len(spread) > 1 else 0.0,
            cell_share=_positive_cells(left, right, null),
        )
