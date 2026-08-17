"""퓨전 결합 규칙과 M4 지표 테스트."""

import numpy as np
import pytest

from hathor.application.evaluate_fusion import EvaluateFusion
from hathor.application.search_similar import SearchSimilar, SearchTrack
from hathor.domain.services.seed_search import FusionMode, fuse_scores
from hathor.interfaces.cli.main import main
from tests.unit.test_search_similar import build_library

DIM = 8


def similarities(*rows: list[float]) -> np.ndarray:
    return np.asarray(rows, dtype=np.float32)


def test_mean_prefers_one_sided_candidate():
    """MEAN이 편중을 만드는 기제를 고정한다. 실측에서 관측된 원인이다."""
    # 후보 0: 시드A와 0.9, 시드B와 0.0 / 후보 1: 양쪽과 0.42
    matrix = similarities([0.9, 0.42], [0.0, 0.42])
    scores = fuse_scores(matrix, FusionMode.MEAN)
    assert scores[0] > scores[1]


def test_min_prefers_balanced_candidate():
    matrix = similarities([0.9, 0.42], [0.0, 0.42])
    scores = fuse_scores(matrix, FusionMode.MIN)
    assert scores[1] > scores[0]


def test_penalized_sits_between():
    matrix = similarities([0.9, 0.42], [0.0, 0.42])
    penalized = fuse_scores(matrix, FusionMode.PENALIZED)
    assert penalized[1] > penalized[0]


def test_penalized_with_zero_penalty_equals_mean():
    matrix = similarities([0.9, 0.42, 0.1], [0.0, 0.42, 0.7])
    assert np.allclose(
        fuse_scores(matrix, FusionMode.PENALIZED, penalty=0.0),
        fuse_scores(matrix, FusionMode.MEAN),
    )


def test_single_seed_modes_agree():
    """시드가 하나면 결합 규칙이 결과를 바꾸지 않아야 한다."""
    matrix = similarities([0.9, 0.1, 0.5])
    base = fuse_scores(matrix, FusionMode.MEAN)
    for mode in FusionMode:
        assert np.allclose(fuse_scores(matrix, mode), base)


def test_fuse_scores_handles_negative_similarity():
    """중심화 후에는 코사인이 음수일 수 있다."""
    matrix = similarities([-0.3, 0.2], [0.4, 0.2])
    assert np.isfinite(fuse_scores(matrix, FusionMode.MIN)).all()


def test_fuse_scores_rejects_empty():
    with pytest.raises(ValueError):
        fuse_scores(np.zeros((0, 3), dtype=np.float32), FusionMode.MEAN)


def make_track(key: str, artist: str, direction: np.ndarray) -> SearchTrack:
    chunks = np.tile(direction, (4, 1)).astype(np.float32)
    return SearchTrack(source_key=key, artist=artist, title=key, embeddings={"layer00": chunks})


def lopsided_corpus() -> list[SearchTrack]:
    """가수A 곡이 많고 가수B 곡이 적은, 편중이 재현되는 코퍼스."""
    axes = np.eye(DIM, dtype=np.float32)
    tracks = [make_track(f"a{i}.mp3", "가수A", axes[0] + 0.01 * i) for i in range(6)]
    tracks += [make_track(f"b{i}.mp3", "가수B", axes[1] + 0.01 * i) for i in range(2)]
    tracks += [make_track("mid.mp3", "가수C", (axes[0] + axes[1]) / 2)]
    return tracks


def test_min_reduces_one_sided_results():
    corpus = lopsided_corpus()
    mean_hits = SearchSimilar(centered=False, fusion=FusionMode.MEAN).run(
        corpus, ["a0.mp3", "b0.mp3"], k=3
    )
    min_hits = SearchSimilar(centered=False, fusion=FusionMode.MIN).run(
        corpus, ["a0.mp3", "b0.mp3"], k=3
    )
    mean_a = sum(1 for hit in mean_hits if hit.source_key.startswith("a"))
    min_a = sum(1 for hit in min_hits if hit.source_key.startswith("a"))
    assert min_a <= mean_a
    assert min_hits[0].source_key == "mid.mp3"


def test_hits_expose_per_seed_similarity():
    """쏠림을 눈으로 확인할 수 있어야 한다."""
    hits = SearchSimilar(centered=False).run(lopsided_corpus(), ["a0.mp3", "b0.mp3"], k=2)
    assert all(len(hit.per_seed) == 2 for hit in hits)


def test_single_seed_has_one_per_seed_value():
    hits = SearchSimilar(centered=False).run(lopsided_corpus(), ["a0.mp3"], k=2)
    assert all(len(hit.per_seed) == 1 for hit in hits)


def test_fusion_report_covers_all_modes():
    report = EvaluateFusion(centered=False, k=3, pairs=20).run(lopsided_corpus(), list(FusionMode))
    assert [score.mode for score in report.scores] == [mode.value for mode in FusionMode]
    assert all(score.pairs > 0 for score in report.scores)


def test_fusion_report_uses_same_pairs_for_every_mode():
    """모드마다 다른 쌍을 쓰면 규칙 차이인지 쌍 차이인지 구분되지 않는다."""
    report = EvaluateFusion(centered=False, k=3, pairs=20).run(lopsided_corpus(), list(FusionMode))
    assert len({score.pairs for score in report.scores}) == 1


def test_min_lowers_cosine_imbalance():
    report = EvaluateFusion(centered=False, k=3, pairs=30).run(
        lopsided_corpus(), [FusionMode.MEAN, FusionMode.MIN]
    )
    mean_score, min_score = report.scores
    assert min_score.cosine_imbalance <= mean_score.cosine_imbalance


def test_fusion_report_is_json_serializable():
    import json

    report = EvaluateFusion(centered=False, k=3, pairs=10).run(lopsided_corpus(), [FusionMode.MEAN])
    payload = json.loads(json.dumps(report.as_record(), ensure_ascii=False))
    assert payload["modes"][0]["mode"] == "mean"


def test_fusion_rejects_tiny_corpus():
    with pytest.raises(ValueError):
        EvaluateFusion().run(lopsided_corpus()[:2], [FusionMode.MEAN])


def test_fusion_rejects_single_artist_corpus():
    axes = np.eye(DIM, dtype=np.float32)
    same = [make_track(f"{i}.mp3", "가수A", axes[i % DIM]) for i in range(5)]
    with pytest.raises(ValueError):
        EvaluateFusion(centered=False, pairs=5).run(same, [FusionMode.MEAN])


def test_cli_eval_fusion_runs(tmp_path, capsys):
    build_library(tmp_path)
    assert main(["eval", "fusion", "--out", str(tmp_path), "-k", "2", "--pairs", "10"]) == 0
    output = capsys.readouterr().out
    assert "mean" in output
    assert "min" in output
    assert "리포트" in output


def test_cli_search_accepts_fusion_mode(tmp_path, capsys):
    build_library(tmp_path)
    code = main(
        [
            "search",
            "--out",
            str(tmp_path),
            "--like",
            "곡A",
            "--like",
            "곡B",
            "--fusion",
            "min",
            "-k",
            "1",
        ]
    )
    assert code == 0
    assert "결합 min" in capsys.readouterr().out
