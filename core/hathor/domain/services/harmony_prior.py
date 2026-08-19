"""화성 도수 사전(prior)의 정보량을 잰다. **O-21의 판정 장치이며 생성기가 아니다.**

### 무엇을 판정하는가

O-21의 접근안은 "저장된 크로마를 조성 기준으로 회전시켜 도수별 가중치로 쓴다"이다.
그 접근이 성립하려면 **곡별 회전 크로마가 코퍼스 평균을 넘는 곡 고유 정보를 담아야**
한다. 담지 않으면 어떤 생성기를 짜도 결과는 코퍼스 평균에 잡음을 더한 것이고,
참조곡을 바꾼 차이는 정보가 아니라 잡음이다.

**이 명제는 생성기 없이 크로마만으로 판정된다.** 그래서 생성기보다 먼저 온다.

### 왜 생성물을 채점하지 않는가

"생성된 진행이 참조곡 크로마와 얼마나 맞는가"로 채점하면 **조건화가 질 수 없다.**
그 지표의 argmax가 곧 조건화 생성기이기 때문이다. 코퍼스 전역 베이스라인은 정의상
지고, 이긴 결과는 배관이 이어졌다는 사실 외에 아무것도 말하지 않는다.

D-0034 계열 일곱 번은 **비교 대상이 조건을 안 따라간** 문제였고, 이것은 한 단계 위의
같은 병이다 — **비교 대상이 이길 수 없는 지표.** 지표를 만들 때 무엇과 비교할지
정하는 것으로 부족하고, **그 비교선이 이길 수 있는지**까지 봐야 한다 (O-25).

### 판정 방식 — 곡 내 홀드아웃

곡을 앞뒤 반으로 가르고 앞반쪽 크로마로 뒷반쪽을 예측한다. 뒷반쪽은 어느 비교선도
보지 못한 자료이므로 **네 선 전부가 질 수 있다.**

| 비교선 | 예측 분포 | 무엇을 재는가 |
|---|---|---|
| `uniform` | 1/12 균등 | **구조가 전혀 없을 때의 최적 예측** |
| `corpus` | 다른 곡 앞반쪽의 평균 (**곡 하나 뺀 평균**) | 참조곡 없이 얻는 것 |
| `other` | **틀린 곡** 앞반쪽 | 곡 고유성이 없을 때의 자기 예측 — 진짜 귀무선 |
| `self` | **자기** 앞반쪽 | 조건화가 주장하는 것 |

**`uniform`은 천장이 아니다.** 코퍼스에 공통 구조가 없으면 균등이 최적이고, 그때
`corpus`는 균등의 잡음 섞인 추정치라 오히려 나쁘다. 단위 검사에서 실제로 그렇게
나왔다. 균등을 "어떤 사전도 이보다 낫다"로 읽으면 D-0061과 같은 종류의 오독이다 —
**대중가요는 온음계에 몰려 있으니 균등보다 나을 것이라는 예상은 도메인 상식이지
베이스라인이 아니다.** `corpus`가 `uniform`을 넘는지 자체가 첫 실측 항목이다.

`corpus`를 곡 하나 뺀 평균으로 계산한다. 전체 평균은 자기 자신을 포함해 새어 든다.
1004곡에서 몫은 작으나, **작아서 괜찮다고 넘긴 것이 D-0034 계열의 시작이었다.**

`other`가 핵심이다. `self`는 곡 하나의 반쪽이라 1000곡 평균인 `corpus`보다 잡음이
크다. 그 불리함을 안고도 이겨야 하는데, **이겼을 때 그것이 곡 고유성 때문인지
단일 곡 분포의 뾰족함 때문인지**는 `other`와 비교해야 갈린다. `other`는 잡음 양이
`self`와 같고 곡 고유성만 없다.

### 채점 — 교차 엔트로피

`H(뒷반쪽, 예측) = -Σ b_d log p_d`. 낮을수록 좋다.

**생성기가 이 사전에서 화음을 뽑을 것이므로 채점도 그 손실이어야 한다.** 코사인이나
상관은 생성 손실이 아니고, 상관은 평균을 빼므로 균등 성분에 불변이다 — D-0058에서
로그 압축 가설을 무너뜨린 바로 그 성질이라 사전 평가에는 맞지 않는다.

곡마다 `H(b)`가 다르므로 **선 간 비교는 같은 곡 안에서 짝지어 뺀다.** 그러면 `H(b)`가
소거되고 남는 것이 KL 차이다.

### 산출물은 숫자 하나다 — λ*

`(1-λ)·corpus + λ·self`를 λ=0..1로 훑어 중앙값 교차 엔트로피가 최소인 λ*를 낸다.

- **λ* = 0** — 참조곡이 보탤 것이 없다. O-21의 크로마 접근을 기각한다.
- **λ* > 0** — 보탤 것이 있고, **λ*가 곧 생성기의 혼합 계수다.**

λ=0이 `corpus` 선이고 λ=1이 `self` 선이므로 **비교선과 곡선이 어긋날 수 없다.**
`other`에도 같은 곡선을 그린다 — 그쪽 λ*는 0이어야 하며, 아니면 지표가 고장 난 것이다.

### 한계 — 미리 적는다

- **순서를 재지 않는다.** 크로마는 곡 전체(반쪽) 평균이라 화음의 배열 정보가 없다.
  이 판정이 통과해도 얻는 것은 **화성 어휘**이지 진행이 아니다.
- **회전이 조성 추정에 의존한다.** 나란한조 혼동은 3반음 어긋난 회전이고 I가 vi로
  간다. 라벨이 없어 그 오차를 잴 수 없다 (O-22). `margin` 기준으로 갈라서 본다.
- 앞뒤 반쪽은 편곡·마스터링·조성을 공유하므로 상관이 높은 것이 당연하다. **그것이
  곧 곡 고유성이며 새는 것이 아니다** — 뒷반쪽은 어느 선도 보지 못했다.
- **선 요약에 중앙값을 쓴다.** 곡 몇 개의 극단값에 흔들리지 않게 하려는 것인데,
  대신 `-Σ b log p ≥ log 12`(평균에서 성립)이 중앙값에서는 성립하지 않는다.
  절대값의 부호로 읽지 말고 **같은 곡 집합 안에서 선끼리만 비교한다.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.domain.services.key_estimation import subtract_harmonics

DEGREE_COUNT = 12
EPSILON = 1e-12

DegreeVector = np.ndarray[tuple[int], np.dtype[np.float64]]
DegreeMatrix = np.ndarray[tuple[int, int], np.dtype[np.float64]]


@dataclass(frozen=True, slots=True)
class HalfChroma:
    """한 곡의 앞뒤 반쪽 크로마와 **앞반쪽에서 추정한** 으뜸음.

    **조성을 앞반쪽에서만 추정한다.** 곡 전체에서 추정하면 뒷반쪽이 회전 정렬에
    관여해 홀드아웃이 아니게 된다. 몫은 작겠으나 홀드아웃은 몫으로 타협하는
    것이 아니다.
    """

    source_key: str
    tonic_pitch_class: int
    margin: float
    head: tuple[float, ...]
    tail: tuple[float, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.tonic_pitch_class < DEGREE_COUNT:
            raise ValueError(f"으뜸음 피치클래스는 0~11이어야 한다: {self.tonic_pitch_class}")
        for name, vector in (("head", self.head), ("tail", self.tail)):
            if len(vector) != DEGREE_COUNT:
                raise ValueError(f"{name} 크로마는 12차원이어야 한다: {len(vector)}")

    @property
    def is_confident(self) -> bool:
        """조성 추정 격차가 기준을 넘는가. 기준값은 조건 객체가 들고 있다."""
        return self.margin >= 0.0


@dataclass(frozen=True, slots=True)
class PriorCondition:
    """실험 조건 한 묶음. **모든 비교선이 이 객체 하나를 받는다** (O-25).

    D-0034 계열이 일곱 번 반복된 형태는 늘 같았다 — 조건을 하나 더 넣고 베이스라인에
    넣는 것을 잊었다. 인자를 늘릴 때마다 사람이 기억해야 했고 **여섯 번 실패했다.**

    조건을 객체 하나로 묶고 예측선 생성 함수가 그것만 받게 하면 **인자 추가를
    잊을 수 없다.** 새 손잡이는 이 클래스에 필드로 들어가고, 그 순간 네 선 전부에
    똑같이 적용된다. O-25가 요구한 구조적 방어이며 여기서 처음 구현한다.
    """

    harmonic: float = 0.0
    """배음 감산 강도 (D-0059 · D-0060). 기본 0(끔)."""

    smoothing: float = 0.01
    """예측 분포를 균등과 섞는 비율. `log(0)`을 막고 과신을 누른다.

    **목표 분포에는 적용하지 않는다.** 목표는 관측된 경험 분포이지 예측이 아니다.
    """

    margin_floor: float = 0.05
    """조성 추정을 신뢰하는 격차 하한 (D-0054와 같은 값)."""

    confident_only: bool = False
    """참이면 격차가 하한 미만인 곡을 뺀다."""

    seed: int = 20260819
    """`other` 선의 짝짓기 시드. 명시 고정한다 (GR-6.5)."""

    blend_steps: int = 11
    """λ 격자 수. 11이면 0.0, 0.1, …, 1.0이다."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.smoothing < 1.0:
            raise ValueError(f"smoothing은 0 이상 1 미만이어야 한다: {self.smoothing}")
        if self.harmonic < 0.0:
            raise ValueError(f"harmonic은 0 이상이어야 한다: {self.harmonic}")
        if self.blend_steps < 2:
            raise ValueError(f"blend_steps는 2 이상이어야 한다: {self.blend_steps}")


def rotate_to_degrees(chroma: DegreeVector, tonic_pitch_class: int) -> DegreeVector:
    """피치클래스 크로마를 도수 크로마로 돌린다. **인덱스 0이 으뜸음이다.**

    인덱스는 으뜸음 위 반음 수이며 도수 표기가 아니다 — 3은 단3도 자리이고
    장조라면 비음계음, 단조라면 III다. 선법 해석은 여기서 하지 않는다.
    """
    if chroma.shape != (DEGREE_COUNT,):
        raise ValueError(f"크로마는 12차원이어야 한다: {chroma.shape}")
    if not 0 <= tonic_pitch_class < DEGREE_COUNT:
        raise ValueError(f"으뜸음 피치클래스는 0~11이어야 한다: {tonic_pitch_class}")
    return np.roll(np.asarray(chroma, dtype=np.float64), -tonic_pitch_class)


def _to_distribution(vector: DegreeVector) -> DegreeVector:
    """음수를 자르고 합을 1로 맞춘다. 전부 0이면 균등을 낸다."""
    clipped = np.maximum(np.asarray(vector, dtype=np.float64), 0.0)
    total = float(clipped.sum())
    if total <= EPSILON:
        return np.full(DEGREE_COUNT, 1.0 / DEGREE_COUNT, dtype=np.float64)
    return clipped / total


def smooth(distribution: DegreeMatrix, condition: PriorCondition) -> DegreeMatrix:
    """예측 분포를 균등과 섞는다. 조건 객체에서 비율을 받는다."""
    weight = condition.smoothing
    return (1.0 - weight) * distribution + weight / DEGREE_COUNT


def cross_entropy(targets: DegreeMatrix, predictions: DegreeMatrix) -> DegreeVector:
    """행마다 `-Σ b log p`. 목표는 평활하지 않고 예측만 평활한 상태로 받는다."""
    if targets.shape != predictions.shape:
        raise ValueError(f"모양이 다르다: {targets.shape} vs {predictions.shape}")
    return -np.sum(targets * np.log(np.maximum(predictions, EPSILON)), axis=1)


def _stack(
    observations: Sequence[HalfChroma], condition: PriorCondition
) -> tuple[DegreeMatrix, DegreeMatrix]:
    """관측을 (앞반쪽, 뒷반쪽) 도수 분포 행렬로 만든다.

    **배음 감산을 여기 한 곳에서만 적용한다.** 선마다 따로 적용하면 어느 선이
    감산됐는지 사람이 기억해야 하고, 그것이 D-0060에서 실제로 틀린 지점이다.
    """
    heads = np.zeros((len(observations), DEGREE_COUNT), dtype=np.float64)
    tails = np.zeros((len(observations), DEGREE_COUNT), dtype=np.float64)
    for index, observation in enumerate(observations):
        for target, raw in ((heads, observation.head), (tails, observation.tail)):
            reduced = subtract_harmonics(np.asarray(raw, dtype=np.float64), condition.harmonic)
            target[index] = _to_distribution(
                rotate_to_degrees(reduced, observation.tonic_pitch_class)
            )
    return heads, tails


def _leave_one_out_mean(heads: DegreeMatrix) -> DegreeMatrix:
    """곡 하나를 뺀 코퍼스 평균. 자기 자신이 예측에 새어 들지 않게 한다."""
    count = heads.shape[0]
    if count < 2:
        raise ValueError("코퍼스 평균에는 곡이 2개 이상 필요하다")
    return (heads.sum(axis=0) - heads) / (count - 1)


PairingIndex = np.ndarray[tuple[int], np.dtype[np.int64]]


def _derangement(count: int, condition: PriorCondition) -> PairingIndex:
    """자기 자신에 대응하지 않는 짝짓기. 고정 오프셋 회전이라 완전 무고정점이다.

    무작위 순열은 고정점이 나올 수 있고, 나오면 그 곡만 `self`가 되어 `other`
    선이 조용히 오염된다.
    """
    if count < 2:
        raise ValueError("짝짓기에는 곡이 2개 이상 필요하다")
    generator = np.random.default_rng(condition.seed)
    offset = int(generator.integers(1, count))
    return (np.arange(count, dtype=np.int64) + offset) % count


@dataclass(frozen=True, slots=True)
class PriorComparison:
    """비교 결과. **λ 곡선이 본체이고 나머지는 그 위의 점이다.**"""

    condition: PriorCondition
    song_count: int
    lambdas: tuple[float, ...]
    self_curve: tuple[float, ...]
    """λ별 중앙값 교차 엔트로피. `self`를 섞은 쪽."""
    other_curve: tuple[float, ...]
    """같은 곡선을 **틀린 곡**으로. 귀무선이며 λ*가 0이어야 한다."""
    uniform_score: float
    self_wins: int
    """곡 단위로 `self`(λ=1)가 `corpus`(λ=0)보다 나았던 수."""
    other_wins: int
    ambiguous_count: int

    @property
    def corpus_score(self) -> float:
        return self.self_curve[0]

    @property
    def self_score(self) -> float:
        return self.self_curve[-1]

    @property
    def other_score(self) -> float:
        return self.other_curve[-1]

    @property
    def best_lambda(self) -> float:
        """중앙값 교차 엔트로피를 최소로 만드는 λ. **이 값이 판정이다.**"""
        return self.lambdas[int(np.argmin(np.asarray(self.self_curve)))]

    @property
    def null_lambda(self) -> float:
        """귀무선의 λ*. 0이 아니면 지표를 의심한다."""
        return self.lambdas[int(np.argmin(np.asarray(self.other_curve)))]

    @property
    def self_win_rate(self) -> float:
        return self.self_wins / self.song_count if self.song_count else 0.0

    @property
    def other_win_rate(self) -> float:
        return self.other_wins / self.song_count if self.song_count else 0.0

    @property
    def is_conditioning_informative(self) -> bool:
        """**사전 등록된 판정 규칙이다** (GR-6.5 지표 우선).

        결과를 보고 고치지 않기 위해 코드에 박아 둔다. 세 조건을 전부 넘어야 한다.

        1. λ* > 0 — 참조곡을 섞는 것이 코퍼스 평균 단독보다 낫다.
        2. `self`가 `corpus`를 곡 과반에서 이긴다 — 중앙값 한 점의 우연이 아니다.
        3. `self`가 `other`보다 낫다 — 이득이 곡 고유성에서 왔지 단일 곡 분포의
           뾰족함에서 온 것이 아니다.

        3이 빠지면 "곡 하나가 평균보다 뾰족해서 이겼다"를 곡 고유성으로 착각한다.
        """
        return (
            self.best_lambda > 0.0
            and self.self_win_rate > 0.5
            and self.self_score < self.other_score
        )


def compare_priors(
    observations: Sequence[HalfChroma], condition: PriorCondition | None = None
) -> PriorComparison:
    """네 비교선을 한 번에 낸다. **선을 따로 만들지 않는다.**

    λ 곡선 하나에서 `corpus`(λ=0)와 `self`(λ=1)를 읽어 내므로, 조건이 바뀌어도
    두 선이 서로 다른 조건으로 계산될 수 없다 — D-0034 계열이 반복된 자리다.
    """
    settings = condition if condition is not None else PriorCondition()
    ambiguous = sum(1 for item in observations if item.margin < settings.margin_floor)
    if settings.confident_only:
        observations = [item for item in observations if item.margin >= settings.margin_floor]
    if len(observations) < 2:
        raise ValueError(f"비교에는 곡이 2개 이상 필요하다: {len(observations)}")

    heads, tails = _stack(observations, settings)
    corpus = _leave_one_out_mean(heads)
    partner = heads[_derangement(heads.shape[0], settings)]

    lambdas = tuple(float(value) for value in np.linspace(0.0, 1.0, settings.blend_steps))
    self_curve: list[float] = []
    other_curve: list[float] = []
    for weight in lambdas:
        for curve, candidate in ((self_curve, heads), (other_curve, partner)):
            blended = smooth((1 - weight) * corpus + weight * candidate, settings)
            curve.append(float(np.median(cross_entropy(tails, blended))))

    corpus_scores = cross_entropy(tails, smooth(corpus, settings))
    self_scores = cross_entropy(tails, smooth(heads, settings))
    other_scores = cross_entropy(tails, smooth(partner, settings))
    uniform = np.full_like(heads, 1.0 / DEGREE_COUNT)

    return PriorComparison(
        condition=settings,
        song_count=heads.shape[0],
        lambdas=lambdas,
        self_curve=tuple(self_curve),
        other_curve=tuple(other_curve),
        uniform_score=float(np.median(cross_entropy(tails, uniform))),
        self_wins=int(np.sum(self_scores < corpus_scores)),
        other_wins=int(np.sum(other_scores < corpus_scores)),
        ambiguous_count=ambiguous,
    )
