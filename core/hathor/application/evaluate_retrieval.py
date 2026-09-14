"""검색 평가 하네스 (M0/M1/M2).

지표가 없으면 95M/330M, 혼합/스템, 청크 크기, 풀링 방식이 전부 반증 불가능한
선택이 된다. 이 유스케이스는 이미 뽑아둔 npz와 스캔 태그만으로 그 선택들을
숫자로 되돌린다. 외부 조회도 GPU도 쓰지 않는다.

**정답 라벨을 외부에서 가져오지 않는다.** 검색 평가에 필요한 것은 정규 신원이
아니라 동치류다. 개인 라이브러리는 리핑 출처가 단일해 태그 문자열이 내부적으로
일관되며, `아이유`가 `IU`로 정규화되는지는 MusicBrainz 조회의 문제지 "이 두 곡이
같은 아티스트인가" 판정과 무관하다. 따라서 O-4(RESOLVED 오답)는 이 평가를
오염시키지 않는다.

**M0는 게이트다.** 곡이 자기 자신조차 찾지 못하면 그 아래에서 나온 M1·M2는
노이즈다. 기본적으로 M0가 기준 미달이면 라벨 지표를 계산하지 않는다.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

import numpy as np

from hathor.domain.ports.audio_analysis import Embedding
from hathor.domain.services.embedding_pooling import (
    CombineMode,
    Matrix,
    PoolMode,
    Vector,
    build_view,
    split_odd_even,
    split_random,
)
from hathor.domain.services.isotropy import anisotropy, center, mean_direction
from hathor.domain.services.retrieval_metrics import (
    BoolMatrix,
    ConsistencyScore,
    RetrievalScore,
    cosine_similarity,
    expected_random_precision,
    score_consistency,
    score_retrieval,
)

MIXTURE_KEY = "mixture"
DEFAULT_SEED = 20260816
DEFAULT_SPLIT_SEED = 20260817
DEFAULT_K = 10
DEFAULT_GATE = 0.95
MIN_CHUNKS = 2
"""분할에 필요한 최소 청크 수. 10초 청크이므로 20초 미만 곡이 걸린다."""


class SplitMode(StrEnum):
    """M0에서 곡을 두 조각으로 자르는 방법. **실험 축이며 선택이다.**

    D-0038까지 이 선택은 존재조차 하지 않았다. `split_odd_even`이 유일한
    구현이었고, 따라서 M0 0.8983이 **가사 표현의 한계인지 분할 규칙의
    부작용인지 구분할 수단이 없었다.** 축으로 올려 실측 대상으로 만든다.
    """

    ODD_EVEN = "odd-even"
    """홀수 청크 대 짝수 청크. 오디오축의 정본이며 기본값이다."""

    RANDOM = "random"
    """무작위 분할. 여러 번 반복해 평균과 표준편차를 낸다."""


@dataclass(frozen=True, slots=True)
class SplitSpec:
    """M0 분할 설정.

    **한 번에 하나만 바꾼다.** `ratio`를 0.5로 고정한 채 `mode`만 바꾸면
    무작위화의 효과가 홀짝과 직접 비교된다. 비대칭 분할(70/30)은 그다음
    슬라이스이며, 두 변경을 함께 돌리면 어느 쪽이 효과를 냈는지 다시 모른다.
    """

    mode: SplitMode = SplitMode.ODD_EVEN
    ratio: float = 0.5
    """왼쪽(쿼리) 조각의 비율. `RANDOM`에서만 쓴다."""

    repeats: int = 1
    """반복 횟수. 무작위 분할은 1회 값이 표본 하나라 그대로 인용하면 안 된다."""

    seed: int = DEFAULT_SPLIT_SEED

    def __post_init__(self) -> None:
        if self.repeats < 1:
            raise ValueError("repeats는 1 이상이어야 한다")
        if self.mode is SplitMode.ODD_EVEN and self.repeats != 1:
            # 결정적 분할을 여러 번 돌리면 같은 값이 반복될 뿐이다. 표준편차 0이
            # 나와 "안정적"이라는 잘못된 인상을 준다. 조용히 1로 깎지 않고 막는다.
            raise ValueError("odd-even은 결정적이라 repeats가 1이어야 한다")

    def as_record(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "ratio": self.ratio,
            "repeats": self.repeats,
            "seed": self.seed,
        }


def label_key(raw: str | None) -> str | None:
    """태그 문자열을 동치류 키로 만든다.

    NFC 정규화·양끝 공백 제거·케이스 폴딩만 한다. 그 이상 손대지 않는다.
    피처링이 섞인 원문(`10CM, BIG Naughty (서동현)`)은 단독 표기와 다른 키가
    되는데, 이것은 라벨을 **더 엄격하게** 만들 뿐이라 점수를 부풀리지 않는다.
    느슨하게 묶는 규칙을 넣으면 그 규칙 자체가 검증 대상이 되어버린다.
    """
    if raw is None:
        return None
    value = unicodedata.normalize("NFC", raw).strip().casefold()
    return value or None


@dataclass(frozen=True, slots=True)
class TrackRecord:
    """평가 입력 한 곡. 태그와 임베딩만 있으면 된다."""

    source_key: str
    album: str | None
    artist: str | None
    embeddings: Mapping[str, Embedding]


@dataclass(frozen=True, slots=True)
class ViewSpec:
    """임베딩을 어떤 벡터로 접을지에 대한 선택. 실험의 축이다."""

    keys: tuple[str, ...] = (MIXTURE_KEY,)
    combine: CombineMode = CombineMode.CONCAT
    pool: PoolMode = PoolMode.MEAN
    chunk_l2: bool = False
    block_l2: bool = False
    """블록별 단위 정규화 후 결합. 서로 다른 추출기를 섞을 때 필수다."""

    centered: bool = True
    """코퍼스 공통 방향 제거. 전 지표가 개선되어 기본값이다 (D-0031).

    끄면 전체 쌍 평균 코사인이 0.95 수준으로 올라가 허브 곡이 상위를 차지한다.
    비교·조사 목적이 아니면 끄지 않는다.
    """

    def as_record(self) -> dict[str, object]:
        return {
            "keys": list(self.keys),
            "combine": self.combine.value,
            "pool": self.pool.value,
            "chunk_l2": self.chunk_l2,
            "block_l2": self.block_l2,
            "centered": self.centered,
        }


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    """실행 설정. 산출 JSON에 그대로 박아 어떤 조건의 수치인지 남긴다."""

    view: ViewSpec = field(default_factory=ViewSpec)
    split: SplitSpec = field(default_factory=SplitSpec)
    k: int = DEFAULT_K
    seed: int = DEFAULT_SEED
    gate: float = DEFAULT_GATE
    force: bool = False
    """M0 미달에도 라벨 지표를 계산한다. 실패 원인 조사용이며 기본은 False."""

    label: str = "unnamed"
    """실험 이름. 여러 조건의 산출 JSON을 나중에 구분하기 위한 것뿐이다."""

    def as_record(self) -> dict[str, object]:
        return {
            "label": self.label,
            "view": self.view.as_record(),
            "split": self.split.as_record(),
            "k": self.k,
            "seed": self.seed,
            "gate": self.gate,
            "force": self.force,
        }


@dataclass(frozen=True, slots=True)
class LabeledMetric:
    """라벨 기반 지표 하나와 그 베이스라인.

    측정값만 남기지 않는다. `MAP 0.41`은 의미가 없고 `무작위 0.02 대비 20배`가
    의미다. 베이스라인 없이 이 값을 인용하는 것을 구조적으로 막는다.
    """

    name: str
    measured: RetrievalScore
    random: RetrievalScore
    expected_random_precision: float

    @property
    def precision_lift(self) -> float:
        if self.random.precision_at_k < 1e-9:
            return float("inf")
        return self.measured.precision_at_k / self.random.precision_at_k

    @property
    def map_lift(self) -> float:
        if self.random.map_at_k < 1e-9:
            return float("inf")
        return self.measured.map_at_k / self.random.map_at_k

    def as_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "measured": self.measured.as_record(),
            "random_baseline": self.random.as_record(),
            "expected_random_precision": round(self.expected_random_precision, 6),
            "precision_lift": round(self.precision_lift, 3),
            "map_lift": round(self.map_lift, 3),
        }


@dataclass(frozen=True, slots=True)
class ConsistencyRun:
    """M0 실측 결과. 반복이 여럿이면 그 분포를 함께 들고 다닌다.

    **평균만 남기지 않는다.** 무작위 분할은 회차마다 값이 다르며, 표준편차를
    보지 않으면 조건 A(0.912)와 조건 B(0.907)의 차이가 실재하는지 표본 잡음인지
    알 수 없다. 베이스라인 없이 수치를 인용하지 않는 원칙의 같은 형태다.
    """

    split: SplitSpec
    scores: tuple[ConsistencyScore, ...]

    @property
    def top1(self) -> float:
        return float(np.mean([score.top1 for score in self.scores]))

    @property
    def top1_std(self) -> float:
        return float(np.std([score.top1 for score in self.scores]))

    @property
    def queries(self) -> int:
        return self.scores[0].queries if self.scores else 0

    def _mean(self, field_name: str) -> float:
        return float(np.mean([getattr(score, field_name) for score in self.scores]))

    @property
    def mrr(self) -> float:
        return self._mean("mrr")

    @property
    def recall_at_5(self) -> float:
        return self._mean("recall_at_5")

    @property
    def recall_at_10(self) -> float:
        return self._mean("recall_at_10")

    @property
    def miss_median_rank(self) -> float:
        return self._mean("miss_median_rank")

    @property
    def random_top1(self) -> float:
        """무작위 순위에서 기대되는 top-1. 후보가 n개면 1/n이다.

        M1·M2와 달리 M0에는 지금까지 베이스라인이 없었다. 계산할 것이 없어
        자명하다는 이유였겠으나, **자명한 하한도 적혀 있지 않으면 인용되지
        않는다.** D-0034에서 겪은 것과 같은 형태의 누락이다.
        """
        return 1.0 / self.queries if self.queries else 0.0

    @property
    def random_median_rank(self) -> float:
        """무작위 순위의 중앙값. 실패 순위 중앙값을 읽는 기준선이다."""
        return (self.queries + 1) / 2.0 if self.queries else 0.0

    def as_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "top1_accuracy": round(self.top1, 6),
            "top1_std": round(self.top1_std, 6),
            "queries": self.queries,
            "random_top1": round(self.random_top1, 8),
            "random_median_rank": round(self.random_median_rank, 1),
            "mrr": round(self.mrr, 6),
            "recall_at_5": round(self.recall_at_5, 6),
            "recall_at_10": round(self.recall_at_10, 6),
            "miss_median_rank": round(self.miss_median_rank, 3),
            "split": self.split.as_record(),
        }
        if len(self.scores) > 1:
            record["repeats"] = [score.as_record() for score in self.scores]
        return record


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """실행 결과 전체. 그대로 JSON으로 떨어진다."""

    config: EvaluationConfig
    tracks: int
    skipped: tuple[tuple[str, str], ...]
    dimension: int
    consistency: ConsistencyRun
    anisotropy: float = 0.0
    """전체 쌍 평균 코사인. 1에 가까울수록 공간이 뭉쳐 허브 곡이 생긴다."""

    metrics: tuple[LabeledMetric, ...] = ()

    @property
    def self_consistency(self) -> float:
        """게이트가 보는 값. 반복이 여럿이면 평균이다."""
        return self.consistency.top1

    @property
    def self_consistency_queries(self) -> int:
        return self.consistency.queries

    @property
    def gate_passed(self) -> bool:
        return self.self_consistency >= self.config.gate

    def as_record(self) -> dict[str, object]:
        return {
            "config": self.config.as_record(),
            "corpus": {
                "tracks": self.tracks,
                "skipped": len(self.skipped),
                "dimension": self.dimension,
                "anisotropy": round(self.anisotropy, 6),
            },
            "m0_self_consistency": {
                **self.consistency.as_record(),
                "gate": self.config.gate,
                "passed": self.gate_passed,
            },
            "metrics": [metric.as_record() for metric in self.metrics],
        }


class EvaluateRetrieval:
    """npz 임베딩과 태그 라벨만으로 검색 품질을 잰다.

    1004 x 768 행렬 다섯 개에 1004x1004 코사인이면 CPU에서 수 초다.
    GPU가 없는 기기에서 도는 것이 설계 요건이다.
    """

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self._config = config or EvaluationConfig()

    def run(self, tracks: Iterable[TrackRecord]) -> EvaluationReport:
        usable, skipped = self._partition(tracks)
        if not usable:
            raise ValueError("평가할 수 있는 곡이 없다")

        consistency = self._self_consistency(usable)
        vectors = np.asarray([self._view(track.embeddings) for track in usable], dtype=np.float32)
        if self._config.view.centered:
            vectors = center(vectors, mean_direction(vectors))
        report = EvaluationReport(
            config=self._config,
            tracks=len(usable),
            skipped=tuple(skipped),
            dimension=int(vectors.shape[1]),
            consistency=consistency,
            anisotropy=anisotropy(vectors),
        )
        if not report.gate_passed and not self._config.force:
            return report

        similarity = cosine_similarity(vectors, vectors)
        albums = [label_key(track.album) for track in usable]
        artists = [label_key(track.artist) for track in usable]

        same_album = _same_label(albums)
        same_artist = _same_label(artists)
        identity = np.eye(len(usable), dtype=np.bool_)

        # M1은 자기 자신만 뺀다. M2는 같은 앨범 곡을 후보에서 통째로 뺀다.
        # 안 빼면 동일 마스터링·믹스가 만드는 앨범 효과를 아티스트 유사도로
        # 착각한다. MIR의 오래된 함정이다.
        return replace(
            report,
            metrics=(
                self._metric("m1_album", similarity, same_album, identity),
                self._metric("m2_artist", similarity, same_artist, same_album | identity),
            ),
        )

    def _partition(
        self, tracks: Iterable[TrackRecord]
    ) -> tuple[list[TrackRecord], list[tuple[str, str]]]:
        """뷰를 만들 수 없는 곡을 걸러낸다. 버린 이유를 곡별로 남긴다."""
        usable: list[TrackRecord] = []
        skipped: list[tuple[str, str]] = []
        for track in tracks:
            missing = [key for key in self._config.view.keys if key not in track.embeddings]
            if missing:
                skipped.append((track.source_key, f"임베딩 키 없음: {','.join(missing)}"))
                continue
            chunks = min(int(track.embeddings[key].shape[0]) for key in self._config.view.keys)
            if chunks < MIN_CHUNKS:
                skipped.append((track.source_key, f"청크 {chunks}개 (최소 {MIN_CHUNKS})"))
                continue
            usable.append(track)
        return usable, skipped

    def _view(self, embeddings: Mapping[str, Embedding]) -> Vector:
        view = self._config.view
        return build_view(
            embeddings,
            view.keys,
            combine=view.combine,
            mode=view.pool,
            chunk_l2=view.chunk_l2,
            block_l2=view.block_l2,
        )

    def _self_consistency(self, tracks: Sequence[TrackRecord]) -> ConsistencyRun:
        """곡의 한 조각으로 나머지 조각을 찾는다 (M0).

        라벨이 필요 없고 외부 지식도 필요 없다. 임베딩이 곡 정체성을 담고
        있는지만 본다. 여기서 무너지면 그 아래 지표는 전부 무의미하다.

        **자르는 방법은 이제 설정이다.** 홀짝은 오디오축의 정본이자 기본값이며,
        무작위 분할은 그 결정성이 결과에 얼마나 기여하는지를 재기 위한 대조군이다.
        """
        split = self._config.split
        scores = tuple(self._consistency_once(tracks, repeat) for repeat in range(split.repeats))
        return ConsistencyRun(split=split, scores=scores)

    def _consistency_once(self, tracks: Sequence[TrackRecord], repeat: int) -> ConsistencyScore:
        left_rows: list[Vector] = []
        right_rows: list[Vector] = []
        for index, track in enumerate(tracks):
            halves = {
                key: self._split(track.embeddings[key], repeat=repeat, index=index)
                for key in self._config.view.keys
            }
            left_rows.append(self._view({key: pair[0] for key, pair in halves.items()}))
            right_rows.append(self._view({key: pair[1] for key, pair in halves.items()}))
        left = np.asarray(left_rows, dtype=np.float32)
        right = np.asarray(right_rows, dtype=np.float32)
        if self._config.view.centered:
            # 두 조각에 같은 중심을 쓴다. 각자 중심을 빼면 서로 다른 좌표계로
            # 옮겨져 M0가 임베딩이 아니라 좌표계 차이를 재게 된다.
            direction = mean_direction(np.concatenate([left, right]))
            left = center(left, direction)
            right = center(right, direction)
        return score_consistency(cosine_similarity(left, right))

    def _split(
        self, embedding: Embedding, *, repeat: int, index: int
    ) -> tuple[Embedding, Embedding]:
        split = self._config.split
        if split.mode is SplitMode.ODD_EVEN:
            return split_odd_even(embedding)
        # 곡마다 다른 분할을 쓰되 재현 가능해야 한다. 곡 인덱스와 회차를 시드에
        # 함께 넣으면 하나의 생성기를 순회하는 방식과 달리 **곡 순서나 --limit이
        # 바뀌어도 같은 곡은 같은 분할을 받는다.**
        seed = int(np.random.SeedSequence([split.seed, repeat, index]).generate_state(1)[0])
        return split_random(embedding, ratio=split.ratio, seed=seed)

    def _metric(
        self, name: str, similarity: Matrix, relevant: BoolMatrix, excluded: BoolMatrix
    ) -> LabeledMetric:
        masked_relevant = np.asarray(relevant & ~excluded, dtype=np.bool_)
        generator = np.random.default_rng(self._config.seed)
        noise = np.asarray(generator.random(similarity.shape), dtype=np.float32)
        return LabeledMetric(
            name=name,
            measured=score_retrieval(similarity, masked_relevant, excluded, self._config.k),
            random=score_retrieval(noise, masked_relevant, excluded, self._config.k),
            expected_random_precision=expected_random_precision(masked_relevant, excluded),
        )


def _same_label(labels: Sequence[str | None]) -> BoolMatrix:
    """같은 라벨이면 True인 (곡, 곡) 행렬. 라벨이 없는 곡은 어디에도 안 묶인다.

    문자열 비교를 N^2번 하지 않고 정수 코드로 바꿔 비교한다. 라벨 없음은
    음수 코드를 곡마다 다르게 주어 자기 자신 외에는 결코 일치하지 않게 한다.
    """
    codes: dict[str, int] = {}
    encoded: list[int] = []
    for index, label in enumerate(labels):
        if label is None:
            encoded.append(-index - 1)
            continue
        encoded.append(codes.setdefault(label, len(codes)))
    column = np.asarray(encoded, dtype=np.int64).reshape(-1, 1)
    return np.asarray(column == column.T, dtype=np.bool_)
