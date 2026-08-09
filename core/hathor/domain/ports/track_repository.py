"""트랙 저장소 포트. 구현은 infrastructure가 담당한다 (DIP)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from hathor.domain.entities.track import Track


class TrackRepository(Protocol):
    """도메인이 요구하는 최소 인터페이스만 선언한다 (ISP)."""

    def add(self, track: Track) -> None: ...

    def find_by_id(self, track_id: UUID) -> Track | None: ...

    def count_all(self) -> int: ...
