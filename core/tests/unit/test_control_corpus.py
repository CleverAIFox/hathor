"""문턱을 재는 대조 코퍼스 (D-0460).

**D-0327이 문턱을 고르며 쓴 코퍼스가 커밋되지 않았다.** 그래서 D-0453이 쌍 수를
올렸을 때 그 문턱을 다시 못 걸었다 — 도구가 없으면 다시 재지 못하고, 다시 재지
못하면 **고른 적 있다는 사실만 남는다** (GR-0.7).

여기 시험은 **그 코퍼스가 대조 구실을 하는지**를 본다: 음성이 정말 교환가능한가,
양성이 정말 차용 칸만 흔드는가, 질량이 목표에 서는가.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.conftest import tool_module

TOOL = tool_module("control_corpus")

BORROWED = (3, 8, 10)
"""`mixture`가 더 보는 칸."""

CONTROL_CELLS = (1, 6, 11)
"""`control`이 더 보는 칸 — ♭2 · ♯4 · 이끔음 (D-0094)."""

DIATONIC = (0, 2, 4, 5, 7, 9)


def _spread(corpus: list[object], cells: tuple[int, ...]) -> float:
    """그 칸들의 **곡 간 로그 표준편차** 평균. 큰 값이 더 곡 고유하다."""
    stacked = np.log(np.asarray([item.prior for item in corpus], dtype=np.float64))  # type: ignore[attr-defined]
    return float(stacked[:, list(cells)].std(axis=0).mean())


def test_음성은_견주는_두_조가_교환가능하다() -> None:
    """**이것이 음성 대조의 전부다** — 다만 **열두 칸이 아니다** (D-0461).

    처음에 *«열두 칸이 교환가능하다»*로 적었고 **그것은 거짓이었다.** 온음계 칸을
    2.62배 밀었으니 당연히 안 같고, 실제로 로그 퍼짐이 8.8% 벌어진다. 10% 문턱이
    그 위에 아슬하게 앉아 **거짓을 참이라 증명하고 있었다.**

    재야 하는 것은 **`mixture`가 더 보는 `{3,8,10}`과 `control`이 더 보는
    `{1,6,11}`**이다. 둘 다 안 밀린 칸이고 **그 둘이 같아야** 차용 어휘가 이길
    까닭이 없다. 그 조를 재면 문턱이 헐겁지 않다.
    """
    for seed in range(8):
        corpus = TOOL.build(600, seed=seed, sigma=0.0)

        borrowed, control = _spread(corpus, BORROWED), _spread(corpus, CONTROL_CELLS)

        assert abs(borrowed - control) < 0.05 * control, (
            f"시드 {seed}: 차용 {borrowed:.4f} · 대조 {control:.4f}로 갈린다"
        )


def test_양성은_차용_칸만_흔든다() -> None:
    """**질 수 있는 자여야 한다** (O-25 (2) · D-0303). 음성만 있으면

    「아무것도 통과 안 시키는 문턱」이 가장 좋아 보인다 — D-0327이 `t>=3`을
    기각한 까닭이 바로 **양성 38%를 놓친다**였다.
    """
    corpus = TOOL.build(600, seed=5, sigma=0.9)

    diatonic, borrowed = _spread(corpus, DIATONIC), _spread(corpus, BORROWED)

    assert borrowed > diatonic * 1.5, f"양성인데 차용 {borrowed:.4f}가 안 흔들린다"


def test_흔들림이_질량을_밀지_않는다() -> None:
    """**심은 결함을 잡은 자리다** (D-0460).

    맨 `exp(sigma*z)`는 기댓값이 1이 아니라 `exp(sigma^2/2)`다. 0.9면 1.50배라
    차용 칸이 통째로 무거워지고 **양성의 온음계 질량이 음성보다 0.03 낮게 섰다.**
    두 대조가 다른 자에서 나오면 견줄 수가 없다 — D-0334가 *«퍼짐만 맞추고
    무게를 안 맞췄다»*로 잡은 것과 같은 부류다.
    """
    gaps = [
        abs(
            TOOL.diatonic_mass_of(TOOL.build(600, seed=seed, sigma=0.0))
            - TOOL.diatonic_mass_of(TOOL.build(600, seed=seed, sigma=0.9))
        )
        for seed in range(8)
    ]

    # **한 시드로 못 박으면 운으로 통과한다** (D-0461). 처음엔 시드 7 하나였고
    # 거기서 간격이 0.0016이었는데, 여덟 시드의 최대가 그 열 배 가까이 간다.
    assert max(gaps) < 0.02, f"질량 간격 최대 {max(gaps):.4f}"
    assert sum(gaps) / len(gaps) < 0.01, f"질량 간격 평균 {sum(gaps) / len(gaps):.4f}"


def test_평균_보존_흔들림이_1을_지킨다() -> None:
    """**양성 대조.** 위 시험만 있으면 흔들림을 0으로 두어도 통과한다."""
    rng = np.random.default_rng(3)
    draws = [TOOL._jitter(0.9, float(z)) for z in rng.standard_normal(20000)]

    assert abs(float(np.mean(draws)) - 1.0) < 0.05
    assert float(np.std(draws)) > 0.5, "흔들림이 0이면 이 자가 헛돈다"


@pytest.mark.parametrize("target", [0.4971, 0.7237])
def test_질량이_목표에_선다(target: float) -> None:
    """**D-0334가 잡은 결함이다.** 옛 합성은 0.4971, 실물은 0.7237이다.

    그 차이가 이득을 41% 움직였으므로(+0.0609 → +0.0358) **문턱도 거기서
    다시 걸어야 한다.**
    """
    corpus = TOOL.build(600, seed=11, sigma=0.0, diatonic_mass=target)

    assert abs(TOOL.diatonic_mass_of(corpus) - target) < 0.01


def test_기본_질량이_실물이다() -> None:
    """**합성을 실물에 맞춘다** — 맞춘 뒤 무엇이 나오는지는 모른다 (D-0058)."""
    assert TOOL.REAL_DIATONIC_MASS == 0.7237


def test_이웃_비례가_느슨함을_받는다() -> None:
    """**인자를 받는 척만 하고 있었다** (D-0461).

    `0.15`가 코드에 박혀 있어 `follow_sigma`를 흔들어도 코퍼스가 바이트까지 같았다.
    """
    tight = TOOL.build(200, seed=3, sigma=0.9, follows=True, follow_sigma=0.02)
    loose = TOOL.build(200, seed=3, sigma=0.9, follows=True, follow_sigma=0.60)

    assert [one.prior for one in tight] != [one.prior for one in loose]
    assert _spread(loose, BORROWED) > _spread(tight, BORROWED)


def test_말이_안_되는_입력을_막는다() -> None:
    """**조용히 도는 대조가 가장 나쁘다** — 수가 나오는데 뜻이 없다 (D-0230)."""
    with pytest.raises(ValueError, match="곡이 둘 이상"):
        TOOL.build(1, seed=1, sigma=0.0)
    with pytest.raises(ValueError, match="흔들림은 0 이상"):
        TOOL.build(10, seed=1, sigma=-0.5)
    with pytest.raises(ValueError, match="흔들림이 있어야"):
        TOOL.build(10, seed=1, sigma=0.0, follows=True)
    with pytest.raises(ValueError, match="0과 1 사이"):
        TOOL.mass_factor(1.0)


def test_같은_시드면_같은_코퍼스다() -> None:
    """**판정이 재현돼야 한다** (D-0009)."""
    first = TOOL.build(40, seed=2, sigma=0.9)
    second = TOOL.build(40, seed=2, sigma=0.9)

    assert [item.prior for item in first] == [item.prior for item in second]
