"""mutagen 기반 태그 추출기. TagExtractor 포트의 구현이다."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mutagen.mp3 import MP3

from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scan_failure import FailureKind
from hathor.domain.entities.track_tags import TrackTags
from hathor.domain.ports.library_scanner import ExtractionResult


class MissingAudioStreamError(Exception):
    """MPEG 헤더를 읽지 못해 스트림 속성이 없다."""

    failure_kind = FailureKind.MISSING_AUDIO_STREAM


class MutagenTagExtractor:
    """ID3 태그와 MPEG 헤더를 읽는다. 오디오는 디코딩하지 않는다.

    D-0010 실측(1004곡 전수): 유효 프레임은 TIT2/TPE1/TALB/USLT 4종뿐이다.
    발매일 프레임과 TSRC는 전량 부재하므로 읽으려 시도하지 않는다.
    APIC는 존재 여부만 기록하고 이미지 바이트는 산출물에 담지 않는다.
    """

    def extract(self, path: Path) -> ExtractionResult:
        audio: Any = MP3(path)  # type: ignore[no-untyped-call]
        stream_info: Any = audio.info
        if stream_info is None:
            raise MissingAudioStreamError(path.name)
        tags: Any = audio.tags

        frame_names = self._frame_names(tags)
        prefixes = frozenset(name.split(":")[0] for name in frame_names)

        return (
            TrackTags(
                title=self._first_text(tags, "TIT2"),
                artist=self._first_text(tags, "TPE1"),
                album=self._first_text(tags, "TALB"),
                lyrics_text=self._lyrics(tags),
                has_album_art="APIC" in prefixes,
                has_synced_lyrics="SYLT" in prefixes,
            ),
            AudioStreamProperties(
                sample_rate_hz=int(stream_info.sample_rate),
                channels=int(stream_info.channels),
                duration_ms=round(float(stream_info.length) * 1000),
                bitrate_bps=int(stream_info.bitrate),
                codec="mp3",
            ),
            frame_names,
        )

    @staticmethod
    def _frame_names(tags: Any) -> tuple[str, ...]:
        """프레임 키를 정렬해 반환한다. 값은 담지 않는다."""
        if tags is None:
            return ()
        return tuple(sorted(str(key) for key in tags))

    @staticmethod
    def _first_text(tags: Any, frame_id: str) -> str | None:
        """텍스트 프레임의 첫 값을 원문 그대로 반환한다.

        정규화하지 않는다. 아티스트의 피처링 분해는 유닛 #2가 담당한다.
        """
        if tags is None:
            return None
        frame = tags.get(frame_id)
        if frame is None:
            return None
        values = getattr(frame, "text", None)
        if not values:
            return None
        text = str(values[0]).strip()
        return text or None

    @staticmethod
    def _lyrics(tags: Any) -> str | None:
        """USLT 가사 본문. 다국어 프레임이 여럿이면 첫 번째를 쓴다."""
        if tags is None:
            return None
        for key in sorted(str(k) for k in tags):
            if key.split(":")[0] != "USLT":
                continue
            text = str(getattr(tags[key], "text", "")).strip()
            if text:
                return text
        return None
