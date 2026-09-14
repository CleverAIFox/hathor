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

from hathor.domain.services import chord_rhythm

Envelope = np.ndarray

TEMPO_RANGE = (50.0, 200.0)
"""박으로 들을 수 있는 빠르기 (BPM). **맞추는 값이 아니라 밖에서 온 상수다.**

이 범위를 좁히면 결과가 좋아 보이게 만들 수 있고 그것이 D-0058이다. **넓게 두고
못 고르면 못 고른다고 낸다.**"""

PHASE_BINS = 4
"""박 하나를 몇 칸으로 볼 것인가. **마디가 4박인 것과 같은 부류의 격자다** —
16분음표 해상도이며 `TICKS_PER_BEAT`가 이미 480으로 4분할을 담고 있다."""


WINDOW_SECONDS = 0.04
"""분석 창의 길이. **홉을 따라 움직이지 않는다** (D-0169).

D-0144는 창을 홉의 네 배로 묶었다 — *"밖에서 오는 값은 홉 하나뿐"*이라는 근거였고,
그 자체로는 옳았다. **그런데 창은 주파수 해상도를 정한다.** 홉을 반으로 줄이면 창도
반이 되고 **스펙트럼이 통째로 달라진다** — 보고 격자를 바꿨을 뿐인데 재는 대상이
바뀐다. D-0103이 *"창 길이가 그 값을 정한다"*며 대각선을 버린 것과 같은 부류다.

**기본 홉 0.01초에서 값이 같다** — `0.01 * 4 = 0.04`이며 산출물이 안 바뀐다.
새로 고른 값이 아니라 **묶여 있던 것을 푼 것이다.**"""


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

    spectra, _ = _spectra(samples, sample_rate, hop_seconds)
    rising = np.maximum(np.diff(spectra, axis=0), 0.0)
    return np.concatenate(([0.0], rising.sum(axis=1)))


def _spectra(
    samples: Sequence[float] | Envelope, sample_rate: int, hop_seconds: float
) -> tuple[np.ndarray, np.ndarray]:
    """`(프레임, 주파수 빈)과 빈의 주파수`. **포락선과 대역이 같은 것을 본다.**

    둘이 따로 창을 잡으면 같은 곡에서 다른 스펙트럼을 보게 되고, 그것이 D-0157이
    겪은 부류다 — 세는 것과 쓰는 것이 어긋난다.
    """
    if sample_rate <= 0:
        raise ValueError("표본율은 양수여야 한다")
    if hop_seconds <= 0.0:
        raise ValueError("홉 길이는 양수여야 한다")

    wave = np.asarray(samples, dtype=np.float64)
    if wave.ndim != 1:
        raise ValueError("파형은 1차원이어야 한다")

    hop = max(1, round(hop_seconds * sample_rate))
    frame = max(4, round(WINDOW_SECONDS * sample_rate))
    if wave.size < frame * 2:
        raise ValueError("파형이 너무 짧다")

    window = np.hanning(frame)
    count = (wave.size - frame) // hop + 1
    spectra = np.empty((count, frame // 2 + 1), dtype=np.float64)
    for index in range(count):
        start = index * hop
        spectra[index] = np.abs(np.fft.rfft(wave[start : start + frame] * window))
    return spectra, np.fft.rfftfreq(frame, 1.0 / sample_rate)


def band_edges(frequencies: np.ndarray, sample_rate: int) -> list[tuple[float, float]]:
    """옥타브 대역. **나이퀴스트에서 반씩 내려오며 빈이 없으면 멈춘다.**

    **옥타브는 밖에서 온 격자다** — 12반음이 한 옥타브인 것과 같은 부류이고 맞추는
    값이 아니다. 개수도 고르지 않는다: 창이 정한 주파수 해상도가 더 못 내려가는
    자리에서 끝난다.

    창이 초로 고정돼 있으므로(D-0169) **홉을 바꿔도 대역 수가 안 바뀐다.** 창이 홉을
    따라오던 때는 9개와 8개가 나왔고, 그러면 두 홉의 뾰족함을 견줄 수 없다.
    """
    edges: list[tuple[float, float]] = []
    top = sample_rate / 2.0
    while True:
        low = top / 2.0
        if not np.any((frequencies >= low) & (frequencies < top)):
            break
        edges.append((low, top))
        top = low
    return edges[::-1]


def bands(samples: Sequence[float] | Envelope, sample_rate: int, hop_seconds: float) -> np.ndarray:
    """`(프레임, 대역)` 크기 스펙트럼 (O-47 · D-0170).

    **선속이 아니라 크기다.** D-0167이 반감점을 1차원 포락선에 두 번 옮기려다
    실패하며 원인을 짚었다 — *"잡음 바닥이 합을 지배한다"*. 크로마에 그 문제가
    없는 이유는 **프레임마다 분포이고 프레임별로 정규화되기 때문**이며, 선속은
    발음 사이가 비어 있어 그 성질을 못 갖는다.

    **여기서 하는 것은 크로마와 같은 것을 더 고운 창으로 하는 것이다.** 크로마는
    스펙트럼을 12반음으로 접고 1초 창으로 본다. 대역은 옥타브로 접고 0.04초 창으로
    본다. **새로 고른 것은 접는 격자뿐이고 그것은 옥타브다.**
    """
    spectra, frequencies = _spectra(samples, sample_rate, hop_seconds)
    edges = band_edges(frequencies, sample_rate)
    if not edges:
        raise ValueError("대역이 서지 않는다")
    stacked = np.stack(
        [
            spectra[:, (frequencies >= low) & (frequencies < high)].sum(axis=1)
            for low, high in edges
        ],
        axis=1,
    )
    return np.asarray(stacked, dtype=np.float64)


def bundle_grid(frames: int) -> tuple[int, ...]:
    """묶음 격자. **`chord_rhythm.BUNDLES`를 곡 길이까지 이은 것이다** (O-47 · D-0171).

    ### 새 격자가 아니다

    `BUNDLES`는 **2의 거듭제곱과 그 1.5배**의 집합이고, 이 함수가 같은 규칙을 계속
    적용할 뿐이다. 앞의 열둘은 `BUNDLES`와 바이트로 같으며 검사가 그것을 고정한다.

    ### 왜 필요했나

    `BUNDLES`의 상한 64는 **칸이지 초가 아니다.** 홉 0.01에서 0.64초, 0.005에서
    0.32초이고 **그보다 긴 사건은 반이 안 내려와 `None`이 된다.**

    실측이 그 선을 칼같이 보여줬다 — 홉 0.005에서 살아남은 7곡은 전부 0.312초
    이하였고, 잃은 열한 곡은 전부 0.364초 이상이었다. **한 곡도 안 섞였다.**

    ### 상한을 고르지 않는다

    **곡이 정한다.** 묶음이 둘은 나와야 반감점을 보간할 수 있으므로 `frames // 2`가
    끝이고, `curve`가 모자란 묶음에서 알아서 멈춘다.
    """
    limit = max(1, frames // 2)
    sizes: set[int] = set()
    size = 1
    while size <= limit:
        sizes.add(size)
        if size * 3 // 2 <= limit:
            sizes.add(size * 3 // 2)
        size *= 2
    return tuple(sorted(sizes))


def event_scale(band_series: np.ndarray, hop_seconds: float) -> float | None:
    """그 곡의 **사건 길이.** 초 단위이며 못 재면 `None`이다 (O-47 · D-0170).

    O-37(D-0125로 닫힘)의 반감점을 그대로 부른다 — **정본은 `chord_rhythm` 하나이고 여기서
    베끼지 않는다** (D-0123과 같은 자리). 대역 분포를 묶으면 뾰족함이 떨어지고,
    **한 사건의 음색이 유지되는 길이를 넘는 순간 급락한다.**

    ### 무엇을 재는가

    **간격이 아니라 길이다.** 합성에서 사건 간격을 8배(1.0초 → 0.125초) 좁혔는데
    값은 1.33배만 움직였다(0.0735 → 0.0552). 감쇠 0.12초가 고정이었고 **값이 그쪽에
    붙어 있다.** 간격을 재는 값으로 쓰면 안 된다.

    그래도 `apart`의 자리에는 이것이 맞다 — **한 사건이 우는 동안의 잔물결은 다른
    발음이 아니다**(D-0156이 막으려던 것). 실측에서 그런지는 안 봤다 (O-47).

    ### 격자 무관 (사전 등록 예측 통과)

    홉을 반·4분의 1로 줄여도 값이 안 바뀐다 — 합성 5곡에서 비 0.991~1.001이고
    **실측 39곡에서 중앙 1.003**이었다 (D-0171). D-0166의 발음 간격은 같은 자리에서
    **0.500**이었다. 창을 초로 고정한 것이 조건이며(D-0169), 창이 홉을 따라오면
    이 성질이 사라진다.

    **창 길이 근처 값은 못 잰 것이다.** 지속음만 있는 합성에서 0.032초가 나왔고
    그것은 창 0.04초의 바닥이다. **위쪽은 묶음 격자가 정하며 곡 길이까지 잇는다**
    (`bundle_grid`) — 안 이으면 0.64초를 넘는 사건이 전부 `None`이 된다 (D-0171).
    """
    if hop_seconds <= 0.0:
        raise ValueError("홉 길이는 양수여야 한다")
    stacked = np.asarray(band_series, dtype=np.float64)
    if stacked.ndim != 2:
        raise ValueError("대역 시계열은 2차원이어야 한다")
    found = chord_rhythm.half_fall(
        chord_rhythm.curve(stacked, bundle_grid(len(stacked))),
        chord_rhythm.limit_spikiness(stacked),
    )
    return None if found is None else float(found) * hop_seconds


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


def peaks(envelope: Sequence[float] | Envelope, *, apart: int = 1) -> list[tuple[int, float]]:
    """봉우리와 바닥 위 높이 (D-0155).

    **발음은 봉우리지 에너지가 아니다.** 실제 곡에는 노래와 지속음이 연속 에너지를
    깔아 두는데, 평균만 빼면 그 바닥이 **모든 위상에 고르게 들어가 분포를 뭉갠다** —
    합성에 바닥을 넣어 재현했다.

    | 바닥 | 박 안 위상 |
    |---|---|
    | 없음 | `0.675 · 0.000 · 0.000 · 0.325` |
    | 0.2 | `0.192 · 0.307 · 0.194 · 0.307` |

    `apart`는 봉우리가 서로 떨어져야 하는 칸 수다. **이것 없이 이웃만 보면 잡음의
    잔물결을 전부 센다** — 실측 5142개(25.7%)에 간격 중앙 3칸이었고 박은 50칸이었다.
    **16.7배 촘촘했고 그래서 위상이 평평했다** (D-0156).

    부르는 쪽이 **보고할 해상도 한 칸**을 준다. `phase_profile`은 `PHASE_BINS`로
    나눈 칸을 주며 **새 값이 아니다** — 이미 그 눈금으로 보고한다.

    문턱은 없다. 중앙값 위 높이를 무게로 쓴다.
    """
    values = np.asarray(envelope, dtype=np.float64)
    if values.size < 3:
        return []
    floor = float(np.median(values))
    reach = max(1, apart)
    found: list[tuple[int, float]] = []
    for index in range(reach, values.size - reach):
        height = float(values[index])
        if height <= floor:
            continue
        window = values[index - reach : index + reach + 1]
        if height >= float(window.max()) and height > float(values[index - 1]):
            found.append((index, height - floor))
    return found


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
    span = period_seconds / hop_seconds
    found = np.zeros(bins, dtype=np.float64)
    for index, height in peaks(values, apart=max(1, int(span / bins / 2))):
        found[int((index % span) / span * bins) % bins] += height
    total = float(found.sum())
    if total <= 0.0:
        return tuple(1.0 / bins for _ in range(bins))
    return tuple(float(value) for value in found / total)
