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

    total = totals.sum()
    if total <= EPSILON:
        return np.zeros(12, dtype=np.float32)
    return np.asarray(totals / total, dtype=np.float32)


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

    def as_record(self) -> dict[str, object]:
        return {
            "key": str(self.key),
            "correlation": round(self.correlation, 4),
            "runner_up": str(self.runner_up),
            "margin": round(self.margin, 4),
        }


RELATIVE_OFFSET = {Mode.MAJOR: 9, Mode.MINOR: 3}
"""나란한조까지의 반음 거리. C장조의 나란한단조는 A단조(+9)다."""


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
    count: int = 2000, seed: int = 20260818
) -> tuple[np.ndarray[tuple[int], np.dtype[np.float64]], ...]:
    """무작위 크로마의 (상관, 격차) 분포. **베이스라인이다** (D-0034).

    상관 0.87이나 격차 0.097이 큰 값인지는 하한을 알아야 판정된다.
    **지표를 추가할 때 베이스라인을 같이 넣지 않으면, 나중에 붙일 때는 이미
    그 지표로 판단을 내린 뒤다.**

    실측으로 확인된 것: 무작위 크로마도 상관 중앙값이 0.62에 이른다. 24개
    프로파일이 서로 닮아 아무 벡터나 넣어도 그중 하나와는 꽤 맞기 때문이다.
    **절대값만 보면 늘 좋아 보인다.**

    디리클레 분포를 쓴다 — 합이 1인 12차원 벡터를 고르게 뽑는다. 균등난수를
    정규화하면 중앙으로 몰려 실제 크로마보다 평평해진다.
    """
    generator = np.random.default_rng(seed)
    samples = generator.dirichlet(np.ones(12), size=count)
    estimates = [estimate_key(np.asarray(row, dtype=np.float32)) for row in samples]
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


def estimate_key(chroma_vector: np.ndarray) -> KeyEstimate:
    """크로마에서 조성을 추정한다 (Krumhansl-Schmuckler).

    24개 후보(12 으뜸음, 장단 각각) 전부와 상관을 재고 1·2등을 남긴다.
    동점이면 인덱스가 앞선 쪽이 이긴다 — 검색 지표의 argmax 규약과 같다.
    """
    if chroma_vector.shape != (12,):
        raise ValueError(f"크로마는 12차원이어야 한다: {chroma_vector.shape}")

    major = np.asarray(KRUMHANSL_MAJOR, dtype=np.float64)
    minor = np.asarray(KRUMHANSL_MINOR, dtype=np.float64)
    vector = np.asarray(chroma_vector, dtype=np.float64)

    scored: list[tuple[float, int, Key]] = []
    for tonic in range(12):
        rotated = np.roll(vector, -tonic)
        for order, (mode, profile) in enumerate(((Mode.MAJOR, major), (Mode.MINOR, minor))):
            key = Key(tonic=PITCH_CLASSES[tonic], mode=mode)
            scored.append((_correlate(rotated, profile), tonic * 2 + order, key))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best, second = scored[0], scored[1]
    return KeyEstimate(
        key=best[2],
        correlation=best[0],
        runner_up=second[2],
        margin=best[0] - second[0],
    )


def chroma(
    waveform: Waveform,
    *,
    mode: str = CHROMA_CQ,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    tuning_cents: float = 0.0,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """피치클래스 12차원 에너지. 합이 1이 되도록 정규화한다.

    기본은 `cq`(반음 격자)다. `linear`는 D-0056 이전 방식이며 **베이스라인
    비교용으로만 남긴다** — 저역에서 반음을 가르지 못한다.
    """
    if mode == CHROMA_CQ:
        return cq_chroma(waveform, sample_rate=sample_rate, tuning_cents=tuning_cents)
    if mode == CHROMA_LINEAR:
        return linear_chroma(waveform, sample_rate=sample_rate)
    raise ValueError(f"mode는 {CHROMA_MODES} 중 하나여야 한다: {mode}")


def estimate_key_from_waveform(
    waveform: StereoWaveform,
    *,
    mode: str = CHROMA_CQ,
    sample_rate: int = SOURCE_SAMPLE_RATE,
) -> KeyEstimate:
    return estimate_key(chroma(to_mono(waveform), mode=mode, sample_rate=sample_rate))
