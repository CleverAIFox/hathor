"""pyin 음고 추적 (D-0203).

**손으로 짜지 않는다.** CQ 격자에서 argmax를 취하는 길이 공짜로 보였으나
pyin은 검증된 구현이고 실측으로 **곡당 8초**라 감당된다. 없는 것을 깔기보다
있는 것을 쓰라는 규율은 **같은 일을 하는 것**에만 적용된다 — argmax는 음고
추적이 아니라 우세 격자 찾기이며 옥타브 오류를 거르지 못한다.

**표본율을 내려서 산다.** 44.1kHz에서 곡당 45초이고 11.025kHz·홉 512에서
8초다. 베이스도 보컬도 5.5kHz 아래에 살므로 잃는 것이 없다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from hathor.domain.ports.audio_analysis import PitchTrack, Waveform

FRAME_LENGTH = 2048
"""분석 창. 11.025kHz에서 186ms이며 35Hz(약 C#1)를 두 주기 담는다."""


class LibrosaPitchTracker:
    """`librosa.pyin`을 포트에 맞춘다.

    **무성 구간을 `NaN`으로 남긴다.** 0으로 채우면 쉼과 저음이 같은 값이 되고,
    보간하면 없던 음이 생긴다 — O-50이 묻는 것이 정확히 *"쉬는가"*다.
    """

    def track(
        self,
        waveform: Waveform,
        *,
        sample_rate: int,
        fmin: float,
        fmax: float,
    ) -> PitchTrack:
        import librosa
        from scipy.signal import resample_poly

        from hathor.domain.ports.audio_analysis import PITCH_HOP, PITCH_SAMPLE_RATE

        signal = np.asarray(waveform, dtype=np.float32)
        if sample_rate != PITCH_SAMPLE_RATE:
            signal = np.asarray(
                resample_poly(signal, PITCH_SAMPLE_RATE, sample_rate), dtype=np.float32
            )
        if signal.size < FRAME_LENGTH:
            return np.zeros(0, dtype=np.float32)
        found, _voiced, _probability = librosa.pyin(
            signal,
            fmin=fmin,
            fmax=fmax,
            sr=PITCH_SAMPLE_RATE,
            frame_length=FRAME_LENGTH,
            hop_length=PITCH_HOP,
        )
        return np.asarray(found, dtype=np.float32)
