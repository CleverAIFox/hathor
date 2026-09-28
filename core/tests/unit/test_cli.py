import json

import pytest

from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.interfaces.cli.main import main
from tests.conftest import scanned_track


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
    from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    track = _fake_track("a.mp3")
    # **반은 객체 하나다** (D-0264). 정본에서 가져와 붙여도 `main`이 보는 것과 같은
    # 것이며, `main`을 통해 읽으면 «`main`이 그것을 내보낸다»에 기대게 된다.
    monkeypatch.setattr(JsonlScanStore, "read_tracks", lambda self: iter([track]))
    index = NpzFeatureStore(tmp_path).index_path
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"source_key": "a.mp3"}) + "\n", encoding="utf-8")

    assert main(["ingest", "features", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "건너뛴다" in out
    assert "처리할 곡이 없다" in out


def _fake_track(source_key: str) -> ScannedTrack:
    """조립은 `tests.conftest.scanned_track` 하나다 (D-0264)."""
    return scanned_track(source_key)


# ---------------------------------------------------------------- ingest compact (O-7(D-0022))


def _seed_features(root, keys, *, duplicates=()):
    """인덱스와 npz를 갖춘 산출물 디렉터리를 만든다."""
    import numpy as np

    from hathor.domain.entities.track_features import TrackFeatures
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    store = NpzFeatureStore(root)
    for key in keys:
        embedding = np.zeros((2, 768), dtype=np.float32)
        store.write_track(
            TrackFeatures(
                source_key=key,
                mixture=embedding,
                stems={name: embedding for name in ("bass", "drums", "other", "vocals")},
            )
        )
    for key in duplicates:
        embedding = np.zeros((5, 768), dtype=np.float32)
        store.write_track(
            TrackFeatures(
                source_key=key,
                mixture=embedding,
                stems={name: embedding for name in ("bass", "drums", "other", "vocals")},
            )
        )
    return store


def test_compact_without_index_exits_2(tmp_path, capsys):
    """산출물이 없는데 조용히 성공하면 잘못된 디렉터리를 짚은 것을 못 알아챈다."""
    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 2
    assert "인덱스가 없다" in capsys.readouterr().err


def test_compact_dry_run_reports_without_writing(tmp_path, capsys):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"], duplicates=["a.mp3"])
    before = store.index_path.read_bytes()

    assert main(["ingest", "compact", "--out", str(tmp_path), "--dry-run"]) == 0

    assert "중복 1줄" in capsys.readouterr().out
    assert store.index_path.read_bytes() == before


def test_compact_removes_duplicates(tmp_path, capsys):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"], duplicates=["a.mp3"])

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0

    assert store.completed_keys() == {"a.mp3", "b.mp3"}
    assert "중복 제거 1줄" in capsys.readouterr().out


def test_compact_drops_orphan_records(tmp_path, capsys):
    """npz가 없는 기록이 남으면 재개가 그 곡을 영영 건너뛴다."""
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"])
    next(store.vectors_dir.glob("*.npz")).unlink()

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0

    assert len(store.completed_keys()) == 1
    assert "npz 없는 기록 제거 1줄" in capsys.readouterr().out


def test_compact_keep_missing_preserves_orphans(tmp_path):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"])
    next(store.vectors_dir.glob("*.npz")).unlink()

    assert main(["ingest", "compact", "--out", str(tmp_path), "--keep-missing"]) == 0

    assert store.completed_keys() == {"a.mp3", "b.mp3"}


def test_compact_reports_no_change(tmp_path, capsys):
    _seed_features(tmp_path, ["a.mp3"])
    main(["ingest", "compact", "--out", str(tmp_path)])

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0
    assert "바꿀 것이 없었다" in capsys.readouterr().out


def test_compact_refuses_while_batch_runs(tmp_path, capsys):
    """배치가 도는 중에 인덱스를 다시 쓰면 진행 중인 기록을 잃는다."""
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    store = _seed_features(tmp_path, ["a.mp3"])
    with store.batch_lock():
        assert main(["ingest", "compact", "--out", str(tmp_path)]) == 3
    assert "배치가 이미 실행 중이다" in capsys.readouterr().err
    assert NpzFeatureStore(tmp_path).completed_keys() == {"a.mp3"}


def test_features_exits_3_when_batch_locked(tmp_path, capsys):
    """O-7(D-0022) 방어. 두 배치가 겹치면 인덱스에 중복이 쌓인다."""
    store = _seed_features(tmp_path, ["a.mp3"])
    with store.batch_lock():
        assert main(["ingest", "features", "--out", str(tmp_path)]) == 3
    captured = capsys.readouterr().err
    assert "배치가 이미 실행 중이다" in captured
    assert "끝내거나 죽인" in captured


# ------------------------------- 저장된 크로마로 다시 판정한다 (D-0281)


def test_재판정이_행을_다시_쓴다():
    """**음원도 GPU도 없이 프로파일을 바꿔 본다** (D-0059)."""
    from hathor.application.replay_keys import recompute

    rows: list[dict[str, object]] = [
        {"chroma": [1.0] + [0.0] * 11, "key": "옛 판정", "correlation": 0.0}
    ]

    assert recompute(rows, strength=0.0, profile="temperley") == 1
    assert rows[0]["key"] != "옛 판정"
    assert rows[0]["profile"] == "temperley"


def test_크로마가_없거나_무게가_0이면_그대로_둔다():
    """**0으로 나누면 `numpy`가 조용히 `nan`을 내고 그것이 분포 보고로 간다** (D-0281)."""
    from hathor.application.replay_keys import recompute

    rows: list[dict[str, object]] = [{"key": "그대로"}, {"chroma": [0.0] * 12, "key": "그대로"}]

    assert recompute(rows, strength=0.0, profile="temperley") == 0
    assert [row["key"] for row in rows] == ["그대로", "그대로"]
