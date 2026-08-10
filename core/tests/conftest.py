"""테스트 픽스처. 실제 음원을 저장소에 커밋하지 않기 위해 합성 mp3를 생성한다."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("mutagen")

FFMPEG = shutil.which("ffmpeg")
requires_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg 미설치")


def _make_silent_mp3(path: Path, seconds: float = 1.0, sample_rate: int = 44100) -> None:
    """무음 mp3를 생성한다. 태그는 없는 상태로 만들어진다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(FFMPEG),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=stereo",
            "-t",
            str(seconds),
            "-b:a",
            "128k",
            str(path),
        ],
        check=True,
    )


@pytest.fixture
def make_mp3() -> Callable[..., Path]:
    """무음 mp3를 만들고 지정한 ID3 태그를 주입한다.

    D-0010 실측 기준으로 라이브러리에 실재하는 프레임만 다룬다:
    TIT2 / TPE1 / TALB / USLT / APIC.
    """

    def _factory(
        path: Path,
        *,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
        album_art: bool = False,
        seconds: float = 1.0,
        sample_rate: int = 44100,
    ) -> Path:
        from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, USLT

        _make_silent_mp3(path, seconds=seconds, sample_rate=sample_rate)

        if not any([title, artist, album, lyrics, album_art]):
            return path

        tags = ID3()
        if title is not None:
            tags.add(TIT2(encoding=3, text=[title]))
        if artist is not None:
            tags.add(TPE1(encoding=3, text=[artist]))
        if album is not None:
            tags.add(TALB(encoding=3, text=[album]))
        if lyrics is not None:
            tags.add(USLT(encoding=3, lang="kor", desc="", text=lyrics))
        if album_art:
            tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="",
                    data=b"\xff\xd8\xff\xd9",
                )
            )
        tags.save(path)
        return path

    return _factory
