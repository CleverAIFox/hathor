"""오디오 스트림 물리 속성. 태그가 아니라 파일 헤더에서 읽는다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioStreamProperties:
    """디코딩 없이 헤더에서 읽을 수 있는 스트림 속성.

    D-0007에 따라 샘플레이트는 인제스트에서 통일하지 않고 원본을 보존한다.
    모델 입력 직전에 리샘플한다.

    실측(1004곡): 44.1kHz 76.8% / 48kHz 23.2%, 포맷 100% mp3.
    """

    sample_rate_hz: int
    channels: int
    duration_ms: int
    bitrate_bps: int
    codec: str

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0

    @property
    def is_mono(self) -> bool:
        return self.channels == 1
