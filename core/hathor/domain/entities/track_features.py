"""곡 하나의 특징 묶음 (O-56 · D-0236).

**응용에 있었다.** 그래서 저장소(`NpzFeatureStore`)가 이것을 담으려면 계층을 거슬러
응용을 봐야 했고, 계약에 예외 다섯 줄이 있었다 (D-0190). 저장소가 담는 것은 응용의
산물이 아니라 **도메인의 것**이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hathor.domain.ports.audio_analysis import Embedding


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    """곡 하나의 특징. 스템별 임베딩과 혼합 임베딩을 갖는다."""

    source_key: str
    mixture: Embedding
    stems: dict[str, Embedding]

    @property
    def chunk_count(self) -> int:
        return int(self.mixture.shape[0])
