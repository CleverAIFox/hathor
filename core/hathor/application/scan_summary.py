"""스캔 집계 결과. 라이브러리 상태를 한눈에 보기 위한 요약이다."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScanSummary:
    """스캔 1회의 집계. 순회 중 점진적으로 채워진다.

    실행 시각을 담지 않는다. 동일 라이브러리를 2대 노트북에서 스캔했을 때
    내용이 바이트 단위로 같아야 하기 때문이다(D-0009, 재현성 CI 잡).
    시각은 파일명에만 쓴다.
    """

    total_files: int = 0
    succeeded: int = 0
    failed: int = 0

    discovered: int = 0
    modified: int = 0
    removed: int = 0
    unchanged: int = 0

    failures_by_kind: dict[str, int] = field(default_factory=dict)
    frame_histogram: dict[str, int] = field(default_factory=dict)
    sample_rates: dict[str, int] = field(default_factory=dict)

    with_title: int = 0
    with_artist: int = 0
    with_album: int = 0
    with_lyrics: int = 0
    with_album_art: int = 0
    with_synced_lyrics: int = 0

    total_duration_ms: int = 0
    total_bytes: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.succeeded / self.total_files

    @property
    def total_duration_hours(self) -> float:
        return self.total_duration_ms / 1000 / 3600

    @property
    def removal_rate(self) -> float:
        """소실 비율. 외장 볼륨 미연결 시 1.0에 근접하므로 경보 지표다(D-0013)."""
        previous_total = self.removed + self.unchanged + self.modified
        if previous_total == 0:
            return 0.0
        return self.removed / previous_total

    def as_record(self) -> dict[str, object]:
        """JSON 직렬화용 딕셔너리. 키 순서를 고정한다."""
        return {
            "total_files": self.total_files,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4),
            "total_duration_hours": round(self.total_duration_hours, 2),
            "total_bytes": self.total_bytes,
            "delta": {
                "discovered": self.discovered,
                "modified": self.modified,
                "removed": self.removed,
                "unchanged": self.unchanged,
            },
            "failures_by_kind": dict(sorted(self.failures_by_kind.items())),
            "sample_rates": dict(sorted(self.sample_rates.items())),
            "frame_histogram": dict(sorted(self.frame_histogram.items())),
            "tag_coverage": {
                "title": self.with_title,
                "artist": self.with_artist,
                "album": self.with_album,
                "lyrics": self.with_lyrics,
                "album_art": self.with_album_art,
                "synced_lyrics": self.with_synced_lyrics,
            },
        }
