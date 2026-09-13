"""박과 온셋 — 발음이 어디에 떨어지는가 (O-46 · D-0143).

### 무엇이 막혀 있었나

D-0142가 들은 결과 **화음 발음 44개가 전부 마디 첫 박**이었고 템포조차 `--tempo`
기본값 96 고정이었다. 참조곡에서 리듬을 뽑으려면 **박과 온셋**이 필요한데, 지금
시간 축 자료는 **1초 창 크로마뿐**이라 그 해상도로는 박을 못 본다.

O-26(절대 눈금)과 같은 벽이다. **하나를 뚫으면 둘이 풀린다.**

### 여기서 하는 것과 안 하는 것

**온셋 포락선을 뽑는 것은 여기가 아니다.** 그것은 음원을 읽는 일이고
`infrastructure`의 몫이며 1004곡 배치가 필요하다. 이 파일은 **포락선이 주어졌을 때
무엇을 읽어낼지**를 정하고, 그것이 맞는지 **합성으로 검증한다.**

D-0123이 반감점에서 쓴 순서와 같다 — 합성에서 참값을 회복하지 못하면 실측에 걸지
않는다.

### 박 주기를 고르지 않는다

자기상관의 봉우리를 그대로 쓴다. **탐색 범위만 밖에서 온다** — `TEMPO_RANGE`는
사람이 박으로 들을 수 있는 범위이며 **맞추는 값이 아니다.** 조성 추정이
Krumhansl-Kessler 프로파일을 외부 상수로 받아들인 것과 같은 자리다.

그리고 **하나만 내지 않는다.** 조성 추정이 1등만 남기면 나란한 장·단조 구분이
사라지는 것처럼(D-0054), 박도 두 배·절반이 늘 함께 선다. **격차를 함께 낸다.**

### 위상은 값이 아니다

박을 알면 **발음이 박 안 어디에 떨어지는가**는 그냥 나눗셈이다. 고를 것이 없다.
그 분포가 반주 리듬의 재료이며, **무엇을 쓸지는 실측을 보고 정한다** — 여기서
정하면 자료를 보기 전에 정하는 것이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

Envelope = np.ndarray

TEMPO_RANGE = (50.0, 200.0)
"""박으로 들을 수 있는 빠르기 (BPM). **맞추는 값이 아니라 밖에서 온 상수다.**

이 범위를 좁히면 결과가 좋아 보이게 만들 수 있고 그것이 D-0058이다. **넓게 두고
못 고르면 못 고른다고 낸다.**"""

PHASE_BINS = 4
"""박 하나를 몇 칸으로 볼 것인가. **마디가 4박인 것과 같은 부류의 격자다** —
16분음표 해상도이며 `TICKS_PER_BEAT`가 이미 480으로 4분할을 담고 있다."""


FRAME_RATIO = 4
"""분석 창은 홉의 이 배수다. **밖에서 오는 값은 홉 하나뿐이다.**

창 길이를 따로 고르면 값이 둘이 되고 둘 다 맞출 수 있게 된다. 홉은 산출물 격자가
정하므로 이미 밖에 있고, **창은 그것을 따라온다.**"""


def envelope(samples: Sequence[float] | Envelope, sample_rate: int, hop_seconds: float) -> Envelope:
    """파형에서 온셋 포락선을 만든다 (O-46 · D-0144).

    **스펙트럼 선속(flux)이다** — 크기 스펙트럼이 프레임 사이에 *늘어난 몫*만 더한다.
    줄어든 몫을 빼면 소리가 끝나는 자리도 온셋으로 세어진다.

    파형을 읽지 파일을 읽지 않는다. **디코딩은 `infrastructure`의 몫이며** 이 함수는
    순수하다 — 그래서 합성 파형으로 검증할 수 있다.
    """
    if sample_rate <= 0:
        raise ValueError("표본율은 양수여야 한다")
    if hop_seconds <= 0.0:
        raise ValueError("홉 길이는 양수여야 한다")

    wave = np.asarray(samples, dtype=np.float64)
    if wave.ndim != 1:
        raise ValueError("파형은 1차원이어야 한다")

    hop = max(1, round(hop_seconds * sample_rate))
    frame = hop * FRAME_RATIO
    if wave.size < frame * 2:
        raise ValueError("파형이 너무 짧다")

    window = np.hanning(frame)
    count = (wave.size - frame) // hop + 1
    spectra = np.empty((count, frame // 2 + 1), dtype=np.float64)
    for index in range(count):
        start = index * hop
        spectra[index] = np.abs(np.fft.rfft(wave[start : start + frame] * window))

    rising = np.maximum(np.diff(spectra, axis=0), 0.0)
    return np.concatenate(([0.0], rising.sum(axis=1)))


def _normalise(envelope: Sequence[float] | Envelope) -> Envelope:
    values = np.asarray(envelope, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("온셋 포락선은 1차원이어야 한다")
    if values.size < 4:
        raise ValueError("포락선이 너무 짧다")
    centred = values - values.mean()
    scale = float(np.abs(centred).max())
    return centred / scale if scale > 0.0 else centred


@dataclass(frozen=True, slots=True)
class Beat:
    """박 추정. **하나만 내지 않는다** (D-0054와 같은 근거)."""

    period_seconds: float
    margin: float
    """1등과 2등 봉우리의 상대 차이."""
    octave_margin: float
    """1등과 **절반·두 배 지연**의 상대 차이.

    사람도 120을 60으로 짚을 수 있다. **배수 모호성은 결함이 아니라 성질이며**,
    나란한 장·단조를 1등만 남겨 지우지 않기로 한 것과 같은 자리다 (D-0054).
    """

    @property
    def tempo_bpm(self) -> float:
        return 60.0 / self.period_seconds


def beat_period(envelope: Sequence[float] | Envelope, hop_seconds: float) -> Beat | None:
    """박 추정. **못 고르면 `None`이다.**"""
    if hop_seconds <= 0.0:
        raise ValueError("홉 길이는 양수여야 한다")
    values = _normalise(envelope)
    if not np.any(values > 0.0):
        return None

    low = max(1, round(60.0 / TEMPO_RANGE[1] / hop_seconds))
    high = min(values.size - 1, round(60.0 / TEMPO_RANGE[0] / hop_seconds))
    if high <= low:
        return None

    # **길이로 나누지 않는다.** 나누면 긴 지연이 밀려 올라가 배수 오류가 난다 —
    # 120BPM·잡음 0.1에서 60BPM을 골랐고 안 나누니 회복됐다 (D-0143 실측).
    scores = np.array([float(np.dot(values[:-lag], values[lag:])) for lag in range(low, high + 1)])
    if not np.any(scores > 0.0):
        return None

    best = int(np.argmax(scores))
    ranked = np.sort(scores)[::-1]
    second = float(ranked[1]) if ranked.size > 1 else 0.0
    top = float(ranked[0])
    margin = (top - second) / top if top > 0.0 else 0.0
    lag = low + best
    rival = max(
        (float(scores[index - low]) for index in (lag // 2, lag * 2) if low <= index <= high),
        default=0.0,
    )
    return Beat(
        period_seconds=(lag + _peak_offset(scores, best)) * hop_seconds,
        margin=margin,
        octave_margin=(top - rival) / top if top > 0.0 else 0.0,
    )


def _peak_offset(scores: Envelope, best: int) -> float:
    """봉우리를 홉 격자 아래로 보간한다. **표류를 막는 것이 요점이다.**

    격자 위 정수로만 뽑으면 96BPM을 96.77로 읽고, **0.8% 오차가 128박 뒤에 1박으로
    쌓여 위상 분포가 통째로 뭉개진다** — 실측했다 (D-0143).

    세 점 포물선이며 **고를 값이 없다.** 봉우리가 끝에 붙으면 보간하지 않는다.
    """
    if best <= 0 or best >= scores.size - 1:
        return 0.0
    left, middle, right = (float(scores[best + step]) for step in (-1, 0, 1))
    bottom = left - 2.0 * middle + right
    if bottom == 0.0:
        return 0.0
    return float(np.clip(0.5 * (left - right) / bottom, -0.5, 0.5))


def tempo_bpm(period_seconds: float) -> float:
    """박 주기를 BPM으로. **반올림하지 않는다** — 격자에 맞추는 것은 쓰는 쪽 일이다."""
    if period_seconds <= 0.0:
        raise ValueError("박 주기는 양수여야 한다")
    return 60.0 / period_seconds


def phase_profile(
    envelope: Sequence[float] | Envelope,
    period_seconds: float,
    hop_seconds: float,
    *,
    bins: int = PHASE_BINS,
) -> tuple[float, ...]:
    """박 안 어디에 에너지가 실리는가. 합이 1이다.

    **고를 것이 없다.** 박을 알면 나눗셈이며, 이 분포가 반주 리듬의 재료다.
    """
    if bins < 1:
        raise ValueError("칸은 1 이상이어야 한다")
    if period_seconds <= 0.0 or hop_seconds <= 0.0:
        raise ValueError("주기와 홉은 양수여야 한다")

    values = np.asarray(envelope, dtype=np.float64)
    values = np.maximum(values - values.mean(), 0.0)
    span = period_seconds / hop_seconds
    found = np.zeros(bins, dtype=np.float64)
    for index, value in enumerate(values):
        found[int((index % span) / span * bins) % bins] += value
    total = float(found.sum())
    if total <= 0.0:
        return tuple(1.0 / bins for _ in range(bins))
    return tuple(float(value) for value in found / total)
