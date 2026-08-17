"""시드곡 조합으로 유사곡을 찾는다 (D-0011 시드 퓨전).

프로젝트 최초의 사용자 대면 산출물이다. 지금까지 나온 것은 전부 지표였다.

**생성 없이 퓨전 개념을 검증한다.** "아이유 + 빅뱅"의 중점이 실제로 그럴듯한
곡을 가리키는지, 아무 데도 아닌 허공인지를 본다. 허공이면 생성 단계의 시드
조건도 성립하지 않으므로, 모델을 붙이기 전에 알아야 하는 문제다.

라벨도 학습도 필요 없다. 이미 뽑아둔 임베딩과 코사인뿐이다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from hathor.domain.ports.audio_analysis import Embedding
from hathor.domain.services.embedding_pooling import PoolMode, Vector, build_view
from hathor.domain.services.isotropy import center, mean_direction
from hathor.domain.services.retrieval_metrics import cosine_similarity
from hathor.domain.services.seed_search import chunk_timestamp, fuse, representative_chunk


@dataclass(frozen=True, slots=True)
class SearchTrack:
    """검색 대상 한 곡."""

    source_key: str
    artist: str | None
    title: str | None
    embeddings: Mapping[str, Embedding]

    @property
    def label(self) -> str:
        return f"{self.artist or '(아티스트 없음)'} — {self.title or self.source_key}"


@dataclass(frozen=True, slots=True)
class SearchHit:
    rank: int
    source_key: str
    label: str
    similarity: float
    highlight: str
    """반복도가 가장 높은 구간의 근사 위치. 후렴이라는 보장은 없다 (실측 필요)."""


class SearchSimilar:
    """시드 벡터를 접고 코사인으로 순위를 낸다.

    시드곡 자신은 결과에서 뺀다. 자기 자신이 1위로 나오는 것은 정보가 아니고
    k개 자리 중 하나를 낭비한다.
    """

    def __init__(
        self,
        keys: Sequence[str] = ("layer00",),
        pool: PoolMode = PoolMode.MEAN,
        *,
        centered: bool = True,
    ) -> None:
        self._keys = tuple(keys)
        self._pool = pool
        self._centered = centered
        """코퍼스 공통 방향을 제거한다. 끄면 허브 곡이 어떤 질의에도 상위에 온다."""

    def run(self, tracks: Sequence[SearchTrack], seeds: Sequence[str], k: int) -> list[SearchHit]:
        if k <= 0:
            raise ValueError("k는 1 이상이어야 한다")
        if not seeds:
            raise ValueError("시드가 최소 하나 필요하다")

        index = {track.source_key: position for position, track in enumerate(tracks)}
        missing = [seed for seed in seeds if seed not in index]
        if missing:
            raise KeyError(f"코퍼스에 없는 시드: {', '.join(missing)}")

        vectors = np.asarray([self._view(track.embeddings) for track in tracks], dtype=np.float32)
        if self._centered:
            # 시드와 후보에 같은 중심을 쓴다. 질의 벡터를 따로 중심화하면
            # 서로 다른 좌표계에서 코사인을 재게 된다.
            vectors = center(vectors, mean_direction(vectors))
        query = fuse([vectors[index[seed]] for seed in seeds]).reshape(1, -1)
        scores = cosine_similarity(query, vectors)[0]

        seed_positions = {index[seed] for seed in seeds}
        order = np.argsort(-scores, kind="stable")
        hits: list[SearchHit] = []
        for position in order:
            if int(position) in seed_positions:
                continue
            track = tracks[int(position)]
            hits.append(
                SearchHit(
                    rank=len(hits) + 1,
                    source_key=track.source_key,
                    label=track.label,
                    similarity=float(scores[position]),
                    highlight=chunk_timestamp(
                        representative_chunk(track.embeddings[self._keys[0]])
                    ),
                )
            )
            if len(hits) == k:
                break
        return hits

    def _view(self, embeddings: Mapping[str, Embedding]) -> Vector:
        return build_view(embeddings, self._keys, mode=self._pool)
