"""퓨전 결합 규칙 평가 (M4).

**문제**: `밤편지 + 뱅뱅뱅` 상위 10곡 중 4곡이 아이유였다. 두 시드의 중점을
찾은 것이 아니라 한쪽으로 쏠렸다. 결합 규칙(MEAN)이 **한쪽에 극단적으로
가까운 곡을 선호**하기 때문이다 (`fuse_scores` 참조).

**그래서 규칙을 바꿀 것인가?** 눈으로 한 사례만 보고 정하면 다른 시드 조합에서
더 나빠져도 알 수 없다. M1/M2는 단일 질의 지표라 여기에 쓸 수 없으므로
퓨전 전용 지표를 만든다.

### M4 — 시드 아티스트 균형

서로 다른 아티스트의 곡 두 개를 시드로 무작위 추출하고 상위 k개를 본다.

- **coverage**: 상위 k 중 두 시드 아티스트의 곡 비율. 시드와 무관한 곡만 나오면
  퓨전이 아무 데도 가리키지 않은 것이다.
- **artist_imbalance**: `|nA - nB| / (nA + nB)`. 0이면 양쪽이 같은 수, 1이면 한쪽뿐이다.
- **cosine_imbalance**: 상위 k 각 곡의 시드별 유사도 차이 평균. 라벨 없이도
  쏠림을 재며, 시드 아티스트의 곡이 상위에 없을 때도 값이 나온다.

**균형만 좋으면 되는 것이 아니다.** 두 시드 모두에서 먼 밋밋한 곡만 뽑아도
균형은 완벽해진다. 그래서 coverage와 평균 유사도를 함께 낸다. **셋을 같이 보고
판단하며, 하나만 인용하지 않는다.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from hathor.application.search_similar import SearchTrack
from hathor.domain.services.embedding_pooling import PoolMode, build_view
from hathor.domain.services.isotropy import center, mean_direction
from hathor.domain.services.retrieval_metrics import cosine_similarity
from hathor.domain.services.seed_search import FusionMode, fuse_scores


def _finite(value: float) -> float | None:
    """NaN은 JSON에 담기지 않는다. oracle은 유사도를 계산하지 않으므로 None이다."""
    return None if np.isnan(value) else round(value, 6)


DEFAULT_PAIRS = 200
DEFAULT_K = 10
DEFAULT_SEED = 20260817


@dataclass(frozen=True, slots=True)
class FusionScore:
    mode: str
    pairs: int
    coverage: float
    artist_imbalance: float
    cosine_imbalance: float
    mean_similarity: float

    def as_record(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "pairs": self.pairs,
            "coverage": round(self.coverage, 6),
            "artist_imbalance": round(self.artist_imbalance, 6),
            "cosine_imbalance": _finite(self.cosine_imbalance),
            "mean_similarity": _finite(self.mean_similarity),
        }


@dataclass(frozen=True, slots=True)
class FusionReport:
    tracks: int
    k: int
    seed: int
    scores: tuple[FusionScore, ...]

    def as_record(self) -> dict[str, object]:
        return {
            "corpus": {"tracks": self.tracks},
            "config": {"k": self.k, "seed": self.seed},
            "modes": [score.as_record() for score in self.scores],
        }


class EvaluateFusion:
    """여러 결합 규칙을 같은 시드 쌍으로 비교한다.

    모드마다 다른 쌍을 쓰면 규칙 차이인지 쌍 차이인지 구분되지 않는다.
    **쌍을 한 번 뽑아 모든 모드에 그대로 쓴다.**
    """

    def __init__(
        self,
        keys: Sequence[str] = ("layer00",),
        *,
        pool: PoolMode = PoolMode.MEAN,
        centered: bool = True,
        k: int = DEFAULT_K,
        pairs: int = DEFAULT_PAIRS,
        seed: int = DEFAULT_SEED,
        penalty: float = 1.0,
    ) -> None:
        self._keys = tuple(keys)
        self._pool = pool
        self._centered = centered
        self._k = k
        self._pairs = pairs
        self._seed = seed
        self._penalty = penalty

    def run(self, tracks: Sequence[SearchTrack], modes: Sequence[FusionMode]) -> FusionReport:
        if self._k <= 0 or self._pairs <= 0:
            raise ValueError("k와 pairs는 1 이상이어야 한다")
        if len(tracks) < 3:
            raise ValueError("곡이 셋 이상이어야 퓨전을 평가할 수 있다")

        vectors = np.asarray(
            [build_view(track.embeddings, self._keys, mode=self._pool) for track in tracks],
            dtype=np.float32,
        )
        if self._centered:
            vectors = center(vectors, mean_direction(vectors))
        similarity = cosine_similarity(vectors, vectors)
        artists = [(track.artist or "").strip().casefold() for track in tracks]
        pairs = self._sample_pairs(artists)
        if not pairs:
            raise ValueError("아티스트가 다른 시드 쌍을 만들 수 없다")

        scores = [self._score(mode.value, similarity, artists, pairs, mode=mode) for mode in modes]
        scores.append(self._random_baseline(similarity, artists, pairs))
        scores.append(self._oracle_baseline(artists, pairs))
        return FusionReport(tracks=len(tracks), k=self._k, seed=self._seed, scores=tuple(scores))

    def _random_baseline(
        self,
        similarity: np.ndarray[tuple[int, int], np.dtype[np.float32]],
        artists: Sequence[str],
        pairs: Sequence[tuple[int, int]],
    ) -> FusionScore:
        """무작위 순위를 같은 코드 경로에 태운다. 별도 계산식을 쓰지 않는다.

        마스크나 제외 처리에 결함이 있으면 베이스라인에도 똑같이 반영되어
        비교가 무의미해지는 것을 막는다 (D-0023과 같은 방식).
        """
        generator = np.random.default_rng(self._seed)
        noise = np.asarray(generator.random(similarity.shape), dtype=np.float32)
        return self._score("random", similarity, artists, pairs, mode=None, scoring=noise)

    def _oracle_baseline(
        self, artists: Sequence[str], pairs: Sequence[tuple[int, int]]
    ) -> FusionScore:
        """코퍼스 구성상 도달 가능한 최선. 어떤 규칙도 이 값을 넘을 수 없다.

        시드를 뺀 뒤 두 아티스트의 곡을 최대한 균형 있게 담았을 때의 coverage와
        불균형을 센다. 유사도는 계산하지 않는다 — 순서가 아니라 **구성의 상한**이다.

        시드 아티스트의 곡이 코퍼스에 2곡뿐이면 상위 k에 1곡만 올 수 있다.
        그 바닥을 드러내는 것이 이 베이스라인의 목적이다.
        """
        counts: dict[str, int] = {}
        for artist in artists:
            if artist:
                counts[artist] = counts.get(artist, 0) + 1

        coverages: list[float] = []
        gaps: list[float] = []
        for left, right in pairs:
            available = sorted((counts[artists[left]] - 1, counts[artists[right]] - 1))
            smaller, larger = available
            taken_small = min(smaller, self._k // 2)
            taken_large = min(larger, self._k - taken_small)
            total = taken_small + taken_large
            coverages.append(total / self._k)
            if total:
                gaps.append(abs(taken_large - taken_small) / total)

        return FusionScore(
            mode="oracle",
            pairs=len(pairs),
            coverage=float(np.mean(coverages)) if coverages else 0.0,
            artist_imbalance=float(np.mean(gaps)) if gaps else 0.0,
            cosine_imbalance=float("nan"),
            mean_similarity=float("nan"),
        )

    def _sample_pairs(self, artists: Sequence[str]) -> list[tuple[int, int]]:
        """아티스트가 서로 다른 시드 쌍. 같은 아티스트면 균형을 잴 수 없다."""
        generator = np.random.default_rng(self._seed)
        picked: list[tuple[int, int]] = []
        attempts = 0
        limit = max(self._pairs * 50, 1000)
        while len(picked) < self._pairs and attempts < limit:
            attempts += 1
            left, right = (int(value) for value in generator.choice(len(artists), 2, replace=False))
            if not artists[left] or not artists[right] or artists[left] == artists[right]:
                continue
            picked.append((left, right))
        return picked

    def _score(
        self,
        label: str,
        similarity: np.ndarray[tuple[int, int], np.dtype[np.float32]],
        artists: Sequence[str],
        pairs: Sequence[tuple[int, int]],
        *,
        mode: FusionMode | None,
        scoring: np.ndarray[tuple[int, int], np.dtype[np.float32]] | None = None,
    ) -> FusionScore:
        coverages: list[float] = []
        artist_gaps: list[float] = []
        cosine_gaps: list[float] = []
        similarities: list[float] = []

        for left, right in pairs:
            rows = similarity[[left, right], :]
            if mode is None:
                # 베이스라인도 시드별 쏠림을 재야 하므로 순위와 유사도를 분리한다.
                # 순위는 무작위 점수로 매기되, 불균형은 실제 코사인으로 잰다.
                assert scoring is not None
                scores = np.asarray(scoring[left], dtype=np.float32).copy()
            else:
                scores = fuse_scores(rows, mode, penalty=self._penalty)
            scores[[left, right]] = -np.inf
            top = np.argsort(-scores, kind="stable")[: self._k]

            left_hits = sum(1 for position in top if artists[position] == artists[left])
            right_hits = sum(1 for position in top if artists[position] == artists[right])
            total = left_hits + right_hits
            coverages.append(total / self._k)
            if total:
                artist_gaps.append(abs(left_hits - right_hits) / total)
            cosine_gaps.append(float(np.mean(np.abs(rows[0, top] - rows[1, top]))))
            actual = fuse_scores(rows, mode or FusionMode.MEAN, penalty=self._penalty)
            similarities.append(float(np.mean(actual[top])))

        return FusionScore(
            mode=label,
            pairs=len(pairs),
            coverage=float(np.mean(coverages)),
            artist_imbalance=float(np.mean(artist_gaps)) if artist_gaps else 0.0,
            cosine_imbalance=float(np.mean(cosine_gaps)),
            mean_similarity=float(np.mean(similarities)),
        )
