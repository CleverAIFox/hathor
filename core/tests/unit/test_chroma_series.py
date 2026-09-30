"""크로마 시계열의 단위 검사 (O-32 · D-0105).

**D-0104의 전제가 여기 걸려 있다** — 묶은 것과 처음부터 그 길이로 뽑은 것이 같아야
"짧게 뽑아 두고 묶는다"가 성립한다. **그것이 이 파일의 첫 검사다.**

### 그 검사가 제품이 안 쓰는 설정으로 돌고 있었다 (D-0319)

배음 감산을 **끄고** 쟀다. 켜면 x8 거리가 0.0129에서 **0.0812**로 벌어지고 문턱 0.02를
넘어서다. 문서 문자열이 그 수를 적어 두고 *"이 검사가 재는 것은 묶기의 충실도"*로
범위를 좁혔다 — **수를 보고 판정을 안 한 것이다.**

그리고 파형이 **순음 3화음**이었다. 배음도 강약도 없어 감산이 뺄 것이 거의 없다.

    자료            감산   x2      x4      x8
    순음            켬     0.0003  0.0002  0.0812
    배음+강약       켬     0.0078  0.0062  0.0313

**x4에서 0.0002와 0.0062는 30배 차이다.** 순음은 안심시키는 쪽으로 틀렸다 (O-25 (5)).

**그 결론도 틀렸다 (D-0322).** 실물 40곡에서 중앙 0.166~0.355 · 최대 0.585가 나왔다 —
**30~60배다.** 이 파형은 화음이 4초마다 바뀌어 **한 2초 창 안의 두 1초 창이 거의 같았고**
세기도 같았다. 실물은 창마다 내용과 세기가 바뀐다 — **실측 구조를 못 담은 자료였다**
(O-25 (5)).

창마다 바뀌는 파형을 더했다. **그것으로 재면 0.3이 나오므로 예측이 처음부터 달랐다.**
전제가 깨진 것과 그 원인 셋은 D-0322가 든다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE, Waveform
from hathor.domain.services.key_estimation import (
    HARMONIC_STRENGTH,
    chroma_series,
    group_series,
)

SR = SOURCE_SAMPLE_RATE


def _chord(seconds: float, roots: tuple[float, ...], seed: int = 3) -> Waveform:
    """화음이 `seconds`마다 바뀌는 합성 파형."""
    rng = np.random.default_rng(seed)
    parts = []
    for root in roots:
        count = int(seconds * SR)
        time = np.arange(count) / SR
        wave = sum(np.sin(2 * np.pi * root * 2 ** (k / 12) * time) for k in (0, 4, 7))
        parts.append((wave / np.abs(wave).max()).astype(np.float32))
    made = np.concatenate(parts)
    noise = rng.standard_normal(made.size).astype(np.float32) * 0.01
    return np.asarray(made + noise, dtype=np.float32)


# ------------------------------------------------------------------ 묶기


def _rich(seconds: float, roots: tuple[float, ...], seed: int = 3) -> Waveform:
    """배음·강약·잡음 바닥이 있는 파형 (D-0319).

    **순음으로는 감산이 뺄 것이 없다.** `subtract_harmonics`가 하는 일이 배음 몫을
    빼는 것이므로, 배음이 없는 자료에서 감산을 검증하면 아무것도 검증하지 않는다.
    """
    generator = np.random.default_rng(seed)
    parts = []
    for root in roots:
        count = int(seconds * SR)
        time = np.arange(count) / SR
        wave = np.zeros(count)
        for step in (0, 4, 7):
            pitch = root * 2 ** (step / 12)
            for overtone, weight in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.2), (5, 0.12), (6, 0.08)):
                wave += weight * np.sin(
                    2 * np.pi * pitch * overtone * time + generator.uniform(0.0, 2 * np.pi)
                )
        swell = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * time / (seconds * 2)))
        wave = wave * swell
        parts.append((wave / np.abs(wave).max()).astype(np.float32))
    made = np.concatenate(parts)
    noise = generator.standard_normal(made.size).astype(np.float32) * 0.05
    return np.asarray(made + noise, dtype=np.float32)


ROOTS = (220.0, 261.6, 196.0, 293.7, 246.9, 174.6, 207.7, 233.1)

PRODUCTION_CEILING = 0.01
"""제품이 쓰는 배수에서의 천장 (D-0319). **실측 최대 0.0078에 붙여 둔다.**

지표 규모가 0.2~0.6이므로 0.01은 그것의 2% 아래다. **느슨하게 두면 벌어지는 것을
못 본다** — 0.02였을 때 x8의 0.0812를 감산을 끄는 것으로 넘겼다.
"""

EIGHT_CEILING = 0.09
"""x8에서의 천장. **제품은 이 배수를 안 쓴다** (`GROUPS = (1, 2, 4)`).

순음에서 0.0812이고 배음 자료에서 0.0313이다. **쓰기 시작하면 이 수부터 판정한다** —
지표 규모의 1/3이라 무시할 수 없다.
"""


def _gaps(wave: Waveform, factor: int, *, harmonic: float | None = None) -> float:
    """묶은 것과 직접 뽑은 것의 전변동 거리 최대값.

    **`harmonic`을 안 주면 제품 기본값이 걸린다** — 그것이 이 검사의 요점이다 (D-0319).
    """
    strength = HARMONIC_STRENGTH if harmonic is None else harmonic
    grouped = group_series(chroma_series(wave, window_seconds=1.0, harmonic=strength), factor)
    direct = chroma_series(wave, window_seconds=float(factor), harmonic=strength)
    count = min(len(grouped), len(direct))
    assert count > 0
    return max(0.5 * float(np.abs(grouped[i] - direct[i]).sum()) for i in range(count))


def _shifting(seconds: float, roots: tuple[float, ...], seed: int = 3) -> Waveform:
    """**창마다 화음과 세기가 바뀌는 파형** (D-0322).

    `_chord`·`_rich`는 화음이 `seconds`마다 바뀐다 — `seconds=4.0`이면 한 2초 창 안의 두
    1초 창이 **거의 같다.** 실물은 그렇지 않고, 그 차이가 전제를 깼다.

    창 하나마다 화음을 바꾸고 **세기를 열 배 오르내린다.** 낮은 쪽이 0.1이다.
    """
    generator = np.random.default_rng(seed)
    parts = []
    for index, root in enumerate(roots):
        for step, level in ((0, 1.0), (3, 0.1)):
            pitch = roots[(index + step) % len(roots)] if step else root
            count = int(SR)
            time = np.arange(count) / SR
            wave = np.zeros(count)
            for tone in (0, 4, 7):
                base = pitch * 2 ** (tone / 12)
                for overtone, weight in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.2)):
                    wave += weight * np.sin(
                        2 * np.pi * base * overtone * time + generator.uniform(0.0, 2 * np.pi)
                    )
            wave = wave / np.abs(wave).max() * level
            noise = generator.standard_normal(count).astype(np.float32) * 0.02 * level
            parts.append((wave + noise).astype(np.float32))
    del seconds
    return np.asarray(np.concatenate(parts), dtype=np.float32)


SHIFTING_FLOOR = 0.2
"""창마다 바뀌는 파형에서의 **바닥** (D-0322).

실측 중앙이 0.166~0.355였고 이 합성이 0.3 규모를 낸다. **바닥으로 두는 이유는 이것이
「작아야 한다」가 아니라 「커야 한다」이기 때문이다** — 작아지면 이 자료가 실물 구조를
다시 못 담게 된 것이고, 그때 전제가 선다고 읽으면 D-0319를 되풀이한다.
"""


def test_창마다_바뀌면_전제가_깨진다():
    """**D-0319의 합성이 안심시킨 이유가 여기 있다** (D-0322 · O-25 (5)).

    화음이 4초마다 바뀌는 파형에서는 한 2초 창 안의 두 1초 창이 거의 같아 **묶기가
    거의 정확하다.** 실물은 창마다 바뀌고, 그것을 넣으면 거리가 30배 커진다.
    """
    shifting = _gaps(_shifting(1.0, ROOTS), 2)
    steady = _gaps(_rich(4.0, ROOTS), 2)
    assert shifting > SHIFTING_FLOOR, f"실물 구조를 못 담았다: {shifting:.4f}"
    assert shifting > steady * 10.0, "창마다 바뀌는 것이 원인이라는 것을 이 줄이 든다"


@pytest.mark.parametrize("factor", [2, 4])
@pytest.mark.parametrize("maker", [_chord, _rich], ids=["순음", "배음강약"])
def test_창_안이_같으면_묶기가_거의_정확하다(factor, maker):
    """**창 안의 두 창이 같을 때만 그렇다** (D-0319 · D-0322).

    **배음 감산을 켠 채로 잰다** — 제품이 그렇게 돈다. 끄고 재면 감산이 묶기와
    교환되는지를 안 보게 되고, 그것이 첫 판이 놓친 자리다.

    **이 수를 D-0104의 전제로 읽으면 안 된다.** 화음이 4초마다 바뀌는 파형이라 한 2초
    창 안의 두 1초 창이 거의 같다 — 실물은 그렇지 않고 거리가 0.3까지 간다 (D-0322).
    """
    found = _gaps(maker(4.0, ROOTS), factor, harmonic=None)
    assert found < PRODUCTION_CEILING, f"묶기가 어긋난다: {found:.4f}"


def test_쓰는_배수만_조인다():
    """**제품이 쓰는 배수와 조이는 배수가 같아야 한다** (D-0319).

    `GROUPS`에 8이 들어오면 이 검사가 깨진다 — 그때 `EIGHT_CEILING`부터 판정한다.
    `test_doc_commands`가 문서와 등재표를 대조하는 것과 같은 자리다.
    """
    from hathor.application.evaluate_chord_quality import GROUPS

    assert GROUPS == (1, 2, 4), "쓰는 배수가 바뀌었다. 위 검사의 배수도 함께 옮긴다"
    assert 8 not in GROUPS


@pytest.mark.parametrize("maker", [_chord, _rich], ids=["순음", "배음강약"])
def test_x8은_더_벌어진다_그리고_안_쓴다(maker):
    """**끄지 않고 수를 적는다** (D-0319 · GR-0.5).

    첫 판은 이 수가 문턱을 넘자 **감산을 껐다.** 값을 끄는 대신 배수를 갈랐다 —
    제품이 안 쓰는 배수이므로 천장이 다른 것이 정직하다.
    """
    found = _gaps(maker(4.0, ROOTS), 8, harmonic=None)
    assert found > PRODUCTION_CEILING, "x8이 x2·x4와 같으면 이 검사를 합친다"
    assert found < EIGHT_CEILING, f"x8이 더 벌어졌다: {found:.4f}"


def test_감산을_끄면_순음이_안심시킨다():
    """**순음은 감산을 검증하지 못한다** (O-25 (5) · D-0319).

    배음이 없으면 뺄 것이 없으므로 감산을 켜도 꺼도 거의 같다. 배음 자료에서는
    갈린다 — **그것이 순음으로 검증한 것이 무효인 이유다.**
    """
    pure = _chord(4.0, ROOTS)
    rich = _rich(4.0, ROOTS)
    assert _gaps(pure, 4, harmonic=0.0) == pytest.approx(_gaps(pure, 4, harmonic=None), abs=1e-3)
    assert _gaps(rich, 4, harmonic=None) > _gaps(pure, 4, harmonic=None) * 5.0


def test_묶으면_창이_그만큼_준다():
    series = chroma_series(_chord(1.0, (220.0,) * 12), window_seconds=1.0)
    assert len(group_series(series, 3)) == len(series) // 3


def test_묶은_창도_합이_1이다():
    series = chroma_series(_chord(1.0, (220.0,) * 8), window_seconds=1.0)
    grouped = group_series(series, 4)
    assert grouped.sum(axis=1) == pytest.approx(np.ones(len(grouped)), abs=1e-6)


def test_묶는_수가_0이면_거부한다():
    with pytest.raises(ValueError, match="1 이상"):
        group_series(np.zeros((4, 12), dtype=np.float32), 0)


def test_창보다_크게_묶으면_비운다():
    """**부분 창은 길이가 달라 평균에 다른 무게를 준다.** 남는 꼬리는 버린다."""
    assert len(group_series(np.zeros((3, 12), dtype=np.float32), 8)) == 0


# ------------------------------------------------------------------ 시계열


def test_창마다_합이_1이다():
    series = chroma_series(_chord(1.0, (220.0,) * 6), window_seconds=1.0)
    assert len(series) == 6
    assert series.sum(axis=1) == pytest.approx(np.ones(len(series)), abs=1e-6)


def test_화음이_바뀌면_창이_달라진다():
    """**시간 축이 살아 있어야 한다.** 전곡 평균은 그것을 지운다."""
    wave = _chord(2.0, (220.0, 311.1))
    series = chroma_series(wave, window_seconds=1.0)
    early = series[0]
    late = series[-1]
    assert 0.5 * float(np.abs(early - late).sum()) > 0.2


def test_짧은_파형은_빈_시계열이다():
    """**길이가 다른 창을 섞지 않는다.** 짧은 꼬리는 프레임이 적어 통계가 다르다."""
    tiny = np.zeros(int(0.1 * SR), dtype=np.float32)
    assert chroma_series(tiny, window_seconds=1.0).shape == (0, 12)


def test_꼬리를_버린다():
    """창 하나에 못 미치는 꼬리는 버린다. `group_series`와 같은 규칙이다."""
    wave = _chord(1.0, (220.0,) * 5)
    padded = np.concatenate([wave, np.zeros(int(0.4 * SR), dtype=np.float32)])
    assert len(chroma_series(padded, window_seconds=1.0)) == 5


def test_같은_파형은_같은_시계열을_낸다():
    wave = _chord(1.0, (220.0,) * 5)
    assert chroma_series(wave, window_seconds=1.0) == pytest.approx(
        chroma_series(wave, window_seconds=1.0)
    )
