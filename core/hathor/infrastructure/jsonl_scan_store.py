"""스캔 산출물 JSONL 기록과 이전 스냅샷 적재."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.domain.entities.scan_event import ScanEventKind
from hathor.domain.entities.scan_failure import ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hathor.application.scan_library import ScanRecord, Snapshot
    from hathor.application.scan_summary import ScanSummary

TRACKS_SUFFIX = ".jsonl"
FAILURES_SUFFIX = ".failures.jsonl"
SUMMARY_SUFFIX = ".summary.json"


def track_as_record(track: ScannedTrack, kind: ScanEventKind) -> dict[str, object]:
    """키 순서를 고정한다. 2대 노트북 산출물이 바이트 단위로 같아야 한다(D-0009)."""
    return {
        "source_key": track.source_key,
        "event": kind.value,
        "file_size_bytes": track.file_size_bytes,
        "modified_at": track.modified_at.isoformat(),
        "stream": {
            "sample_rate_hz": track.stream.sample_rate_hz,
            "channels": track.stream.channels,
            "duration_ms": track.stream.duration_ms,
            "bitrate_bps": track.stream.bitrate_bps,
            "codec": track.stream.codec,
        },
        "tags": {
            "title": track.tags.title,
            "artist": track.tags.artist,
            "album": track.tags.album,
            "lyrics_text": track.tags.lyrics_text,
            "has_album_art": track.tags.has_album_art,
            "has_synced_lyrics": track.tags.has_synced_lyrics,
            "release_date_raw": track.tags.release_date_raw,
            "isrc": track.tags.isrc,
        },
        "raw_frame_names": list(track.raw_frame_names),
    }


def failure_as_record(failure: ScanFailure, kind: ScanEventKind) -> dict[str, object]:
    return {
        "source_key": failure.source_key,
        "event": kind.value,
        "failure_kind": failure.failure_kind.value,
        "detail": failure.detail,
    }


class JsonlScanStore:
    """스캔 산출물을 JSONL 3종으로 기록하고 이전 스냅샷을 읽는다.

    산출물은 var/ 아래에 두며 저장소에 커밋하지 않는다.
    파일명에만 실행 시각을 넣고 내용에는 넣지 않는다(재현성).
    """

    def __init__(self, output_root: Path) -> None:
        self._root = output_root

    def latest_snapshot(self) -> Snapshot:
        """가장 최근 산출물에서 (mtime, size) 스냅샷을 만든다.

        산출물이 없으면 빈 스냅샷을 반환하고 전수 스캔이 된다.
        """
        latest = self._latest_tracks_path()
        if latest is None:
            return {}

        snapshot: Snapshot = {}
        with latest.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                snapshot[record["source_key"]] = (
                    record["modified_at"],
                    record["file_size_bytes"],
                )
        return snapshot

    def _latest_tracks_path(self) -> Path | None:
        if not self._root.is_dir():
            return None
        candidates = sorted(
            path
            for path in self._root.glob(f"scan-*{TRACKS_SUFFIX}")
            if not path.name.endswith(FAILURES_SUFFIX)
        )
        return candidates[-1] if candidates else None

    def write(self, records: Iterable[ScanRecord], summary: ScanSummary) -> Path:
        """레코드를 스트리밍 기록하고 요약 파일 경로를 반환한다."""
        self._root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        base = self._root / f"scan-{stamp}"

        tracks_path = base.with_suffix(TRACKS_SUFFIX)
        failures_path = Path(f"{base}{FAILURES_SUFFIX}")
        summary_path = Path(f"{base}{SUMMARY_SUFFIX}")

        with (
            tracks_path.open("w", encoding="utf-8") as tracks,
            failures_path.open("w", encoding="utf-8") as failures,
        ):
            for record in records:
                outcome = record.outcome
                if isinstance(outcome, ScannedTrack):
                    line = track_as_record(outcome, record.event.kind)
                    self._write_line(tracks, line)
                elif isinstance(outcome, ScanFailure):
                    line = failure_as_record(outcome, record.event.kind)
                    self._write_line(failures, line)
                else:
                    self._write_line(
                        failures,
                        {
                            "source_key": record.event.source_key,
                            "event": ScanEventKind.REMOVED.value,
                        },
                    )

        summary_path.write_text(
            json.dumps(summary.as_record(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary_path

    @staticmethod
    def _write_line(stream: object, record: dict[str, object]) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=False)
        stream.write(line + "\n")  # type: ignore[attr-defined]
