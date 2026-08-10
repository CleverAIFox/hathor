"""스캔 실패 기록. 단일 파일 실패가 전체 스캔을 중단시키지 않는다."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureKind(Enum):
    """실패 분류. 스캔 요약에서 원인별 집계에 사용한다."""

    UNREADABLE_FILE = "unreadable_file"
    CORRUPT_HEADER = "corrupt_header"
    MISSING_AUDIO_STREAM = "missing_audio_stream"
    TAG_DECODE_ERROR = "tag_decode_error"
    PERMISSION_DENIED = "permission_denied"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True, slots=True)
class ScanFailure:
    """한 파일의 스캔 실패.

    source_key는 성공 레코드와 동일하게 라이브러리 루트 기준 상대경로다.
    detail은 예외 타입과 메시지를 담되 절대경로를 포함하지 않는다
    (D-0009: 머신마다 루트가 달라 산출물 동일성이 깨진다).
    """

    source_key: str
    failure_kind: FailureKind
    detail: str
