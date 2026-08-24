"""출력 차이 측정의 단위 검사 (O-29 · D-0079).

**양성 대조와 음성 대조를 둘 다 둔다.** 하네스가 "정보 있음"을 낼 수 있다는 것만
확인하면 늘 통과하는 하네스와 구분되지 않는다 — D-0062가 같은 자리에서 한 것이다.

그리고 **사전을 무시하는 생성기를 끼워 넣어 하네스가 빨갛게 뜨는지 본다.**
아무것도 못 잡는 검사는 이길 수 없는 지표와 같다 (GR-0.9).
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application import evaluate_harmony_output as module
from hathor.application.evaluate_harmony_output import (
    EvaluateHarmonyOutput,
    OutputCondition,
    ReferencePrior,
    SourceComparison,
    degree_histogram,
    sweep_bar_counts,
    total_variation,
    weight_distance,
)
from hathor.domain.value_objects.key import Key, Mode

DEGREES = 12
FAST = OutputCondition(seed_count=120, bar_count=8, pair_count=12)


def _references(count: int, *, contrast: float, seed: int = 7) -> list[ReferencePrior]:
    """곡마다 다른 도수 사전. `contrast`가 클수록 균등에서 멀다."""
    rng = np.random.default_rng(seed)
    made: list[ReferencePrior] = []
    for index in range(count):
        shape = rng.dirichlet(np.full(DEGREES, 0.6))
        mixed = (1.0 - contrast) * np.full(DEGREES, 1.0 / DEGREES) + contrast * shape
        made.append(
            ReferencePrior(f"곡{index:03d}.flac", tuple(float(v) for v in mixed / mixed.sum()))
        )
    return made


def _identical(count: int) -> list[ReferencePrior]:
    """전부 같은 사전. **곡 고유성이 0인 음성 대조다.**"""
    shape = np.random.default_rng(3).dirichlet(np.full(DEGREES, 0.6))
    prior = tuple(float(v) for v in shape)
    return [ReferencePrior(f"곡{index:03d}.flac", prior) for index in range(count)]


# ------------------------------------------------------------------ 계량


def test_히스토그램은_합이_1이고_등장하지_않은_도수는_0이다():
    histogram = degree_histogram(("I", "I", "IV"), Mode.MAJOR)
    assert histogram.sum() == pytest.approx(1.0)
    assert histogram[0] == pytest.approx(2 / 3)


def test_같은_진행의_거리는_0이다():
    left = degree_histogram(("I", "IV", "V"), Mode.MAJOR)
    assert total_variation(left, left) == pytest.approx(0.0)


def test_겹치지_않는_진행의_거리는_1이다():
    left = degree_histogram(("I", "I"), Mode.MAJOR)
    right = degree_histogram(("vi", "vi"), Mode.MAJOR)
    assert total_variation(left, right) == pytest.approx(1.0)


def test_전변동에_마디_수를_곱하면_옮겨야_하는_마디_수다():
    left = degree_histogram(("I", "I", "I", "IV"), Mode.MAJOR)
    right = degree_histogram(("I", "I", "IV", "IV"), Mode.MAJOR)
    assert total_variation(left, right) * 4 == pytest.approx(1.0)


def test_가중치_거리는_생성기가_쓰는_함수를_그대로_쓴다():
    """비음계음만 다른 두 사전은 **가중치 거리가 0이어야 한다.**

    생성기는 다이어토닉 6도수만 보므로 나머지 6칸의 차이는 출력에 닿지 않는다.
    여기서 6도수 정규화를 다시 구현하면 생성기와 어긋나고, **어긋나도 아무도
    모른다.**
    """
    left = [1.0] * DEGREES
    right = [1.0] * DEGREES
    right[1] = 50.0  # 단2도는 장조 다이어토닉 근음이 아니다
    assert weight_distance(tuple(left), tuple(right), Mode.MAJOR) == pytest.approx(0.0)


# ------------------------------------------------------------------ 조건 객체


@pytest.mark.parametrize(
    "field,value",
    [("seed_count", 0), ("bar_count", 0), ("pair_count", 0)],
)
def test_조건은_표본_크기를_검사한다(field, value):
    with pytest.raises(ValueError):
        OutputCondition(**{field: value})


def test_같은_시드는_같은_쌍을_낸다():
    harness = EvaluateHarmonyOutput(FAST)
    assert harness.pair_indices(40) == harness.pair_indices(40)


def test_다른_시드는_다른_쌍을_낸다():
    from dataclasses import replace

    first = EvaluateHarmonyOutput(FAST).pair_indices(40)
    second = EvaluateHarmonyOutput(replace(FAST, seed=FAST.seed + 1)).pair_indices(40)
    assert first != second


# ------------------------------------------------------------------ 하네스 자체


def test_같은_사전_두_번은_정확히_0이다():
    """**시드가 짝지어지므로 바닥이 표집 잡음에 흔들리지 않는다.**"""
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    line = report.line("identical")
    assert line.mean_distance == 0.0
    assert line.mean_mismatch == 0.0
    assert line.mean_limit == 0.0


@pytest.mark.parametrize("mode", [Mode.MAJOR, Mode.MINOR])
def test_한_도수_몰빵_쌍은_상한_1이다(mode):
    """**선법마다 확인한다.** 장조 기준으로 도수를 박으면 단조에서는 다이어토닉

    근음이 아니라 가중치가 전부 0이 되고, `degree_weights`가 균등으로 되돌려
    **상한선이 조용히 1.0이 아니게 된다.** 실제로 그렇게 짰다가 잡았다.
    """
    from dataclasses import replace

    condition = replace(FAST, key=Key(tonic="C", mode=mode))
    report = EvaluateHarmonyOutput(condition).run(_references(20, contrast=0.9), "test")
    assert report.line("onehot").mean_distance == pytest.approx(1.0)
    assert report.is_harness_sound


def test_사전을_무시하는_생성기를_끼우면_하네스가_빨갛게_뜬다(monkeypatch):
    """**일부러 결함을 되살린다** (GR-0.9).

    사전을 무시하는 생성기에서는 어떤 사전 쌍도 같은 진행을 내므로 상한선이
    무너지고 `paired`가 0이 된다. 이 검사가 통과하지 않으면 나머지 검사가
    "늘 통과하는 하네스"인지 알 수 없다.
    """
    from hathor.engines.compose.harmony_generator import generate_harmony as real

    def ignores_prior(seed, key, bar_count=4, *, prior=None, vocabulary=None):
        return real(seed, key, bar_count, prior=None)

    monkeypatch.setattr(module, "generate_harmony", ignores_prior)
    report = EvaluateHarmonyOutput(FAST).run(_references(20, contrast=0.9), "test")
    assert report.line("paired").mean_distance == 0.0
    assert report.line("onehot").mean_distance == 0.0
    assert not report.is_harness_sound
    assert not report.is_output_conditioned


# ------------------------------------------------------------------ 판정


def test_곡마다_사전이_다르면_출력이_갈린다():
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    paired = report.line("paired")
    assert paired.mean_distance > 0.0
    assert paired.positive_share > 0.5
    assert report.is_output_conditioned


def test_사전이_전부_같으면_정보_없음을_낸다():
    """**음성 대조.** 참조곡을 바꿔도 사전이 같으면 출력이 바뀔 이유가 없다."""
    report = EvaluateHarmonyOutput(FAST).run(_identical(30), "test")
    assert report.line("paired").mean_distance == 0.0
    assert not report.is_output_conditioned


def test_무작위_사전_쌍이_실측보다_느슨하다():
    """`random`은 단체 위 균등분포라 실측보다 훨씬 뾰족하다. 귀무선이 실측에 지면

    사전이 아니라 지표나 배관을 의심해야 한다 — 판정 규칙 3항이 그것이다.
    """
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    assert report.line("paired").mean_distance < report.line("random").mean_distance


# ------------------------------------------------------------------ 극한과 마디 수


def test_8마디_실측은_극한보다_크다():
    """**초과분은 전달된 정보가 아니라 유한 표본의 되튐이다.**"""
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    paired = report.line("paired")
    assert paired.mean_distance > paired.mean_limit > 0.0


def test_마디_수를_늘리면_실측이_극한으로_내려간다():
    """**"8마디는 표본이 아니다"가 사실인지 여기서 갈린다** (D-0078)."""
    rows = sweep_bar_counts(_references(20, contrast=0.9), (8, 32, 128), FAST)
    observed = [value for _, value, _ in rows]
    limits = {round(value, 9) for _, _, value in rows}
    assert len(limits) == 1, "극한은 마디 수와 무관해야 한다"
    assert observed[0] > observed[1] > observed[2] >= rows[0][2]


# ------------------------------------------------------------------ 출처 비교


def test_대비가_큰_사전이_출력을_더_갈라놓는다():
    """O-29의 본문. **같은 쌍·같은 시드로 짝지어 센다.**"""
    harness = EvaluateHarmonyOutput(FAST)
    flat = harness.run(_references(30, contrast=0.35), "mix")
    peaky = harness.run(_references(30, contrast=0.95), "other")
    comparison = SourceComparison(baseline=flat, target=peaky)
    assert comparison.gain > 0.0
    assert comparison.limit_gain > 0.0
    assert comparison.win_rate > 0.5
    assert comparison.transmits_prior_contrast


def test_같은_사전이면_전달_이득이_없다():
    harness = EvaluateHarmonyOutput(FAST)
    left = harness.run(_references(30, contrast=0.9), "a")
    right = harness.run(_references(30, contrast=0.9), "b")
    assert SourceComparison(baseline=left, target=right).gain == pytest.approx(0.0)
    assert not SourceComparison(baseline=left, target=right).transmits_prior_contrast


def test_곡_집합이_다르면_짝지은_비교를_거부한다():
    """**곡이 다르면 출처 차이인지 쌍 차이인지 갈리지 않는다** (D-0033)."""
    harness = EvaluateHarmonyOutput(FAST)
    left = harness.run(_references(30, contrast=0.9), "a")
    right = harness.run(_references(20, contrast=0.9), "b")
    with pytest.raises(ValueError, match="참조곡 수가 다르다"):
        SourceComparison(baseline=left, target=right)


def test_조건이_다르면_짝지은_비교를_거부한다():
    from dataclasses import replace

    left = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "a")
    right = EvaluateHarmonyOutput(replace(FAST, bar_count=16)).run(
        _references(30, contrast=0.9), "b"
    )
    with pytest.raises(ValueError, match="조건이 다르다"):
        SourceComparison(baseline=left, target=right)


# ------------------------------------------------------------------ 입력 검사


def test_사전이_12차원이_아니면_거부한다():
    with pytest.raises(ValueError, match="12차원"):
        ReferencePrior("곡.flac", (0.1,) * 11)


def test_참조곡이_둘_미만이면_거부한다():
    with pytest.raises(ValueError, match="2개 이상"):
        EvaluateHarmonyOutput(FAST).run(_references(1, contrast=0.9), "test")


def test_없는_비교선을_찾으면_거부한다():
    report = EvaluateHarmonyOutput(FAST).run(_references(20, contrast=0.9), "test")
    with pytest.raises(KeyError):
        report.line("없는선")


# ------------------------------------------------------------------ 어휘 (O-36 · D-0094)


def test_기본_어휘는_기존_동작과_같다():
    """**기존 산출물이 안 바뀐다.** 어휘를 더해도 기본값은 6도수다."""
    from hathor.engines.compose.harmony_generator import Vocabulary, generate_harmony

    key = Key(tonic="C", mode=Mode.MAJOR)
    assert (
        generate_harmony(7, key, 8).degrees
        == generate_harmony(7, key, 8, vocabulary=Vocabulary.BASE).degrees
    )


@pytest.mark.parametrize("vocabulary,expected", [("base", 6), ("mixture", 9), ("control", 9)])
def test_어휘마다_칸_수가_다르다(vocabulary, expected):
    from hathor.engines.compose.harmony_generator import Vocabulary, vocabulary_roots

    assert len(vocabulary_roots(Mode.MAJOR, Vocabulary(vocabulary))) == expected


def test_차용_어휘의_근음은_삼총사와_같다():
    """**D-0093이 잰 칸이 그대로 근음이다** — 그래서 근음만으로 들어간다."""
    from hathor.engines.compose.harmony_generator import (
        BORROWED_ROOT_SEMITONES,
        MODAL_MIXTURE_CELLS,
    )

    assert BORROWED_ROOT_SEMITONES[Mode.MAJOR] == MODAL_MIXTURE_CELLS


def test_대조군은_차용_어휘와_칸_수가_같다():
    """**칸 수가 다르면 대조가 아니다.** 늘어난 칸만으로 거리가 오른다."""
    from hathor.engines.compose.harmony_generator import Vocabulary, vocabulary_roots

    assert len(vocabulary_roots(Mode.MAJOR, Vocabulary.MIXTURE)) == len(
        vocabulary_roots(Mode.MAJOR, Vocabulary.CONTROL)
    )
    assert not set(vocabulary_roots(Mode.MAJOR, Vocabulary.MIXTURE)) & {1, 6, 11}


def test_어휘를_넓히면_아무것도_안_배워도_거리가_오른다():
    """**대조군이 필요한 이유다** (D-0094). 이 검사가 그것을 고정한다."""
    from dataclasses import replace

    from hathor.engines.compose.harmony_generator import Vocabulary

    made = _references(30, contrast=0.9)
    base = EvaluateHarmonyOutput(FAST).run(made, "base")
    control = EvaluateHarmonyOutput(replace(FAST, vocabulary=Vocabulary.CONTROL)).run(
        made, "control"
    )
    assert control.line("paired").mean_distance > base.line("paired").mean_distance


def test_단조에는_차용_어휘가_없다():
    """**D-0093은 장조만 쟀다. 재지 않은 것을 넣지 않는다** (GR-0.5)."""
    from hathor.engines.compose.harmony_generator import Vocabulary, vocabulary_roots

    assert vocabulary_roots(Mode.MINOR, Vocabulary.MIXTURE) == vocabulary_roots(
        Mode.MINOR, Vocabulary.BASE
    )


def test_극한이_어휘마다_다르다():
    """**`--vocabulary`가 극한 계산에 안 걸려 세 어휘가 전부 같은 값을 냈다** (D-0095).

    문자열 치환 하나가 조용히 안 먹은 것이고, 이 검사가 그 부류를 막는다.
    """
    from dataclasses import replace

    from hathor.engines.compose.harmony_generator import Vocabulary

    made = _references(30, contrast=0.9)
    limits = {
        vocabulary: EvaluateHarmonyOutput(replace(FAST, vocabulary=vocabulary))
        .run(made, vocabulary.value)
        .line("paired")
        .mean_limit
        for vocabulary in Vocabulary
    }
    assert len(set(limits.values())) == len(Vocabulary), f"극한이 겹친다: {limits}"


def test_칸_흔들림을_잰다():
    """**상관과 분산은 다른 양이다** (D-0095)."""
    from hathor.application.evaluate_harmony_output import cell_spread

    flat = _references(40, contrast=0.05)
    peaky = _references(40, contrast=0.95)
    assert cell_spread(peaky, (3, 8, 10)) > cell_spread(flat, (3, 8, 10))


# ------------------------------------------------------------------ 순서 지표 (O-32 · D-0102)


def test_전이_행렬은_순서를_본다():
    """**도수 히스토그램은 순서에 눈이 없다.** `I V vi IV`와 `IV vi V I`의 거리가 0이다."""
    from hathor.application.evaluate_harmony_output import bigram_matrix

    forward = ("I", "V", "vi", "IV")
    backward = ("IV", "vi", "V", "I")
    assert total_variation(
        degree_histogram(forward, Mode.MAJOR), degree_histogram(backward, Mode.MAJOR)
    ) == pytest.approx(0.0)
    assert (
        total_variation(bigram_matrix(forward, Mode.MAJOR), bigram_matrix(backward, Mode.MAJOR))
        > 0.0
    )


def test_전이_행렬은_합이_1이다():
    from hathor.application.evaluate_harmony_output import bigram_matrix

    assert bigram_matrix(("I", "V", "I"), Mode.MAJOR).sum() == pytest.approx(1.0)


def test_한_마디짜리_진행은_전이가_없다():
    """**0으로 나누지 않는다.**"""
    from hathor.application.evaluate_harmony_output import bigram_matrix

    assert bigram_matrix(("I",), Mode.MAJOR).sum() == 0.0


def test_지금은_순서_정보가_없다():
    """**음성 대조.** 생성기가 마디를 독립으로 뽑으므로 초과가 0이어야 한다 (D-0062).

    이것이 참이 되는 날이 O-32가 풀린 날이다.
    """
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    line = report.line("paired")
    assert not line.carries_order
    assert abs(line.order_excess) < 0.02


def test_같은_치환_귀무선이라야_커플링이_산다():
    """마디를 **각자** 뒤섞으면 시드 짝짓기까지 깨져 거리가 오히려 커진다 (D-0102).

    탐색에서 초과가 -0.25로 나왔다. 같은 치환을 쓰면 -0.00이다.
    """
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    line = report.line("paired")
    assert line.mean_transition == pytest.approx(float(np.mean(line.transition_nulls)), abs=0.03)


def test_같은_사전_두_번은_전이도_0이다():
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    assert report.line("identical").mean_transition == 0.0


def test_대각선을_빼면_구간_길이에_불변이다():
    """**재료를 마디에 맞출 필요가 없다** (D-0103).

    같은 화음을 몇 구간 유지하는지는 **자르는 방식이 정한다.** 그것이 대각선을
    통째로 부풀리고, 대각선을 빼면 사라진다.
    """
    from hathor.application.evaluate_harmony_output import bigram_matrix

    quick = ("I", "V", "vi", "IV")
    held = tuple(name for name in quick for _ in range(3))
    assert total_variation(
        bigram_matrix(quick, Mode.MAJOR, drop_diagonal=True),
        bigram_matrix(held, Mode.MAJOR, drop_diagonal=True),
    ) == pytest.approx(0.0, abs=1e-9)
    assert total_variation(bigram_matrix(quick, Mode.MAJOR), bigram_matrix(held, Mode.MAJOR)) > 0.3


def test_대각선을_빼도_음성_대조가_선다():
    """구간 길이 불변을 얻으면서 눈을 잃지 않았는지 본다."""
    report = EvaluateHarmonyOutput(FAST).run(_references(30, contrast=0.9), "test")
    assert not report.line("paired").carries_order
