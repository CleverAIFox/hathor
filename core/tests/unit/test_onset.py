"""박·온셋의 단위 검사 (O-46 · D-0143).

**합성에서 참값을 회복하지 못하면 실측에 걸지 않는다** — D-0123이 반감점에서 쓴
순서와 같다. 이 파일이 그 관문이다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.services import chord_rhythm
from hathor.domain.services.chord_rhythm import BUNDLES, shuffled
from hathor.domain.services.onset import (
    PHASE_BINS,
    TEMPO_RANGE,
    WINDOW_SECONDS,
    band_edges,
    bands,
    beat_period,
    bundle_grid,
    envelope,
    event_scale,
    peaks,
    phase_profile,
    tempo_bpm,
)

HOP = 0.01


def synth(bpm, pattern=None, *, noise=0.0, seed=1, bars=32):
    """참 박이 있는 온셋 포락선. **참값을 아는 자료로 먼저 본다.**"""
    pattern = pattern or {0.0: 1.0}
    rng = np.random.default_rng(seed)
    period = 60.0 / bpm
    size = int(bars * 4 * period / HOP)
    found = np.zeros(size)
    for beat in range(int(size * HOP / period)):
        for phase, amplitude in pattern.items():
            index = int((beat + phase) * period / HOP)
            if index < size:
                found[index] = amplitude
    smeared = np.convolve(found, np.hanning(7), mode="same")
    return smeared + rng.normal(0.0, noise, size)


# ------------------------------------------------------------------ 박


@pytest.mark.parametrize("bpm", [72, 96, 120, 140])
def test_참_빠르기를_회복한다(bpm):
    """**격자 아래로 보간한다.** 안 하면 96을 96.77로 읽는다 (D-0143 실측)."""
    found = beat_period(synth(bpm), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - bpm) < 0.5


@pytest.mark.parametrize("bpm", [72, 96, 140])
def test_잡음에도_회복한다(bpm):
    found = beat_period(synth(bpm, noise=0.3), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - bpm) < 1.0


def test_배수_오류를_스스로_신고한다():
    """**배수 모호성은 결함이 아니라 성질이다** (D-0054와 같은 근거).

    120BPM에 잡음 0.3이면 절반을 고른다. 사람도 그렇게 짚을 수 있으며 **그 사실이
    사라지면 안 된다** — `octave_margin`이 낮게 나온다.
    """
    found = beat_period(synth(120, noise=0.3), HOP)
    assert found is not None
    assert found.octave_margin < 0.20


def test_길이로_나누지_않는다():
    """나누면 긴 지연이 밀려 올라간다 — 120BPM·잡음 0.1에서 60을 골랐다."""
    found = beat_period(synth(120, noise=0.1), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - 120) < 1.0


def test_무음이면_못_고른다():
    """**없는 것을 지어내지 않는다** (GR-0.5)."""
    assert beat_period(np.zeros(500), HOP) is None


def test_탐색_범위는_맞추는_값이_아니다():
    """좁히면 결과가 좋아 보이게 만들 수 있고 그것이 D-0058이다."""
    assert TEMPO_RANGE == (50.0, 200.0)


def test_너무_짧으면_거부한다():
    with pytest.raises(ValueError, match="너무 짧다"):
        beat_period([1.0, 0.0], HOP)


def test_홉이_양수여야_한다():
    with pytest.raises(ValueError, match="홉 길이"):
        beat_period(synth(96), 0.0)


def test_빠르기_환산():
    assert tempo_bpm(0.5) == 120.0
    with pytest.raises(ValueError, match="박 주기"):
        tempo_bpm(0.0)


# ------------------------------------------------------------------ 위상


def test_정박만_있으면_한_칸에_몰린다():
    found = beat_period(synth(96), HOP)
    assert found is not None
    profile = phase_profile(synth(96), found.period_seconds, HOP)
    assert max(profile) > 0.5
    assert sum(1 for value in profile if value == 0.0) >= 2


def test_뒤박이_섞이면_퍼진다():
    """**이 차이가 반주 리듬의 재료다.**"""
    envelope = synth(96, {0.0: 1.0, 0.5: 0.7})
    found = beat_period(envelope, HOP)
    assert found is not None
    profile = phase_profile(envelope, found.period_seconds, HOP)
    assert max(profile) < 0.5


def test_합이_1이다():
    found = beat_period(synth(96), HOP)
    assert found is not None
    assert sum(phase_profile(synth(96), found.period_seconds, HOP)) == pytest.approx(1.0)


def test_칸수는_박의_4분할이다():
    """`TICKS_PER_BEAT`가 이미 480으로 4분할을 담는다. **새 격자가 아니다.**"""
    assert PHASE_BINS == 4


def test_에너지가_없으면_균등이다():
    assert phase_profile(np.zeros(500), 0.5, HOP) == tuple([0.25] * 4)


def test_칸이_0이면_거부한다():
    with pytest.raises(ValueError, match="칸은 1 이상"):
        phase_profile(synth(96), 0.5, HOP, bins=0)


# ------------------------------------------------------------------ 포락선 (D-0144)

SR = 22050


def audio(bpm, pattern=None, *, seconds=30, noise=0.0, seed=1):
    """합성 음원. **참 박을 아는 자료로 관통을 본다.**"""
    pattern = pattern or {0.0: 1.0}
    rng = np.random.default_rng(seed)
    size = SR * seconds
    wave = np.zeros(size)
    period = 60.0 / bpm
    span = np.linspace(0.0, 0.03, int(SR * 0.03))
    click = np.exp(-np.linspace(0.0, 12.0, span.size)) * np.sin(2 * np.pi * 900 * span)
    for beat in range(int(seconds / period)):
        for phase, amplitude in pattern.items():
            index = int((beat + phase) * period * SR)
            if index + click.size < size:
                wave[index : index + click.size] += click * amplitude
    return wave + rng.normal(0.0, noise, size)


@pytest.mark.parametrize("bpm", [72, 96, 120, 140])
def test_음원에서_박까지_관통한다(bpm):
    """**파형 → 포락선 → 박.** 합성이 이 관문을 못 지나면 실측에 안 건다."""
    found = beat_period(envelope(audio(bpm), SR, HOP), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - bpm) < 1.0


def test_잡음이_섞여도_관통한다():
    found = beat_period(envelope(audio(120, noise=0.05), SR, HOP), HOP)
    assert found is not None
    assert abs(found.tempo_bpm - 120) < 1.0


def test_음원의_위상이_패턴을_가른다():
    plain = envelope(audio(96), SR, HOP)
    mixed = envelope(audio(96, {0.0: 1.0, 0.5: 0.7}), SR, HOP)
    straight = phase_profile(plain, beat_period(plain, HOP).period_seconds, HOP)
    offbeat = phase_profile(mixed, beat_period(mixed, HOP).period_seconds, HOP)
    assert max(straight) > max(offbeat)


def test_늘어난_몫만_센다():
    """**줄어든 몫을 빼면 소리가 잦아드는 자리도 온셋이 된다.**

    한 번 치고 천천히 꺼지는 소리를 넣는다. 봉우리는 **치는 순간 하나뿐이어야
    한다** — 꺼지는 동안 선속이 다시 오르면 절반이 잘못 세어진 것이다.
    """
    span = np.linspace(0.0, 2.0, SR * 2)
    struck = np.exp(-span * 3.0) * np.sin(2 * np.pi * 440 * span)
    found = envelope(struck, SR, HOP)
    peak = int(np.argmax(found))
    assert peak < len(found) // 4
    assert float(found[len(found) // 2 :].max()) < float(found.max()) * 0.1


def test_창은_홉을_따라오지_않는다():
    """**창은 주파수 해상도를 정한다** (D-0169).

    홉을 따라 움직이면 보고 격자를 바꿨을 뿐인데 재는 대상이 바뀐다 — D-0103이
    대각선을 버린 것과 같은 부류다. **기본 홉에서 값은 그대로다** (0.01 × 4).
    """
    assert WINDOW_SECONDS == 0.04


def test_홉을_바꿔도_포락선_길이만_바뀐다():
    """창이 고정이므로 **같은 구간을 더 촘촘히 볼 뿐이다.**"""
    wave = audio(120)
    assert len(envelope(wave, SR, HOP / 2)) > len(envelope(wave, SR, HOP)) * 1.9


def test_파형이_짧으면_거부한다():
    with pytest.raises(ValueError, match="너무 짧다"):
        envelope(np.zeros(100), SR, HOP)


def test_표본율이_양수여야_한다():
    with pytest.raises(ValueError, match="표본율"):
        envelope(np.zeros(SR), 0, HOP)


def test_스테레오는_거부한다():
    """**섞는 규칙을 여기서 정하지 않는다.** 어느 스템을 볼지는 부르는 쪽이 안다."""
    with pytest.raises(ValueError, match="1차원"):
        envelope(np.zeros((2, SR)), SR, HOP)


# ------------------------------------------------------------------ 봉우리 (D-0155)


def test_뒤박이_섞이면_두_칸에_선다():
    """**반주 리듬의 재료다.** 한 칸에 몰리면 정박, 두 칸이면 뒤박이 있다."""
    rng = np.random.default_rng(1)
    base = synth(120, {0.0: 1.0, 0.5: 0.7}, bars=50)
    noisy = base + np.abs(rng.normal(0.0, 0.1, base.size))
    found = beat_period(noisy, HOP)
    assert found is not None
    profile = phase_profile(noisy, found.period_seconds, HOP)
    assert sorted(profile)[-2] > 0.25


def test_바닥이_있어도_위상이_안_뭉개진다():
    """**실제 곡에는 노래와 지속음이 연속 에너지를 깔아 둔다.**

    평균만 빼면 그 바닥이 모든 위상에 고르게 들어가 분포가 평평해진다 — 20곡
    실측이 `0.257 · 0.247 · 0.247 · 0.250`이었다 (D-0154).
    """
    rng = np.random.default_rng(1)
    plain = synth(120, bars=50)
    noisy = plain + np.abs(rng.normal(0.0, 0.05, plain.size))
    found = beat_period(noisy, HOP)
    assert found is not None
    profile = phase_profile(noisy, found.period_seconds, HOP)
    assert max(profile) > 0.5


def test_발음은_봉우리다():
    """이웃보다 높은 칸만 고른다. **문턱은 없다.**"""
    found = peaks([0.0, 1.0, 0.0, 0.0, 2.0, 0.0])
    assert [index for index, _ in found] == [1, 4]


def test_해상도_한_칸에_하나다():
    """**이웃만 보면 잡음의 잔물결을 전부 센다** — 실측 5142개에 간격 3칸이었다."""
    values = [0.0, 1.0, 0.0, 3.0, 0.0, 1.0, 0.0] + [0.0] * 20
    assert [index for index, _ in peaks(values, apart=3)] == [3]


def test_잡음_바닥에서_봉우리가_줄어든다():
    """박 50칸에 봉우리 5142개면 **봉우리가 발음이 아니다** (D-0156)."""
    rng = np.random.default_rng(1)
    noisy = synth(120, bars=50) + np.abs(rng.normal(0.0, 0.1, synth(120, bars=50).size))
    dense = peaks(noisy)
    sparse = peaks(noisy, apart=12)
    assert len(sparse) < len(dense) / 2


def test_바닥_위_높이를_무게로_쓴다():
    found = dict(peaks([1.0, 3.0, 1.0, 1.0, 5.0, 1.0]))
    assert found[4] > found[1]


def test_바닥_아래는_봉우리가_아니다():
    """중앙값 아래로 솟은 것은 발음이 아니다."""
    assert peaks([5.0, 5.0, 0.0, 1.0, 0.0, 5.0, 5.0]) == []


def test_짧으면_봉우리가_없다():
    assert peaks([1.0, 2.0]) == []


# ------------------------------------------------------------------ 대역 (O-47 · D-0170)


def mixed(bpm, *, spacing=None, seconds=40, noise=0.02, drone=0.3, seed=1):
    """음색이 사건마다 바뀌는 합성 음원.

    **대역 분포가 사건마다 달라야 반감점이 뜻을 갖는다.** 지속 베이스를 깔아
    실제 곡의 연속 에너지를 흉내 낸다 — D-0155가 그것에 당했다.
    """
    rng = np.random.default_rng(seed)
    size = SR * seconds
    wave = np.zeros(size)
    step = spacing if spacing is not None else 60.0 / bpm

    def hit(freq, decay, length=0.12):
        span = np.linspace(0.0, length, int(SR * length))
        return np.exp(-np.linspace(0.0, decay, span.size)) * np.sin(2 * np.pi * freq * span)

    voices = [hit(60, 8.0), hit(700, 10.0), hit(3000, 18.0, 0.06)]
    for count in range(int(seconds / step)):
        index = int(count * step * SR)
        voice = voices[count % 3]
        if index + voice.size < size:
            wave[index : index + voice.size] += voice
    span = np.arange(size) / SR
    wave += drone * np.sin(2 * np.pi * 110 * span)
    return wave + rng.normal(0.0, noise, size)


def test_대역은_옥타브다():
    """**밖에서 온 격자다** — 12반음이 한 옥타브인 것과 같은 부류다."""
    frequencies = np.fft.rfftfreq(round(WINDOW_SECONDS * SR), 1.0 / SR)
    edges = band_edges(frequencies, SR)
    assert edges
    assert all(high / low == pytest.approx(2.0) for low, high in edges)
    assert edges[-1][1] == pytest.approx(SR / 2.0)


def test_대역_수가_홉에_안_흔들린다():
    """창이 고정이므로 대역도 고정이다 (D-0169).

    창이 홉을 따라오던 때는 같은 곡에서 **9개와 8개**가 나왔고, 그러면 두 홉의
    뾰족함을 나란히 놓을 수 없다.
    """
    wave = mixed(120)
    assert bands(wave, SR, HOP).shape[1] == bands(wave, SR, HOP / 2).shape[1]


def test_사건_길이가_격자에_안_흔들린다():
    """**사전 등록 예측이다** (D-0170). 발음 간격은 같은 자리에서 0.500이었다 (D-0166).

    홉을 반으로 줄여도 값이 안 바뀌어야 한다. 바뀌면 O-47(D-0173으로 닫힘)의
    우회로가 또 막힌 것이다.
    """
    wave = mixed(120)
    coarse = event_scale(bands(wave, SR, HOP), HOP)
    fine = event_scale(bands(wave, SR, HOP / 2), HOP / 2)
    assert coarse is not None
    assert fine is not None
    assert abs(fine / coarse - 1.0) < 0.05


def test_시간_순서에서_온다():
    """뒤섞으면 짧아진다. **귀무 대조를 먼저 돌린다** (D-0086 · O-25 (5))."""
    series = bands(mixed(120), SR, HOP)
    real = event_scale(series, HOP)
    null = event_scale(shuffled(series), HOP)
    assert real is not None
    assert null is not None
    assert real > null * 1.2


def test_창보다_짧으면_못_잰_것이다():
    """**창 길이보다 짧은 값은 사건이 아니다** (D-0170).

    잴 수 있는 가장 짧은 길이가 창이며 그보다 아래는 바닥이다. 문턱을 고른 것이
    아니라 **분해능이 그렇다.** 백색잡음 0.014초 · 지속음만 0.035초로 둘 다 창
    아래이고, 사건이 있는 곡은 0.071초다.
    """
    rng = np.random.default_rng(3)
    span = np.arange(SR * 20) / SR
    noise_only = event_scale(bands(rng.normal(0.0, 1.0, SR * 20), SR, HOP), HOP)
    drone_only = event_scale(
        bands(
            0.3 * np.sin(2 * np.pi * 110 * span) + 0.02 * rng.normal(0.0, 1.0, span.size), SR, HOP
        ),
        HOP,
    )
    played = event_scale(bands(mixed(120), SR, HOP), HOP)
    assert noise_only is not None
    assert drone_only is not None
    assert played is not None
    assert noise_only < WINDOW_SECONDS
    assert drone_only < WINDOW_SECONDS
    assert played > WINDOW_SECONDS * 1.5


def test_간격보다_길이에_붙어_있다():
    """**간격을 재는 값이 아니다.**

    간격을 8배 좁혀도 값은 1.5배 안쪽에서 움직인다 — 감쇠 시간이 지배한다.
    `apart`의 자리에는 맞을 수 있으나 **간격으로 읽으면 안 된다.**
    """
    wide = event_scale(bands(mixed(0, spacing=1.0), SR, HOP), HOP)
    tight = event_scale(bands(mixed(0, spacing=0.125), SR, HOP), HOP)
    assert wide is not None
    assert tight is not None
    assert 1.0 < wide / tight < 1.5


def test_대역_시계열은_2차원이어야_한다():
    with pytest.raises(ValueError, match="2차원"):
        event_scale(np.zeros(100), HOP)


def test_사건_길이도_홉이_양수여야_한다():
    with pytest.raises(ValueError, match="홉 길이"):
        event_scale(np.zeros((100, 4)), 0.0)


# ------------------------------------------------------------------ 묶음 격자 (D-0171)


def held(hold, *, seconds=60, noise=0.02, seed=1):
    """`hold`초마다 음색이 바뀌는 지속음. **사건 길이를 아는 자료다.**"""
    rng = np.random.default_rng(seed)
    size = SR * seconds
    wave = np.zeros(size)
    span = np.arange(size) / SR
    for count in range(int(seconds / hold)):
        start, end = int(count * hold * SR), min(size, int((count + 1) * hold * SR))
        freq = [110, 165, 220, 330][count % 4]
        wave[start:end] += np.sin(2 * np.pi * freq * span[start:end])
        wave[start:end] += 0.5 * np.sin(2 * np.pi * 3 * freq * span[start:end])
    return wave + rng.normal(0.0, noise, size)


def test_격자는_새로_고른_것이_아니다():
    """`BUNDLES`는 **2의 거듭제곱과 그 1.5배**이고 같은 규칙을 이을 뿐이다."""
    grid = bundle_grid(100_000)
    assert grid[: len(BUNDLES)] == BUNDLES
    assert grid[len(BUNDLES) : len(BUNDLES) + 4] == (96, 128, 192, 256)


def test_상한은_곡이_정한다():
    """묶음이 둘은 나와야 반감점을 보간한다. **고른 값이 없다.**"""
    assert max(bundle_grid(40)) <= 20
    assert max(bundle_grid(4000)) <= 2000
    assert bundle_grid(0) == (1,)


def test_긴_사건을_놓치지_않는다():
    """`BUNDLES` 상한 64는 **칸이지 초가 아니다** (D-0171).

    홉 0.01에서 0.64초이고 그보다 긴 사건은 반이 안 내려와 `None`이 됐다. 실측
    39곡에서 홉 0.005가 7곡밖에 못 잰 것이 그 탓이었다.
    """
    for hold in (0.8, 1.5, 3.0):
        found = event_scale(bands(held(hold), SR, HOP), HOP)
        assert found is not None, f"{hold}초 사건을 못 쟀다"
        assert found > WINDOW_SECONDS


def test_긴_사건도_격자에_안_흔들린다():
    """격자 무관이 **전 범위로** 간다. 늘리기 전에는 아래쪽에서만 확인됐다."""
    wave = held(1.5)
    coarse = event_scale(bands(wave, SR, HOP), HOP)
    fine = event_scale(bands(wave, SR, HOP / 2), HOP / 2)
    assert coarse is not None
    assert fine is not None
    assert abs(fine / coarse - 1.0) < 0.05


def test_이미_재던_값은_안_바뀐다():
    """격자를 늘린 것이 **값을 옮기지 않는다.**

    짧은 사건은 `BUNDLES` 안에서 이미 반을 지나므로 뒤를 이어도 같은 자리에서
    끊긴다. 안 그러면 D-0171이 옛 수치를 전부 무효로 만든다.
    """
    series = bands(held(0.3), SR, HOP)
    old = chord_rhythm.measure(series)
    new = event_scale(series, HOP)
    assert old is not None
    assert new is not None
    assert abs(new / (old * HOP) - 1.0) < 0.01
