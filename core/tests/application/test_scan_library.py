"""델타 감지 검증(D-0013). 재스캔 비용이 변경분에 비례해야 한다."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hathor.application.scan_library import ScanLibrary, Snapshot
from hathor.domain.entities.scan_event import ScanEventKind
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.infrastructure.filesystem_scanner import FilesystemLibraryScanner
from hathor.infrastructure.mutagen_tag_extractor import MutagenTagExtractor
from tests.conftest import requires_ffmpeg

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def use_case() -> ScanLibrary:
    return ScanLibrary(FilesystemLibraryScanner(MutagenTagExtractor()))


def _snapshot_of(root: Path) -> Snapshot:
    """현재 상태를 스냅샷으로 만든다."""
    scanner = ScanLibrary(FilesystemLibraryScanner(MutagenTagExtractor()))
    snapshot: Snapshot = {}
    for record in scanner.run(root):
        if isinstance(record.outcome, ScannedTrack):
            snapshot[record.outcome.source_key] = (
                record.outcome.modified_at.isoformat(),
                record.outcome.file_size_bytes,
            )
    return snapshot


@requires_ffmpeg
class TestDeltaDetection:
    def test_first_scan_is_all_discovered(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가")
        make_mp3(tmp_path / "b.mp3", title="나")

        kinds = [r.event.kind for r in use_case.run(tmp_path)]

        assert kinds == [ScanEventKind.DISCOVERED] * 2
        assert use_case.summary.discovered == 2

    def test_rescan_without_changes_is_all_unchanged(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가")
        make_mp3(tmp_path / "b.mp3", title="나")
        previous = _snapshot_of(tmp_path)

        kinds = [r.event.kind for r in use_case.run(tmp_path, previous)]

        assert kinds == [ScanEventKind.UNCHANGED] * 2
        assert use_case.summary.unchanged == 2
        assert use_case.summary.discovered == 0

    def test_new_file_is_discovered_others_unchanged(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가")
        previous = _snapshot_of(tmp_path)
        make_mp3(tmp_path / "b.mp3", title="나")

        records = list(use_case.run(tmp_path, previous))

        by_key = {r.event.source_key: r.event.kind for r in records}
        assert by_key["a.mp3"] is ScanEventKind.UNCHANGED
        assert by_key["b.mp3"] is ScanEventKind.DISCOVERED

    def test_size_change_is_modified(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가", seconds=1.0)
        previous = _snapshot_of(tmp_path)
        make_mp3(tmp_path / "a.mp3", title="가", seconds=2.0)

        (record,) = list(use_case.run(tmp_path, previous))

        assert record.event.kind is ScanEventKind.MODIFIED
        assert use_case.summary.modified == 1

    def test_deleted_file_is_removed_with_no_outcome(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        """소실은 실패가 아니므로 outcome이 None이다."""
        make_mp3(tmp_path / "a.mp3", title="가")
        make_mp3(tmp_path / "b.mp3", title="나")
        previous = _snapshot_of(tmp_path)
        (tmp_path / "b.mp3").unlink()

        records = list(use_case.run(tmp_path, previous))

        removed = [r for r in records if r.event.kind is ScanEventKind.REMOVED]
        assert len(removed) == 1
        assert removed[0].event.source_key == "b.mp3"
        assert removed[0].outcome is None
        assert use_case.summary.removed == 1
        assert use_case.summary.failed == 0

    def test_removal_rate_flags_disconnected_volume(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        """외장 볼륨 미연결을 전량 삭제로 오인하면 안 된다(D-0013)."""
        for name in ("a.mp3", "b.mp3", "c.mp3"):
            make_mp3(tmp_path / name, title=name)
        previous = _snapshot_of(tmp_path)
        for name in ("a.mp3", "b.mp3", "c.mp3"):
            (tmp_path / name).unlink()

        list(use_case.run(tmp_path, previous))

        assert use_case.summary.removal_rate == 1.0


@requires_ffmpeg
class TestSummaryAccumulation:
    def test_tag_coverage_counts(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가", artist="A", lyrics="가사")
        make_mp3(tmp_path / "b.mp3", title="나")

        list(use_case.run(tmp_path))
        summary = use_case.summary

        assert summary.with_title == 2
        assert summary.with_artist == 1
        assert summary.with_lyrics == 1
        assert summary.with_album == 0

    def test_failure_does_not_pollute_success_stats(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가")
        (tmp_path / "b.mp3").write_text("깨진 파일", encoding="utf-8")

        list(use_case.run(tmp_path))
        summary = use_case.summary

        assert summary.total_files == 2
        assert summary.succeeded == 1
        assert summary.failed == 1
        assert summary.success_rate == 0.5
        assert sum(summary.failures_by_kind.values()) == 1

    def test_sample_rate_histogram(
        self, tmp_path: Path, use_case: ScanLibrary, make_mp3: Callable[..., Path]
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="가", sample_rate=44100)
        make_mp3(tmp_path / "b.mp3", title="나", sample_rate=48000)

        list(use_case.run(tmp_path))

        assert use_case.summary.sample_rates == {"44100": 1, "48000": 1}
