"""생성된 화성 진행이 참조곡에 따라 얼마나 갈리는지 잰다 (O-29 · D-0078).

### 왜 필요한가

D-0074에서 조건화 이득이 세 배가 됐다(K-K 폭 대비 14.1% → 44.3%). 그런데 같은
시드·같은 조성·8마디에서 두 참조곡의 진행을 눈으로 세어 보니 **다른 마디 수가
2개로 그대로였다.**

이것을 "효과 없음"으로 읽으면 안 된다. **8마디는 표본이 아니고**, `rng.choices`는
가중치에 비례해 결과가 바뀌는 것이 아니라 **가중치가 뽑힌 난수를 넘어설 때만**
바뀐다. 문턱이지 비례가 아니다. 8번 뽑아 2번 바뀌었다는 사실 자체로는 아무것도
판정할 수 없다 — **"2마디밖에"도 "그래도 달라졌네"도 베이스라인 없는 판정이다.**

### 무엇을 재는가 — 도수 히스토그램 거리

마디별 일치율이 아니다. **같은 어휘를 다른 순서로 뽑은 것과 다른 어휘를 뽑은 것은
다르다.** 진행 두 개를 다이어토닉 6도수 히스토그램으로 만들고 전변동 거리를 잰다.

`TV = 0.5 * sum|p - q|`이며 0~1이다. 8마디에서는 `TV * 8`이 **히스토그램상 옮겨야 하는
마디 수**라 "다른 마디 수"와 직접 견줄 수 있다.

마디 불일치율(위치까지 같은지)도 함께 낸다. **진단이지 판정이 아니다** — 지난
세션이 본 "2/8"이 어느 자리의 값이었는지 잇기 위한 것이다.

### 시드가 짝지어진다 — 그래서 바닥이 정확히 0이다

`generate_harmony`는 시드에서만 난수를 만든다. 두 사전에 같은 시드를 주면 **같은
난수열 위에서** 뽑으므로, 사전이 같으면 진행이 **정확히** 같고 거리는 0이다.
바닥이 표집 잡음에 흔들리지 않는다. `identical` 선이 그것을 매번 확인한다.

### 비교선 — 전부 같은 조건 객체를 받는다 (O-25)

| 선 | 사전 쌍 | 무엇을 재는가 |
|---|---|---|
| `identical` | 같은 곡 두 번 | **0이어야 한다.** 결정성·배관 |
| `uniform` | 균등 사전 ↔ 참조곡 | 조건화가 **무조건부 대비** 움직인 몫 |
| `corpus` | **그 곡을 뺀** 코퍼스 평균 ↔ 참조곡 | 참조곡 없이 얻는 것 대비 |
| `paired` | 참조곡 A ↔ B | **재려는 것** |
| `shuffled` | 두 참조곡 사전의 **도수를 치환** | 뾰족함은 같고 곡 고유성만 없다 |
| `random` | 단체 위 균등분포에서 뽑은 사전 둘 | **귀무선.** 아무 사전 둘 (D-0078) |
| `onehot` | 서로 다른 한 도수에 몰빵 | **계량 상한.** 1.0이어야 한다 |

**`uniform` 선이 `prior=None`이 아니다.** `prior=None`은 `rng.choice`를 쓰고 사전이
있으면 `rng.choices`를 쓴다. 난수 소비가 달라 시드 짝짓기가 깨지므로, 조건 없음의
비교선은 **같은 코드 경로를 타는 균등 사전 벡터**여야 한다. 베이스라인을 같은
경로에 태우는 것은 D-0023 이래의 규칙이다.

**`shuffled`를 넣은 것이 D-0078이 적은 셋과 다른 지점이다.** "아무 사전 둘"은
단체 위 균등분포에서 뽑으면 실측보다 훨씬 뾰족해 느슨한 기준이 된다(탐색에서
0.60 대 0.26). 도수를 치환하면 **뾰족함이 정확히 같고 어느 도수인지만 사라진다** —
D-0062가 `other` 선을 넣은 것과 같은 이유다. 둘 다 낸다.

### 상한을 무엇으로 읽는가 (O-25 (3))

**사전 가중치 벡터 자체의 TV 거리**가 마디 수를 무한히 늘렸을 때의 극한이다.
8마디 실측을 그 옆에 놓아야 뜻이 생긴다.

**실측은 극한보다 크게 나온다.** 탐색에서 극한 0.11일 때 8마디가 0.18이었다 —
초과분은 유한 표본의 되튐이지 전달된 정보가 아니다. 마디 수를 늘리면 단조
감소해 극한으로 내려간다(8 → 0.221, 256 → 0.151, 극한 0.145). **8마디 값을 "사전
대비가 이만큼 전달됐다"로 읽으면 안 된다.** 사람이 실제로 듣게 될 8마디의 차이는
그 값이 맞고, 그중 얼마가 사전에서 온 것인지는 극한이 답한다.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import (
    DIATONIC_ROOT_SEMITONES,
    Vocabulary,
    degree_weights,
    generate_harmony,
    vocabulary_degrees,
)

Histogram = np.ndarray[tuple[int], np.dtype[np.float64]]

DEFAULT_SEED_COUNT = 1000
DEFAULT_BAR_COUNT = 8
DEFAULT_PAIR_COUNT = 100
DEFAULT_SEED = 20260822
DEFAULT_KEY = Key(tonic="C", mode=Mode.MAJOR)

DegreePrior = tuple[float, ...]
Progression = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReferencePrior:
    """참조곡 하나의 도수 사전. **이미 으뜸음으로 회전된 12차원이다.**"""

    source_key: str
    prior: DegreePrior

    def __post_init__(self) -> None:
        if len(self.prior) != DEGREE_COUNT:
            raise ValueError(f"도수 사전은 12차원이어야 한다: {len(self.prior)}")


@dataclass(frozen=True, slots=True)
class OutputCondition:
    """실험 조건 한 묶음. **모든 비교선이 이 객체 하나를 받는다** (O-25).

    D-0062의 `PriorCondition`과 같은 구조다. 새 손잡이는 여기 필드로 들어가고,
    그 순간 일곱 선 전부에 똑같이 걸린다. **인자 추가를 잊을 수 없다.**
    """

    seed_count: int = DEFAULT_SEED_COUNT
    """시드 몇 개로 잴 것인가. **8마디 하나는 표본이 아니다** (D-0078)."""

    bar_count: int = DEFAULT_BAR_COUNT
    """마디 수. 늘리면 실측이 극한으로 내려간다."""

    pair_count: int = DEFAULT_PAIR_COUNT
    """참조곡 쌍을 몇 개 볼 것인가."""

    key: Key = DEFAULT_KEY
    """출력 조성. **고정한다** — 조성이 갈리면 화성만 떼어 볼 수 없다 (D-0063)."""

    seed: int = DEFAULT_SEED
    """쌍 추첨·도수 치환·무작위 사전의 시드. 명시 고정한다 (GR-6.5).

    **선마다 흐름이 따로다** (O-34 · D-0094). 예전에는 난수기 하나에서 차례로 뽑아
    **비교선을 하나 더하면 뒤 선의 추첨이 통째로 밀렸다.** `evaluate_degree_restriction`
    에서 실제로 그 일이 났고(D-0086 → D-0087) 여기도 같은 상태였다.
    **어휘 선을 더하는 이번이 그것을 고칠 때다.**
    """

    vocabulary: Vocabulary = Vocabulary.BASE
    """코드 풀. **`MIXTURE`는 `CONTROL`과 견주지 않으면 읽을 수 없다** (D-0094)."""

    def __post_init__(self) -> None:
        if self.seed_count < 1:
            raise ValueError(f"시드 수는 1 이상이어야 한다: {self.seed_count}")
        if self.bar_count < 1:
            raise ValueError(f"마디 수는 1 이상이어야 한다: {self.bar_count}")
        if self.pair_count < 1:
            raise ValueError(f"쌍 수는 1 이상이어야 한다: {self.pair_count}")

    @property
    def seeds(self) -> tuple[int, ...]:
        return tuple(range(self.seed_count))


def degree_histogram(
    progression: Progression, mode: Mode, vocabulary: Vocabulary = Vocabulary.BASE
) -> Histogram:
    """진행을 코드 풀의 도수 히스토그램으로. 합이 1이다.

    **칸 수가 어휘마다 다르다.** 칸이 늘면 두 진행이 겹칠 확률이 낮아져 거리가
    기계적으로 오르므로 **같은 칸 수의 대조군과만 견준다** (D-0094).
    """
    counts = Counter(progression)
    pool = vocabulary_degrees(mode, vocabulary)
    vector = np.asarray([counts.get(name, 0) for name in pool], dtype=np.float64)
    total = float(vector.sum())
    return vector / total if total > 0 else vector


def total_variation(left: Histogram, right: Histogram) -> float:
    """전변동 거리. 0~1이며 **`TV * 마디 수`가 옮겨야 하는 마디 수다.**"""
    return 0.5 * float(np.abs(left - right).sum())


def weight_distance(
    left: DegreePrior,
    right: DegreePrior,
    mode: Mode,
    vocabulary: Vocabulary = Vocabulary.BASE,
) -> float:
    """두 사전의 **가중치 벡터** 거리. 마디 수를 늘렸을 때의 극한이다 (O-25 (3)).

    생성기가 실제로 쓰는 `degree_weights`를 그대로 부른다. 여기서 6도수 정규화를
    다시 구현하면 생성기와 어긋날 수 있고, **어긋나도 아무도 모른다.**
    """
    return total_variation(
        np.asarray(degree_weights(left, mode, vocabulary), dtype=np.float64),
        np.asarray(degree_weights(right, mode, vocabulary), dtype=np.float64),
    )


@dataclass(frozen=True, slots=True)
class OutputLine:
    """비교선 하나의 결과. **쌍별 값을 들고 있다** — 짝지은 비교에 필요하다."""

    name: str
    distances: tuple[float, ...]
    """쌍마다 시드 평균 도수 히스토그램 거리."""
    mismatches: tuple[float, ...]
    """쌍마다 시드 평균 마디 불일치율. 진단이다."""
    limits: tuple[float, ...]
    """쌍마다 사전 가중치 거리. 무한 마디 극한이다."""

    @property
    def pair_count(self) -> int:
        return len(self.distances)

    @property
    def mean_distance(self) -> float:
        """**평균을 쓴다.** 지표가 [0,1]로 유계이고 8마디에서 1/8 격자라
        중앙값은 계단으로 뭉개진다. D-0062가 중앙값을 쓴 이유(극단값)가 여기엔 없다.
        """
        return float(np.mean(self.distances)) if self.distances else 0.0

    @property
    def mean_mismatch(self) -> float:
        return float(np.mean(self.mismatches)) if self.mismatches else 0.0

    @property
    def mean_limit(self) -> float:
        return float(np.mean(self.limits)) if self.limits else 0.0

    @property
    def standard_error(self) -> float:
        if len(self.distances) < 2:
            return 0.0
        return float(np.std(self.distances, ddof=1) / np.sqrt(len(self.distances)))

    @property
    def positive_share(self) -> float:
        """거리가 0보다 큰 쌍의 비율. 평균 한 점의 우연이 아님을 본다."""
        if not self.distances:
            return 0.0
        return float(np.mean(np.asarray(self.distances) > 0.0))


@dataclass(frozen=True, slots=True)
class OutputReport:
    """한 사전 출처(전체 믹스 또는 스템 조합)의 결과."""

    label: str
    condition: OutputCondition
    reference_count: int
    lines: tuple[OutputLine, ...]

    def line(self, name: str) -> OutputLine:
        for item in self.lines:
            if item.name == name:
                return item
        raise KeyError(f"그런 비교선이 없다: {name}")

    @property
    def is_harness_sound(self) -> bool:
        """**하네스 자체 검사다.** 이것이 거짓이면 나머지 숫자를 읽지 않는다.

        `identical`이 0이 아니면 시드 짝짓기가 깨진 것이고, `onehot`이 1이 아니면
        계량이 포화하지 못해 상한을 읽을 수 없다. **아무것도 못 잡는 검사는 늘
        통과하는 하네스와 같다** (GR-0.9) — 그래서 판정과 따로 둔다.
        """
        return (
            self.line("identical").mean_distance == 0.0 and self.line("onehot").mean_distance == 1.0
        )

    @property
    def is_output_conditioned(self) -> bool:
        """**사전 등록한 판정 규칙이다** (GR-6.5). 결과를 보고 고치지 않는다.

        1. `paired` 거리가 0보다 크다 — 참조곡을 바꾸면 출력이 바뀐다.
        2. **쌍 과반에서** 0보다 크다 — 평균 한 점의 우연이 아니다.
        3. `paired`가 `random`을 넘지 않는다 — 실측이 아무 사전 둘보다 더 갈리면
           사전이 아니라 지표나 배관을 의심해야 한다.

        3이 없으면 규칙이 질 수 없다. **이길 수만 있는 규칙은 규칙이 아니다** (O-25 (2)).
        """
        paired = self.line("paired")
        return (
            paired.mean_distance > 0.0
            and paired.positive_share > 0.5
            and paired.mean_distance <= self.line("random").mean_distance
        )


@dataclass(frozen=True, slots=True)
class SourceComparison:
    """두 사전 출처를 **같은 쌍·같은 시드로** 견준다. O-29의 본문이다."""

    baseline: OutputReport
    target: OutputReport

    def __post_init__(self) -> None:
        # **같은 쌍·같은 시드가 아니면 짝지은 비교가 아니다.** 곡 목록이 다르면
        # 쌍 추첨이 서로 다른 곡을 가리키고, 그러면 출처 차이인지 쌍 차이인지
        # 갈리지 않는다 — D-0033이 "쌍을 한 번 뽑아 모든 모드에 쓴다"고 정한 자리다.
        if self.baseline.reference_count != self.target.reference_count:
            raise ValueError(
                "두 출처의 참조곡 수가 다르다: "
                f"{self.baseline.reference_count} vs {self.target.reference_count}. "
                "같은 곡 집합으로 맞춰야 짝지은 비교가 성립한다"
            )
        if self.baseline.condition != self.target.condition:
            raise ValueError("두 출처의 조건이 다르다. 같은 조건 객체를 써야 한다")

    @property
    def gain(self) -> float:
        return self.target.line("paired").mean_distance - self.baseline.line("paired").mean_distance

    @property
    def limit_gain(self) -> float:
        return self.target.line("paired").mean_limit - self.baseline.line("paired").mean_limit

    @property
    def win_rate(self) -> float:
        """쌍마다 목표 출처가 더 갈렸는가. **짝지은 비교라 검정력이 높다.**"""
        target = np.asarray(self.target.line("paired").distances)
        baseline = np.asarray(self.baseline.line("paired").distances)
        if target.size == 0 or target.size != baseline.size:
            return 0.0
        return float(np.mean(target > baseline))

    @property
    def transmits_prior_contrast(self) -> bool:
        """**사전 등록한 판정 규칙이다.** 사전 대비가 커지면 출력 차이도 커지는가.

        1. 목표 출처의 `paired` 거리가 기준선보다 크다.
        2. **쌍 과반에서** 그렇다 — 같은 쌍·같은 시드로 짝지어 센다.

        둘 다 넘지 못하면 **문턱 추출이 사전 대비를 삼킨 것이며**, 사전을 더
        뾰족하게 만드는 축(O-27)은 출력에 닿지 않는다.
        """
        return self.gain > 0.0 and self.win_rate > 0.5


class EvaluateHarmonyOutput:
    """참조곡을 바꿨을 때 출력이 얼마나 갈리는지 잰다.

    **비교선을 따로 만들지 않는다.** 사전 표 하나를 세우고 인덱스 쌍으로 선을
    정의하므로, 조건이 바뀌어도 어떤 선만 다른 조건으로 계산될 수 없다 —
    D-0034 계열이 열한 번 반복된 자리다.
    """

    def __init__(self, condition: OutputCondition | None = None) -> None:
        self._condition = condition if condition is not None else OutputCondition()

    def run(self, references: Sequence[ReferencePrior], label: str) -> OutputReport:
        settings = self._condition
        if len(references) < 2:
            raise ValueError(f"참조곡이 2개 이상 필요하다: {len(references)}")

        def stream(line: int) -> np.random.Generator:
            """**선마다 흐름이 따로다** (O-34 · D-0094). 선을 더해도 다른 선이 안 밀린다."""
            return np.random.default_rng([settings.seed, line])

        pairs = self._sample_pairs(len(references), stream(0))
        priors = [item.prior for item in references]

        uniform: DegreePrior = tuple([1.0 / DEGREE_COUNT] * DEGREE_COUNT)
        shuffle_rng = stream(1)
        shuffled = [
            tuple(float(value) for value in shuffle_rng.permutation(np.asarray(item)))
            for item in priors
        ]
        draw_rng = stream(2)
        drawn = [
            tuple(float(value) for value in draw_rng.dirichlet(np.ones(DEGREE_COUNT)))
            for _ in range(2 * len(pairs))
        ]
        stacked = np.asarray(priors, dtype=np.float64)
        # **코퍼스 평균은 그 곡을 뺀다** (D-0062). 전체 평균은 자기 자신이 새어 든다.
        # 1004곡에서 몫은 작으나 작아서 괜찮다고 넘긴 것이 D-0034 계열의 시작이었다.
        leave_one_out = (stacked.sum(axis=0) - stacked) / max(len(priors) - 1, 1)

        cache: dict[int, tuple[Progression, ...]] = {}
        table: list[DegreePrior] = []

        def register(prior: DegreePrior) -> int:
            table.append(prior)
            return len(table) - 1

        song = [register(item) for item in priors]
        shuffled_index = [register(item) for item in shuffled]
        drawn_index = [register(item) for item in drawn]
        corpus_index = [
            register(tuple(float(value) for value in leave_one_out[index]))
            for index in range(len(priors))
        ]
        uniform_index = register(uniform)
        # **선법의 다이어토닉 근음에서 골라야 한다.** 장조 기준으로 9(vi)를 박으면
        # 단조에서는 근음이 아니라 `degree_weights`가 전부 0을 보고 균등으로
        # 되돌린다 — 상한선이 조용히 1.0이 아니게 된다. 실제로 그렇게 짰다가 잡았다.
        roots = DIATONIC_ROOT_SEMITONES[settings.key.mode]
        onehot: list[int] = []
        for semitone in (roots[0], roots[-1]):
            vector = [0.0] * DEGREE_COUNT
            vector[semitone] = 1.0
            onehot.append(register(tuple(vector)))

        def progressions(index: int) -> tuple[Progression, ...]:
            if index not in cache:
                cache[index] = tuple(
                    generate_harmony(
                        seed,
                        settings.key,
                        bar_count=settings.bar_count,
                        prior=table[index],
                        vocabulary=settings.vocabulary,
                    ).degrees
                    for seed in settings.seeds
                )
            return cache[index]

        def measure(name: str, index_pairs: Sequence[tuple[int, int]]) -> OutputLine:
            distances: list[float] = []
            mismatches: list[float] = []
            limits: list[float] = []
            for left, right in index_pairs:
                first, second = progressions(left), progressions(right)
                per_seed = [
                    total_variation(
                        degree_histogram(a, settings.key.mode, settings.vocabulary),
                        degree_histogram(b, settings.key.mode, settings.vocabulary),
                    )
                    for a, b in zip(first, second, strict=True)
                ]
                mismatch = [
                    sum(1 for x, y in zip(a, b, strict=True) if x != y) / settings.bar_count
                    for a, b in zip(first, second, strict=True)
                ]
                distances.append(float(np.mean(per_seed)))
                mismatches.append(float(np.mean(mismatch)))
                limits.append(
                    weight_distance(
                        table[left], table[right], settings.key.mode, settings.vocabulary
                    )
                )
            return OutputLine(
                name=name,
                distances=tuple(distances),
                mismatches=tuple(mismatches),
                limits=tuple(limits),
            )

        lines = (
            measure("identical", [(song[left], song[left]) for left, _ in pairs]),
            measure("uniform", [(uniform_index, song[left]) for left, _ in pairs]),
            measure("corpus", [(corpus_index[left], song[left]) for left, _ in pairs]),
            measure("paired", [(song[left], song[right]) for left, right in pairs]),
            measure(
                "shuffled",
                [(shuffled_index[left], shuffled_index[right]) for left, right in pairs],
            ),
            measure(
                "random",
                [(drawn_index[2 * i], drawn_index[2 * i + 1]) for i in range(len(pairs))],
            ),
            measure("onehot", [(onehot[0], onehot[1])]),
        )
        return OutputReport(
            label=label,
            condition=settings,
            reference_count=len(references),
            lines=lines,
        )

    def pair_indices(self, count: int) -> tuple[tuple[int, int], ...]:
        """쌍 추첨을 밖에서도 볼 수 있게 낸다. **두 출처가 같은 쌍을 써야 한다.**"""
        return self._sample_pairs(count, np.random.default_rng([self._condition.seed, 0]))

    def _sample_pairs(
        self, count: int, generator: np.random.Generator
    ) -> tuple[tuple[int, int], ...]:
        """서로 다른 두 곡을 뽑는다. **시드가 같으면 같은 쌍이 나온다.**

        같은 곡을 짝지으면 `paired`가 `identical`이 되어 재려는 것이 사라진다.
        """
        picked: list[tuple[int, int]] = []
        attempts = 0
        limit = max(self._condition.pair_count * 50, 1000)
        while len(picked) < self._condition.pair_count and attempts < limit:
            attempts += 1
            left, right = (int(value) for value in generator.choice(count, 2, replace=False))
            picked.append((left, right))
        if not picked:
            raise ValueError("참조곡 쌍을 만들 수 없다")
        return tuple(picked)


def cell_spread(references: Sequence[ReferencePrior], cells: Sequence[int]) -> float:
    """지정한 칸들의 **곡 간 로그 표준편차** 평균 (D-0095).

    D-0093은 칸들이 **함께 오르는가**(상관)를 쟀다. 출력 히스토그램 거리를 만드는
    것은 **얼마나 흔들리는가**(분산)다. **둘은 다른 양이며**, 상관이 커도 분산이
    비슷하면 어휘를 넓혀도 출력이 더 갈리지 않는다.

    합성에서 확인했다 — 칸별 분산을 맞추고 뭉침만 바꾸면 거리가 0.3526에서
    0.3553으로 거의 안 움직인다. **"뭉치면 중복이라 손해"라는 가설은 기각됐다.**
    """
    stacked = np.asarray([item.prior for item in references], dtype=np.float64)
    logged = np.log(np.maximum(stacked[:, list(cells)], 1e-12))
    return float(np.mean(logged.std(axis=0, ddof=1)))


def sweep_bar_counts(
    references: Sequence[ReferencePrior],
    bar_counts: Sequence[int],
    condition: OutputCondition | None = None,
) -> tuple[tuple[int, float, float], ...]:
    """마디 수를 훑는다. **"8마디는 표본이 아니다"가 실제로 그런지 본다** (D-0078).

    `(마디 수, 8마디 실측, 극한)`을 낸다. 실측이 마디 수와 함께 극한으로 내려가면
    초과분이 유한 표본의 되튐이라는 뜻이다.
    """
    from dataclasses import replace

    settings = condition if condition is not None else OutputCondition()
    rows: list[tuple[int, float, float]] = []
    for bars in bar_counts:
        report = EvaluateHarmonyOutput(replace(settings, bar_count=bars)).run(references, "sweep")
        paired = report.line("paired")
        rows.append((bars, paired.mean_distance, paired.mean_limit))
    return tuple(rows)
