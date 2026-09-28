"""`eval retrieval` — M0/M1/M2와 무작위 베이스라인 (D-0260).

**`main.py`에 있었다.** §3의 빚 «`main.py`의 `eval` 보고»에서 가장 큰 덩이다.
보고를 찍는 헬퍼 셋(`_print_report` · `_gate_failure_message` · `_default_label`)이
이 명령 전용이므로 함께 온다.
"""

from __future__ import annotations

import argparse
import sys

from hathor.application.evaluate_retrieval import (
    DEFAULT_GATE,
    DEFAULT_K,
    DEFAULT_SEED,
    DEFAULT_SPLIT_SEED,
    EvaluateRetrieval,
    EvaluationConfig,
    EvaluationReport,
    SplitMode,
    SplitSpec,
    TrackRecord,
    ViewSpec,
)
from hathor.application.search_similar import SearchTrack
from hathor.domain.services.embedding_pooling import CombineMode, PoolMode
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.interfaces.cli.feature_sources import (
    namespaced,
    open_feature_source,
    parse_feature_stores,
    store_keys,
)
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import DEFAULT_FEATURE_DIRNAME, DEFAULT_OUTPUT_ROOT
from hathor.shared.config.paths import resolve_path


def _default_label(view: ViewSpec, split: SplitSpec | None = None) -> str:
    """뷰·분할 설정에서 실험 이름을 만든다. 산출 파일명이 조건을 말하게 한다.

    분할이 기본값(홀짝)이면 이름에 넣지 않는다. 넣으면 D-0038까지 쌓인 리포트
    파일명과 어긋나 같은 조건의 수치를 나란히 놓을 수 없다.
    """
    parts = ["+".join(view.keys), view.combine.value, view.pool.value]
    if view.chunk_l2:
        parts.append("chunkl2")
    if view.block_l2:
        parts.append("blockl2")
    if not view.centered:
        parts.append("raw")
    if split is not None and split.mode is not SplitMode.ODD_EVEN:
        parts.append(f"{split.mode.value}{split.ratio:g}x{split.repeats}")
    return "-".join(parts)


def run_eval_retrieval(args: argparse.Namespace) -> int:
    """M0/M1/M2를 재고 리포트를 남긴다.

    GPU도 외부 조회도 쓰지 않는다. 1004x768 행렬에 1004x1004 코사인이면
    CPU에서 수 초다. 광인사에서 도는 것이 요건이다.
    """
    from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore

    keys = tuple(token.strip() for token in args.keys.split(",") if token.strip())
    if not keys:
        print("--keys에 임베딩 키를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2

    view = ViewSpec(
        keys=keys,
        combine=CombineMode(args.combine),
        pool=PoolMode(args.pool),
        chunk_l2=args.chunk_l2,
        block_l2=args.block_l2,
        centered=not args.raw,
    )
    try:
        split = SplitSpec(
            mode=SplitMode(args.split),
            ratio=args.split_ratio,
            repeats=args.split_repeats,
            seed=args.split_seed,
        )
    except ValueError as error:
        print(f"분할 설정이 잘못됐다: {error}", file=sys.stderr)
        return 2

    label = args.label or _default_label(view, split)
    config = EvaluationConfig(
        view=view,
        split=split,
        k=args.k,
        seed=args.seed,
        gate=args.gate,
        force=args.force,
        label=label,
    )

    tags = {track.source_key: track.tags for track in JsonlScanStore(args.out).read_tracks()}
    if not tags:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    stores = parse_feature_stores(args.features, args.out / DEFAULT_FEATURE_DIRNAME)
    merged: dict[str, dict[str, object]] = {}
    coverage: dict[str, int] = {}
    for name, root in stores:
        store = open_feature_source(root, store_keys(name, keys))
        if not store.index_path.exists():
            print(f"특징 인덱스가 없다: {store.index_path}", file=sys.stderr)
            return 2
        seen: set[str] = set()
        for source_key, vectors in store.iter_vectors():
            if source_key in seen:
                # O-7(D-0022)의 재발이다. 중복을 조용히 흡수하면 유사도 행렬에 같은 곡이
                # 여러 번 들어가 지표가 틀어진 채로 그럴듯한 숫자를 낸다.
                print(f"인덱스에 중복 키가 있다: {source_key} ({root})", file=sys.stderr)
                print("먼저 `hathor ingest compact`로 정리한다.", file=sys.stderr)
                return 2
            seen.add(source_key)
            slot = merged.setdefault(source_key, {})
            for key, vector in vectors.items():
                slot[namespaced(name, key)] = vector
        coverage[name or str(root)] = len(seen)

    if len(stores) > 1:
        print(
            "저장소별 곡 수: " + ", ".join(f"{label} {count}" for label, count in coverage.items()),
            flush=True,
        )

    records: list[TrackRecord] = []
    orphans: list[str] = []
    partial: list[str] = []
    for source_key in sorted(merged):
        tag = tags.get(source_key)
        if tag is None:
            orphans.append(source_key)
            continue
        # 저장소가 여럿일 때 한쪽에만 있는 곡은 뺀다. 남기면 뷰 조립에서
        # 키가 없다고 터지거나, 유스케이스가 조용히 건너뛰어 저장소마다
        # 다른 곡 집합을 비교하게 된다.
        if any(key not in merged[source_key] for key in keys):
            partial.append(source_key)
            continue
        records.append(
            TrackRecord(
                source_key=source_key,
                album=tag.album,
                artist=tag.artist,
                embeddings=merged[source_key],  # type: ignore[arg-type]
            )
        )

    if orphans:
        print(f"경고: 스캔 산출물에 없는 곡 {len(orphans)}건을 제외했다", file=sys.stderr)
    if partial:
        print(f"경고: 일부 저장소에만 있는 곡 {len(partial)}건을 제외했다", file=sys.stderr)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        print("평가할 곡이 없다", file=sys.stderr)
        return 2

    report = EvaluateRetrieval(config).run(records)
    path = JsonEvaluationStore(args.out).write(report.as_record(), label)
    _print_report(report)
    print(f"리포트: {path}")

    if not report.gate_passed:
        print(_gate_failure_message(report), file=sys.stderr)
        return 1
    return 0


def _gate_failure_message(report: EvaluationReport) -> str:
    """게이트 미달의 성격을 순위 진단으로 갈라 말한다 (D-0044).

    옛 문구는 미달을 하나로 묶어 "임베딩이 곡 정체성조차 담지 못한 것"이라고
    단정했다. **실측이 이를 반증했다.** 가사 8192 조건은 top-1 0.9174로 미달이나
    R@10이 0.9715이고 실패 순위 중앙값이 3.8이다(무작위 502). 정답은 4등쯤에 있다.
    같은 문구가 damp 조건(R@10 0.4688, 실패 순위 831)에도 붙어 있었으므로,
    **처방이 정반대인 두 상황을 같은 말로 보고하고 있었다.**
    """
    consistency = report.consistency
    # **가르는 규칙은 유스케이스가 든다** (D-0234). 여기서 다시 계산하면 두 곳이
    # 갈라진다 — D-0046이 세운 판정을 `report.collapsed`가 그대로 옮겨 갖고 있다.
    if not report.collapsed:
        return (
            f"M0 식별 미달 (top-1 {report.self_consistency:.4f}). "
            f"다만 R@10 {consistency.recall_at_10:.4f}, 실패 순위 중앙값 "
            f"{consistency.miss_median_rank:.1f}(무작위 {consistency.random_median_rank:.1f})다. "
            "정답이 상위권에 있으므로 표현이 무너진 것이 아니라 top-1을 못 넘는 것이다. "
            "**M1/M2는 계산했고 비교용으로만 쓴다** — 정본 지표로 인용하지 않는다 (D-0234)."
        )
    return (
        f"M0 게이트 미달 (top-1 {report.self_consistency:.4f}, "
        f"R@10 {consistency.recall_at_10:.4f}). 실패 순위 중앙값 "
        f"{consistency.miss_median_rank:.1f}(무작위 {consistency.random_median_rank:.1f})로 "
        "정답이 상위권에도 없다. 표현이 곡을 특정하지 못한다. 추출 설정부터 다시 본다."
    )


def _print_report(report: EvaluationReport) -> None:
    view = report.config.view
    print(
        f"곡 {report.tracks}개 (제외 {len(report.skipped)}) / "
        f"뷰 {'+'.join(view.keys)} {view.combine.value}·{view.pool.value}"
        f"{'·chunk-l2' if view.chunk_l2 else ''}"
        f"{'·block-l2' if view.block_l2 else ''}"
        f"{'·centered' if view.centered else '·raw'} / {report.dimension}차원"
    )
    print(f"  전체 쌍 평균 코사인 {report.anisotropy:.4f} (1에 가까울수록 허브 곡이 생긴다)")
    verdict = "통과" if report.gate_passed else "미달"
    consistency = report.consistency
    split = consistency.split
    spread = f" ±{consistency.top1_std:.4f}" if len(consistency.scores) > 1 else ""
    detail = (
        f"{split.mode.value}"
        if split.mode is SplitMode.ODD_EVEN
        else f"{split.mode.value} {split.ratio:g} x{split.repeats}회"
    )
    print(
        f"  M0 자기일관성  top-1 {report.self_consistency:.4f}{spread} "
        f"(기준 {report.config.gate:.2f}) {verdict}  [분할 {detail}]"
    )
    # top-1만 보면 실패의 성격을 모른다. 실패가 순위 2~3에 몰려 있으면 표현이
    # 아니라 관문이 문제이고, 수백 등에 흩어져 있으면 표현이 없는 것이다.
    print(
        f"     MRR {consistency.mrr:.4f}  "
        f"R@5 {consistency.recall_at_5:.4f}  "
        f"R@10 {consistency.recall_at_10:.4f}  "
        f"실패 순위 중앙값 {consistency.miss_median_rank:.1f} "
        f"(무작위 {consistency.random_median_rank:.1f})"
    )
    for metric in report.metrics:
        print(
            f"  {metric.name:<10} P@{report.config.k} {metric.measured.precision_at_k:.4f}  "
            f"MAP@{report.config.k} {metric.measured.map_at_k:.4f}  "
            f"쿼리 {metric.measured.queries:>4}  "
            f"| 무작위 {metric.random.precision_at_k:.4f} "
            f"({metric.precision_lift:.1f}배)"
        )
    if not report.metrics:
        print("  M1/M2는 계산하지 않았다 (**붕괴 판정** · D-0234).")
    elif not report.citable:
        # 표를 옮겨 적는 사람이 이 줄을 같이 가져가게 **지표 바로 옆에** 둔다.
        print("  ↑ **식별 미달이라 비교용이다.** 정본 지표로 인용하지 않는다 (D-0234).")


def load_search_tracks(args: argparse.Namespace, keys: tuple[str, ...]) -> list[SearchTrack]:
    """스캔 태그와 임베딩을 합쳐 검색 대상을 만든다."""
    tags = {track.source_key: track.tags for track in JsonlScanStore(args.out).read_tracks()}
    if not tags:
        raise FileNotFoundError(f"스캔 산출물이 없다: {args.out}")

    root = args.features or args.out / DEFAULT_FEATURE_DIRNAME
    if not root.exists():
        raise FileNotFoundError(f"특징 산출물이 없다: {root}")
    # **모양을 보고 읽는 쪽을 고른다** (D-0233 · O-69 닫힘 D-0274). 예전에는 여기가
    # `NpzFeatureStore`를 박아 놓아서 **`--features`로 묶음을 줘도 못 읽었다** —
    # `search`와 `eval fusion`이 그 자리를 공유하므로 둘 다 묶음을 못 봤다.
    store = open_feature_source(root, keys)
    if not store.index_path.exists():
        raise FileNotFoundError(f"특징 인덱스가 없다: {store.index_path}")

    tracks: list[SearchTrack] = []
    for source_key, vectors in store.iter_vectors():
        tag = tags.get(source_key)
        if tag is None or any(key not in vectors for key in keys):
            continue
        tracks.append(
            SearchTrack(
                source_key=source_key,
                artist=tag.artist,
                title=tag.title,
                embeddings=vectors,
            )
        )
    return tracks


# ------------------------------------------ 명령 등재 (D-0273)


def _build_retrieval(parser: argparse.ArgumentParser) -> None:
    """`hathor eval retrieval` 인자."""
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치"
    )
    parser.add_argument(
        "--features",
        action="append",
        default=None,
        metavar="[이름=]경로",
        help=(
            "특징 산출물 루트 (미지정 시 --out). 여러 번 줄 수 있으며, 둘 이상이면 "
            "각각에 이름이 필요하고 키를 `이름:mixture`로 지정한다"
        ),
    )
    parser.add_argument(
        "--keys",
        default="mixture",
        help="쓸 임베딩 키 (쉼표 구분). 예: mixture / drums,bass,other,vocals",
    )
    parser.add_argument("--combine", choices=[m.value for m in CombineMode], default="concat")
    parser.add_argument("--pool", choices=[m.value for m in PoolMode], default="mean")
    parser.add_argument(
        "--chunk-l2",
        action="store_true",
        help="풀링 전에 청크별 L2 정규화 (곡 벡터 L2는 코사인에서 무의미하다)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="중심화를 끈다. 허브 곡이 상위를 차지한다 (비교용, D-0031)",
    )
    parser.add_argument(
        "--block-l2",
        action="store_true",
        help="블록별 단위 정규화 후 결합. 서로 다른 추출기를 섞을 때 필수다",
    )
    parser.add_argument(
        "--split",
        choices=[m.value for m in SplitMode],
        default=SplitMode.ODD_EVEN.value,
        help="M0 분할 규칙. odd-even은 결정적이며 오디오축 정본이다 (D-0040)",
    )
    parser.add_argument(
        "--split-ratio",
        type=float,
        default=0.5,
        help="random 분할에서 쿼리 조각의 비율. 0.5가 홀짝과 직접 비교된다",
    )
    parser.add_argument(
        "--split-repeats",
        type=int,
        default=1,
        help="random 분할 반복 횟수. 1회 값은 표본 하나라 그대로 인용하면 안 된다",
    )
    parser.add_argument("--split-seed", type=int, default=DEFAULT_SPLIT_SEED, help="분할 시드")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="상위 k개")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="무작위 베이스라인 시드")
    parser.add_argument("--gate", type=float, default=DEFAULT_GATE, help="M0 통과 기준")
    parser.add_argument(
        "--force",
        action="store_true",
        help="붕괴 판정에도 M1/M2를 계산한다. 조사용이며 그 수치를 인용하면 안 된다",
    )
    parser.add_argument("--label", default=None, help="실험 이름 (미지정 시 뷰에서 생성)")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")


COMMANDS: tuple[Command, ...] = (
    Command("retrieval", "M0/M1/M2 + 무작위 베이스라인", _build_retrieval, run_eval_retrieval),
)
"""`eval` 표에 실리는 것 (D-0273). **등재와 배선이 한 줄에 선다.**"""
