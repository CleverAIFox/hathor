"""화음 품질 템플릿 적합 테스트 (O-64 · D-0300).

**세 가지를 고정한다.** (1) O-64 (닫힘 D-0305)가 적은 측정이 성립하지 않는다는 것, (2) 코사인
argmax에 화음수 편향이 있고 z 표준화가 그것을 내린다는 것, (3) 순환 회전이 품질 축의
귀무가 아니라는 것. 셋 다 실측한 수를 박는다 — 재현되지 않으면 여기가 깨져야 한다.
"""

import numpy as np
import pytest

from hathor.domain.services.harmony_quality import (
    _SEVENTH_ONLY,
    _TEMPLATES,
    DEGREE_COUNT,
    QUALITIES,
    TEMPLATE_NAMES,
    TRIAD_QUALITIES,
    null_windows,
    quality_share,
    rotated_windows,
    seventh_share,
    templates,
    verdicts,
    z_fit,
)

NULL_FLOOR = 0.5440
"""균등난수 2만 창(시드 3)에서 z 적합이 4음을 고르는 비율. **0.5가 아니다.**"""

COSINE_FLOOR = 0.8713
"""같은 자료에서 코사인 argmax가 4음을 고르는 비율. 이것이 z를 쓰는 이유다."""

WINDOWS = 20000
SEED = 3


def uniform() -> np.ndarray:
    return np.random.default_rng(SEED).random((WINDOWS, DEGREE_COUNT))


def chord(quality: str, *, count: int, noise: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """근음이 무작위인 화음 창. 잡음을 더해 완벽하지 않게 만든다."""
    generator = np.random.default_rng(seed)
    roots = generator.integers(0, DEGREE_COUNT, count)
    frame = np.zeros((count, DEGREE_COUNT))
    for index, root in enumerate(roots):
        for tone in QUALITIES[quality]:
            frame[index, (root + tone) % DEGREE_COUNT] = 1.0
    return frame + generator.random((count, DEGREE_COUNT)) * noise, roots


def test_다이어토닉_7음만_나오는_음정이_없다() -> None:
    """**O-64 (닫힘 D-0305)가 적은 측정이 성립하지 않는다.**

    *"7음 성분이 3화음 대비 얼마나 실리는지 재면"*이 원문이다. 장음계에서 7음으로
    쓰이는 음정 집합과 3화음으로 쓰이는 음정 집합이 **같으므로** 평균 크로마로는
    둘을 가를 수 없다. 이 시험이 초록이면 그 측정은 영원히 불가능하다.
    """
    assert _SEVENTH_ONLY == ()


def test_템플릿은_72개이고_이진이다() -> None:
    matrix, names = templates()
    assert matrix.shape == (len(QUALITIES) * DEGREE_COUNT, DEGREE_COUNT)
    assert len(names) == 72
    assert set(np.unique(matrix)) == {0.0, 1.0}
    assert len(set(names)) == len(names)
    # 정규화하지 않고 낸다 — z 표준화가 이진 지시자를 전제한다.
    assert matrix.sum(axis=1).min() == 3.0
    assert matrix.sum(axis=1).max() == 4.0


def test_코사인_argmax에_화음수_편향이_있다() -> None:
    """귀무 자료에서 자가 한쪽으로 기울어 있다 — **O-25가 일곱 번 겪은 부류다.**

    균등난수 크로마에는 화음 구조가 없으므로 품질 분포가 고를 이유가 없다. 코사인은
    4음을 0.87로 고른다. 이 시험은 **결함을 고정하는 시험이다** — 초록이어야 z를
    쓰는 이유가 서 있다.
    """
    frame = uniform()
    normalized = frame / np.linalg.norm(frame, axis=1, keepdims=True)
    unit = _TEMPLATES / np.linalg.norm(_TEMPLATES, axis=1, keepdims=True)
    picked = np.argmax(normalized @ unit.T, axis=1)
    four = float(np.mean([TEMPLATE_NAMES[index][1] not in TRIAD_QUALITIES for index in picked]))
    assert four == pytest.approx(COSINE_FLOOR, abs=5e-4)


def test_z_표준화가_편향을_내리되_없애지는_못한다() -> None:
    """0.8713 → 0.5440. **0.5가 아니다** — 그래서 절대 비율을 인용하지 않는다."""
    share = seventh_share(verdicts(uniform()))
    assert share == pytest.approx(NULL_FLOOR, abs=5e-4)
    assert share < COSINE_FLOOR
    assert share > 0.5


@pytest.mark.parametrize("quality", sorted(QUALITIES))
def test_깨끗한_화음은_품질과_근음을_맞춘다(quality: str) -> None:
    frame, roots = chord(quality, count=600, noise=0.3, seed=5)
    picked = verdicts(frame)
    assert len(picked) == 600
    assert all(name == quality for _, name, _ in picked)
    assert [root for root, _, _ in picked] == [int(value) for value in roots]


def test_순열_귀무는_에너지를_남기고_구조만_지운다() -> None:
    frame, _ = chord("dom7", count=2000, noise=0.6, seed=7)
    shuffled = null_windows(frame, seed=1)
    # 창마다 값 다중집합이 그대로다 — 총량·최댓값·분산이 실측과 같다.
    assert np.allclose(np.sort(frame, axis=1), np.sort(shuffled, axis=1))
    assert seventh_share(verdicts(frame)) > seventh_share(verdicts(shuffled))


def test_순환_회전은_품질_축의_귀무가_아니다() -> None:
    """**회전 귀무를 쓰면 차가 0으로 나오고, 그것을 «구조 없음»으로 읽으면 틀린다.**

    회전은 근음만 옮긴다. 품질 판정은 완전히 불변이며 근음만 같은 만큼 돌아간다.
    """
    frame, _ = chord("m7", count=500, noise=0.4, seed=9)
    before = verdicts(frame)
    after = verdicts(rotated_windows(frame, seed=1))
    assert [name for _, name, _ in before] == [name for _, name, _ in after]
    assert [round(score, 9) for _, _, score in before] == [round(score, 9) for _, _, score in after]


def test_평평한_창은_빠진다() -> None:
    """z가 전부 0인 창을 남기면 `argmax`가 표의 첫 항목(C maj)을 늘 고른다."""
    flat = np.ones((5, DEGREE_COUNT)) * 0.3
    assert z_fit(flat).max() == 0.0
    assert verdicts(flat) == ()
    assert quality_share(()) == {}


def test_꼴이_다른_행렬을_거부한다() -> None:
    with pytest.raises(ValueError, match="창 행렬"):
        z_fit(np.zeros((4, 7)))
    with pytest.raises(ValueError, match="창 행렬"):
        z_fit(np.zeros(DEGREE_COUNT))


def test_비율은_합이_1이고_빈_품질도_들어간다() -> None:
    frame, _ = chord("sus4", count=50, noise=0.2, seed=11)
    share = quality_share(verdicts(frame))
    assert set(share) == set(QUALITIES)
    assert sum(share.values()) == pytest.approx(1.0)
    assert share["sus4"] == pytest.approx(1.0)
