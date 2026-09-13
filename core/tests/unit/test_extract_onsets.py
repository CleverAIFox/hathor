"""온셋 추출 배선의 단위 검사 (O-46 · D-0145).

**음원이 없어도 돈다.** 디코더는 포트이므로 합성 파형을 내는 가짜를 끼운다 —
포트를 나눈 이유가 그것이다 (D-0021).
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.extract_onsets import HOP_SECONDS, ExtractOnsets
from hathor.domain.ports.audio_analysis import SOURCE_SAMPLE_RATE
from hathor.infrastructure.onset_store import (
    envelope_path,
    find_envelope_root,
    load_envelope,
    write_envelope,
)


class Track:
    def __init__(self, source_key: str) -> None:
        self.source_key = source_key


class Decoder:
    """클릭 열을 내는 가짜 디코더. **참 박을 아는 자료다.**"""

    def __init__(self, bpm: float = 120.0, seconds: int = 8, broken: set[str] | None = None):
        self.bpm, self.seconds, self.broken = bpm, seconds, broken or set()
        self.seen: list[str] = []

    def decode(self, path):
        name = path.name
        self.seen.append(name)
        if name in self.broken:
            raise OSError(f"못 읽는다: {name}")
        size = SOURCE_SAMPLE_RATE * self.seconds
        wave = np.zeros(size, dtype=np.float32)
        step = int(60.0 / self.bpm * SOURCE_SAMPLE_RATE)
        wave[::step] = 1.0
        return np.stack([wave, wave])


# ------------------------------------------------------------------ 추출


def test_곡마다_포락선_하나(tmp_path):
    found = list(ExtractOnsets(Decoder(), tmp_path).run([Track("a.flac"), Track("b.flac")]))
    assert [item.source_key for item in found] == ["a.flac", "b.flac"]
    assert all(item.envelope.size > 0 for item in found)


def test_한_곡이_깨져도_배치가_안_멈춘다(tmp_path):
    """**1004곡 배치가 거기서 멈추면 안 된다** (D-0075와 같은 근거)."""
    decoder = Decoder(broken={"b.flac"})
    extractor = ExtractOnsets(decoder, tmp_path)
    found = list(extractor.run([Track("a.flac"), Track("b.flac"), Track("c.flac")]))
    assert [item.source_key for item in found] == ["a.flac", "c.flac"]
    assert len(extractor.failures) == 1


def test_실패가_조용히_사라지지_않는다(tmp_path):
    """**없는 것을 없다고 말한다** (GR-0.5)."""
    extractor = ExtractOnsets(Decoder(broken={"a.flac"}), tmp_path)
    list(extractor.run([Track("a.flac")]))
    assert extractor.failures[0][0] == "a.flac"
    assert "못 읽는다" in extractor.failures[0][1]


def test_모노로_섞는다(tmp_path):
    """**좌우 차이는 발음 자리를 안 바꾼다.** 채널마다 따로 뽑으면 값이 생긴다."""
    found = next(iter(ExtractOnsets(Decoder(), tmp_path).run([Track("a.flac")])))
    assert found.envelope.ndim == 1


def test_홉이_0이면_거부한다(tmp_path):
    with pytest.raises(ValueError, match="홉 길이"):
        ExtractOnsets(Decoder(), tmp_path, hop_seconds=0.0)


def test_홉이_박을_볼_만큼_곱다():
    """**1초 창이 박을 못 본 것이 O-46의 원인이었다** (D-0142)."""
    assert HOP_SECONDS <= 0.075


def test_추출한_포락선에서_박이_나온다(tmp_path):
    """**배선이 통하는지 여기서 본다.** 파형부터 박까지 한 줄로 이어진다."""
    from hathor.domain.services.onset import beat_period

    found = next(iter(ExtractOnsets(Decoder(bpm=120, seconds=20), tmp_path).run([Track("a.flac")])))
    beat = beat_period(found.envelope, found.hop_seconds)
    assert beat is not None
    assert abs(beat.tempo_bpm - 120.0) < 2.0


# ------------------------------------------------------------------ 저장소


def test_쓰고_읽는다(tmp_path):
    write_envelope(tmp_path, "곡/이름.flac", [0.0, 1.0, 0.5], hop_seconds=0.01)
    found = load_envelope(tmp_path, "곡/이름.flac")
    assert found is not None
    assert found[1] == 0.01
    assert list(np.round(found[0], 3)) == [0.0, 1.0, 0.5]


def test_없으면_None이다(tmp_path):
    assert load_envelope(tmp_path, "없다.flac") is None


def test_파일_이름에_곡_제목을_안_쓴다(tmp_path):
    """**슬래시와 유니코드가 섞여 있다** (D-0105와 같은 근거)."""
    path = envelope_path(tmp_path, "아티스트/곡 제목.flac")
    assert "곡" not in path.name
    assert path.suffix == ".npz"


def test_홉을_파일에_적는다(tmp_path):
    """**자료의 성질이지 읽는 쪽의 약속이 아니다.**"""
    write_envelope(tmp_path, "a.flac", [1.0, 0.0], hop_seconds=0.02)
    found = load_envelope(tmp_path, "a.flac")
    assert found is not None and found[1] == 0.02


def test_홉이_0이면_안_쓴다(tmp_path):
    with pytest.raises(ValueError, match="홉 길이"):
        write_envelope(tmp_path, "a.flac", [1.0], hop_seconds=0.0)


def test_비어_있는_폴더는_건너뛴다(tmp_path):
    """**`other`로 뽑은 폴더에 `bass`를 찾으러 가면 0곡이 된다** (D-0110)."""
    (tmp_path / "var" / "ingest" / "keys-0.01s.onsets").mkdir(parents=True)
    assert find_envelope_root(tmp_path) is None


def test_가장_최근_폴더를_고른다(tmp_path):
    ingest = tmp_path / "var" / "ingest"
    for name in ("keys-0.01s.onsets", "keys-0.02s.onsets"):
        folder = ingest / name
        folder.mkdir(parents=True)
        write_envelope(folder, "a.flac", [1.0, 0.0], hop_seconds=0.01)
    found = find_envelope_root(tmp_path)
    assert found is not None and found.name == "keys-0.02s.onsets"
