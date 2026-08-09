"""인메모리 트랙 저장소. P1에서 PostgreSQL 구현으로 교체된다."""

from __future__ import annotations

from uuid import UUID

from hathor.domain.entities.track import Track


class InMemoryTrackRepository:
    """TrackRepository 포트의 테스트·부트스트랩용 구현."""

    def __init__(self) -> None:
        self._tracks: dict[UUID, Track] = {}

    def add(self, track: Track) -> None:
        self._tracks[track.track_id] = track

    def find_by_id(self, track_id: UUID) -> Track | None:
        return self._tracks.get(track_id)

    def count_all(self) -> int:
        return len(self._tracks)
