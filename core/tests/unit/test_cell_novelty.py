"""잔차 퍼짐이 **`base`가 아는 몫**을 빼는가 (O-73 · D-0333).

D-0095의 `cell_spread`는 날것의 퍼짐이라 **다른 칸과 함께 움직이는 몫**을 못 뺀다.
실물에서 퍼짐은 큰데 어휘 이득이 0이었고(D-0327), 그 간극을 설명하려면 *"흔들리는가"*가
아니라 *"`base`가 이미 아는가"*를 물어야 한다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.cell_novelty import (
    NEGATIVE_GAP,
    POSITIVE_GAP,
    compare_cells,
    gap_of,
    novelty,
    reading,
    residual_spread,
)
from hathor.application.evaluate_harmony_output import ReferencePrior
from hathor.domain.value_objects.key import Mode

DEGREES = 12
DIATONIC = (0, 2, 4, 5, 7, 9)
BORROWED = (3, 8, 10)


NEIGHBOUR = {3: 2, 8: 7, 10: 9}
"""차용 칸과 **이웃한 온음계 칸**. 누설이라면 이 비율로 따라온다 (D-0091).

**공통 인자를 여러 칸에 싣는 식으로는 안 된다.** 12칸 중 9칸을 같이 올리면 합도 같이
올라 정규화에서 거의 상쇄된다 — 설명된 몫이 4.3%에 그쳤다. 비례 관계여야 로그
비율에 남는다.
"""


def _corpus(count: int, *, seed: int, sigma: float, follows: bool) -> list[ReferencePrior]:
    """`follows`면 차용 칸이 **이웃 온음계 칸에 비례**한다 — `base`가 이미 아는 모양이다."""
    rng = np.random.default_rng(seed)
    made: list[ReferencePrior] = []
    for index in range(count):
        shape = rng.dirichlet(np.full(DEGREES, 3.385))
        if sigma > 0.0:
            for cell in BORROWED:
                noise = float(rng.standard_normal())
                if follows:
                    shape[cell] = shape[NEIGHBOUR[cell]] * np.exp(0.15 * noise)
                else:
                    shape[cell] *= np.exp(sigma * noise)
        made.append(ReferencePrior(f"곡{index:03d}", tuple(float(v) for v in shape / shape.sum())))
    return made


def test_곡이_모자라면_거부한다() -> None:
    """**설명 변수보다 곡이 적으면 잔차가 0이 된다** — 완벽히 맞춘 것처럼 보인다 (GR-0.5)."""
    few = _corpus(5, seed=1, sigma=0.0, follows=False)
    with pytest.raises(ValueError, match="곡이 모자란다"):
        residual_spread(few, BORROWED, Mode.MAJOR)


def test_온음계로_설명되면_잔차가_줄어든다() -> None:
    """**이것이 이 자의 전부다.** 날퍼짐은 그대로인데 잔차만 줄어야 한다."""
    followed = _corpus(400, seed=3, sigma=0.9, follows=True)
    found = novelty(followed, BORROWED, Mode.MAJOR, "차용")

    assert found.residual_spread < found.raw_spread, "설명된 몫이 0이면 회귀가 안 걸린 것이다"
    assert found.explained > 0.1, f"온음계를 따라가는데 설명된 몫이 {found.explained:.1%}뿐이다"


def test_고유하게_흔들리면_잔차가_안_줄어든다() -> None:
    """**질 수 있는 자여야 한다** (O-25 (2)). 양방향으로 본다 (D-0303)."""
    own = _corpus(400, seed=3, sigma=0.9, follows=False)
    found = novelty(own, BORROWED, Mode.MAJOR, "차용")

    assert found.explained < 0.1, f"고유 변동인데 온음계가 {found.explained:.1%}를 설명했다"


def test_음성_코퍼스에서_두_묶음이_안_갈린다() -> None:
    """차용 칸이 안 흔들리면 대조 칸과 같아야 한다 — **음성 눈금이다.**"""
    flat = _corpus(400, seed=5, sigma=0.0, follows=False)
    borrowed, control = compare_cells(flat, Mode.MAJOR)

    assert abs(gap_of(borrowed, control)) < 0.05, "안 흔드는데 두 묶음이 갈렸다"


def test_양성_코퍼스에서_차용이_더_남는다() -> None:
    """차용 칸만 고유하게 흔들면 잔차가 벌어져야 한다 — **양성 눈금이다.**"""
    own = _corpus(400, seed=5, sigma=0.9, follows=False)
    borrowed, control = compare_cells(own, Mode.MAJOR)

    assert gap_of(borrowed, control) > 0.1, "고유 변동인데 잔차 차이가 안 벌어졌다"


def test_읽는_법이_셋을_가른다() -> None:
    """**사전 등록한 규칙이다** (D-0333). 실물을 재기 전에 적었다."""
    assert "base가 이미 안다" in reading(NEGATIVE_GAP)
    assert "가설이 틀렸다" in reading(POSITIVE_GAP)

    middle = reading((NEGATIVE_GAP + POSITIVE_GAP) / 2)
    assert "둘 다 아니다" in middle, "가운데를 둘 중 하나로 읽으면 안 된다"
    assert str(POSITIVE_GAP) in middle, "눈금을 화면에 들어야 읽는 사람이 판단한다"

    # **음수는 「base가 안다」의 더 강한 증거다** — 이웃 비례 코퍼스가 -0.383을 냈고
    # 거기서 이득이 0이었다. 그것을 «둘 다 아니다»로 읽으면 답을 놓친다.
    assert "base가 이미 안다" in reading(-0.383)
