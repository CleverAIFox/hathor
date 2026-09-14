"""온셋 포락선 추출 유스케이스 (O-46 · D-0145).

디코딩 → 모노 → 포락선 순으로 곡 하나를 처리한다. 결과를 모으지 않고 **스트리밍한다** —
1004곡이며 중단·재개가 전제다 (D-0015 · D-0075).

**파일을 쓰지 않는다.** 산출물 기록은 호출자의 책임이며 `ExtractFeatures`와 같다.

### 스템을 안 나눈다

크로마는 `other` 스템에서 뽑는다 — 화음을 보려면 가락과 타악을 걷어내야 하기
때문이다. **온셋은 반대다.** 발음이 어디에 떨어지는가를 보려는 것이고 **타악이 바로
그 신호다.** 분리기를 안 태우므로 곡당 비용이 크로마보다 훨씬 싸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.domain.services.onset import bands, envelope

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.domain.ports.audio_analysis import AudioDecoder

HOP_SECONDS = 0.01
"""포락선 한 칸의 길이.

**10ms다.** 박은 빨라야 0.3초(200BPM)이고 16분음표가 그 4분의 1이므로 한 칸이
75ms까지는 보여야 한다. **10ms는 그보다 일곱 배 곱고 파일은 곡당 수만 칸이다** —
`.series`의 1초 창이 박을 못 본 것이 O-46의 원인이었다 (D-0142).
"""


@dataclass(frozen=True, slots=True)
class TrackOnsets:
    """곡 하나의 포락선."""

    source_key: str
    envelope: np.ndarray
    bands: np.ndarray
    """`(프레임, 대역)` 크기 스펙트럼 (O-47 · D-0170).

    **포락선과 같은 디코딩에서 나온다.** 따로 뽑으면 1004곡을 두 번 읽는다.
    """
    hop_seconds: float

    @property
    def seconds(self) -> float:
        return float(self.envelope.size) * self.hop_seconds


class ExtractOnsets:
    """곡을 순차 처리하며 포락선을 방출한다."""

    def __init__(
        self, decoder: AudioDecoder, root: Path, *, hop_seconds: float = HOP_SECONDS
    ) -> None:
        if hop_seconds <= 0.0:
            raise ValueError("홉 길이는 양수여야 한다")
        self._decoder = decoder
        self._root = root
        self._hop_seconds = hop_seconds
        self._failures: list[tuple[str, str]] = []

    @property
    def failures(self) -> tuple[tuple[str, str], ...]:
        """실패한 곡과 사유. **조용히 사라지지 않는다** (GR-0.5)."""
        return tuple(self._failures)

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[TrackOnsets]:
        """곡마다 포락선 하나. **한 곡이 실패해도 나머지를 돌린다.**

        디코딩이 깨지는 곡이 있고 1004곡 배치가 거기서 멈추면 안 된다 — D-0075가
        이어받기를 만든 이유와 같다. 실패한 곡은 **그냥 안 나온다.**
        """
        for track in tracks:
            try:
                yield self._extract_one(track)
            # **한 곡의 실패가 배치를 멈추면 안 된다** (D-0075와 같은 근거).
            except Exception as exc:
                self._failures.append((track.source_key, str(exc)))

    def _extract_one(self, track: ScannedTrack) -> TrackOnsets:
        stereo = np.asarray(self._decoder.decode(self._root / track.source_key), dtype=np.float64)
        # **모노로 섞는다.** 좌우 차이는 발음 자리를 안 바꾸고, 채널마다 따로 뽑으면
        # 어느 쪽을 쓸지가 값이 된다.
        mono = stereo.mean(axis=0) if stereo.ndim > 1 else stereo
        return TrackOnsets(
            source_key=track.source_key,
            envelope=envelope(mono, SOURCE_SAMPLE_RATE, self._hop_seconds),
            bands=bands(mono, SOURCE_SAMPLE_RATE, self._hop_seconds),
            hop_seconds=self._hop_seconds,
        )
