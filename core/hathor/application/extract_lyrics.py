"""가사 특징 추출 (가사축 착수).

오디오 경로와 달리 **디코딩도 GPU도 없다.** 스캔 산출물의 USLT 원문만 쓰며
1004곡이 수 초다. D-0011이 "가사축만 P1 산출물로 즉시 착수 가능"이라고
지목한 그 경로다.

산출물 규격을 오디오와 동일하게 맞춘다. (구간, 차원) 행렬을 같은 npz 저장소에
쓰므로 **평가 하네스가 구분 없이 읽는다.** 가사축 전용 지표를 새로 만들지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol

from hathor.application.extract_features import TrackFeatures
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.ports.audio_analysis import Embedding
from hathor.domain.services.lyrics_segmentation import split_segments

LYRICS_KEY = "lyrics"


class LyricsEncoder(Protocol):
    """가사 구간 목록을 (구간, 차원) 행렬로 만든다.

    해싱 n-gram이 첫 구현이며, 신경망 인코더로 교체할 수 있도록 포트를 둔다.
    어느 쪽이 나은지는 M1/M2로 판정한다.
    """

    def extract(self, segments: list[str]) -> Embedding: ...


class ExtractLyrics:
    """구간으로 나눌 수 있는 곡만 처리한다.

    구간이 둘 미만이면 건너뛴다. M0가 홀·짝 분할을 요구하므로 한 구간짜리 곡은
    평가에서 어차피 빠지고, 그때 걸러내면 원인이 추출인지 평가인지 흐려진다.
    **여기서 이유와 함께 남긴다.**
    """

    def __init__(self, encoder: LyricsEncoder) -> None:
        self._encoder = encoder
        self.processed = 0
        self.skipped: list[tuple[str, str]] = []

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[TrackFeatures]:
        for track in tracks:
            segments = split_segments(track.tags.lyrics_text)
            if not segments:
                reason = "가사 없음" if not track.tags.lyrics_text else "구간 2개 미만"
                self.skipped.append((track.source_key, reason))
                continue
            matrix = self._encoder.extract(segments)
            yield TrackFeatures(source_key=track.source_key, mixture=matrix, stems={})
            self.processed += 1
