"""취향 라벨 수집 저장소와 CLI 테스트."""

import json

import numpy as np
import pytest

from hathor.application.extract_features import TrackFeatures
from hathor.domain.entities.preference_comparison import PreferenceComparison, Side
from hathor.infrastructure.jsonl_preference_store import JsonlPreferenceStore
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.main import main
from tests.unit.test_eval_cli import write_scan

DIM = 8
CHUNKS = 3


def build_library(tmp_path, count=6):
    """스캔 산출물과 임베딩을 갖춘 최소 라이브러리."""
    store = NpzFeatureStore(tmp_path / "mert-layers")
    entries = []
    for index in range(count):
        source_key = f"가수{index % 3}/앨범/{index:02d}.mp3"
        entries.append((source_key, f"가수{index % 3}", "앨범"))
        store.write_track(
            TrackFeatures(
                source_key=source_key,
                mixture=np.full((CHUNKS, DIM), float(index), dtype=np.float32),
                stems={"layer00": np.full((CHUNKS, DIM), float(index), dtype=np.float32)},
            )
        )
    write_scan(tmp_path, entries)
    return [key for key, _, _ in entries]


def test_store_appends_and_reads_back(tmp_path):
    store = JsonlPreferenceStore(tmp_path)
    store.append(PreferenceComparison(left="가", right="나", winner=Side.LEFT, recorded_at="t"))
    store.append(PreferenceComparison(left="가", right="다", winner=None, recorded_at="t"))

    items = list(store.read_all())
    assert len(items) == 2
    assert items[0].preferred == "가"
    assert items[1].skipped


def test_store_survives_partial_session(tmp_path):
    """응답마다 즉시 쓴다. 사람의 응답은 되돌릴 방법이 없는 유일한 자산이다."""
    store = JsonlPreferenceStore(tmp_path)
    store.append(PreferenceComparison(left="가", right="나", winner=Side.LEFT, recorded_at="t"))
    assert store.path.read_text(encoding="utf-8").count("\n") == 1


def test_store_read_all_on_missing_file(tmp_path):
    assert list(JsonlPreferenceStore(tmp_path).read_all()) == []


def test_store_counts_by_mode(tmp_path):
    store = JsonlPreferenceStore(tmp_path)
    store.append(PreferenceComparison(left="가", right="나", winner=Side.LEFT, recorded_at="t"))
    store.append(
        PreferenceComparison(left="가", right="다", winner=None, recorded_at="t", mode="adaptive")
    )
    counts = store.counts()
    assert counts == {
        "total": 2,
        "answered": 1,
        "skipped": 1,
        "mode:random": 1,
        "mode:adaptive": 1,
    }


def test_compare_records_answers(tmp_path, monkeypatch, capsys):
    build_library(tmp_path)
    answers = iter(["1", "2", "s"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    assert main(["taste", "compare", "--out", str(tmp_path), "--count", "3"]) == 0

    items = list(JsonlPreferenceStore(tmp_path).read_all())
    assert len(items) == 3
    assert [item.skipped for item in items] == [False, False, True]
    assert all(item.mode == "random" for item in items)
    assert "누적 3건" in capsys.readouterr().out


def test_compare_stores_canonical_order(tmp_path, monkeypatch):
    """제시 순서는 섞이지만 저장은 정규 순서다."""
    build_library(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "1")
    main(["taste", "compare", "--out", str(tmp_path), "--count", "5"])
    assert all(item.left <= item.right for item in JsonlPreferenceStore(tmp_path).read_all())


def test_compare_quits_and_keeps_progress(tmp_path, monkeypatch, capsys):
    build_library(tmp_path)
    answers = iter(["1", "q"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    assert main(["taste", "compare", "--out", str(tmp_path), "--count", "5"]) == 0
    assert len(list(JsonlPreferenceStore(tmp_path).read_all())) == 1
    assert "중단한다" in capsys.readouterr().out


def test_compare_does_not_repeat_answered_pairs(tmp_path, monkeypatch):
    build_library(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "1")
    main(["taste", "compare", "--out", str(tmp_path), "--count", "4"])
    main(["taste", "compare", "--out", str(tmp_path), "--count", "4"])

    items = list(JsonlPreferenceStore(tmp_path).read_all())
    keys = [(item.left, item.right) for item in items]
    assert len(keys) == len(set(keys))


def test_compare_only_offers_tracks_with_embeddings(tmp_path, monkeypatch):
    """임베딩이 없는 곡은 응답을 받아도 모델에 쓸 수 없다."""
    keys = build_library(tmp_path, count=4)
    extra = [(key, "가수", "앨범") for key in keys]
    extra.append(("임베딩없음.mp3", "가수", "앨범"))
    write_scan(tmp_path, extra)

    monkeypatch.setattr("builtins.input", lambda *_: "1")
    main(["taste", "compare", "--out", str(tmp_path), "--count", "6"])
    offered = {
        key for item in JsonlPreferenceStore(tmp_path).read_all() for key in (item.left, item.right)
    }
    assert "임베딩없음.mp3" not in offered


def test_compare_handles_eof_as_quit(tmp_path, monkeypatch):
    build_library(tmp_path)

    def raise_eof(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert main(["taste", "compare", "--out", str(tmp_path), "--count", "3"]) == 0
    assert list(JsonlPreferenceStore(tmp_path).read_all()) == []


def test_compare_without_scan_output(tmp_path):
    assert main(["taste", "compare", "--out", str(tmp_path)]) == 2


def test_compare_without_features(tmp_path):
    write_scan(tmp_path, [("가.mp3", "가수", "앨범")])
    assert main(["taste", "compare", "--out", str(tmp_path)]) == 2


def test_status_reports_counts(tmp_path, capsys):
    build_library(tmp_path)
    store = JsonlPreferenceStore(tmp_path)
    store.append(PreferenceComparison(left="가", right="나", winner=Side.LEFT, recorded_at="t"))
    assert main(["taste", "status", "--out", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "누적 1건" in output
    assert "random: 1건" in output


def test_status_on_empty_store(tmp_path, capsys):
    assert main(["taste", "status", "--out", str(tmp_path)]) == 0
    assert "기록된 응답이 없다" in capsys.readouterr().out


def test_records_are_valid_json_lines(tmp_path, monkeypatch):
    build_library(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "2")
    main(["taste", "compare", "--out", str(tmp_path), "--count", "2"])
    for line in JsonlPreferenceStore(tmp_path).path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        assert set(record) == {"left", "right", "winner", "recorded_at", "mode"}


def test_taste_requires_subcommand():
    with pytest.raises(SystemExit):
        main(["taste"])
