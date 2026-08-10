"""스캔 델타 이벤트. 파일시스템 이벤트가 아니라 도메인 이벤트다(D-0013)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScanEventKind(Enum):
    """이전 스냅샷 대비 변화 유형."""

    DISCOVERED = "discovered"
    MODIFIED = "modified"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ScanEvent:
    """한 source_key에 대한 변화 판정.

    판정 기준은 mtime과 file_size_bytes다(D-0013).
    UNCHANGED인 파일은 태그 추출을 건너뛰므로 재스캔 비용이 변경분에 비례한다.

    REMOVED는 이전 스냅샷에만 존재하고 현재 순회에서 발견되지 않은 경우다.
    파일이 실제로 삭제됐을 수도, 외장 볼륨이 연결되지 않았을 수도 있다.
    후자를 삭제로 오인하면 라이브러리 전체가 소실 처리되므로
    호출자가 REMOVED 비율을 검사해야 한다.
    """

    source_key: str
    kind: ScanEventKind
