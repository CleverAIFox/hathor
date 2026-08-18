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

import numpy as np

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE, StereoWaveform, Waveform
from hathor.domain.value_objects.key import PITCH_CLASSES, Key, Mode

FFT_SIZE = 4096
"""MFCC(2048)보다 크다. 낮은 음의 피치클래스를 가르려면 주파수 해상도가 필요하다.
44.1kHz에서 2048이면 빈 간격이 21.5Hz라 저역 반음(C2~C#2는 8Hz 차이)이 뭉갠다."""

HOP_SIZE = 2048
MIN_HZ = 65.0
"""C2. 이보다 낮은 대역은 베이스 배음이 흐려 피치클래스 판정이 불안정하다."""

MAX_HZ = 2093.0
"""C7. 이 위는 배음이 지배해 근음 정보를 더하지 않는다."""

REFERENCE_A4 = 440.0
EPSILON = 1e-12

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


def chroma(
    waveform: Waveform,
    *,
    sample_rate: int = SOURCE_SAMPLE_RATE,
    fft_size: int = FFT_SIZE,
    hop_size: int = HOP_SIZE,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """피치클래스 12차원 에너지. 합이 1이 되도록 정규화한다.

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


def estimate_key_from_waveform(
    waveform: StereoWaveform, *, sample_rate: int = SOURCE_SAMPLE_RATE
) -> KeyEstimate:
    return estimate_key(chroma(to_mono(waveform), sample_rate=sample_rate))
