"""특징 저장소 테스트 (유닛 #4).

벡터는 npz, 메타는 JSONL이다. GPU도 실제 음원도 쓰지 않는다.
"""

import json
from pathlib import Path

import numpy as np

from hathor.application.extract_features import TrackFeatures
from hathor.infrastructure.npz_feature_store import (
    MIXTURE_KEY,
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
