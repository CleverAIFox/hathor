"""스캐너·추출기 계약 검증. 실제 mp3를 생성해 통합 동작을 확인한다."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hathor.domain.entities.scan_failure import FailureKind, ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.infrastructure.filesystem_scanner import FilesystemLibraryScanner
from hathor.infrastructure.mutagen_tag_extractor import MutagenTagExtractor
from tests.conftest import requires_ffmpeg

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def scanner() -> FilesystemLibraryScanner:
    return FilesystemLibraryScanner(MutagenTagExtractor())


@requires_ffmpeg
class TestTagExtraction:
    def test_reads_four_valid_frames(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        make_mp3(
            tmp_path / "자우림-스물다섯.mp3",
            title="스물다섯",
            artist="자우림",
            album="Ashes To Ashes",
            lyrics="가사 본문",
            album_art=True,
        )
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.tags.title == "스물다섯"
        assert result.tags.artist == "자우림"
        assert result.tags.album == "Ashes To Ashes"
        assert result.tags.lyrics_text == "가사 본문"
        assert result.tags.has_album_art is True
        assert result.tags.has_synced_lyrics is False

    def test_preserves_featuring_artist_verbatim(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        """아티스트 원문을 정규화하지 않는다. 분해는 유닛 #2 책임이다."""
        raw = "10CM, BIG Naughty (서동현)"
        make_mp3(tmp_path / "a.mp3", title="제목", artist=raw)
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.tags.artist == raw

    def test_untagged_file_yields_none_fields(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        make_mp3(tmp_path / "무태그.mp3")
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.tags.title is None
        assert result.tags.is_identifiable is False

    def test_release_date_and_isrc_stay_none(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        """D-0010: 인제스트는 발매일·ISRC를 태그에서 읽지 않는다."""
        make_mp3(tmp_path / "a.mp3", title="제목", artist="가수")
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.tags.release_date_raw is None
        assert result.tags.isrc is None


@requires_ffmpeg
class TestStreamProperties:
    def test_reads_sample_rate_and_channels(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        make_mp3(tmp_path / "a.mp3", title="제목", sample_rate=48000)
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.stream.sample_rate_hz == 48000
        assert result.stream.channels == 2
        assert result.stream.codec == "mp3"
        assert result.stream.duration_ms > 0


@requires_ffmpeg
class TestSourceKey:
    def test_is_relative_not_absolute(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        """절대경로가 새면 2대 노트북의 산출물이 달라진다(D-0009)."""
        make_mp3(tmp_path / "하위" / "a.mp3", title="제목")
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScannedTrack)
        assert result.source_key == "하위/a.mp3"
        assert str(tmp_path) not in result.source_key


@requires_ffmpeg
class TestDeterminism:
    def test_emission_order_is_sorted(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        for name in ("c.mp3", "a.mp3", "b.mp3"):
            make_mp3(tmp_path / name, title=name)

        keys = [r.source_key for r in scanner.scan(tmp_path)]
        assert keys == sorted(keys)

    def test_repeated_scans_match(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        for name in ("a.mp3", "b.mp3"):
            make_mp3(tmp_path / name, title=name)

        first = [r.source_key for r in scanner.scan(tmp_path)]
        second = [r.source_key for r in scanner.scan(tmp_path)]
        assert first == second


@requires_ffmpeg
class TestFailureIsolation:
    def test_corrupt_file_does_not_stop_scan(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
        make_mp3: Callable[..., Path],
    ) -> None:
        """단일 파일 실패가 1004곡 순회를 중단시켜서는 안 된다."""
        make_mp3(tmp_path / "a.mp3", title="정상")
        (tmp_path / "b.mp3").write_text("이건 mp3가 아니다", encoding="utf-8")
        make_mp3(tmp_path / "c.mp3", title="정상2")

        results = list(scanner.scan(tmp_path))

        assert len(results) == 3
        assert sum(isinstance(r, ScannedTrack) for r in results) == 2
        assert sum(isinstance(r, ScanFailure) for r in results) == 1

    def test_empty_file_is_classified(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
    ) -> None:
        (tmp_path / "빈파일.mp3").touch()
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScanFailure)
        assert result.failure_kind is not FailureKind.UNEXPECTED_ERROR

    def test_failure_detail_has_no_absolute_path(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
    ) -> None:
        (tmp_path / "깨진.mp3").write_bytes(b"\x00" * 64)
        (result,) = list(scanner.scan(tmp_path))

        assert isinstance(result, ScanFailure)
        assert str(tmp_path) not in result.detail


class TestNonAudioFiles:
    def test_ignores_non_mp3_extensions(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
    ) -> None:
        (tmp_path / "노래.txt").write_text("위시리스트", encoding="utf-8")
        (tmp_path / "커버.jfif").write_bytes(b"\xff\xd8")

        assert list(scanner.scan(tmp_path)) == []

    def test_empty_directory_yields_nothing(
        self,
        tmp_path: Path,
        scanner: FilesystemLibraryScanner,
    ) -> None:
        assert list(scanner.scan(tmp_path)) == []
