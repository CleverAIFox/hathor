"""평가 CLI 통합 테스트.

스캔 JSONL과 npz를 합성해 `eval retrieval` 전 경로를 돌린다.
실제 음원도 GPU도 쓰지 않는다 (NFR-SEC-003·004).
"""

import json

import numpy as np
import pytest

from hathor.application.extract_features import TrackFeatures
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.main import main

DIM = 32
CHUNKS = 6


def write_scan(root, tracks):
    """JsonlScanStore가 읽는 형식으로 스캔 산출물을 만든다."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "scan-20260816T000000Z.jsonl"
    with path.open("w", encoding="utf-8") as stream:
        for source_key, artist, album in tracks:
            record = {
                "source_key": source_key,
                "event": "discovered",
                "file_size_bytes": 1,
                "modified_at": "2026-08-16T00:00:00+00:00",
                "stream": {
                    "sample_rate_hz": 44100,
                    "channels": 2,
                    "duration_ms": 60000,
                    "bitrate_bps": 320000,
                    "codec": "mp3",
                },
                "tags": {
                    "title": source_key,
                    "artist": artist,
                    "album": album,
                    "lyrics_text": None,
                    "has_album_art": False,
                    "has_synced_lyrics": False,
                    "release_date_raw": None,
                    "isrc": None,
                },
                "raw_frame_names": ["TIT2", "TPE1", "TALB"],
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def build_corpus(tmp_path, albums=4, per_album=4, features_root=None):
    """앨범별 중심 + 곡별 고유 편차를 가진 합성 코퍼스를 디스크에 만든다."""
    generator = np.random.default_rng(11)
    store = NpzFeatureStore(features_root or tmp_path)
    entries = []
    for album_index in range(albums):
        center = generator.normal(0.0, 1.0, size=(1, DIM))
        artist = f"아티스트{album_index // 2}"
        album = f"앨범{album_index}"
        for track_index in range(per_album):
            identity = generator.normal(0.0, 0.35, size=(1, DIM))
            noise = generator.normal(0.0, 0.02, size=(CHUNKS, DIM))
            source_key = f"{artist}/{album}/{track_index:02d}.mp3"
            entries.append((source_key, artist, album))
            store.write_track(
                TrackFeatures(
                    source_key=source_key,
                    mixture=np.asarray(center + identity + noise, dtype=np.float32),
                    stems={"vocals": np.asarray(center + identity + noise * 2, dtype=np.float32)},
                )
            )
    write_scan(tmp_path, entries)
    return entries


def latest_report(tmp_path):
    reports = sorted((tmp_path / "eval").glob("*.eval.json"))
    return json.loads(reports[-1].read_text(encoding="utf-8"))


def test_eval_retrieval_end_to_end(tmp_path, capsys):
    build_corpus(tmp_path)
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--k", "3"]) == 0

    output = capsys.readouterr().out
    assert "M0 자기일관성" in output
    assert "m1_album" in output

    report = latest_report(tmp_path)
    assert report["corpus"]["tracks"] == 16
    assert report["m0_self_consistency"]["passed"] is True
    assert [metric["name"] for metric in report["metrics"]] == ["m1_album", "m2_artist"]
    assert (
        report["metrics"][0]["measured"]["map_at_k"]
        > report["metrics"][0]["random_baseline"]["map_at_k"]
    )


def test_eval_retrieval_records_view_config(tmp_path):
    build_corpus(tmp_path)
    code = main(
        [
            "eval",
            "retrieval",
            "--out",
            str(tmp_path),
            "--keys",
            "mixture,vocals",
            "--pool",
            "mean-std",
            "--chunk-l2",
            "--k",
            "3",
        ]
    )
    assert code == 0
    report = latest_report(tmp_path)
    assert report["config"]["view"]["keys"] == ["mixture", "vocals"]
    assert report["config"]["view"]["pool"] == "mean-std"
    assert report["config"]["view"]["chunk_l2"] is True
    # 키 2종 x (평균+표준편차)
    assert report["corpus"]["dimension"] == DIM * 4


def test_eval_retrieval_report_filename_carries_label(tmp_path):
    build_corpus(tmp_path)
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--label", "실험 A/1"]) == 0
    names = [path.name for path in (tmp_path / "eval").glob("*.eval.json")]
    assert any(name.endswith("-A-1.eval.json") for name in names)


def test_eval_retrieval_rejects_duplicate_index(tmp_path, capsys):
    """O-7 재발 방어. 중복을 흡수하면 지표가 조용히 틀어진다."""
    build_corpus(tmp_path)
    store = NpzFeatureStore(tmp_path)
    store.write_track(
        TrackFeatures(
            source_key="아티스트0/앨범0/00.mp3",
            mixture=np.zeros((CHUNKS, DIM), dtype=np.float32),
            stems={},
        )
    )
    assert main(["eval", "retrieval", "--out", str(tmp_path)]) == 2
    assert "compact" in capsys.readouterr().err


def test_eval_retrieval_warns_on_orphan_features(tmp_path, capsys):
    build_corpus(tmp_path)
    NpzFeatureStore(tmp_path).write_track(
        TrackFeatures(
            source_key="스캔에없는곡.mp3",
            mixture=np.zeros((CHUNKS, DIM), dtype=np.float32),
            stems={},
        )
    )
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--k", "3"]) == 0
    assert "스캔 산출물에 없는 곡 1건" in capsys.readouterr().err


def test_eval_retrieval_fails_gate_on_noise(tmp_path, capsys):
    """임베딩이 곡 정체성을 못 담으면 비정상 종료한다."""
    generator = np.random.default_rng(2)
    store = NpzFeatureStore(tmp_path)
    entries = []
    for index in range(10):
        source_key = f"아티스트/앨범/{index:02d}.mp3"
        entries.append((source_key, "아티스트", "앨범"))
        store.write_track(
            TrackFeatures(
                source_key=source_key,
                mixture=np.asarray(generator.normal(size=(CHUNKS, DIM)), dtype=np.float32),
                stems={},
            )
        )
    write_scan(tmp_path, entries)

    assert main(["eval", "retrieval", "--out", str(tmp_path)]) == 1
    assert "M0 게이트 미달" in capsys.readouterr().err
    assert latest_report(tmp_path)["metrics"] == []


def test_eval_retrieval_separate_features_root(tmp_path):
    """베이스라인 비교 경로. 스캔은 공유하고 특징만 갈아끼운다."""
    baseline = tmp_path / "baseline-mfcc"
    build_corpus(tmp_path)
    build_corpus(tmp_path, features_root=baseline)
    code = main(
        [
            "eval",
            "retrieval",
            "--out",
            str(tmp_path),
            "--features",
            str(baseline),
            "--label",
            "mfcc",
            "--k",
            "3",
        ]
    )
    assert code == 0
    assert latest_report(tmp_path)["config"]["label"] == "mfcc"


def test_eval_retrieval_without_scan_output(tmp_path):
    assert main(["eval", "retrieval", "--out", str(tmp_path)]) == 2


def test_eval_retrieval_without_features(tmp_path):
    write_scan(tmp_path, [("가.mp3", "가수", "앨범")])
    assert main(["eval", "retrieval", "--out", str(tmp_path)]) == 2


def test_eval_retrieval_rejects_empty_keys(tmp_path):
    build_corpus(tmp_path)
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--keys", " , "]) == 2


def test_eval_retrieval_limit(tmp_path):
    build_corpus(tmp_path)
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--limit", "8", "--k", "3"]) == 0
    assert latest_report(tmp_path)["corpus"]["tracks"] == 8


def test_eval_mfcc_without_scan_output(tmp_path):
    """스캔 산출물이 없으면 디코더를 만들기 전에 빠져나온다."""
    assert main(["eval", "mfcc", "--out", str(tmp_path)]) == 2


def test_eval_mfcc_skips_completed(tmp_path, capsys):
    build_corpus(tmp_path, albums=1, per_album=2, features_root=tmp_path / "baseline-mfcc")
    code = main(["eval", "mfcc", "--out", str(tmp_path), "--root", str(tmp_path)])
    assert code == 0
    assert "처리할 곡이 없다" in capsys.readouterr().out


def test_eval_requires_subcommand():
    with pytest.raises(SystemExit):
        main(["eval"])
