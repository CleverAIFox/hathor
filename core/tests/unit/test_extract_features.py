"""특징 추출 유스케이스 테스트 (유닛 #4).

GPU를 쓰지 않는다. 디코더·분리기·추출기는 가짜를 주입한다.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hathor.application.extract_features import ExtractFeatures
from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags


def make_track(source_key: str = "a.mp3") -> ScannedTrack:
    return ScannedTrack(
        source_key=source_key,
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            sample_rate_hz=44100, channels=2, duration_ms=1000, bitrate_bps=320000, codec="mp3"
        ),
        tags=TrackTags(
            title="t",
            artist="a",
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        ),
        raw_frame_names=(),
    )


class FakeDecoder:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.seen: list[Path] = []

    def decode(self, path: Path):
        self.seen.append(path)
        if self.fail:
            raise OSError("디코딩 실패")
        return np.zeros((2, 44100), dtype=np.float32)


class FakeSeparator:
    def separate(self, waveform):
        return {name: waveform for name in ("drums", "bass", "other", "vocals")}


class FakeExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, waveform):
        self.calls += 1
        return np.full((3, 768), float(self.calls), dtype=np.float32)


def test_혼합과_스템_4종의_특징을_뽑는다():
    extractor = FakeExtractor()
    use_case = ExtractFeatures(FakeDecoder(), FakeSeparator(), extractor, Path("/음원"))

    results = list(use_case.run([make_track()]))

    assert len(results) == 1
    assert set(results[0].stems) == {"drums", "bass", "other", "vocals"}
    assert results[0].chunk_count == 3
    # 혼합 1회 + 스템 4회
    assert extractor.calls == 5


def test_라이브러리_루트를_source_key에_붙인다():
    decoder = FakeDecoder()
    use_case = ExtractFeatures(decoder, FakeSeparator(), FakeExtractor(), Path("/음원"))

    list(use_case.run([make_track("가수/곡.mp3")]))

    assert decoder.seen == [Path("/음원/가수/곡.mp3")]


def test_한_곡의_실패가_배치를_멈추지_않는다():
    # 1004곡 배치에서 한 곡 때문에 5시간을 날리면 안 된다
    use_case = ExtractFeatures(
        FakeDecoder(fail=True), FakeSeparator(), FakeExtractor(), Path("/음원")
    )

    results = list(use_case.run([make_track("x.mp3"), make_track("y.mp3")]))

    assert results == []
    assert use_case.processed == 0
    assert [key for key, _ in use_case.failed] == ["x.mp3", "y.mp3"]
    assert "디코딩 실패" in use_case.failed[0][1]


def test_성공_건수를_센다():
    use_case = ExtractFeatures(FakeDecoder(), FakeSeparator(), FakeExtractor(), Path("/음원"))

    list(use_case.run([make_track("a.mp3"), make_track("b.mp3")]))

    assert use_case.processed == 2
    assert use_case.failed == []


class FakeLayeredExtractor:
    """레이어 추출기 대역. GPU도 모델도 쓰지 않는다."""

    def __init__(self, layers=(0, 3), chunks=2, dim=4):
        self._layers = layers
        self._chunks = chunks
        self._dim = dim
        self.calls = 0

    def extract_layers(self, waveform):
        import numpy as np

        self.calls += 1
        views = {"mixture": np.full((self._chunks, self._dim), 9.0, dtype=np.float32)}
        for index in self._layers:
            views[f"layer{index:02d}"] = np.full(
                (self._chunks, self._dim), float(index), dtype=np.float32
            )
        return views


class BrokenLayeredExtractor:
    def extract_layers(self, waveform):
        import numpy as np

        return {"layer00": np.zeros((1, 4), dtype=np.float32)}


def test_layer_features_put_layers_in_stem_slot(tmp_path):
    """산출물 규격이 기존과 같아야 평가 하네스가 구분 없이 읽는다."""
    from hathor.application.extract_features import ExtractLayerFeatures

    extractor = FakeLayeredExtractor()
    use_case = ExtractLayerFeatures(FakeDecoder(), extractor, tmp_path)
    features = list(use_case.run([make_track("가/노래.mp3")]))

    assert len(features) == 1
    assert set(features[0].stems) == {"layer00", "layer03"}
    assert features[0].chunk_count == 2
    assert use_case.processed == 1


def test_layer_features_decode_once_per_track(tmp_path):
    """레이어 수만큼 추론을 반복하면 배치 시간이 그만큼 배가된다."""
    from hathor.application.extract_features import ExtractLayerFeatures

    extractor = FakeLayeredExtractor(layers=(0, 3, 6, 9))
    use_case = ExtractLayerFeatures(FakeDecoder(), extractor, tmp_path)
    list(use_case.run([make_track("가/노래.mp3")]))
    assert extractor.calls == 1


def test_layer_features_require_mixture_key(tmp_path):
    from hathor.application.extract_features import ExtractLayerFeatures

    use_case = ExtractLayerFeatures(FakeDecoder(), BrokenLayeredExtractor(), tmp_path)
    assert list(use_case.run([make_track("가/노래.mp3")])) == []
    assert len(use_case.failed) == 1
    assert "KeyError" in use_case.failed[0][1]
