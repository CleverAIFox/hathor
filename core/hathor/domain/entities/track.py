"""라이브러리 음원 엔티티."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Track:
    """인제스트가 해석한 음원 1건. 파일이 아니라 정규화된 곡을 가리킨다."""

    title: str
    artist: str
    duration_ms: int
    source_path: str
    track_id: UUID = field(default_factory=uuid4)
    isrc: str | None = None
    has_lyric_tag: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise ValueError("재생 시간은 양수여야 한다")
        if not self.title.strip():
            raise ValueError("제목이 비어 있다")

    @property
    def is_normalized(self) -> bool:
        """ISRC 보유 시 정규화 신뢰도 1.00으로 본다 (부록 B)."""
        return self.isrc is not None
