"""ffmpeg 기반 오디오 디코더. AudioDecoder 포트의 구현이다 (D-0021).

soundfile과 파형 품질이 동일하다(스케일 보정 후 평균오차 0.00095).
품질이 같으므로 기준은 환경 재현성이며 ffmpeg 4.4.2가 2대에 통일돼 있다.

출력은 44.1kHz 스테레오다. Demucs가 이 규격을 기대하며 원본에 가장 가깝다.
MERT용 24kHz 모노는 여기서 파생시킨다. 디코딩을 두 번 하지 않는다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE, StereoWaveform

FFMPEG_BIN = "ffmpeg"
SOURCE_CHANNELS = 2
DECODE_TIMEOUT_SECONDS = 120


class AudioDecodeError(Exception):
    """ffmpeg가 파형을 내놓지 못했다."""


class FfmpegAudioDecoder:
    """서브프로세스로 ffmpeg를 호출해 44.1kHz 스테레오 float32를 얻는다.

    프로세스 생성 비용은 곡당 10~50ms로 Demucs 12초 대비 0.5% 미만이다.

    정규화하지 않는다. mp3 인터샘플 피크로 ±1을 넘는 값이 나올 수 있으며
    MERT는 특징 추출기가 흡수한다. Demucs 경로의 영향은 실측이 필요하다.
    """

    def __init__(self, binary: str = FFMPEG_BIN) -> None:
        self._binary = binary

    def decode(self, path: Path) -> StereoWaveform:
        command = [
            self._binary,
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            str(SOURCE_CHANNELS),
            "-ar",
            str(SOURCE_SAMPLE_RATE),
            "-f",
            "f32le",
            "-",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, timeout=DECODE_TIMEOUT_SECONDS, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioDecodeError(str(path)) from exc

        if result.returncode != 0 or not result.stdout:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise AudioDecodeError(f"{path}: {detail or 'no output'}")

        flat = np.frombuffer(result.stdout, dtype=np.float32)
        # ffmpeg는 채널 인터리브로 낸다. (샘플, 채널) -> (채널, 샘플)
        stereo: StereoWaveform = flat.reshape(-1, SOURCE_CHANNELS).T.copy()
        return stereo
