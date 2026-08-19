"""크로마에서 조성을 추정한다. 순수 함수이며 numpy만 쓴다.

### 왜 필요한가

생성 경로가 관통했으나(D-0052) **화성이 참조곡과 무관했다.** 참조곡을 바꿔도
진행이 같았고, 조성도 C장조로 고정이었다. 사용자가 직접 들어보고 "두 파일이
크게 다르지 않다"고 관찰한 것이 그 증거다.

조성만 맞아도 참조곡별로 확연히 갈린다. **화성 진행 조건화보다 값싸고 먼저다.**

### 방법 — Krumhansl-Schmuckler

크로마 12차원(피치클래스별 에너지)을 뽑고, 장·단조 24개 프로파일과 상관을 재
가장 높은 것을 고른다. 1990년 발표된 고전이며 **의존성이 없다.**

MFCC 베이스라인을 만든 것과 같은 판단이다 (D-0025). **값싼 기준선을 먼저 세우고
비싼 것이 그것을 넘는지 본다.** 신경망 조성 추정기는 이 값을 넘지 못할 때 꺼낸다.

### 한계를 미리 적는다

- **K-S는 조옮김이 잦은 곡, 모달 화성, 무조 음악에서 약하다.** 대중가요 대부분은
  한 조성을 유지하므로 코퍼스와는 맞으나, 틀리는 곡이 있을 것이다 (실측 필요).
- **장조와 나란한 단조를 자주 혼동한다** (C장조 ↔ A단조). 구성음이 같기 때문이며
  알고리즘의 원리적 한계다.
- 정답 라벨이 없어 **정확도를 잴 방법이 현재 없다.** 분포와 안정성만 본다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE, StereoWaveform, Waveform
from hathor.domain.value_objects.key import PITCH_CLASSES, Key, Mode

FFT_SIZE = 4096
"""선형 STFT 창 크기. `linear` 방식에만 쓴다."""

HOP_SIZE = 2048
MIN_HZ = 65.41
"""C2. 이보다 낮은 대역은 베이스 배음이 흐려 피치클래스 판정이 불안정하다."""

MAX_HZ = 2093.0
"""C7. 이 위는 배음이 지배해 근음 정보를 더하지 않는다."""

REFERENCE_A4 = 440.0
EPSILON = 1e-12

CHROMA_LINEAR = "linear"
CHROMA_CQ = "cq"
CHROMA_MODES = (CHROMA_CQ, CHROMA_LINEAR)
"""크로마 추출 방식. **기본은 `cq`이며 `linear`는 베이스라인으로 남긴다** (D-0056).

`linear`는 선형 FFT 빈을 피치클래스로 반올림한다. **저역에서 반음을 가르지 못한다** —
44.1kHz · FFT 4096이면 빈 간격이 10.77Hz인데 65Hz에서 한 반음은 3.9Hz다.
한 빈이 2.65반음을 덮으므로 C2·C#2·D#2가 전부 D로 뭉친다. 실측으로 확인했다.

그리고 빈 수가 주파수에 비례해 **1~2kHz 한 옥타브가 크로마의 52%를 차지한다.**
그 대역은 배음과 심벌즈이지 근음이 아니다.

`cq`는 반음마다 필터를 하나씩 두어 두 결함을 동시에 없앤다.
"""

SEMITONE_BINS = 60
"""C2~B6, 5옥타브 60반음. 반음마다 필터 하나다."""

CQ_WINDOWS: tuple[int, ...] = (32768, 16384, 8192, 4096)
"""옥타브 대역별 창 크기. **저역은 길게, 고역은 짧게.**

이것이 constant-Q의 핵심이다. 65Hz에서 반음 간격 3.9Hz를 가르려면 창이 최소
44100/3.9 ≈ 11300 샘플이어야 하고, 여유를 두어 32768을 쓴다(0.74초).
고역은 반음 간격이 넓어 짧은 창으로 충분하며, 짧게 잡아야 시간 해상도를 지킨다.
"""

PROFILE_KRUMHANSL = "krumhansl"
PROFILE_TEMPERLEY = "temperley"
PROFILE_NAMES = (PROFILE_KRUMHANSL, PROFILE_TEMPERLEY)
"""조성 프로파일. **기본은 `krumhansl`이며 베이스라인이다** (D-0058).

Krumhansl-Kessler는 1980년대 **서양 고전음악** 청취 실험에서 얻은 값이다.
Temperley는 그것을 조성 판정 과제에 맞게 개정했으며 으뜸음과 5음의 무게를
낮추고 나머지 음계음을 올렸다 — 대중음악처럼 화성이 단순하고 반복이 많은
자료에서 낫다고 알려져 있다.

**어느 쪽이 이 코퍼스에 맞는지는 실측해야 안다.** 둘 다 두고 비교한다.
"""

KRUMHANSL_MAJOR: tuple[float, ...] = (
    6.35,
    2.23,
    3.48,
    2.33,
    4.38,
    4.09,
    2.52,
    5.19,
    2.39,
    3.66,
    2.29,
    2.88,
)
KRUMHANSL_MINOR: tuple[float, ...] = (
    6.33,
    2.68,
    3.52,
    5.38,
    2.60,
    3.53,
    2.54,
    4.75,
    3.98,
    2.69,
    3.34,
    3.17,
)
"""Krumhansl-Kessler 조성 프로파일. 으뜸음을 0으로 놓은 상대 가중치다."""

TEMPERLEY_MAJOR: tuple[float, ...] = (
    5.0,
    2.0,
    3.5,
    2.0,
    4.5,
    4.0,
    2.0,
    4.5,
    2.0,
    3.5,
    1.5,
    4.0,
)
TEMPERLEY_MINOR: tuple[float, ...] = (
    5.0,
    2.0,
    3.5,
    4.5,
    2.0,
    4.0,
    2.0,
    4.5,
    3.5,
    2.0,
    1.5,
    4.0,
)
"""Temperley 개정 프로파일. 으뜸음 무게가 낮고 이끔음(7음)이 높다.

K-K는 으뜸음이 6.35로 압도적이라 **베이스가 강한 곡에서 근음 하나에 끌려간다.**
Temperley는 5.0으로 낮추고 이끔음을 2.88에서 4.0으로 올려 조성 전체의 모양을
본다. 대중음악처럼 반복이 많은 자료에서 낫다고 알려져 있다.
"""

PROFILES: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    PROFILE_KRUMHANSL: (KRUMHANSL_MAJOR, KRUMHANSL_MINOR),
    PROFILE_TEMPERLEY: (TEMPERLEY_MAJOR, TEMPERLEY_MINOR),
}


def to_mono(stereo: StereoWaveform) -> Waveform:
    """산술 평균 다운믹스. MFCC·MERT 경로와 같은 규약이다 (D-0021)."""
    mono = stereo.mean(axis=0) if stereo.ndim > 1 else stereo
    return np.asarray(mono, dtype=np.float32)


def pitch_class_map(
    sample_rate: int = SOURCE_SAMPLE_RATE, fft_size: int = FFT_SIZE
) -> np.ndarray[tuple[int], np.dtype[np.int64]]:
    """FFT 빈을 피치클래스로 보낸다. 범위 밖은 -1이다.

    호출마다 같은 값이 나온다. 미리 계산해 두면 프레임마다 로그를 다시 재지 않는다.
    """
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    mapping = np.full(frequencies.shape[0], -1, dtype=np.int64)
    usable = (frequencies >= MIN_HZ) & (frequencies <= MAX_HZ)
    # A4=440을 기준으로 반음 번호를 재고 12로 접는다. C를 0으로 맞추기 위해 +9.
    semitones = 12.0 * np.log2(frequencies[usable] / REFERENCE_A4) + 9.0
    mapping[usable] = np.round(semitones).astype(np.int64) % 12
    return mapping


def semitone_hz(index: int) -> float:
    """반음 번호를 주파수로. 0이 C2(65.41Hz)다."""
    return MIN_HZ * 2 ** (index / 12)


def _octave_band(index: int) -> int:
    """반음 번호가 속한 옥타브. 창 크기 선택에 쓴다."""
    return min(index // 12, len(CQ_WINDOWS) - 1)


@lru_cache(maxsize=16)
def cq_filterbank(
    window_size: int,
    band: int,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    tuning_cents: float = 0.0,
) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
    """한 옥타브 대역의 (반음, 주파수빈) 삼각 필터뱅크.

    반음 중심에서 1이고 인접 반음 중심에서 0인 삼각형이다. 멜 필터뱅크와 같은
    모양이며 격자만 로그다. **호출마다 같은 값이 나온다** — 미리 계산해 캐시한다.

    삼각형을 쓰는 이유는 사각형이면 경계에 걸린 성분이 통째로 한쪽에 실려
    미세한 조율 차이(A=442Hz 등)에 결과가 흔들리기 때문이다.
    """
    frequencies = np.fft.rfftfreq(window_size, d=1.0 / sample_rate)
    shift = 2 ** (tuning_cents / 1200)
    bank = np.zeros((12, frequencies.shape[0]), dtype=np.float32)
    for pitch in range(12):
        index = band * 12 + pitch
        if index >= SEMITONE_BINS:
            continue
        center = semitone_hz(index) * shift
        low = semitone_hz(index - 1) * shift
        high = semitone_hz(index + 1) * shift
        rising = (frequencies > low) & (frequencies <= center)
        falling = (frequencies > center) & (frequencies < high)
        bank[pitch, rising] = (frequencies[rising] - low) / (center - low)
        bank[pitch, falling] = (high - frequencies[falling]) / (high - center)
    return bank


LOG_GAMMA = 0.0
"""로그 압축 계수. `log(1 + gamma * x)`의 gamma다. **기본은 0(끔)이다** (D-0058).

음향 처리에서 흔히 쓰는 기법이나 **실측이 도움 없음을 보였다.**

가설은 "드럼과 배음이 크로마를 평평하게 만들어 24개 프로파일 어느 것과도
비슷하게 맞는다"였다. 분포 엔트로피 3.52(균등 3.58)가 그 증상으로 보였다.

**가설이 틀렸다. 피어슨 상관은 평균을 빼므로 균등 성분에 완전히 불변이다.**
균등 성분을 90% 섞어 엔트로피를 3.17에서 3.58로 올려도 상관이 0.9590으로
소수점 넷째 자리까지 같고 판정도 바뀌지 않았다. 드럼처럼 12개에 고르게
실리는 성분은 K-S 판정에 영향을 주지 않는다.

그리고 로그는 큰 값을 눌러 대비를 줄이므로 **상관을 오히려 낮춘다**
(합성 실측 0.871 → 0.837). **얻을 것이 없고 잃을 것이 있다.**

구현을 지우지 않고 남기는 이유는, 지우면 나중에 근거 없이 되살리게 되기
때문이다. 반증 기록과 함께 둔다.
"""

HARMONIC_INTERVALS: tuple[tuple[int, float], ...] = (
    (7, 1 / 3),
    (4, 1 / 5),
    (10, 1 / 7),
)
"""배음이 만드는 (반음 간격, 상대 크기). 근음 위로 몇 반음에 얼마나 실리는가.

배음렬은 근음의 정수배 주파수다. 피치클래스로 접으면 이렇게 된다.

| 배음 | 주파수비 | 반음 | 결과 음 |
|---|---|---|---|
| 2 · 4 · 8 | 2·4·8배 | 0 | 근음 자신 (옥타브) |
| **3** | 3배 | **+7** | 완전5도 |
| **5** | 5배 | **+4** | 장3도 |
| **7** | 7배 | **+10** | 단7도 — **스케일 밖 음** |

크기는 대략 1/n로 줄어든다. 옥타브 배음(2·4·8)은 같은 피치클래스로 접히므로
빼지 않는다 — 근음을 깎게 된다.

**7배음이 문제다.** 장조의 단7도는 스케일에 없다. C를 울리면 A#이 따라 들어와
C장조 크로마에 A#이 실리고, 그것이 F장조나 A#장조와의 상관을 올린다.
이것은 균등하지 않아 **피어슨 상관에 실제로 영향을 준다** — 로그 압축이
반증된 이유(균등 성분은 상관에 불변)와 정확히 대비되는 지점이다 (D-0058).
"""

HARMONIC_STRENGTH = 0.0
"""배음 감산 강도. 0이 끔이며 기본이다.

**켜는 것이 기본이 아닌 이유는 아직 실측되지 않았기 때문이다.** D-0058에서
로그 압축을 "흔히 쓰는 기법"이라는 이유로 기본으로 넣을 뻔했고 실측이 반증했다.
같은 실수를 되풀이하지 않는다.
"""


TUNING_STEPS = 5
"""반음을 몇 조각으로 나눠 조율 편차를 훑을지. 홀수여야 0센트가 격자에 놓인다."""

TUNING_RANGE_CENTS = 50.0
"""탐색 폭. 반음의 절반이다. 그 이상 벗어나면 이웃 반음이 더 가까워 구분이 무의미하다."""


def estimate_tuning_cents(waveform: Waveform, *, sample_rate: int = SOURCE_SAMPLE_RATE) -> float:
    """음원이 A=440에서 얼마나 벗어났는지 센트로 잰다 (D-0057).

    **반음 격자로 바꾸고 나서야 보이게 된 문제다.** 선형 방식은 저역이 뭉개져
    조율 편차를 감췄다. 이제 반음을 정확히 가르므로, 음원이 반음의 절반 이상
    벗어나 있으면 **이웃 반음으로 통째로 넘어간다.**

    격자를 옮겨 가며 크로마를 뽑고 **가장 뾰족한** 지점을 찾는다. 격자가 실제
    음정에 맞을수록 에너지가 반음마다 모이고, 어긋날수록 이웃 반음에 갈린다.

    뾰족함은 **최댓값이 아니라 제곱합**으로 잰다. 최댓값은 한 음만 보므로
    화음에서 흔들린다. 제곱합은 12개 전체가 얼마나 몰려 있는지를 재며, 합이
    1로 고정돼 있어 비교가 성립한다.

    **경계를 -50~+50센트 안쪽으로 제한한다.** ±50은 이웃 반음까지의 거리라
    그 지점에서는 어느 쪽으로 붙여도 같다. 끝값이 나오면 순환이 일어나
    -40이 +50으로 보고되므로, 탐색 범위를 좁혀 그 모호함을 없앤다.

    되돌리는 보정은 하지 않는다. **먼저 얼마나 벗어나 있는지 알아야 한다** —
    편차가 작으면 검은건반 조 편중은 다른 원인이고, 크면 보정이 답이다.
    """
    limit = TUNING_RANGE_CENTS * (TUNING_STEPS - 1) / TUNING_STEPS
    offsets = np.linspace(-limit, limit, TUNING_STEPS * 2 + 1)
    best_offset = 0.0
    best_sharpness = -1.0
    for offset in offsets:
        vector = cq_chroma(waveform, sample_rate=sample_rate, tuning_cents=float(offset))
        sharpness = float(np.square(vector).sum())
        if sharpness > best_sharpness:
            best_sharpness, best_offset = sharpness, float(offset)
    return best_offset


def cq_chroma(
    waveform: Waveform,
    *,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    tuning_cents: float = 0.0,
    gamma: float = LOG_GAMMA,
    harmonic: float = HARMONIC_STRENGTH,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """반음 격자 크로마. 옥타브 대역마다 다른 창으로 STFT를 돌린다 (D-0056).

    **대역마다 기여를 정규화한다.** 정규화하지 않으면 긴 창을 쓴 저역이 프레임
    수가 적어 과소 반영되고, 그러면 선형 방식의 고역 편중을 방향만 바꿔 되풀이한다.
    """
    totals = np.zeros(12, dtype=np.float64)
    bands = (SEMITONE_BINS + 11) // 12

    for band in range(bands):
        window_size = CQ_WINDOWS[min(band, len(CQ_WINDOWS) - 1)]
        if waveform.size < window_size:
            continue
        hop = window_size // 2
        window = np.hanning(window_size).astype(np.float32)
        bank = cq_filterbank(window_size, band, sample_rate, tuning_cents)
        band_total = np.zeros(12, dtype=np.float64)
        frames = 0
        for start in range(0, waveform.size - window_size + 1, hop):
            magnitude = np.abs(np.fft.rfft(waveform[start : start + window_size] * window))
            band_total += bank @ magnitude
            frames += 1
        if not frames:
            continue
        # **프레임 수와 창 길이로만 나눈다.** 대역 합을 1로 맞추면 에너지가 거의
        # 없는 대역까지 온전한 무게를 받아, 새어 든 성분이 실제 음처럼 커진다.
        # 실측으로 확인했다 — C6 단일음이 B로 판정됐다.
        # 긴 창은 프레임이 적고 FFT 크기가 커 값이 커지므로 그 둘만 보정한다.
        totals += band_total / (frames * window_size)

    return _compress(subtract_harmonics(totals, harmonic), gamma)


def subtract_harmonics(
    vector: np.ndarray[tuple[int], np.dtype[np.float64]], strength: float
) -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    """각 피치클래스에서 다른 음의 배음으로 설명되는 몫을 뺀다 (D-0059).

    피치클래스 `p`의 에너지 중, `p - 7`·`p - 4`·`p - 10`에 있는 음의 배음이
    기여했을 양을 추정해 감산한다. 음수는 0으로 자른다.

    **한 번만 감산한다.** 배음의 배음까지 재귀로 빼면 무엇이 남았는지 설명할 수
    없게 되고, 감산 횟수가 또 하나의 근거 없는 파라미터가 된다.

    `strength`가 0이면 원본을 그대로 돌려준다.
    """
    if strength < 0:
        raise ValueError(f"strength는 0 이상이어야 한다: {strength}")
    if strength == 0:
        return vector

    reduced = vector.copy()
    for interval, ratio in HARMONIC_INTERVALS:
        # 근음 위 `interval` 반음에 실린 배음을 그 자리에서 뺀다.
        reduced -= strength * ratio * np.roll(vector, interval)
    return np.maximum(reduced, 0.0)


def _compress(
    totals: np.ndarray[tuple[int], np.dtype[np.float64]], gamma: float
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """합을 1로 맞춘 뒤 로그 압축하고 다시 정규화한다.

    **압축 전에 정규화한다.** 그러지 않으면 곡의 절대 음량이 압축 강도를 바꿔,
    마스터링 볼륨이 조성 판정에 섞인다 — D-0021이 막으려던 것과 같은 종류다.
    """
    if gamma < 0:
        raise ValueError(f"gamma는 0 이상이어야 한다: {gamma}")
    total = totals.sum()
    if total <= EPSILON:
        return np.zeros(12, dtype=np.float32)
    normalized = totals / total
    if gamma > 0:
        normalized = np.log1p(gamma * normalized)
        scale = normalized.sum()
        if scale <= EPSILON:
            return np.zeros(12, dtype=np.float32)
        normalized = normalized / scale
    return np.asarray(normalized, dtype=np.float32)


def linear_chroma(
    waveform: Waveform,
    *,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    fft_size: int = FFT_SIZE,
    hop_size: int = HOP_SIZE,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """선형 FFT 빈을 피치클래스로 반올림한다. **베이스라인으로만 남긴다** (D-0056).

    **크기 스펙트럼을 쓰고 파워를 쓰지 않는다.** 파워는 큰 소리에 과도한 가중을
    주어 드럼 타격이 크로마를 지배한다. 마스터링 볼륨이 결과에 섞이면 안 된다는
    D-0021과 같은 이유다.
    """
    if fft_size < 2 or hop_size < 1:
        raise ValueError("FFT 크기는 2 이상, 홉은 1 이상이어야 한다")
    if waveform.size < fft_size:
        return np.zeros(12, dtype=np.float32)

    window = np.hanning(fft_size).astype(np.float32)
    mapping = pitch_class_map(sample_rate, fft_size)
    totals = np.zeros(12, dtype=np.float64)

    for start in range(0, waveform.size - fft_size + 1, hop_size):
        frame = waveform[start : start + fft_size] * window
        magnitude = np.abs(np.fft.rfft(frame))
        for pitch in range(12):
            totals[pitch] += float(magnitude[mapping == pitch].sum())

    total = totals.sum()
    if total <= EPSILON:
        return np.zeros(12, dtype=np.float32)
    return np.asarray(totals / total, dtype=np.float32)


@dataclass(frozen=True, slots=True)
class KeyEstimate:
    """추정 결과. **확신도를 함께 낸다.**

    조성 추정은 틀릴 수 있고, 특히 나란한 장·단조를 혼동한다. 1등만 남기면
    그 사실이 사라진다. 2등과의 격차를 들고 다녀야 "이 곡은 애매하다"를 말할 수 있다.
    """

    key: Key
    correlation: float
    runner_up: Key
    margin: float
    """1등과 2등 상관의 차. 작으면 추정을 신뢰하지 않는다."""

    chroma: tuple[float, ...] = ()
    """판정에 쓴 크로마. **버리지 않고 들고 나온다** (D-0063).

    화성 어휘 조건화가 같은 크로마를 필요로 하는데, 없으면 생성 경로에서 음원을
    한 번 더 디코딩해야 한다. 이미 계산한 것을 버릴 이유가 없다.

    `as_record()`에는 넣지 않는다 — JSONL은 `chroma` 필드를 따로 쓰고 있고,
    형식을 바꾸면 기존 산출물과 갈린다.
    """

    def as_record(self) -> dict[str, object]:
        return {
            "key": str(self.key),
            "correlation": round(self.correlation, 4),
            "runner_up": str(self.runner_up),
            "margin": round(self.margin, 4),
        }


RELATIVE_OFFSET = {Mode.MAJOR: 9, Mode.MINOR: 3}
"""나란한조까지의 반음 거리. C장조의 나란한단조는 A단조(+9)다."""


BLACK_KEYS: frozenset[str] = frozenset({"C#", "D#", "F#", "G#", "A#"})
"""검은건반 으뜸음. O-23의 핵심 지표이며 **리포트에 반드시 찍는다** (D-0060).

실제 대중가요는 기타·피아노 친화적인 조에 몰려 검은건반 조가 드물다.
33.5%는 명백히 높으며, 그 값이 줄어드는지가 배음 감산의 성패를 가른다.

**지표를 만들어두고 보지 않은 것이 아니라 아예 만들지 않았다** — 교차표만
내고 합계를 안 찍어 손으로 더하고 있었다 (D-0030의 변형).
"""


def relative_key(key: Key) -> Key:
    """나란한조. 조표가 같아 구성음이 동일하다.

    **K-S가 원리적으로 구분하지 못하는 짝이다.** 2등이 나란한조인지 확인하면
    "애매함"이 원리적 한계인지 다른 문제인지 갈린다 — 나란한조 혼동이면 고칠
    수 없고, 엉뚱한 조가 2등이면 크로마 추출이나 프로파일 쪽 문제다.
    """
    other = Mode.MINOR if key.mode is Mode.MAJOR else Mode.MAJOR
    tonic = (key.tonic_pitch_class + RELATIVE_OFFSET[key.mode]) % 12
    return Key(tonic=PITCH_CLASSES[tonic], mode=other)


def random_baseline(
    count: int = 2000,
    seed: int = 20260818,
    *,
    profile: str = PROFILE_KRUMHANSL,
    harmonic: float = HARMONIC_STRENGTH,
) -> tuple[np.ndarray[tuple[int], np.dtype[np.float64]], ...]:
    """무작위 크로마의 (상관, 격차) 분포. **베이스라인이다** (D-0034).

    상관 0.87이나 격차 0.097이 큰 값인지는 하한을 알아야 판정된다.
    **지표를 추가할 때 베이스라인을 같이 넣지 않으면, 나중에 붙일 때는 이미
    그 지표로 판단을 내린 뒤다.**

    실측으로 확인된 것: 무작위 크로마도 상관 중앙값이 0.62에 이른다. 24개
    프로파일이 서로 닮아 아무 벡터나 넣어도 그중 하나와는 꽤 맞기 때문이다.
    **절대값만 보면 늘 좋아 보인다.**

    **`profile`을 반드시 함께 넘긴다** (D-0059). 하한은 프로파일마다 다르다 —
    Krumhansl 0.6192, Temperley 0.5488이다. 조건이 바뀌었는데 베이스라인이
    따라가지 않으면 비교가 성립하지 않고, **실제로 판정이 뒤집혔다.**

    디리클레 분포를 쓴다 — 합이 1인 12차원 벡터를 고르게 뽑는다. 균등난수를
    정규화하면 중앙으로 몰려 실제 크로마보다 평평해진다.
    """
    generator = np.random.default_rng(seed)
    samples = generator.dirichlet(np.ones(12), size=count)
    estimates = []
    for row in samples:
        # **감산도 무작위에 똑같이 적용한다** (D-0060). 코퍼스만 감산하고 하한을
        # 원본으로 두면 하한이 실제보다 높아 판별력이 낮게 보고된다. D-0059에서
        # 프로파일로 고친 것과 같은 결함을 같은 함수에서 다시 냈다.
        vector = subtract_harmonics(np.asarray(row, dtype=np.float64), harmonic)
        total = vector.sum()
        if total <= EPSILON:
            continue
        estimates.append(
            estimate_key(np.asarray(vector / total, dtype=np.float32), profile=profile)
        )
    return (
        np.asarray([item.correlation for item in estimates], dtype=np.float64),
        np.asarray([item.margin for item in estimates], dtype=np.float64),
    )


def _correlate(vector: np.ndarray, profile: np.ndarray) -> float:
    """피어슨 상관. 분모가 0이면 0을 낸다."""
    left = vector - vector.mean()
    right = profile - profile.mean()
    denominator = float(np.sqrt((left**2).sum() * (right**2).sum()))
    return float((left * right).sum() / denominator) if denominator > EPSILON else 0.0


def estimate_key(chroma_vector: np.ndarray, *, profile: str = PROFILE_KRUMHANSL) -> KeyEstimate:
    """크로마에서 조성을 추정한다 (Krumhansl-Schmuckler).

    24개 후보(12 으뜸음, 장단 각각) 전부와 상관을 재고 1·2등을 남긴다.
    동점이면 인덱스가 앞선 쪽이 이긴다 — 검색 지표의 argmax 규약과 같다.

    `profile`은 가중치 표를 고른다. 기본 `krumhansl`이 베이스라인이다.
    """
    if chroma_vector.shape != (12,):
        raise ValueError(f"크로마는 12차원이어야 한다: {chroma_vector.shape}")
    if profile not in PROFILES:
        raise ValueError(f"profile은 {PROFILE_NAMES} 중 하나여야 한다: {profile}")

    major_table, minor_table = PROFILES[profile]
    major = np.asarray(major_table, dtype=np.float64)
    minor = np.asarray(minor_table, dtype=np.float64)
    vector = np.asarray(chroma_vector, dtype=np.float64)

    scored: list[tuple[float, int, Key]] = []
    for tonic in range(12):
        rotated = np.roll(vector, -tonic)
        for order, (mode, weights) in enumerate(((Mode.MAJOR, major), (Mode.MINOR, minor))):
            key = Key(tonic=PITCH_CLASSES[tonic], mode=mode)
            scored.append((_correlate(rotated, weights), tonic * 2 + order, key))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best, second = scored[0], scored[1]
    return KeyEstimate(
        key=best[2],
        correlation=best[0],
        runner_up=second[2],
        margin=best[0] - second[0],
        chroma=tuple(float(value) for value in vector),
    )


AGGREGATE_MEAN = "mean"
AGGREGATE_MEDIAN = "median"
AGGREGATES = (AGGREGATE_MEAN, AGGREGATE_MEDIAN)

WINDOW_SECONDS = 10.0
"""창별 집계에서 창 하나의 길이. 대중가요 한 악절 정도다."""


def _split_windows(waveform: Waveform, sample_rate: int, window_seconds: float) -> list[Waveform]:
    """파형을 대략 같은 길이의 창으로 자른다.

    나머지를 따로 두지 않고 전체를 균등 분할한다. 끝에 짧은 조각이 남으면 그 창의
    크로마만 통계가 다르고, 중앙값이 그것에 끌린다.
    """
    if window_seconds <= 0.0:
        raise ValueError(f"창 길이는 0보다 커야 한다: {window_seconds}")
    size = int(waveform.shape[0])
    span = max(1, int(sample_rate * window_seconds))
    count = max(1, round(size / span))
    return [np.asarray(part) for part in np.array_split(waveform, count) if part.size > 0]


def chroma(
    waveform: Waveform,
    *,
    mode: str = CHROMA_CQ,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    tuning_cents: float = 0.0,
    gamma: float = LOG_GAMMA,
    harmonic: float = HARMONIC_STRENGTH,
    aggregate: str = AGGREGATE_MEAN,
    window_seconds: float = WINDOW_SECONDS,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """피치클래스 12차원 에너지. 합이 1이 되도록 정규화한다.

    기본은 `cq`(반음 격자)다. `linear`는 D-0056 이전 방식이며 **베이스라인
    비교용으로만 남긴다** — 저역에서 반음을 가르지 못한다.

    ### 집계 방식 (O-27)

    `mean`은 전곡을 한 번에 변환한다. 무음·간주·박수·페이드까지 전부 같은 무게로
    섞이고, **그런 구간은 음정이 없어 12칸에 고르게 퍼진 에너지를 낸다.** 곡의
    화성 정보가 균등 성분에 희석되는 경로다.

    `median`은 창마다 크로마를 뽑아 **성분별 중앙값**을 낸다. 창의 절반 넘게가
    음정이 없어야 중앙값이 평평해지므로, 소수의 잡음 구간이 전체를 끌어내리지
    못한다.

    **가설이지 사실이 아니다.** D-0063이 잰 달성 가능 폭 0.0187이 올라가는지로
    판정한다. 안 오르면 전곡 평균이 원인이 아니라는 뜻이고 `mean`으로 되돌린다.
    """
    if aggregate not in AGGREGATES:
        raise ValueError(f"aggregate는 {AGGREGATES} 중 하나여야 한다: {aggregate}")

    def once(segment: Waveform) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
        if mode == CHROMA_CQ:
            # **`harmonic`을 넘긴다.** 이전에는 인자를 받고도 `cq_chroma`에 넘기지
            # 않아 조용히 무시됐다 (D-0064). 기본값이 0.0이라 기록된 결과는 전부
            # 무효가 아니지만, `ingest keys --harmonic`은 아무 일도 하지 않았다.
            return cq_chroma(
                segment,
                sample_rate=sample_rate,
                tuning_cents=tuning_cents,
                gamma=gamma,
                harmonic=harmonic,
            )
        if mode == CHROMA_LINEAR:
            # 선형 경로는 배음 감산을 내장하지 않아 뒤에서 걸고 다시 정규화한다.
            reduced = subtract_harmonics(
                np.asarray(linear_chroma(segment, sample_rate=sample_rate), dtype=np.float64),
                harmonic,
            )
            total = float(reduced.sum())
            if total <= 0.0:
                return np.full(12, 1.0 / 12, dtype=np.float32)
            return np.asarray(reduced / total, dtype=np.float32)
        raise ValueError(f"mode는 {CHROMA_MODES} 중 하나여야 한다: {mode}")

    if aggregate == AGGREGATE_MEAN:
        return once(waveform)

    windows = _split_windows(waveform, sample_rate, window_seconds)
    stacked = np.stack([once(window) for window in windows])
    combined = np.median(stacked, axis=0)
    total = float(combined.sum())
    if total <= 0.0:
        return np.full(12, 1.0 / 12, dtype=np.float32)
    return np.asarray(combined / total, dtype=np.float32)


def estimate_key_from_waveform(
    waveform: StereoWaveform,
    *,
    mode: str = CHROMA_CQ,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    gamma: float = LOG_GAMMA,
    harmonic: float = HARMONIC_STRENGTH,
    profile: str = PROFILE_KRUMHANSL,
) -> KeyEstimate:
    return estimate_key(
        chroma(
            to_mono(waveform),
            mode=mode,
            sample_rate=sample_rate,
            gamma=gamma,
            harmonic=harmonic,
        ),
        profile=profile,
    )
