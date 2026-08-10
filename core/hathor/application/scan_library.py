"""라이브러리 스캔 유스케이스. 순회 결과를 집계하고 델타를 판정한다."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from hathor.application.scan_summary import ScanSummary
from hathor.domain.entities.scan_event import ScanEvent, ScanEventKind
from hathor.domain.entities.scan_failure import ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.ports.library_scanner import LibraryScanner

type Snapshot = dict[str, tuple[str, int]]
"""source_key -> (modified_at ISO 문자열, file_size_bytes)"""


@dataclass(frozen=True, slots=True)
class ScanRecord:
    """스캔 결과 1건과 그 델타 판정.

    REMOVED 이벤트는 outcome이 None이다. 파일이 사라진 것은 실패가 아니라
    정상적인 라이브러리 변화이므로 ScanFailure로 표현하지 않는다.
    """

    outcome: ScannedTrack | ScanFailure | None
    event: ScanEvent


class ScanLibrary:
    """라이브러리를 순회하며 결과를 방출하고 요약을 누적한다.

    파일을 쓰지 않는다. 산출물 기록은 호출자(infrastructure)의 책임이다.
    결과를 리스트로 모으지 않고 스트리밍한다.
    """

    def __init__(self, scanner: LibraryScanner) -> None:
        self._scanner = scanner
        self.summary = ScanSummary()

    def run(self, root: Path, previous: Snapshot | None = None) -> Iterator[ScanRecord]:
        baseline: Snapshot = previous or {}
        seen: set[str] = set()

        for outcome in self._scanner.scan(root):
            seen.add(outcome.source_key)
            event = ScanEvent(
                source_key=outcome.source_key,
                kind=self._classify(outcome, baseline),
            )
            self._accumulate(outcome, event)
            yield ScanRecord(outcome=outcome, event=event)

        for source_key in sorted(set(baseline) - seen):
            event = ScanEvent(source_key=source_key, kind=ScanEventKind.REMOVED)
            self.summary.removed += 1
            yield ScanRecord(outcome=None, event=event)

    @staticmethod
    def _classify(outcome: ScannedTrack | ScanFailure, baseline: Snapshot) -> ScanEventKind:
        if not isinstance(outcome, ScannedTrack):
            return ScanEventKind.MODIFIED
        recorded = baseline.get(outcome.source_key)
        if recorded is None:
            return ScanEventKind.DISCOVERED
        current = (outcome.modified_at.isoformat(), outcome.file_size_bytes)
        return ScanEventKind.UNCHANGED if recorded == current else ScanEventKind.MODIFIED

    def _accumulate(self, outcome: ScannedTrack | ScanFailure, event: ScanEvent) -> None:
        summary = self.summary
        summary.total_files += 1

        if event.kind is ScanEventKind.DISCOVERED:
            summary.discovered += 1
        elif event.kind is ScanEventKind.MODIFIED:
            summary.modified += 1
        elif event.kind is ScanEventKind.UNCHANGED:
            summary.unchanged += 1

        if isinstance(outcome, ScanFailure):
            summary.failed += 1
            key = outcome.failure_kind.value
            summary.failures_by_kind[key] = summary.failures_by_kind.get(key, 0) + 1
            return

        summary.succeeded += 1
        summary.total_bytes += outcome.file_size_bytes
        summary.total_duration_ms += outcome.stream.duration_ms

        rate = str(outcome.stream.sample_rate_hz)
        summary.sample_rates[rate] = summary.sample_rates.get(rate, 0) + 1

        for name in outcome.raw_frame_names:
            prefix = name.split(":")[0]
            summary.frame_histogram[prefix] = summary.frame_histogram.get(prefix, 0) + 1

        tags = outcome.tags
        summary.with_title += tags.title is not None
        summary.with_artist += tags.artist is not None
        summary.with_album += tags.album is not None
        summary.with_lyrics += tags.lyrics_text is not None
        summary.with_album_art += tags.has_album_art
        summary.with_synced_lyrics += tags.has_synced_lyrics
