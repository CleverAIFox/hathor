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


def test_eval_retrieval_merges_two_feature_stores(tmp_path):
    """서로 다른 추출기 두 벌을 이름으로 네임스페이스해 하나의 뷰로 합친다."""
    other = tmp_path / "baseline-mfcc"
    build_corpus(tmp_path)
    build_corpus(tmp_path, features_root=other)
    code = main(
        [
            "eval",
            "retrieval",
            "--out",
            str(tmp_path),
            "--features",
            f"mert={tmp_path}",
            "--features",
            f"mfcc={other}",
            "--keys",
            "mert:mixture,mfcc:mixture",
            "--block-l2",
            "--k",
            "3",
        ]
    )
    assert code == 0
    report = latest_report(tmp_path)
    assert report["corpus"]["tracks"] == 16
    assert report["corpus"]["dimension"] == DIM * 2
    assert report["config"]["view"]["block_l2"] is True


def test_eval_retrieval_requires_names_for_multiple_stores(tmp_path):
    other = tmp_path / "baseline-mfcc"
    build_corpus(tmp_path)
    build_corpus(tmp_path, features_root=other)
    with pytest.raises(SystemExit):
        main(
            [
                "eval",
                "retrieval",
                "--out",
                str(tmp_path),
                "--features",
                str(tmp_path),
                "--features",
                str(other),
            ]
        )


def test_eval_retrieval_rejects_duplicate_store_names(tmp_path):
    build_corpus(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "eval",
                "retrieval",
                "--out",
                str(tmp_path),
                "--features",
                f"a={tmp_path}",
                "--features",
                f"a={tmp_path}",
            ]
        )


def test_eval_retrieval_drops_tracks_missing_from_one_store(tmp_path, capsys):
    """한쪽 저장소에만 있는 곡은 뺀다. 저장소마다 다른 곡 집합을 비교하면 안 된다."""
    other = tmp_path / "baseline-mfcc"
    # 작은 쪽을 먼저 만든다. build_corpus가 스캔 산출물을 덮어쓰므로 마지막
    # 호출이 곡 목록을 정한다. 전체 16곡 중 mfcc에는 12곡만 있는 상태가 된다.
    build_corpus(tmp_path, albums=3, per_album=4, features_root=other)
    build_corpus(tmp_path)
    code = main(
        [
            "eval",
            "retrieval",
            "--out",
            str(tmp_path),
            "--features",
            f"mert={tmp_path}",
            "--features",
            f"mfcc={other}",
            "--keys",
            "mert:mixture,mfcc:mixture",
            "--block-l2",
            "--k",
            "3",
        ]
    )
    assert code == 0
    assert "일부 저장소에만 있는 곡" in capsys.readouterr().err
    assert latest_report(tmp_path)["corpus"]["tracks"] == 12


def test_eval_retrieval_single_store_keeps_bare_keys(tmp_path):
    """저장소가 하나면 이름 없이 기존 사용법이 그대로 돈다."""
    build_corpus(tmp_path)
    assert main(["eval", "retrieval", "--out", str(tmp_path), "--features", str(tmp_path)]) == 0


def test_eval_layers_without_scan_output(tmp_path):
    assert main(["eval", "layers", "--out", str(tmp_path)]) == 2


def test_eval_layers_rejects_non_integer(tmp_path, capsys):
    write_scan(tmp_path, [("가.mp3", "가수", "앨범")])
    assert main(["eval", "layers", "--out", str(tmp_path), "--layers", "여섯"]) == 2
    assert "정수" in capsys.readouterr().err


def test_eval_layers_rejects_empty(tmp_path, capsys):
    write_scan(tmp_path, [("가.mp3", "가수", "앨범")])
    assert main(["eval", "layers", "--out", str(tmp_path), "--layers", " , "]) == 2
    assert "최소 하나" in capsys.readouterr().err


def test_eval_layers_skips_completed(tmp_path, capsys):
    """모델 적재 전에 재개 판정이 끝나야 GPU 없는 기기에서도 게이트가 돈다."""
    build_corpus(tmp_path, albums=1, per_album=2, features_root=tmp_path / "mert-layers")
    assert main(["eval", "layers", "--out", str(tmp_path), "--root", str(tmp_path)]) == 0
    assert "처리할 곡이 없다" in capsys.readouterr().out


def test_gate_failure_distinguishes_near_miss_from_collapse():
    """미달의 성격을 순위 진단으로 가른다 (D-0044).

    실측이 반증한 것을 고정한다. 가사 8192는 top-1 0.9174로 미달이나 R@10 0.9715,
    실패 순위 중앙값 3.8이었다(무작위 502). damp는 R@10 0.4688, 실패 순위 831이었다.
    **옛 문구는 둘을 같은 말로 보고했다.**
    """
    from hathor.interfaces.cli.main import _gate_failure_message

    near_miss = _gate_failure_message(_report_with(top1=0.9174, recall10=0.9715, miss=3.8))
    collapsed = _gate_failure_message(_report_with(top1=0.3850, recall10=0.4688, miss=831.1))

    assert "표현이 무너진 것이 아니라" in near_miss
    assert "추출 설정부터 다시 본다" not in near_miss
    assert "상위권에도 없다" in collapsed
    assert "추출 설정부터 다시 본다" in collapsed


def test_gate_failure_uses_rank_when_recall_is_just_short():
    """R@10 하나로 가르면 경계에서 틀린다 (D-0046).

    BGE-M3 홀짝 조건이 실측에서 **실패 순위 중앙값 5.5인데 R@10 0.9442**로
    0.95에 못 미쳐 "정답이 상위권에도 없다"로 보고됐다. 5.5는 상위권이다.
    """
    from hathor.interfaces.cli.main import _gate_failure_message

    message = _gate_failure_message(_report_with(top1=0.8504, recall10=0.9442, miss=5.5))
    assert "표현이 무너진 것이 아니라" in message


def test_gate_failure_still_flags_real_collapse_with_low_recall():
    """순위 중앙값이 k를 넘으면 여전히 붕괴로 본다. 완화가 아니다."""
    from hathor.interfaces.cli.main import _gate_failure_message

    message = _gate_failure_message(_report_with(top1=0.3850, recall10=0.4688, miss=831.1))
    assert "상위권에도 없다" in message


def _report_with(*, top1: float, recall10: float, miss: float):
    """지정한 순위 진단을 갖는 최소 리포트. 코퍼스를 만들지 않는다."""
    from dataclasses import dataclass

    from hathor.application.evaluate_retrieval import EvaluationConfig

    @dataclass(frozen=True)
    class _Consistency:
        recall_at_10: float
        miss_median_rank: float
        random_median_rank: float = 502.0

    @dataclass(frozen=True)
    class _Report:
        consistency: _Consistency
        self_consistency: float
        config: EvaluationConfig

    return _Report(
        consistency=_Consistency(recall_at_10=recall10, miss_median_rank=miss),
        self_consistency=top1,
        config=EvaluationConfig(),
    )


# --- CLI 배선 (D-0046) ---


def test_lyrics_extract_accepts_every_documented_flag():
    """문서와 러너가 쓰는 플래그가 실제로 파서에 있는지 본다.

    **`--pooling`이 파서에 없는 채로 배포된 적이 있다.** 인코더에는 구현돼
    있었고 인코더 테스트도 통과했으나 CLI 배선만 빠져서, 리전에서 실행하고
    나서야 `unrecognized arguments`로 드러났다.

    인코더 단위 테스트는 배선을 보지 않는다. **여기가 그 구멍이다.**
    """
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(
        [
            "lyrics",
            "extract",
            "--out",
            "var/ingest",
            "--features",
            "var/ingest/lyrics-bge-m3-mean",
            "--encoder",
            "bge-m3",
            "--pooling",
            "mean",
            "--device",
            "cpu",
            "--batch-size",
            "8",
        ]
    )
    assert args.encoder == "bge-m3"
    assert args.pooling == "mean"
    assert args.device == "cpu"
    assert args.batch_size == 8


def test_lyrics_extract_defaults_reproduce_previous_outputs():
    """기본값이 바뀌면 기존 산출물을 다시 만들 수 없다."""
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(["lyrics", "extract"])
    assert args.encoder == "hashed"
    assert args.pooling == "cls"


def test_lyrics_extract_rejects_unknown_pooling():
    from hathor.interfaces.cli.main import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["lyrics", "extract", "--pooling", "nonsense"])


def test_generate_accepts_every_documented_flag():
    """생성 CLI 배선 (D-0054). D-0047에서 겪은 누락을 되풀이하지 않는다."""
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(
        [
            "generate",
            "--seed",
            "7",
            "--midi",
            "var/out/demo.mid",
            "--reference",
            "10CM",
            "--reference",
            "아이유",
            "--tempo",
            "108",
            "--max-references",
            "3",
            "--no-key-estimation",
        ]
    )
    assert args.reference == ["10CM", "아이유"]
    assert args.tempo == 108
    assert args.max_references == 3
    assert args.no_key_estimation is True


def test_generate_defaults_follow_the_decision_record():
    """참조곡 상한 5개는 D-0011이 정한 값이다."""
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(["generate", "--seed", "1"])
    assert args.max_references == 5
    assert args.no_key_estimation is False
    assert args.reference is None


def test_ingest_keys_is_wired():
    """조성 분포 실측 배선 (O-22)."""
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(["ingest", "keys", "--limit", "50"])
    assert args.ingest_command == "keys"
    assert args.limit == 50


def test_ingest_keys_sweep_is_wired():
    """배음 스윕 배선 (D-0060)."""
    from hathor.interfaces.cli.main import build_parser

    args = build_parser().parse_args(
        ["ingest", "keys", "--replay", "keys.jsonl", "--harmonic-sweep"]
    )
    assert args.harmonic_sweep is True
    assert build_parser().parse_args(["ingest", "keys"]).harmonic_sweep is False
