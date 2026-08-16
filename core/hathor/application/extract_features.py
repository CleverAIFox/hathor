"""오디오 특징 추출 유스케이스 (유닛 #4).

디코딩 -> 스템 분리 -> 특징 추출 순으로 곡 하나를 처리한다.
결과를 리스트로 모으지 않고 스트리밍한다. 1004곡에 5시간 안팎이며
중단·재개가 전제다 (D-0015).

파일을 쓰지 않는다. 산출물 기록은 호출자의 책임이다.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.ports.audio_analysis import (
    AudioDecoder,
    Embedding,
    FeatureExtractor,
    LayeredFeatureExtractor,
    StemSeparator,
)

MIXTURE_KEY = "mixture"


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    """곡 하나의 특징. 스템별 임베딩과 혼합 임베딩을 갖는다."""

    source_key: str
    mixture: Embedding
    stems: dict[str, Embedding]

    @property
    def chunk_count(self) -> int:
        return int(self.mixture.shape[0])


class ExtractFeatures:
    """곡을 순차 처리하며 특징을 방출한다.

    스템은 44.1kHz 스테레오로 나오므로 특징 추출기가 24kHz 모노로
    파생시킨다. 디코딩은 곡당 한 번이다 (D-0021).

    실패는 예외로 올리되 호출자가 개별 곡을 건너뛸 수 있게 한다.
    1004곡 배치에서 한 곡의 실패가 5시간을 날리면 안 된다.
    """

    def __init__(
        self,
        decoder: AudioDecoder,
        separator: StemSeparator | None,
        extractor: FeatureExtractor,
        library_root: Path,
    ) -> None:
        self._decoder = decoder
        self._separator = separator
        self._extractor = extractor
        self._root = library_root
        self.processed = 0
        self.failed: list[tuple[str, str]] = []

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[TrackFeatures]:
        for track in tracks:
            try:
                yield self._extract_one(track)
            except Exception as exc:
                self.failed.append((track.source_key, f"{type(exc).__name__}: {exc}"))
                continue
            self.processed += 1

    def _extract_one(self, track: ScannedTrack) -> TrackFeatures:
        waveform = self._decoder.decode(self._root / track.source_key)
        # 분리기가 없으면 혼합만 뽑는다. MFCC 베이스라인은 스템이 필요 없고
        # 곡당 GPU 12초를 쓸 이유도 없다. 산출물 규격은 그대로 유지된다.
        stems = {} if self._separator is None else self._separator.separate(waveform)
        return TrackFeatures(
            source_key=track.source_key,
            mixture=self._extractor.extract(waveform),
            stems={name: self._extractor.extract(stem) for name, stem in stems.items()},
        )


class ExtractLayerFeatures:
    """혼합 파형에서 레이어별 임베딩을 뽑는다 (O-8).

    스템 분리를 하지 않는다. D-0024에서 스템이 검색에 기여하지 않음이
    확정됐으므로 곡당 GPU 12초를 다시 낼 이유가 없다. 배치가 6~7시간에서
    1시간 안팎으로 줄어든다.

    산출물은 `ExtractFeatures`와 같은 `TrackFeatures`다. 마지막 레이어를
    `mixture`에 두고 나머지를 `stems` 자리에 담는다. 저장소가 키를 그대로
    npz에 쓰므로 평가 하네스가 `--keys layer06`으로 읽는다.
    """

    def __init__(
        self,
        decoder: AudioDecoder,
        extractor: LayeredFeatureExtractor,
        library_root: Path,
    ) -> None:
        self._decoder = decoder
        self._extractor = extractor
        self._root = library_root
        self.processed = 0
        self.failed: list[tuple[str, str]] = []

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[TrackFeatures]:
        for track in tracks:
            try:
                yield self._extract_one(track)
            except Exception as exc:
                self.failed.append((track.source_key, f"{type(exc).__name__}: {exc}"))
                continue
            self.processed += 1

    def _extract_one(self, track: ScannedTrack) -> TrackFeatures:
        waveform = self._decoder.decode(self._root / track.source_key)
        views = dict(self._extractor.extract_layers(waveform))
        mixture = views.pop(MIXTURE_KEY, None)
        if mixture is None:
            raise KeyError(f"레이어 추출기가 {MIXTURE_KEY} 키를 내지 않았다")
        return TrackFeatures(source_key=track.source_key, mixture=mixture, stems=views)
