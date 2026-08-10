"""파일시스템 순회 스캐너. LibraryScanner 포트의 구현이다."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from mutagen import MutagenError

from hathor.domain.entities.scan_failure import FailureKind, ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.ports.library_scanner import ScanOutcome, TagExtractor
from hathor.infrastructure.mutagen_tag_extractor import MissingAudioStreamError

AUDIO_SUFFIXES = frozenset({".mp3"})


class FilesystemLibraryScanner:
    """라이브러리 루트를 재귀 순회하며 트랙을 방출한다.

    순회 순서는 sorted()로 고정한다. rglob 순서는 파일시스템에 의존하므로
    2대 노트북 간 산출물 동일성이 깨진다(D-0009, 재현성 CI 잡).

    단일 파일 실패는 ScanFailure로 격리되고 순회는 계속된다.
    """

    def __init__(self, tag_extractor: TagExtractor) -> None:
        self._tag_extractor = tag_extractor

    def scan(self, root: Path) -> Iterator[ScanOutcome]:
        for path in self._audio_paths(root):
            yield self._scan_one(root, path)

    @staticmethod
    def _audio_paths(root: Path) -> list[Path]:
        return sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
        )

    @staticmethod
    def _source_key(root: Path, path: Path) -> str:
        """루트 기준 상대경로. NFC 정규화 후 POSIX 구분자로 통일한다.

        절대경로를 쓰지 않는 이유는 D-0009 참조(머신마다 루트가 다르다).
        """
        relative = path.relative_to(root).as_posix()
        return unicodedata.normalize("NFC", relative)

    def _scan_one(self, root: Path, path: Path) -> ScanOutcome:
        source_key = self._source_key(root, path)
        try:
            stat = path.stat()
            tags, stream, frame_names = self._tag_extractor.extract(path)
        except MissingAudioStreamError as exc:
            return self._failure(source_key, FailureKind.MISSING_AUDIO_STREAM, exc)
        except PermissionError as exc:
            return self._failure(source_key, FailureKind.PERMISSION_DENIED, exc)
        except MutagenError as exc:
            return self._failure(source_key, FailureKind.CORRUPT_HEADER, exc)
        except OSError as exc:
            return self._failure(source_key, FailureKind.UNREADABLE_FILE, exc)
        except Exception as exc:
            return self._failure(source_key, FailureKind.UNEXPECTED_ERROR, exc)

        if stream.duration_ms <= 0:
            return ScanFailure(
                source_key=source_key,
                failure_kind=FailureKind.MISSING_AUDIO_STREAM,
                detail="재생 시간이 0 이하다",
            )

        return ScannedTrack(
            source_key=source_key,
            file_size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            stream=stream,
            tags=tags,
            raw_frame_names=frame_names,
        )

    @staticmethod
    def _failure(source_key: str, failure_kind: FailureKind, exc: Exception) -> ScanFailure:
        """예외를 실패 레코드로 변환한다.

        detail에 절대경로가 섞이지 않도록 예외 타입명과 메시지만 담는다.
        """
        return ScanFailure(
            source_key=source_key,
            failure_kind=failure_kind,
            detail=f"{type(exc).__name__}: {exc}",
        )
