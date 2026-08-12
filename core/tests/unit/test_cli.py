import json

import pytest

from hathor.interfaces.cli.main import main


def test_cli_writes_identical_output_for_same_seed(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        code = main(
            [
                "generate",
                "--seed",
                "42",
                "--dry-run",
                "--stages",
                "structure,harmony",
                "--out",
                str(out),
            ]
        )
        assert code == 0
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    ja.pop("job"), jb.pop("job")
    assert ja == jb


def test_cli_prints_when_no_out(capsys):
    assert main(["generate", "--seed", "1", "--dry-run"]) == 0
    assert "harmony" in capsys.readouterr().out


def test_cli_requires_dry_run():
    assert main(["generate", "--seed", "1"]) == 2


def test_cli_rejects_unknown_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", "mixing"])


def test_cli_rejects_empty_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", " , "])


def test_ingest_features_without_scan_output(tmp_path, capsys):
    """스캔 산출물이 없으면 모델을 만들기 전에 빠져나온다."""
    assert main(["ingest", "features", "--out", str(tmp_path)]) == 2
    assert "스캔 산출물이 없다" in capsys.readouterr().err


def test_ingest_features_skips_completed(tmp_path, capsys, monkeypatch):
    """전부 추출된 상태면 GPU 구현체를 만들지 않고 끝난다."""
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore
    from hathor.interfaces.cli import main as cli

    track = _fake_track("a.mp3")
    monkeypatch.setattr(cli.JsonlScanStore, "read_tracks", lambda self: iter([track]))
    index = NpzFeatureStore(tmp_path).index_path
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"source_key": "a.mp3"}) + "\n", encoding="utf-8")

    assert main(["ingest", "features", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "건너뛴다" in out
    assert "처리할 곡이 없다" in out


def _fake_track(source_key):
    from datetime import UTC, datetime

    from hathor.domain.entities.audio_stream import AudioStreamProperties
    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.domain.entities.track_tags import TrackTags

    return ScannedTrack(
        source_key=source_key,
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            sample_rate_hz=44100,
            channels=2,
            duration_ms=1000,
            bitrate_bps=320000,
            codec="mp3",
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
