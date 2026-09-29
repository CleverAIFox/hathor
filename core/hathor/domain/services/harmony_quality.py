"""화음 품질 어휘를 창 단위 템플릿 적합으로 잰다 (O-64 · D-0300).

**O-64가 적은 측정은 성립하지 않는다.** 원문은 *"7음 성분이 3화음 대비 얼마나
실리는지 재면"*이라고 적었다. 다이어토닉에서 **7음으로만 나오는 음정이 하나도
없다** — I의 7음은 vii의 근음이고 ii의 7음은 I의 근음이다. 평균 크로마는 어느
화음이 그 음을 냈는지 모르므로 원리적으로 못 가른다. `_SEVENTH_ONLY`가 그것을
고정한다.

되는 것은 **창 하나를 화음 하나로 보고 템플릿에 맞춰 보는 것**이다. 12 근음 x
여섯 품질 = 72개 템플릿 중 가장 잘 맞는 것을 고른다.

### 코사인 argmax는 쓰지 않는다 — 화음수 편향이 있다

균등난수 크로마 2만 창(시드 3)에서 코사인 최적합의 **0.8713이 4음 화음**으로 나왔다
(기대 0.5). 4음 템플릿은 회전 12개 중 최댓값을 고를 때 3음보다 더 높이 올라간다.
그대로 쓰면 *"코퍼스에 7화음이 많다"*가 자료가 아니라 자의 편향이 된다 — O-25가
일곱 번 겪은 부류이고, D-0058이 걸린 함정과 같다.

`z_fit`은 **빈 순열 귀무로 표준화한다.** 창의 12개 값을 섞어 m개를 뽑는 것은
비복원 추출이므로 기댓값과 분산이 닫힌 식으로 나온다 — 시늉으로 돌릴 필요가 없다.
같은 자료에서 4음 비율이 **0.5440**으로 내려갔다.

### 그래도 0.500이 아니다 — 판정은 차로만 한다

0.5440은 0.5가 아니다. 회전 12개 중 최댓값을 고르는 단계의 분산 차이가 남는다.
그래서 **절대 비율을 인용하지 않는다.** `null_fit`이 코퍼스 자신의 창을 섞어
같은 자를 다시 대고, 판정은 실측과 그 귀무의 **차**로만 한다 (O-25 다섯째 줄 —
귀무 자료가 실측 구조를 재현해야 한다. 빈 순열은 창의 에너지 분포를 그대로 남긴다).

### 순환 회전은 이 축의 귀무가 아니다

창을 순환 회전시키면 근음만 바뀌고 **품질 판정은 완전히 불변이다**
(`test_harmony_quality`가 고정한다). 회전 귀무를 쓰면 차가 정확히 0으로 나오고,
그것을 *"품질 구조가 없다"*로 읽으면 틀린다. 회전은 근음 축의 귀무다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from numpy.typing import NDArray

DEGREE_COUNT = 12
"""피치클래스 수. `harmony_generator.DEGREE_COUNT`와 같은 값이며 뜻도 같다."""

QUALITIES: Mapping[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "sus4": (0, 5, 7),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
}
"""근음에서 센 반음 간격. **O-64가 이름으로 지목한 셋(maj7 · m7 · sus4)이 들어 있다.**

여섯으로 끊는다. 더 넣으면 (dim · aug · m7b5 · 9th) 72개가 백 개를 넘고, 창 하나에
4음 이상이 실릴 근거가 아직 없다 — 어휘를 넓히는 것만으로 적합이 오르는 것이
D-0094가 겪은 일이다.
"""

FLAT_RATIO = 1e-9
"""평평한 창 판정 기준. 창의 범위가 평균의 이 배 이하면 화음이랄 것이 없다.

**분산으로 묻지 않는다** — 상수 창의 부동소수 분산이 0이 아니라서 z가 잡음에서
2.35까지 올라갔다. 범위 대 평균은 크기에 무관하다.
"""

TRIAD_QUALITIES = tuple(name for name, tones in QUALITIES.items() if len(tones) == 3)
"""3음 품질. 화음수 편향을 세는 쪽이 이 이름들로 가른다."""


def _major_scale() -> tuple[int, ...]:
    return (0, 2, 4, 5, 7, 9, 11)


def _seventh_only() -> tuple[int, ...]:
    """다이어토닉에서 **7음으로만 쓰이는** 음정. 빈 순서열이다 (O-64 반증).

    장음계 일곱 도수마다 3화음(1-3-5)과 7화음의 7음을 음계 위에서 쌓고, 7음 집합에서
    3화음 집합을 뺀다. 남는 것이 없으므로 평균 크로마로는 둘을 가를 수 없다.
    """
    scale = _major_scale()
    triad: set[int] = set()
    seventh: set[int] = set()
    for degree in range(len(scale)):
        for step in (0, 2, 4):
            triad.add(scale[(degree + step) % len(scale)])
        seventh.add(scale[(degree + 6) % len(scale)])
    return tuple(sorted(seventh - triad))


_SEVENTH_ONLY = _seventh_only()


def templates() -> tuple[NDArray[np.float64], tuple[tuple[int, str], ...]]:
    """72개 이진 템플릿과 그 이름 `(근음, 품질)`.

    **정규화하지 않고 낸다.** `z_fit`은 이진 지시자에 곧바로 내적을 하고 순열 귀무로
    표준화한다. 여기서 L2로 나누면 그 표준화가 화음수를 다시 타게 된다.
    """
    rows: list[NDArray[np.float64]] = []
    names: list[tuple[int, str]] = []
    for quality, tones in QUALITIES.items():
        for root in range(DEGREE_COUNT):
            row = np.zeros(DEGREE_COUNT, dtype=np.float64)
            for tone in tones:
                row[(root + tone) % DEGREE_COUNT] = 1.0
            rows.append(row)
            names.append((root, quality))
    return np.asarray(rows, dtype=np.float64), tuple(names)


_TEMPLATES, TEMPLATE_NAMES = templates()
_CARDINALITY = _TEMPLATES.sum(axis=1)


def z_fit(windows: NDArray[np.float64]) -> NDArray[np.float64]:
    """창별 x 템플릿별 적합도. **빈 순열 귀무 기준의 z값이다.**

    창의 12개 값에서 m개를 비복원으로 뽑은 합의 기댓값은 `m * 평균`이고 분산은
    `m * 모분산 * (12 - m) / 11`이다 (유한모집단 보정). 이 닫힌 식으로 표준화하므로
    화음수 m이 기댓값 단계에서는 빠진다.

    ### 상수 창을 분산으로 묻지 않는다

    `[0.3] * 12`의 표본분산은 **0이 아니라 1e-17**이다. `spread <= 0`으로 걸렀더니
    분자도 1e-17이라 z가 2.35로 나왔다 — 잡음을 신호로 읽은 것이고 D-0058이 걸린
    함정과 같은 꼴이다. **범위를 평균과 견줘서** 판정한다. 크기에 무관한 물음이다.

    평평한 창은 모든 z가 0으로 나온다 — **0을 «맞았다»로 읽지 않도록** `verdicts`가
    걸러낸다.
    """
    frame = np.asarray(windows, dtype=np.float64)
    if frame.ndim != 2 or frame.shape[1] != DEGREE_COUNT:
        raise ValueError(f"창 행렬은 (창, {DEGREE_COUNT}) 꼴이어야 한다")
    raw = frame @ _TEMPLATES.T
    mean = frame.mean(axis=1, keepdims=True)
    variance = frame.var(axis=1, keepdims=True)
    spread = np.sqrt(variance * _CARDINALITY * (DEGREE_COUNT - _CARDINALITY) / 11.0)
    span = (frame.max(axis=1) - frame.min(axis=1)).reshape(-1, 1)
    flat = span <= FLAT_RATIO * np.maximum(np.abs(mean), FLAT_RATIO)
    return np.where(flat, 0.0, (raw - mean * _CARDINALITY) / np.where(spread > 0.0, spread, 1.0))


def verdicts(windows: NDArray[np.float64]) -> tuple[tuple[int, str, float], ...]:
    """창마다 `(근음, 품질, z)`. **평평한 창은 빠진다.**

    z가 전부 0인 창은 크로마가 상수라 화음이랄 것이 없다. 남기면 `argmax`가 표의
    첫 항목(C maj)을 늘 골라 *"C major가 많다"*는 거짓을 만든다.
    """
    scores = z_fit(windows)
    picked: list[tuple[int, str, float]] = []
    for row in range(scores.shape[0]):
        best = int(np.argmax(scores[row]))
        top = float(scores[row][best])
        if top <= 0.0:
            continue
        root, quality = TEMPLATE_NAMES[best]
        picked.append((root, quality, top))
    return tuple(picked)


def quality_share(picked: Sequence[tuple[int, str, float]]) -> dict[str, float]:
    """품질별 비율. 창이 없으면 빈 사전이며 **0으로 채우지 않는다** (D-0058)."""
    if not picked:
        return {}
    total = float(len(picked))
    counted = {name: 0 for name in QUALITIES}
    for _, quality, _ in picked:
        counted[quality] += 1
    return {name: count / total for name, count in counted.items()}


def seventh_share(picked: Sequence[tuple[int, str, float]]) -> float:
    """4음 화음으로 판정된 창의 비율. **귀무와 나란히 놓기 전엔 뜻이 없다.**"""
    share = quality_share(picked)
    return sum(value for name, value in share.items() if name not in TRIAD_QUALITIES)


def null_windows(windows: NDArray[np.float64], *, seed: int) -> NDArray[np.float64]:
    """창마다 12개 빈을 섞은 귀무 자료.

    **에너지 분포는 그대로 남는다** — 창의 값 다중집합이 보존되므로 총량·최댓값·
    분산이 실측과 같다. 사라지는 것은 음정 사이의 구조뿐이고 그것이 재려는 것이다.
    """
    frame = np.asarray(windows, dtype=np.float64)
    generator = np.random.default_rng(seed)
    order = np.argsort(generator.random(frame.shape), axis=1)
    return np.take_along_axis(frame, order, axis=1)


def rotated_windows(windows: NDArray[np.float64], *, seed: int) -> NDArray[np.float64]:
    """창마다 순환 회전시킨 자료. **품질 축의 귀무가 아니다.**

    회전은 근음만 옮기고 음정 구조를 그대로 남기므로 품질 판정이 불변이다. 근음
    분포를 볼 때만 귀무로 쓴다.
    """
    frame = np.asarray(windows, dtype=np.float64)
    generator = np.random.default_rng(seed)
    shifts = np.asarray(generator.integers(0, DEGREE_COUNT, size=frame.shape[0]), dtype=np.int64)
    columns = (np.arange(DEGREE_COUNT).reshape(1, -1) - shifts.reshape(-1, 1)) % DEGREE_COUNT
    return np.take_along_axis(frame, columns, axis=1)
