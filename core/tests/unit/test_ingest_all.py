"""한 패스 추출과 묶음 저장 (D-0203)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
import pytest

from hathor.application.ingest_all import (
    MIXTURE,
    ONSET_SOURCES,
    PITCH_SOURCES,
    IngestAll,
)
from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags
from hathor.infrastructure.track_bundle_store import TrackBundleStore, bundle_name

if TYPE_CHECKING:
    from pathlib import Path

STEMS = ("bass", "drums", "other", "vocals")
LAYERS = (0, 3, 6)


def _track(name: str) -> ScannedTrack:
    return ScannedTrack(
        source_key=name,
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            sample_rate_hz=44100, channels=2, duration_ms=3000, bitrate_bps=320000, codec="mp3"
        ),
        tags=TrackTags(
            title=name,
            artist="누구",
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        ),
        raw_frame_names=(),
    )


class FakeDecoder:
    def decode(self, path):  # type: ignore[no-untyped-def]
        generator = np.random.default_rng(len(str(path)))
        return generator.standard_normal((2, 44100 * 3)).astype(np.float32) * 0.1


class FakeSeparator:
    def separate(self, waveform):  # type: ignore[no-untyped-def]
        return {name: waveform * 0.5 for name in STEMS}


class FakeExtractor:
    layers = LAYERS

    def extract_layers(self, waveform):  # type: ignore[no-untyped-def]
        keys = (MIXTURE, *(f"layer{index:02d}" for index in LAYERS))
        return dict.fromkeys(keys, np.zeros((4, 768), dtype=np.float32))


class FakePitch:
    def track(self, waveform, *, sample_rate, fmin, fmax):  # type: ignore[no-untyped-def]
        return np.full(10, fmin * 2, dtype=np.float32)


class BrokenDecoder:
    def decode(self, path):  # type: ignore[no-untyped-def]
        raise RuntimeError("디코딩 실패")


@pytest.fixture
def job(tmp_path: Path) -> IngestAll:
    return IngestAll(
        decoder=FakeDecoder(),
        separator=FakeSeparator(),
        extractor=FakeExtractor(),
        pitch=FakePitch(),
        library_root=tmp_path,
    )


def test_디코딩과_분리를_곡당_한_번만_한다(job: IngestAll) -> None:
    """**이것이 이 모듈의 존재 이유다** (D-0203).

    축마다 명령이 따로였고 `features`가 분리를 하고 `keys`가 또 했다. 스템은
    4분 곡 하나가 340MB라 **디스크에 못 남기므로** 캐시로는 못 푼다.
    """
    calls: list[str] = []

    class Counting(FakeSeparator):
        def separate(self, waveform):  # type: ignore[no-untyped-def]
            calls.append("분리")
            return super().separate(waveform)

    job.separator = Counting()
    list(job.run([_track("가.mp3")]))

    assert calls == ["분리"]


def test_믹스와_스템_전부에서_층을_뽑는다(job: IngestAll) -> None:
    bundle = next(iter(job.run([_track("가.mp3")])))

    for source in (MIXTURE, *STEMS):
        for index in LAYERS:
            assert f"mert/{source}/layer{index:02d}" in bundle.arrays


def test_온셋은_믹스에서_안_뽑는다(job: IngestAll) -> None:
    """**무엇이 울린 것인지 안 갈린다** (O-46).

    지금 산출물이 믹스 포락선이라 드럼과 화음이 섞여 *"화음이 마디 안 어디에
    떨어지나"*에 답이 안 나온다.
    """
    bundle = next(iter(job.run([_track("가.mp3")])))

    assert f"onset/{MIXTURE}" not in bundle.arrays
    for name in ONSET_SOURCES:
        assert f"onset/{name}" in bundle.arrays


def test_음고는_단성_스템에만_건다(job: IngestAll) -> None:
    """다성에 걸면 **무엇의 음고인지 알 수 없다.**"""
    bundle = next(iter(job.run([_track("가.mp3")])))

    tracked = {name for name in bundle.arrays if name.startswith("pitch/")}
    assert tracked == {f"pitch/{name}" for name, _, _ in PITCH_SOURCES}
    assert "pitch/drums" not in bundle.arrays
    assert f"pitch/{MIXTURE}" not in bundle.arrays


def test_무음은_판정하지_않고_원값을_남긴다(job: IngestAll) -> None:
    """문턱을 걸어 0/1로 접으면 **문턱을 바꿀 때마다 다시 뽑아야 한다** (O-28)."""
    bundle = next(iter(job.run([_track("가.mp3")])))

    silence = bundle.arrays["silence/mixture"]
    assert silence.dtype == np.float32
    assert set(np.unique(silence)) != {0.0, 1.0}


def test_실패해도_순회가_계속되고_원인이_남는다(tmp_path: Path) -> None:
    """**지난 배치가 240곡을 원인 없이 잃었다** (`failures: []`)."""
    job = IngestAll(
        decoder=BrokenDecoder(),
        separator=FakeSeparator(),
        extractor=FakeExtractor(),
        pitch=FakePitch(),
        library_root=tmp_path,
    )

    bundles = list(job.run([_track("가.mp3"), _track("나.mp3")]))

    assert bundles == []
    assert job.processed == 0
    assert len(job.failed) == 2
    assert "RuntimeError: 디코딩 실패" in job.failed[0][1]


def test_manifest가_산출물을_설명한다(tmp_path: Path, job: IngestAll) -> None:
    """**옛 묶음은 아무것도 안 들었다** (D-0203).

    `mert-layers`가 어느 모델·어느 입력으로 뽑혔는지 저장소 어디에도 없어
    `stem_names`에 `layer03`이 든 것을 보고 추측해야 했다.
    """
    store = TrackBundleStore(tmp_path / "audio")
    bundle = next(iter(job.run([_track("가.mp3")])))

    store.write(bundle.source_key, bundle.arrays, bundle.manifest)

    written = json.loads(
        (tmp_path / "audio" / f"{bundle_name('가.mp3')}.manifest.json").read_text(encoding="utf-8")
    )
    assert written["source_key"] == "가.mp3"
    assert written["layers"] == sorted(LAYERS)
    assert written["dtype"] == "float32"
    assert written["pitch_sample_rate"] == 11025
    assert "revision" in written and "written_at" in written


def test_manifest가_있어야_끝난_것이다(tmp_path: Path, job: IngestAll) -> None:
    """npz만 있으면 **manifest를 쓰다 죽은 것**이다. 다시 뽑는다."""
    store = TrackBundleStore(tmp_path / "audio")
    bundle = next(iter(job.run([_track("가.mp3")])))
    store.write(bundle.source_key, bundle.arrays, bundle.manifest)
    assert store.has("가.mp3")

    (tmp_path / "audio" / f"{bundle_name('가.mp3')}.manifest.json").unlink()

    assert not store.has("가.mp3")


def test_실패_기록이_쌓인다(tmp_path: Path) -> None:
    store = TrackBundleStore(tmp_path / "audio")

    store.record_failure("가.mp3", "RuntimeError: 터짐")
    store.record_failure("나.mp3", "OSError: 없음")

    assert store.counts() == {"done": 0, "failed": 2}


def test_타임스탬프_폴더를_만들지_않는다(tmp_path: Path, job: IngestAll) -> None:
    """`scan-*.jsonl`이 셋 · `keys-*.jsonl`이 열하나였다 (D-0203).

    **실행마다 새 이름이면 옛것은 영원히 안 지워진다.**
    """
    store = TrackBundleStore(tmp_path / "audio")
    for _ in range(2):
        bundle = next(iter(job.run([_track("가.mp3")])))
        store.write(bundle.source_key, bundle.arrays, bundle.manifest)

    assert sorted(path.name for path in (tmp_path / "audio").iterdir()) == [
        f"{bundle_name('가.mp3')}.manifest.json",
        f"{bundle_name('가.mp3')}.npz",
    ]
