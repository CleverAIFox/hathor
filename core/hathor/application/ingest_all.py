"""곡 하나를 한 번만 열어 **전부 뽑는다** (D-0203).

### 왜 한 패스인가

지금은 축마다 명령이 따로다. `ingest features`가 디코딩·분리를 하고,
`ingest keys`가 **또** 하고, `ingest onsets`는 디코딩을 **또** 한다. 분리가
곡당 비용의 대부분이므로 축을 늘릴수록 같은 일을 다시 한다.

**스템이 메모리에 떠 있는 그 한 번에 스템 의존 산출물을 전부 뽑는다.**
스템은 4분 곡 하나가 340MB라 1004곡이면 340GB이고 **디스크에 못 남긴다** —
캐시로는 못 푸는 문제이며 그래서 패스를 쪼갤 수 없다.

### 무엇을 뽑나

| | 대상 |
|---|---|
| MERT 13층 | 믹스 + 스템 넷 |
| 크로마 요약 | 스템 조합 |
| 크로마 시계열 | 믹스 · `other` · `bass` · `vocals` |
| 온셋 포락선 | `other` · `drums` · `bass` · `vocals` |
| 음고 | `bass` · `vocals` — **단성에만 건다** |
| 무음 구간 | 믹스 |

**층은 열셋 전부다.** 한 번의 forward에서 다 나오므로 골라 담는 것이 공짜이고,
D-0181은 **넷만 보고** `layer03`을 골랐다 — 이웃 층이 더 나은지 **안 뽑아서
모른다.** 전부 뽑으면 그 질문이 재추출 없이 풀린다.

**가사는 여기 없다.** 오디오를 안 쓰므로 분리에 얹을 이유가 없다.

### 실패를 남긴다

지난 배치가 *"성공 689곡, 실패 240곡"*을 찍고 **원인을 한 줄도 안 남겼다.**
`failures: []`였다. 곡마다 예외 타입·메시지를 적고 순회는 계속한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.ports.audio_analysis import (
    PITCH_HOP,
    PITCH_SAMPLE_RATE,
    SOURCE_SAMPLE_RATE,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.domain.ports.audio_analysis import (
        AudioDecoder,
        LayeredFeatureExtractor,
        PitchTracker,
        StemSeparator,
        StereoWaveform,
        Waveform,
    )

MIXTURE = "mixture"

MERT_LAST_KEY = "mixture"
"""추출기가 `last_hidden_state`를 내놓는 키. **층을 전부 뽑으면 중복이다.**

이름이 같은 것은 우연이 아니다 — 포트가 *"반환 키에 반드시 `mixture`가
포함된다"*고 규약했고 그 자리를 마지막 층이 쓴다. 소스별로 부를 때는 그 이름이
거짓이 되므로 여기서 걷어낸다.
"""

CHROMA_SERIES_SOURCES = (MIXTURE, "other", "bass", "vocals")
"""크로마 시계열을 낼 곳. **`drums`는 뺀다** — 음고가 없어 크로마가 잡음이다."""

ONSET_SOURCES = ("other", "drums", "bass", "vocals")
"""온셋을 낼 곳. **믹스는 뺀다** — 무엇이 울린 것인지 안 갈린다.

O-46이 묻는 것은 *"화음이 마디 안 어디에 떨어지나"*이고 믹스 포락선으로는
드럼과 화음이 섞여 답이 안 나온다. 지금 산출물이 그 상태였다.
"""

PITCH_SOURCES: tuple[tuple[str, float, float], ...] = (
    ("bass", 35.0, 330.0),
    ("vocals", 65.0, 1100.0),
)
"""(스템, fmin, fmax). **단성 스템만 건다.**

`bass`는 O-50의 저역 성부에, `vocals`는 O-45의 도약에 쓴다. 다성 채보는 못
해도 **이 둘은 단성이라 실제로 된다** — 지금 없는 비교선이 서는 유일한 길이다.
"""

CHROMA_SERIES_SECONDS = 1.0
"""크로마 시계열 창. **가장 짧은 창으로 뽑고 읽을 때 묶는다** (D-0104)."""

SILENCE_FLOOR = 1e-4
"""무음 판정 진폭. 16비트 양자화 바닥(약 3e-5)보다 위에 둔다."""

SILENCE_HOP_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class TrackBundle:
    """곡 하나에서 나온 전부. **파일을 쓰지 않는다** — 기록은 호출자가 한다."""

    source_key: str
    arrays: dict[str, np.ndarray[tuple[int, ...], np.dtype[np.float32]]]
    manifest: dict[str, object]


@dataclass
class IngestAll:
    """디코딩 1회 · 분리 1회로 곡 하나의 산출물을 전부 낸다."""

    decoder: AudioDecoder
    separator: StemSeparator
    extractor: LayeredFeatureExtractor
    pitch: PitchTracker
    library_root: Path
    processed: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[TrackBundle]:
        for track in tracks:
            try:
                bundle = self._one(track)
            except Exception as exc:
                # **원인을 적는다.** 지난 배치가 240곡을 원인 없이 잃었다.
                self.failed.append((track.source_key, f"{type(exc).__name__}: {exc}"))
                continue
            self.processed += 1
            yield bundle

    def _one(self, track: ScannedTrack) -> TrackBundle:
        from hathor.domain.services.key_estimation import (
            HARMONIC_STRENGTH,
            LOG_GAMMA,
            chroma_series,
            cq_chroma,
        )
        from hathor.domain.services.onset import envelope

        waveform = self.decoder.decode(self.library_root / track.source_key)
        stems = self.separator.separate(waveform)
        sources: dict[str, StereoWaveform] = {MIXTURE: waveform, **stems}

        arrays: dict[str, np.ndarray[tuple[int, ...], np.dtype[np.float32]]] = {}

        # MERT — 한 번의 forward에서 열세 층이 나온다.
        for name, signal in sources.items():
            for layer, matrix in self.extractor.extract_layers(signal).items():
                # **`mixture` 키를 안 담는다** (D-0205). 포트가 그 이름으로
                # `last_hidden_state`를 내는데 층을 전부 요청하면 **마지막 층과
                # 같은 행렬이다.** 담으면 소스마다 한 벌씩 중복되고, 무엇보다
                # `mert/bass/mixture`는 *"베이스의 믹스"*라 뜻이 안 된다 —
                # `stem_names`에 층 이름을 밀어 넣던 것과 같은 결함이다.
                if layer == MERT_LAST_KEY:
                    continue
                arrays[f"mert/{name}/{layer}"] = matrix

        for name, signal in sources.items():
            mono = _mono(signal)
            # **조건을 인자로 넘기고 manifest에 적는다** (D-0211). D-0203은 기본값에
            # 기대고 안 적어서, 배음이 이미 빠진 크로마를 `--replay`가 또 뺄 뻔했다.
            arrays[f"chroma/{name}"] = np.asarray(
                cq_chroma(mono, gamma=LOG_GAMMA, harmonic=HARMONIC_STRENGTH), dtype=np.float32
            )
            if name in CHROMA_SERIES_SOURCES:
                arrays[f"chroma_series/{name}"] = chroma_series(
                    mono,
                    window_seconds=CHROMA_SERIES_SECONDS,
                    gamma=LOG_GAMMA,
                    harmonic=HARMONIC_STRENGTH,
                )
            if name in ONSET_SOURCES:
                arrays[f"onset/{name}"] = np.asarray(
                    envelope(mono, SOURCE_SAMPLE_RATE, SILENCE_HOP_SECONDS), dtype=np.float32
                )

        for name, low, high in PITCH_SOURCES:
            if name not in stems:
                continue
            # **표본율을 여기서 내리지 않는다.** 어떻게 내릴지는 추적기의
            # 사정이고, 응용이 `scipy`를 끌어오면 GPU 엑스트라 없는 기기에서
            # 검사가 안 돈다.
            arrays[f"pitch/{name}"] = self.pitch.track(
                _mono(stems[name]),
                sample_rate=SOURCE_SAMPLE_RATE,
                fmin=low,
                fmax=high,
            )

        arrays["silence/mixture"] = _silence(_mono(waveform))

        return TrackBundle(
            source_key=track.source_key,
            arrays=arrays,
            manifest={
                "stems": sorted(stems),
                "layers": sorted(self.extractor.layers),
                "pitch_sample_rate": PITCH_SAMPLE_RATE,
                "pitch_hop": PITCH_HOP,
                "pitch_sources": {name: [low, high] for name, low, high in PITCH_SOURCES},
                "onset_hop_seconds": SILENCE_HOP_SECONDS,
                "silence_floor": SILENCE_FLOOR,
                "dtype": "float32",
                "chroma_mode": "cq",
                "chroma_harmonic": HARMONIC_STRENGTH,
                "chroma_gamma": LOG_GAMMA,
                "chroma_series_seconds": CHROMA_SERIES_SECONDS,
            },
        )


def _mono(signal: StereoWaveform) -> Waveform:
    if signal.ndim == 1:
        return np.asarray(signal, dtype=np.float32)
    return np.asarray(signal.mean(axis=0), dtype=np.float32)


def _silence(signal: Waveform) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """창별 최대 진폭. **판정을 여기서 하지 않는다** (O-28).

    `SILENCE_FLOOR`를 걸어 0/1로 접으면 문턱을 바꿀 때마다 다시 뽑아야 한다.
    원값을 남기고 문턱은 읽을 때 건다.
    """
    step = max(1, int(SOURCE_SAMPLE_RATE * SILENCE_HOP_SECONDS))
    count = len(signal) // step
    if count < 1:
        return np.zeros(0, dtype=np.float32)
    framed = np.abs(signal[: count * step]).reshape(count, step)
    return np.asarray(framed.max(axis=1), dtype=np.float32)
