"""평가 하네스 테스트.

합성 임베딩으로 코퍼스를 만든다. 앨범마다 다른 중심을 주고 잡음을 얹으면
지표가 이론값에 가까워야 한다. 실제 npz도 GPU도 쓰지 않는다.
"""

import numpy as np
import pytest

from hathor.application.evaluate_retrieval import (
    EvaluateRetrieval,
    EvaluationConfig,
    SplitMode,
    SplitSpec,
    TrackRecord,
    ViewSpec,
    label_key,
)
from hathor.domain.services.embedding_pooling import (
    CombineMode,
    PoolMode,
    build_view,
    split_odd_even,
)
from hathor.domain.services.isotropy import center, mean_direction
from hathor.domain.services.retrieval_metrics import cosine_similarity, top1_accuracy

DIM = 16
CHUNKS = 6


def make_track(
    index: int,
    album: str | None,
    artist: str | None,
    *,
    center: np.ndarray,
    noise: float = 0.05,
    chunks: int = CHUNKS,
    keys: tuple[str, ...] = ("mixture", "vocals"),
) -> TrackRecord:
    generator = np.random.default_rng(1000 + index)
    embeddings = {}
    for offset, key in enumerate(keys):
        jitter = generator.normal(0.0, noise, size=(chunks, DIM))
        embeddings[key] = np.asarray(center + offset * 0.01 + jitter, dtype=np.float32)
    return TrackRecord(
        source_key=f"{artist}/{album}/{index:03d}.mp3",
        album=album,
        artist=artist,
        embeddings=embeddings,
    )


def build_corpus(albums: int = 6, per_album: int = 4, noise: float = 0.02) -> list[TrackRecord]:
    """앨범마다 뚜렷이 다른 중심을 주고, 곡마다 작은 고유 편차를 준다.

    곡 고유 편차가 없으면 같은 앨범 곡이 서로 구별되지 않아 M0가 무너진다.
    실제 코퍼스에서도 곡 정체성 > 앨범 근접성이므로 이 순서를 맞춘다.
    """
    generator = np.random.default_rng(7)
    tracks: list[TrackRecord] = []
    index = 0
    for album_index in range(albums):
        center = generator.normal(0.0, 1.0, size=(1, DIM))
        artist = f"아티스트{album_index // 2}"
        for _ in range(per_album):
            identity = generator.normal(0.0, 0.35, size=(1, DIM))
            tracks.append(
                make_track(
                    index,
                    album=f"앨범{album_index}",
                    artist=artist,
                    center=center + identity,
                    noise=noise,
                )
            )
            index += 1
    return tracks


def test_label_key_normalizes_case_and_space():
    assert label_key("  IU ") == label_key("iu")


def test_label_key_treats_empty_as_missing():
    assert label_key("   ") is None
    assert label_key(None) is None


def test_self_consistency_is_perfect_on_separable_corpus():
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(
        build_corpus()
    )
    assert report.self_consistency == 1.0
    assert report.gate_passed


def test_album_retrieval_beats_random_by_far():
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=3)).run(
        build_corpus()
    )
    album = next(metric for metric in report.metrics if metric.name == "m1_album")
    assert album.measured.map_at_k == pytest.approx(1.0)
    assert album.precision_lift > 3.0


def test_random_baseline_matches_analytic_prevalence():
    """경험적 무작위와 해석적 기대값이 크게 어긋나면 마스크 구성이 틀린 것이다."""
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=5)).run(
        build_corpus(albums=8, per_album=5)
    )
    album = next(metric for metric in report.metrics if metric.name == "m1_album")
    assert album.random.precision_at_k == pytest.approx(album.expected_random_precision, abs=0.06)


def test_artist_metric_excludes_same_album_candidates():
    """같은 앨범을 빼지 않으면 앨범 효과가 아티스트 점수로 새어든다.

    앨범 안은 뭉치고 같은 아티스트의 다른 앨범은 멀도록 코퍼스를 만든다.
    같은 앨범이 후보에 남으면 M2가 높게 나오므로, 낮게 나와야 정상이다.
    """
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=3)).run(
        build_corpus()
    )
    artist = next(metric for metric in report.metrics if metric.name == "m2_artist")
    album = next(metric for metric in report.metrics if metric.name == "m1_album")
    assert artist.measured.map_at_k < album.measured.map_at_k


def test_gate_blocks_labeled_metrics():
    """M0가 무너지면 M1/M2를 아예 내지 않는다."""
    generator = np.random.default_rng(3)
    tracks = [
        TrackRecord(
            source_key=f"{index}.mp3",
            album="같은앨범",
            artist="같은아티스트",
            embeddings={
                "mixture": np.asarray(generator.normal(size=(CHUNKS, DIM)), dtype=np.float32)
            },
        )
        for index in range(12)
    ]
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(tracks)
    assert not report.gate_passed
    assert report.metrics == ()


def test_force_computes_metrics_despite_gate():
    generator = np.random.default_rng(3)
    tracks = [
        TrackRecord(
            source_key=f"{index}.mp3",
            album=f"앨범{index % 3}",
            artist="같은아티스트",
            embeddings={
                "mixture": np.asarray(generator.normal(size=(CHUNKS, DIM)), dtype=np.float32)
            },
        )
        for index in range(12)
    ]
    config = EvaluationConfig(view=ViewSpec(keys=("mixture",)), force=True, k=3)
    report = EvaluateRetrieval(config).run(tracks)
    assert not report.gate_passed
    assert len(report.metrics) == 2


def test_short_tracks_are_skipped_with_reason():
    corpus = build_corpus(albums=3, per_album=3)
    center = np.zeros((1, DIM))
    corpus.append(make_track(999, "앨범0", "아티스트0", center=center, chunks=1))
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(corpus)
    assert report.tracks == 9
    assert len(report.skipped) == 1
    assert "청크" in report.skipped[0][1]


def test_missing_key_is_skipped():
    corpus = build_corpus(albums=3, per_album=3)
    corpus.append(
        make_track(998, "앨범0", "아티스트0", center=np.zeros((1, DIM)), keys=("mixture",))
    )
    config = EvaluationConfig(view=ViewSpec(keys=("mixture", "vocals")))
    report = EvaluateRetrieval(config).run(corpus)
    assert len(report.skipped) == 1
    assert "임베딩 키 없음" in report.skipped[0][1]


def test_concat_view_doubles_dimension():
    config = EvaluationConfig(view=ViewSpec(keys=("mixture", "vocals")))
    report = EvaluateRetrieval(config).run(build_corpus(albums=3, per_album=3))
    assert report.dimension == DIM * 2


def test_mean_std_pool_doubles_dimension():
    config = EvaluationConfig(view=ViewSpec(keys=("mixture",), pool=PoolMode.MEAN_STD))
    report = EvaluateRetrieval(config).run(build_corpus(albums=3, per_album=3))
    assert report.dimension == DIM * 2


def test_average_combine_keeps_dimension():
    config = EvaluationConfig(
        view=ViewSpec(keys=("mixture", "vocals"), combine=CombineMode.AVERAGE)
    )
    report = EvaluateRetrieval(config).run(build_corpus(albums=3, per_album=3))
    assert report.dimension == DIM


def test_singleton_labels_are_not_queried():
    """단일 곡 앨범은 정답이 존재하지 않으므로 쿼리에서 빠진다."""
    corpus = build_corpus(albums=3, per_album=3)
    corpus.append(make_track(997, "혼자앨범", "혼자아티스트", center=np.ones((1, DIM)) * 5.0))
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=3)).run(corpus)
    album = next(metric for metric in report.metrics if metric.name == "m1_album")
    assert album.measured.queries == 9


def test_missing_labels_do_not_match_each_other():
    """라벨 없는 곡끼리 서로 정답이 되면 안 된다. 그 순간 지표가 부풀려진다."""
    corpus = build_corpus(albums=3, per_album=3)
    for index in range(2):
        corpus.append(
            make_track(
                900 + index,
                album=None,
                artist=None,
                center=np.eye(1, DIM, k=index) * 5.0,
            )
        )
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=3)).run(corpus)
    album = next(metric for metric in report.metrics if metric.name == "m1_album")
    assert report.tracks == 11
    assert album.measured.queries == 9


def test_report_record_is_json_serializable():
    import json

    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(
        build_corpus(albums=3, per_album=3)
    )
    payload = json.loads(json.dumps(report.as_record(), ensure_ascii=False))
    assert payload["m0_self_consistency"]["passed"] is True
    assert payload["config"]["view"]["keys"] == ["mixture"]
    assert len(payload["metrics"]) == 2


def test_run_rejects_empty_corpus():
    with pytest.raises(ValueError):
        EvaluateRetrieval().run([])


def test_same_config_gives_same_numbers():
    """무작위 베이스라인까지 포함해 재실행 결과가 같아야 한다 (D-0009 계층 1)."""
    corpus = build_corpus(albums=4, per_album=4)
    config = EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=3)
    first = EvaluateRetrieval(config).run(corpus).as_record()
    second = EvaluateRetrieval(config).run(corpus).as_record()
    assert first == second


def test_report_includes_anisotropy():
    """공간이 얼마나 뭉쳐 있는지가 리포트에 남아야 나중에 비교된다."""
    report = EvaluateRetrieval(
        EvaluationConfig(view=ViewSpec(keys=("mixture",), centered=False))
    ).run(build_corpus(albums=4, per_album=4))
    assert 0.0 <= report.anisotropy <= 1.0
    assert report.as_record()["corpus"]["anisotropy"] == pytest.approx(report.anisotropy, abs=1e-5)


def test_centering_lowers_anisotropy():
    corpus = build_corpus(albums=4, per_album=4)
    plain = EvaluateRetrieval(
        EvaluationConfig(view=ViewSpec(keys=("mixture",), centered=False))
    ).run(corpus)
    centered = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(corpus)
    assert centered.anisotropy < plain.anisotropy
    assert centered.as_record()["config"]["view"]["centered"] is True


def test_centering_keeps_self_consistency_measurable():
    """홀·짝에 같은 중심을 써야 M0가 좌표계 차이를 재지 않는다."""
    report = EvaluateRetrieval(
        EvaluationConfig(view=ViewSpec(keys=("mixture",), centered=True))
    ).run(build_corpus(albums=4, per_album=4))
    assert report.self_consistency == 1.0


def test_centering_is_on_by_default():
    """전 지표가 개선됐으므로 켠 쪽이 기본이다 (D-0031)."""
    assert ViewSpec().centered is True
    assert EvaluationConfig().as_record()["view"]["centered"] is True  # type: ignore[index]


# --- O-12: 분할 규칙 (D-0040) ---


def test_split_defaults_to_odd_even():
    """기본값이 바뀌면 오디오축 정본 수치가 통째로 무효가 된다."""
    config = EvaluationConfig()
    assert config.split.mode is SplitMode.ODD_EVEN
    assert config.split.repeats == 1


def test_odd_even_reproduces_legacy_self_consistency():
    """분할 축 도입 전 계산과 **정확히** 같은 값이 나와야 한다.

    D-0031~D-0038의 M0 수치가 전부 이 경로에서 나왔다. 여기가 조금이라도
    움직이면 과거 리포트와 새 리포트를 나란히 놓을 수 없고, 그 사실은
    수치가 비슷해 보이는 한 눈에 띄지 않는다.
    """
    tracks = build_corpus()
    keys = ("mixture", "vocals")
    view = ViewSpec(keys=keys)

    odd, even = [], []
    for track in tracks:
        halves = {key: split_odd_even(track.embeddings[key]) for key in keys}
        odd.append(build_view({k: v[0] for k, v in halves.items()}, keys))
        even.append(build_view({k: v[1] for k, v in halves.items()}, keys))
    left = np.asarray(odd, dtype=np.float32)
    right = np.asarray(even, dtype=np.float32)
    direction = mean_direction(np.concatenate([left, right]))
    expected = top1_accuracy(cosine_similarity(center(left, direction), center(right, direction)))

    report = EvaluateRetrieval(EvaluationConfig(view=view)).run(tracks)
    assert report.self_consistency == expected


def test_odd_even_rejects_repeats():
    """결정적 분할을 반복하면 표준편차 0이 나와 '안정적'으로 오독된다."""
    with pytest.raises(ValueError):
        SplitSpec(mode=SplitMode.ODD_EVEN, repeats=5)


def test_random_split_is_reproducible():
    tracks = build_corpus()
    config = EvaluationConfig(split=SplitSpec(mode=SplitMode.RANDOM, repeats=3, seed=99))
    first = EvaluateRetrieval(config).run(tracks)
    second = EvaluateRetrieval(config).run(tracks)
    assert first.consistency.as_record() == second.consistency.as_record()


def test_random_split_is_stable_under_track_order():
    """곡 순서가 바뀌어도 같은 곡은 같은 분할을 받는다.

    생성기 하나를 순회하는 방식이면 `--limit`이나 정렬 변경만으로 M0가
    움직인다. 그러면 조건 비교가 아니라 순서 비교가 된다.
    """
    tracks = build_corpus()
    config = EvaluationConfig(split=SplitSpec(mode=SplitMode.RANDOM, repeats=2, seed=5))
    baseline = EvaluateRetrieval(config).run(tracks)
    shortened = EvaluateRetrieval(config).run(tracks[:12])
    assert baseline.consistency.scores[0].queries == len(tracks)
    assert shortened.consistency.scores[0].queries == 12


def test_repeats_expose_spread():
    tracks = build_corpus()
    config = EvaluationConfig(split=SplitSpec(mode=SplitMode.RANDOM, repeats=4))
    report = EvaluateRetrieval(config).run(tracks)
    assert len(report.consistency.scores) == 4
    assert report.consistency.top1_std >= 0.0
    assert "repeats" in report.as_record()["m0_self_consistency"]


def test_single_repeat_omits_repeat_list():
    """반복이 하나면 분포가 없다. 빈 목록을 남기면 있는 것처럼 보인다."""
    report = EvaluateRetrieval(EvaluationConfig()).run(build_corpus())
    assert "repeats" not in report.as_record()["m0_self_consistency"]


def test_report_includes_rank_diagnostics():
    report = EvaluateRetrieval(EvaluationConfig()).run(build_corpus())
    record = report.as_record()["m0_self_consistency"]
    assert record["mrr"] >= record["top1_accuracy"]
    assert record["recall_at_10"] >= record["top1_accuracy"]
    assert record["split"]["mode"] == "odd-even"


def test_gate_reads_mean_of_repeats():
    tracks = build_corpus()
    config = EvaluationConfig(split=SplitSpec(mode=SplitMode.RANDOM, repeats=3), gate=1.01)
    report = EvaluateRetrieval(config).run(tracks)
    assert not report.gate_passed
    assert report.metrics == ()


def test_m0_reports_analytic_baseline():
    """M0에도 베이스라인이 있어야 한다. top-1 0.90은 후보 수 없이 의미가 없다."""
    report = EvaluateRetrieval(EvaluationConfig()).run(build_corpus())
    record = report.as_record()["m0_self_consistency"]
    assert record["random_top1"] == pytest.approx(1.0 / report.tracks)
    assert record["random_median_rank"] == pytest.approx((report.tracks + 1) / 2.0)


def _twinned_corpus(pairs: int = 8, singles: int = 40) -> list[TrackRecord]:
    """쌍둥이 곡을 심는다 — **top-1은 놓치고 2등에서 맞히는** 코퍼스다 (D-0234).

    실물에서 이 모양이 나왔다. CLAP은 청크 절반이 자기 나머지 반쪽 대신 «거의 같은 곡»을
    1등으로 집었고 정답은 5등쯤에 있었다. 무작위 잡음(붕괴)과 전혀 다른 상황이다.
    """
    generator = np.random.default_rng(17)
    tracks: list[TrackRecord] = []
    for index in range(singles):
        middle = generator.normal(0.0, 1.0, size=(1, DIM))
        tracks.append(make_track(index, f"앨범{index % 3}", "가수", center=middle))
    for index in range(pairs):
        middle = generator.normal(0.0, 1.0, size=(1, DIM))
        for twin in range(2):
            # 두 곡이 거의 같다. 잡음이 곡 사이 거리보다 크면 반쪽끼리 못 찾는다.
            tracks.append(
                make_track(
                    1000 + index * 2 + twin,
                    f"앨범{index % 3}",
                    "가수",
                    center=middle + generator.normal(0.0, 0.001, size=(1, DIM)),
                    noise=0.01,
                )
            )
    return tracks


def test_근접_실패는_계산하고_표식을_단다():
    """**D-0234의 강제자.** top-1 미달이라고 M1/M2를 안 내면 판정 자체를 못 한다."""
    config = EvaluationConfig(view=ViewSpec(keys=("mixture",)), k=10)
    report = EvaluateRetrieval(config).run(_twinned_corpus())

    assert not report.gate_passed, "쌍둥이가 top-1을 뺏어야 이 시험이 뜻이 있다"
    assert not report.collapsed, "정답이 상위권에 있으면 무너진 것이 아니다"
    assert len(report.metrics) == 2, "근접 실패에서도 지표를 낸다"
    assert not report.citable, "그러나 정본으로 인용하지 않는다"
    consistency = report.as_record()["m0_self_consistency"]
    assert isinstance(consistency, dict)
    assert consistency["citable"] is False, "자격은 산출물이 들고 다닌다"


def test_붕괴는_여전히_계산하지_않는다():
    """무작위 잡음은 정답이 수십·수백 등에 흩어진다. 그 M1/M2는 볼 값이 아니다."""
    generator = np.random.default_rng(3)
    tracks = [
        TrackRecord(
            source_key=f"{index}.mp3",
            album="같은앨범",
            artist="같은아티스트",
            embeddings={
                "mixture": np.asarray(generator.normal(size=(CHUNKS, DIM)), dtype=np.float32)
            },
        )
        for index in range(60)
    ]
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(tracks)
    assert report.collapsed
    assert report.metrics == ()
    assert not report.citable


def test_통과한_실행은_인용할_수_있다():
    corpus = build_corpus(albums=4, per_album=4)
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(corpus)
    assert report.citable
    consistency = report.as_record()["m0_self_consistency"]
    assert isinstance(consistency, dict)
    assert consistency["collapsed"] is False


def test_작은_코퍼스에서_잡음을_근접실패로_읽지_않는다():
    """**무작위 중앙값이 k 안이면 k로 하는 말이 무의미하다** (D-0234).

    곡 12개면 찍어도 6등이고 R@10도 저절로 높다. 두 조건 다 참이 되어 순수 잡음이
    «정답이 상위권»으로 분류된다.
    """
    generator = np.random.default_rng(3)
    tracks = [
        TrackRecord(
            source_key=f"{index}.mp3",
            album="같은앨범",
            artist="같은아티스트",
            embeddings={
                "mixture": np.asarray(generator.normal(size=(CHUNKS, DIM)), dtype=np.float32)
            },
        )
        for index in range(12)
    ]
    report = EvaluateRetrieval(EvaluationConfig(view=ViewSpec(keys=("mixture",)))).run(tracks)
    assert report.consistency.random_median_rank <= report.config.k, "이 시험의 전제"
    assert report.collapsed
