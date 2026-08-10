"""라이브러리 스캔 포트. 구현은 infrastructure가 담당한다 (DIP)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scan_failure import ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags

type ScanOutcome = ScannedTrack | ScanFailure
type ExtractionResult = tuple[TrackTags, AudioStreamProperties, tuple[str, ...]]


class TagExtractor(Protocol):
    """파일 하나에서 태그와 스트림 속성을 읽는다.

    오디오를 디코딩하지 않는다. 헤더와 태그 프레임만 읽는다.
    """

    def extract(self, path: Path) -> ExtractionResult: ...


class LibraryScanner(Protocol):
    """라이브러리 루트를 순회하며 스캔 결과를 순차 방출한다.

    단일 파일의 실패가 순회를 중단시키지 않는다. 실패는 ScanFailure로
    방출되고 순회는 계속된다.

    방출 순서는 결정적이어야 한다(재현성 CI 잡 요구사항).
    """

    def scan(self, root: Path) -> Iterator[ScanOutcome]: ...
