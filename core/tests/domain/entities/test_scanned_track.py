"""라이브러리 도메인 모델 계약 검증.

값 대입 자체는 검증하지 않는다(dataclass 문법 테스트는 무가치).
불변성, slots 강제, 파생 속성 계산만 확인한다.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scan_failure import FailureKind, ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags


def _stream() -> AudioStreamProperties:
    return AudioStreamProperties(
        sample_rate_hz=44100,
        channels=2,
        duration_ms=213_000,
        bitrate_bps=320_000,
        codec="mp3",
    )


def _tags() -> TrackTags:
    return TrackTags(
        title="스물다섯 스물하나",
        artist="자우림",
        album="Ashes To Ashes",
        lyrics_text="가사 본문",
        has_album_art=True,
        has_synced_lyrics=False,
    )


def _track() -> ScannedTrack:
    return ScannedTrack(
        source_key="자우림-스물다섯 스물하나.mp3",
        file_size_bytes=8_520_000,
        modified_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        stream=_stream(),
        tags=_tags(),
        raw_frame_names=("TIT2", "TPE1", "TALB", "USLT", "APIC"),
    )


class TestImmutability:
    def test_track_is_frozen(self) -> None:
        track = _track()
        with pytest.raises(FrozenInstanceError):
            track.source_key = "다른값"  # type: ignore[misc]

    def test_tags_are_frozen(self) -> None:
        tags = _tags()
        with pytest.raises(FrozenInstanceError):
            tags.title = "다른값"  # type: ignore[misc]

    def test_slots_reject_unknown_field(self) -> None:
        """slots=True이므로 오타 필드는 조용히 추가되지 않고 즉시 실패한다.

        frozen=True와 slots=True를 함께 쓰면 예외 타입이 파이썬 구현 세부사항에
        의존하므로(AttributeError 또는 TypeError) 타입을 고정하지 않는다.
        검증 대상은 "실패한다"와 "상태가 변하지 않는다"이다.
        """
        track = _track()
        with pytest.raises(Exception):  # noqa: B017
            track.sorce_key = "오타"  # type: ignore[attr-defined]
        assert not hasattr(track, "sorce_key")


class TestDerivedProperties:
    def test_duration_seconds(self) -> None:
        assert _stream().duration_seconds == pytest.approx(213.0)

    def test_is_mono_false_for_stereo(self) -> None:
        assert _stream().is_mono is False

    def test_is_identifiable_requires_both_title_and_artist(self) -> None:
        assert _tags().is_identifiable is True

    @pytest.mark.parametrize(
        ("title", "artist"),
        [(None, "자우림"), ("제목", None), (None, None), ("", "자우림")],
    )
    def test_is_identifiable_false_when_incomplete(
        self, title: str | None, artist: str | None
    ) -> None:
        tags = TrackTags(
            title=title,
            artist=artist,
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        )
        assert tags.is_identifiable is False


class TestExternalLookupFields:
    def test_release_date_and_isrc_default_to_none(self) -> None:
        """D-0010: 태그에 발매일·ISRC가 전량 부재하므로 인제스트는 채우지 않는다.

        유닛 #3의 AcoustID/MusicBrainz 조회가 이후에 채운다.
        """
        tags = _tags()
        assert tags.release_date_raw is None
        assert tags.isrc is None


class TestScanFailure:
    def test_failure_kind_values_are_stable(self) -> None:
        """실패 분류 문자열은 스캔 요약 집계 키로 쓰이므로 변경 시 산출물이 깨진다."""
        assert FailureKind.CORRUPT_HEADER.value == "corrupt_header"

    def test_failure_is_frozen(self) -> None:
        failure = ScanFailure(
            source_key="깨진파일.mp3",
            failure_kind=FailureKind.CORRUPT_HEADER,
            detail="ID3NoHeaderError",
        )
        with pytest.raises(FrozenInstanceError):
            failure.detail = "다른값"  # type: ignore[misc]
