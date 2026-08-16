"""특징 저장소 테스트 (유닛 #4).

벡터는 npz, 메타는 JSONL이다. GPU도 실제 음원도 쓰지 않는다.
"""

import contextlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from hathor.application.extract_features import TrackFeatures
from hathor.infrastructure.npz_feature_store import (
    MIXTURE_KEY,
    BatchAlreadyRunningError,
    NpzFeatureStore,
    features_as_record,
    vector_filename,
)

STEM_NAMES = ("drums", "bass", "other", "vocals")


def make_features(source_key: str = "가수/노래.mp3", chunks: int = 3) -> TrackFeatures:
    """청크 수만 다른 결정적 임베딩을 만든다."""

    def embedding(seed: int) -> np.ndarray:
        return np.full((chunks, 768), float(seed), dtype=np.float32)

    return TrackFeatures(
        source_key=source_key,
        mixture=embedding(0),
        stems={name: embedding(index + 1) for index, name in enumerate(STEM_NAMES)},
    )


def test_vector_filename_is_stable_and_safe() -> None:
    name = vector_filename("가수/노래 (Live).mp3")
    assert name == vector_filename("가수/노래 (Live).mp3")
    assert "/" not in name
    assert name.endswith(".npz")


def test_vector_filename_differs_by_key() -> None:
    assert vector_filename("a.mp3") != vector_filename("b.mp3")


def test_record_keeps_key_order() -> None:
    """D-0009. 2대 산출물이 바이트 단위로 같으려면 키 순서가 고정이어야 한다."""
    record = features_as_record(make_features())
    assert list(record) == [
        "source_key",
        "vector_file",
        "chunk_count",
        "feature_dim",
        "stem_names",
    ]
    assert record["chunk_count"] == 3
    assert record["feature_dim"] == 768
    assert record["stem_names"] == sorted(STEM_NAMES)


def test_record_has_no_timestamp() -> None:
    """기록 시각이 들어가면 두 노트북 산출물이 달라진다."""
    record = features_as_record(make_features())
    assert not any(key.endswith(("_at", "_time", "stamp")) for key in record)


def test_write_track_roundtrip(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    features = make_features()

    target = store.write_track(features)

    with np.load(target) as loaded:
        assert set(loaded) == {MIXTURE_KEY, *STEM_NAMES}
        assert loaded[MIXTURE_KEY].shape == (3, 768)
        assert loaded[MIXTURE_KEY].dtype == np.float32
        np.testing.assert_array_equal(loaded["vocals"], features.stems["vocals"])


def test_index_appends_across_runs(tmp_path: Path) -> None:
    """실행마다 새 파일을 만들면 재개가 불가능하다. 인덱스는 이어져야 한다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    NpzFeatureStore(tmp_path).write_track(make_features("b.mp3"))

    lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["source_key"] for line in lines] == ["a.mp3", "b.mp3"]


def test_completed_keys_empty_before_any_write(tmp_path: Path) -> None:
    assert NpzFeatureStore(tmp_path).completed_keys() == set()


def test_completed_keys_reports_written(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    store.write_track(make_features("b.mp3"))
    assert store.completed_keys() == {"a.mp3", "b.mp3"}


def test_no_temporary_file_survives(tmp_path: Path) -> None:
    """중단되어도 반쪽 npz가 남지 않아야 한다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features())
    assert list(store.vectors_dir.glob("*.tmp")) == []


def test_summary_is_per_run(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    path = store.write_summary({"processed": 3, "failed": 0})
    assert json.loads(path.read_text(encoding="utf-8"))["processed"] == 3


# ---------------------------------------------------------------- O-7 정리·잠금


def test_compact_keeps_last_record_per_key(tmp_path: Path) -> None:
    """npz는 덮어써졌으므로 파일과 짝이 맞는 것은 나중 기록이다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3", chunks=3))
    store.write_track(make_features("a.mp3", chunks=9))

    report = store.compact_index()

    records = store.read_records()
    assert [record["source_key"] for record in records] == ["a.mp3"]
    assert records[0]["chunk_count"] == 9
    assert report.total_lines == 2
    assert report.duplicates_removed == 1
    assert report.kept == 1


def test_compact_sorts_by_source_key(tmp_path: Path) -> None:
    """D-0009. 중단·재개 지점에 따라 순서가 달라지면 기기 간 비교가 불가능하다."""
    store = NpzFeatureStore(tmp_path)
    for key in ("c.mp3", "a.mp3", "b.mp3"):
        store.write_track(make_features(key))

    store.compact_index()

    assert [record["source_key"] for record in store.read_records()] == [
        "a.mp3",
        "b.mp3",
        "c.mp3",
    ]


def test_compact_drops_records_without_vector(tmp_path: Path) -> None:
    """npz가 없는데 완료로 남으면 재개가 그 곡을 영영 건너뛴다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    target = store.write_track(make_features("b.mp3"))
    target.unlink()

    report = store.compact_index()

    assert store.completed_keys() == {"a.mp3"}
    assert report.missing_vectors_dropped == 1


def test_compact_keeps_missing_when_asked(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3")).unlink()

    report = store.compact_index(drop_missing=False)

    assert store.completed_keys() == {"a.mp3"}
    assert report.missing_vectors_dropped == 0


def test_compact_drops_malformed_lines(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    with store.index_path.open("a", encoding="utf-8") as stream:
        stream.write("{잘린 줄\n")

    report = store.compact_index()

    assert report.malformed_dropped == 1
    assert store.completed_keys() == {"a.mp3"}


def test_compact_is_idempotent(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    store.write_track(make_features("a.mp3"))

    store.compact_index()
    first = store.index_path.read_bytes()
    second_report = store.compact_index()

    assert store.index_path.read_bytes() == first
    assert second_report.changed is False


def test_compact_backs_up_original(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    store.write_track(make_features("a.mp3"))
    original = store.index_path.read_bytes()

    store.compact_index()

    backup = store.index_path.with_suffix(store.index_path.suffix + ".bak")
    assert backup.read_bytes() == original


def test_compact_on_missing_index_is_noop(tmp_path: Path) -> None:
    report = NpzFeatureStore(tmp_path).compact_index()
    assert report.total_lines == 0
    assert report.changed is False


def test_batch_lock_blocks_second_holder(tmp_path: Path) -> None:
    """O-7. 두 배치가 겹쳐 돌면 인덱스에 중복이 쌓인다."""
    store = NpzFeatureStore(tmp_path)
    with store.batch_lock():
        other = NpzFeatureStore(tmp_path)
        with pytest.raises(BatchAlreadyRunningError), other.batch_lock():
            pass


def test_batch_lock_releases_on_exit(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    with store.batch_lock():
        pass
    with store.batch_lock():
        pass


def test_batch_lock_releases_on_exception(tmp_path: Path) -> None:
    """절전·발열로 죽어도 잠금이 남으면 안 된다. flock을 쓰는 이유다."""
    store = NpzFeatureStore(tmp_path)
    with contextlib.suppress(RuntimeError), store.batch_lock():
        raise RuntimeError("배치 중단")
    with store.batch_lock():
        pass


def test_batch_lock_records_holder(tmp_path: Path) -> None:
    store = NpzFeatureStore(tmp_path)
    with store.batch_lock():
        assert f"pid={os.getpid()}" in store.batch_lock_path.read_text(encoding="utf-8")


def test_compact_rerun_preserves_original_backup(tmp_path: Path) -> None:
    """두 번째 실행이 백업을 정리본으로 덮어쓰면 원본을 잃는다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    store.write_track(make_features("a.mp3"))
    original = store.index_path.read_bytes()

    store.compact_index()
    store.compact_index()

    backup = store.index_path.with_suffix(store.index_path.suffix + ".bak")
    assert backup.read_bytes() == original


def test_compact_leaves_sorted_index_untouched(tmp_path: Path) -> None:
    """이미 정리된 인덱스는 백업조차 만들지 않는다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("a.mp3"))
    before = store.index_path.read_bytes()

    report = store.compact_index()

    assert report.changed is False
    assert store.index_path.read_bytes() == before
    assert not (store.index_path.with_suffix(store.index_path.suffix + ".bak")).exists()


def test_read_vectors_roundtrip(tmp_path):
    """평가 하네스가 읽는 경로다. 저장한 배열이 그대로 돌아와야 한다."""
    store = NpzFeatureStore(tmp_path)
    features = make_features("가수/노래.mp3", chunks=4)
    store.write_track(features)

    vectors = store.read_vectors(vector_filename(features.source_key))
    assert set(vectors) == {MIXTURE_KEY, *STEM_NAMES}
    assert vectors[MIXTURE_KEY].shape == (4, 768)
    assert vectors[MIXTURE_KEY].dtype == np.float32
    assert np.array_equal(vectors[MIXTURE_KEY], features.mixture)


def test_iter_vectors_follows_index_order(tmp_path):
    store = NpzFeatureStore(tmp_path)
    for name in ("나.mp3", "가.mp3"):
        store.write_track(make_features(name, chunks=2))
    assert [key for key, _ in store.iter_vectors()] == ["나.mp3", "가.mp3"]


def test_iter_vectors_exposes_duplicates(tmp_path):
    """중복을 조용히 감추지 않는다. O-7이 지표 단계에서야 드러나면 늦는다."""
    store = NpzFeatureStore(tmp_path)
    store.write_track(make_features("가.mp3", chunks=2))
    store.write_track(make_features("가.mp3", chunks=2))
    assert len(list(store.iter_vectors())) == 2


def test_iter_vectors_on_empty_store(tmp_path):
    assert list(NpzFeatureStore(tmp_path).iter_vectors()) == []
