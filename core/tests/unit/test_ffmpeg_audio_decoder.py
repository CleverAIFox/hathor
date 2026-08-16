"""ffmpeg 디코더 테스트 (D-0021).

합성 파형으로 출력 규격을 검증한다. 실제 음원 검증은 라이브러리 루트가
설정된 환경에서만 돈다. CI에는 음원이 없다.
"""

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.infrastructure.ffmpeg_audio_decoder import (
    AudioDecodeError,
    FfmpegAudioDecoder,
)

LIBRARY_ROOT_ENV = "HATHOR_LIBRARY_ROOT"


@pytest.fixture
def sine_mp3(tmp_path: Path) -> Path:
    """440Hz 2초 스테레오 mp3를 만든다. ffmpeg는 환경에 이미 있다."""
    path = tmp_path / "tone.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2:sample_rate=44100",
            "-ac",
            "2",
            str(path),
        ],
        check=True,
    )
    return path


def test_출력이_44100hz_스테레오_float32다(sine_mp3):
    wave = FfmpegAudioDecoder().decode(sine_mp3)
    assert wave.ndim == 2
    assert wave.shape[0] == 2
    assert wave.dtype == np.float32


def test_길이가_입력_초와_맞는다(sine_mp3):
    wave = FfmpegAudioDecoder().decode(sine_mp3)
    seconds = wave.shape[1] / SOURCE_SAMPLE_RATE
    # mp3 인코더가 앞뒤에 무음 프레임을 넣어 정확히 2초가 아니다
    assert 1.9 < seconds < 2.2


def test_쓰기_가능해야_한다(sine_mp3):
    # frombuffer는 읽기 전용이고 .T는 뷰다. torch에 넣으려면 복사가 필요하다
    assert FfmpegAudioDecoder().decode(sine_mp3).flags.writeable


def test_파일이_없으면_예외(tmp_path):
    with pytest.raises(AudioDecodeError):
        FfmpegAudioDecoder().decode(tmp_path / "없는파일.mp3")


def test_바이너리가_없으면_예외(sine_mp3):
    with pytest.raises(AudioDecodeError):
        FfmpegAudioDecoder(binary="ffmpeg-존재하지-않음").decode(sine_mp3)


def _first_mp3() -> Path | None:
    root = os.environ.get(LIBRARY_ROOT_ENV)
    if not root or not Path(root).is_dir():
        return None
    return next(iter(sorted(Path(root).rglob("*.mp3"))), None)


@pytest.mark.skipif(_first_mp3() is None, reason=f"{LIBRARY_ROOT_ENV} 미설정 또는 음원 없음")
def test_실제_음원_디코딩():
    """합성 사인파는 mp3 인코딩 특성을 담지 못한다.

    실측 인터샘플 피크가 1.12로 ±1을 넘는데 합성 파형에서는 재현되지 않는다.
    """
    path = _first_mp3()
    assert path is not None
    wave = FfmpegAudioDecoder().decode(path)

    assert wave.shape[0] == 2
    assert wave.dtype == np.float32
    assert wave.shape[1] > SOURCE_SAMPLE_RATE  # 최소 1초는 넘는다
    assert np.isfinite(wave).all()
