"""빠른 길이 느린 길과 **같은 수**를 내나 (D-0463).

이 파일의 요점은 시험 하나다 — `paired_distances`가 `run().line("paired")`와
**비트까지** 같은 거리를 낸다. 그 동일성이 깨지면 **느린 길로 모은 판과 빠른 길로
모은 판을 같이 못 센다**(GR-0.5). `probe_threshold`의 음성 대조가 바로 그 두 길에
걸쳐 모이고 있으므로 이것은 성능 시험이 아니라 **판정의 전제**다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.compare_output import VocabularyComparison, gap_of
from hathor.application.evaluate_harmony_output import (
    EvaluateHarmonyOutput,
    OutputCondition,
    ReferencePrior,
)
from hathor.application.paired_output import output_distances
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import Vocabulary

FAST = OutputCondition(seed_count=40, bar_count=8, pair_count=6)


def _corpus(count: int = 24, *, seed: int = 11) -> list[ReferencePrior]:
    """곡마다 다른 12차원 사전. **뾰족하게 뽑아 거리가 0에 안 깔리게 한다.**"""
    rng = np.random.default_rng(seed)
    rows = rng.dirichlet(np.ones(12) * 0.4, count)
    return [ReferencePrior(f"곡{index:03d}.flac", tuple(row)) for index, row in enumerate(rows)]


def test_빠른_길이_느린_길과_비트까지_같다() -> None:
    """**이 파일의 전부다.** `approx`가 아니라 `==`다 — 섞어 세려면 같은 수여야 한다."""
    corpus = _corpus()
    evaluator = EvaluateHarmonyOutput(FAST)

    fast = evaluator.paired_distances(corpus)
    slow = evaluator.run(corpus, "느린 길").line("paired").distances

    assert fast == slow


def test_그물이_비어_있지_않다() -> None:
    """**양성 대조** (D-0230 · D-0259). 둘 다 0만 내도 위 시험은 통과한다."""
    distances = EvaluateHarmonyOutput(FAST).paired_distances(_corpus())

    assert len(distances) == FAST.pair_count
    assert min(distances) > 0.0, "짝지은 거리가 전부 0이면 재는 것이 없다"
    assert len(set(distances)) > 1, "쌍마다 같은 수면 쌍을 안 보고 있다"


@pytest.mark.parametrize("word", ["base", "control", "mixture"])
def test_어휘를_바꿔도_두_길이_안_갈린다(word: str) -> None:
    """**어휘가 칸 수를 바꾼다** (D-0094). 히스토그램 폭이 달라지는 자리라 따로 건다."""
    from dataclasses import replace

    corpus = _corpus()
    evaluator = EvaluateHarmonyOutput(replace(FAST, vocabulary=Vocabulary(word)))

    assert (
        evaluator.paired_distances(corpus) == evaluator.run(corpus, word).line("paired").distances
    )


def test_시드를_밀면_수가_바뀐다() -> None:
    """`seed_offset`이 **빠른 길에서도** 닿는다 (D-0461).

    느린 길에서 안 닿던 것이 D-0461이 당한 결함이다. 길을 새로 내면서 **같은 구멍을
    다시 뚫지 않았는지**를 여기서 본다.
    """
    from dataclasses import replace

    corpus = _corpus()
    here = EvaluateHarmonyOutput(FAST).paired_distances(corpus)
    there = EvaluateHarmonyOutput(replace(FAST, seed_offset=5000)).paired_distances(corpus)

    assert here != there, "생성 시드를 밀었는데 거리가 그대로다 — 시드가 생성기에 안 닿는다"


def test_판정까지_같은_수가_나온다() -> None:
    """`probe_threshold`가 **실제로 읽는 수**에서 두 길이 같나.

    거리 목록이 같으면 `gap_of`도 같아야 하나, 탐침이 `VocabularyComparison`을 떼면서
    바꾼 것이 **이 줄**이므로 그 줄을 직접 건다 (D-0463).
    """
    from dataclasses import replace

    corpus = _corpus()
    reports = {
        word: EvaluateHarmonyOutput(replace(FAST, vocabulary=Vocabulary(word))).run(corpus, word)
        for word in ("base", "control", "mixture")
    }
    slow = VocabularyComparison(**reports)
    fast = gap_of(
        *(
            EvaluateHarmonyOutput(replace(FAST, vocabulary=Vocabulary(word))).paired_distances(
                corpus
            )
            for word in ("mixture", "control")
        )
    )

    assert fast.gain == slow.gain
    assert fast.standard_error == slow.standard_error
    assert fast.beats == slow.beats_control


def test_곡마다_시드를_다시_돈다() -> None:
    """**소진되는 반복자를 받으면 둘째 곡부터 빈 묶음이 된다.**

    `seeds`를 튜플로 굳히는 한 줄이 없으면 `zip(..., strict=True)`가 터지거나 — 더
    나쁘게 — 길이 0 평균이 `nan`으로 조용히 샌다.
    """
    corpus = _corpus(8)
    pairs = ((0, 1), (2, 3))
    key = Key(tonic="C", mode=Mode.MAJOR)

    lazy = output_distances(
        [item.prior for item in corpus], pairs, seeds=(n for n in range(20)), key=key
    )
    eager = output_distances([item.prior for item in corpus], pairs, seeds=range(20), key=key)

    assert lazy == eager
    assert not any(np.isnan(lazy))


def test_시드가_없으면_거부한다() -> None:
    """**잴 것이 없는 것을 거리 0이라 안 한다** (GR-0.5)."""
    corpus = _corpus(4)
    with pytest.raises(ValueError, match="시드가 없다"):
        output_distances(
            [item.prior for item in corpus],
            ((0, 1),),
            seeds=(),
            key=Key(tonic="C", mode=Mode.MAJOR),
        )


def test_곡을_쌍마다_다시_안_만든다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**생성이 쌍 수가 아니라 덮은 곡 수에 비례한다** (D-0454).

    이 캐시가 빠른 길의 값싼 까닭 절반이다. 없어도 수는 맞으므로 **수만 보는 시험은
    이것을 못 잡는다.**
    """
    from hathor.engines.compose.harmony_generator import generate_harmony

    calls: list[int] = []

    def counted(seed: int, *args: object, **kwargs: object) -> object:
        calls.append(seed)
        return generate_harmony(seed, *args, **kwargs)  # type: ignore[arg-type]

    # **점 이름으로 건다.** 모듈 객체에서 꺼내면 `paired_output`이 그 이름을 다시
    # 내보내지 않아 `--strict`가 운다 — 바꾸려는 자리는 그 모듈의 전역이 맞다.
    monkeypatch.setattr("hathor.application.paired_output.generate_harmony", counted)
    corpus = _corpus(8)
    # 곡 0이 세 쌍에 나온다 — 캐시가 없으면 생성이 세 배다.
    pairs = ((0, 1), (0, 2), (0, 3))
    output_distances(
        [item.prior for item in corpus], pairs, seeds=range(5), key=Key(tonic="C", mode=Mode.MAJOR)
    )

    assert len(calls) == 4 * 5, "덮은 곡 4개 × 시드 5개여야 한다"
