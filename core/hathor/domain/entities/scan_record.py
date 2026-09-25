"""스캔 결과 1건과 라이브러리 스냅숏 (O-56 · D-0236).

`JsonlScanStore`가 담는 것이라 도메인에 둔다. 응용에 두면 저장소가 계층을 거스른다.
"""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.entities.scan_event import ScanEvent
from hathor.domain.entities.scan_failure import ScanFailure
from hathor.domain.entities.scanned_track import ScannedTrack

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
