"""스캔된 트랙 하나. 인제스트 파이프라인의 최소 단위."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.track_tags import TrackTags


@dataclass(frozen=True, slots=True)
class ScannedTrack:
    """파일 하나에서 읽어낸 전체 관측 결과.

    source_key는 라이브러리 루트 기준 상대경로이며 POSIX 구분자와
    NFC 정규화를 적용한다. 절대경로를 쓰지 않는 이유는 D-0009 참조
    (리전 /mnt/f, 광인사 /mnt/d로 루트가 다르다).

    source_key는 스캔 단위의 멱등 키일 뿐 곡의 정규 신원이 아니다.
    파일이 이동하거나 개명되면 값이 바뀐다. 지문 기반 정규 식별자는
    유닛 #3에서 부여한다(D-0006).

    raw_frame_names는 태그 프레임 이름만 담고 값은 담지 않는다.
    스캔 요약의 프레임 히스토그램 산출과 라이브러리 구성 변화 감지에 쓴다.
    """

    source_key: str
    file_size_bytes: int
    modified_at: datetime
    stream: AudioStreamProperties
    tags: TrackTags
    raw_frame_names: tuple[str, ...]
