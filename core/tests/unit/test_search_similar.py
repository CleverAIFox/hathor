"""시드 퓨전 검색 테스트."""

import numpy as np
import pytest

from hathor.application.extract_features import TrackFeatures
from hathor.application.search_similar import SearchSimilar, SearchTrack
from hathor.domain.services.seed_search import chunk_timestamp, fuse, representative_chunk
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.main import main
from tests.unit.test_eval_cli import write_scan

DIM = 6


def vector(*values: float) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def test_fuse_normalizes_before_averaging():
    """노름이 큰 곡이 조합을 지배하면 퓨전이 아니라 그 곡 하나가 된다."""
    loud = vector(100.0, 0.0)
    quiet = vector(0.0, 0.01)
    fused = fuse([loud, quiet])
    assert fused[0] == pytest.approx(fused[1], abs=1e-6)


def test_fuse_single_seed_is_unit_vector():
    fused = fuse([vector(3.0, 4.0)])
    assert np.linalg.norm(fused) == pytest.approx(1.0)


def test_fuse_rejects_empty():
    with pytest.raises(ValueError):
        fuse([])


def test_fuse_rejects_mismatched_dimensions():
    with pytest.raises(ValueError):
        fuse([vector(1.0, 0.0), vector(1.0, 0.0, 0.0)])


def test_representative_chunk_picks_repeated_section():
    """반복되는 구간이 다른 청크들과 평균 유사도가 가장 높다."""
    repeated = np.asarray([1.0, 0.0], dtype=np.float32)
    embedding = np.asarray([[0.0, 1.0], repeated, [0.0, 1.0], repeated, repeated], dtype=np.float32)
    assert representative_chunk(embedding) in {1, 3, 4}


def test_representative_chunk_single_chunk():
    assert representative_chunk(np.ones((1, 4), dtype=np.float32)) == 0


def test_representative_chunk_rejects_empty():
    with pytest.raises(ValueError):
        representative_chunk(np.zeros((0, 4), dtype=np.float32))


def test_chunk_timestamp_formats_minutes():
    assert chunk_timestamp(0) == "0:00"
    assert chunk_timestamp(7) == "1:10"


def make_track(key: str, artist: str, title: str, direction: np.ndarray) -> SearchTrack:
    chunks = np.tile(direction, (4, 1)).astype(np.float32)
    return SearchTrack(source_key=key, artist=artist, title=title, embeddings={"layer00": chunks})


def corpus() -> list[SearchTrack]:
    axes = np.eye(DIM, dtype=np.float32)
    tracks = [
        make_track("a.mp3", "가수A", "곡A", axes[0]),
        make_track("b.mp3", "가수B", "곡B", axes[1]),
        make_track("mid.mp3", "가수C", "중간곡", (axes[0] + axes[1]) / 2),
        make_track("far.mp3", "가수D", "먼곡", axes[2]),
    ]
    return tracks


def test_fusion_finds_the_midpoint_track():
    """A와 B를 퓨전하면 둘 사이에 있는 곡이 1위여야 한다."""
    hits = SearchSimilar().run(corpus(), ["a.mp3", "b.mp3"], k=2)
    assert hits[0].source_key == "mid.mp3"


def test_seeds_are_excluded_from_results():
    hits = SearchSimilar().run(corpus(), ["a.mp3"], k=3)
    assert all(hit.source_key != "a.mp3" for hit in hits)


def test_results_are_ranked_by_similarity():
    hits = SearchSimilar().run(corpus(), ["a.mp3"], k=3)
    assert [hit.rank for hit in hits] == [1, 2, 3]
    assert hits[0].similarity >= hits[-1].similarity


def test_run_rejects_unknown_seed():
    with pytest.raises(KeyError):
        SearchSimilar().run(corpus(), ["없음.mp3"], k=3)


def test_run_rejects_zero_k():
    with pytest.raises(ValueError):
        SearchSimilar().run(corpus(), ["a.mp3"], k=0)


def test_run_rejects_no_seed():
    with pytest.raises(ValueError):
        SearchSimilar().run(corpus(), [], k=3)


def build_library(tmp_path):
    store = NpzFeatureStore(tmp_path / "mert-layers")
    axes = np.eye(DIM, dtype=np.float32)
    entries = [
        ("가수A/곡A.mp3", "가수A", "첫 번째 곡", axes[0]),
        ("가수B/곡B.mp3", "가수B", "두 번째 곡", axes[1]),
        ("가수C/중간.mp3", "가수C", "중간 곡", (axes[0] + axes[1]) / 2),
        ("가수D/먼곡.mp3", "가수D", "먼 곡", axes[2]),
    ]
    for key, _, _, direction in entries:
        chunks = np.tile(direction, (4, 1)).astype(np.float32)
        store.write_track(TrackFeatures(source_key=key, mixture=chunks, stems={"layer00": chunks}))
    write_scan(tmp_path, [(key, artist, "앨범") for key, artist, _, _ in entries])
    # write_scan은 제목을 source_key로 넣으므로 검색어는 경로 기준으로 맞춘다.
    return entries


def test_cli_search_runs(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["search", "--out", str(tmp_path), "--like", "곡A", "-k", "2"]) == 0
    output = capsys.readouterr().out
    assert "시드" in output
    assert "반복" in output


def test_cli_search_fusion_of_two_seeds(tmp_path, capsys):
    build_library(tmp_path)
    code = main(["search", "--out", str(tmp_path), "--like", "곡A", "--like", "곡B", "-k", "1"])
    assert code == 0
    assert "중간" in capsys.readouterr().out


def test_cli_search_reports_ambiguous_query(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["search", "--out", str(tmp_path), "--like", "곡"]) == 2
    assert "걸린다" in capsys.readouterr().err


def test_cli_search_reports_missing_query(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["search", "--out", str(tmp_path), "--like", "없는곡"]) == 2
    assert "맞는 곡이 없다" in capsys.readouterr().err


def test_cli_search_rejects_duplicate_seed(tmp_path, capsys):
    build_library(tmp_path)
    code = main(["search", "--out", str(tmp_path), "--like", "곡A", "--like", "곡A"])
    assert code == 2
    assert "두 번" in capsys.readouterr().err


def test_cli_search_requires_seed(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["search", "--out", str(tmp_path)]) == 2
    assert "최소 하나" in capsys.readouterr().err


def test_cli_search_without_scan_output(tmp_path):
    assert main(["search", "--out", str(tmp_path), "--like", "가"]) == 2


def test_cli_search_without_features(tmp_path):
    write_scan(tmp_path, [("가.mp3", "가수", "앨범")])
    assert main(["search", "--out", str(tmp_path), "--like", "가"]) == 2


def test_search_centering_is_on_by_default():
    """허브 곡이 어떤 질의에도 상위에 오는 것을 기본으로 막는다."""
    assert SearchSimilar()._centered is True


def test_raw_flag_disables_centering(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["search", "--out", str(tmp_path), "--like", "곡A", "--raw", "-k", "2"]) == 0
    assert "원본" in capsys.readouterr().out


def test_centering_changes_ranking_when_a_hub_exists():
    """중심 근처에 곡이 몰려 있으면 중심화 전후 순위가 달라져야 한다."""
    generator = np.random.default_rng(5)
    shared = np.zeros(DIM, dtype=np.float32)
    shared[0] = 1.0
    tracks = []
    for index in range(30):
        direction = shared + generator.normal(0.0, 0.15, size=DIM).astype(np.float32)
        tracks.append(make_track(f"{index}.mp3", f"가수{index}", f"곡{index}", direction))

    plain = SearchSimilar(centered=False).run(tracks, ["0.mp3"], k=5)
    centered = SearchSimilar(centered=True).run(tracks, ["0.mp3"], k=5)
    assert [hit.source_key for hit in plain] != [hit.source_key for hit in centered]
