"""CLI 진입점. 비즈니스 로직은 두지 않는다 (GR-2.2)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.application.evaluate_retrieval import (
    DEFAULT_GATE,
    DEFAULT_K,
    DEFAULT_SEED,
    EvaluateRetrieval,
    EvaluationConfig,
    EvaluationReport,
    TrackRecord,
    ViewSpec,
)
from hathor.application.extract_features import ExtractFeatures
from hathor.application.orchestrator.generation_pipeline import run_dry
from hathor.application.resolve_identities import ResolutionRecord, ResolveIdentities
from hathor.application.scan_library import ScanLibrary
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.domain.services.embedding_pooling import CombineMode, PoolMode
from hathor.infrastructure.filesystem_scanner import FilesystemLibraryScanner
from hathor.infrastructure.jsonl_resolution_store import JsonlResolutionStore
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.infrastructure.musicbrainz_lookup import (
    MusicBrainzClient,
    MusicBrainzLookup,
)
from hathor.infrastructure.mutagen_tag_extractor import MutagenTagExtractor

if TYPE_CHECKING:
    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

DEFAULT_LIBRARY_ROOT_ENV = "HATHOR_LIBRARY_ROOT"
DEFAULT_OUTPUT_ROOT = Path("var/ingest")
DEFAULT_CONTACT = "https://github.com/CleverAIFox/hathor"
DEFAULT_MFCC_DIRNAME = "baseline-mfcc"


def _parse_stages(raw: str) -> tuple[Stage, ...]:
    stages: list[Stage] = []
    for token in raw.split(","):
        name = token.strip().lower()
        if not name:
            continue
        try:
            stages.append(Stage(name))
        except ValueError as exc:
            valid = ", ".join(s.value for s in Stage)
            raise SystemExit(f"알 수 없는 단계: {name} (가능: {valid})") from exc
    if not stages:
        raise SystemExit("단계를 최소 1개 지정해야 한다")
    return tuple(stages)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hathor", description="HATHOR CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="생성 파이프라인 실행")
    gen.add_argument("--seed", type=int, required=True, help="난수 시드 (GR-6.5)")
    gen.add_argument("--stages", type=str, default="structure,harmony")
    gen.add_argument("--dry-run", action="store_true", help="모델 없이 결정적 산출물만")
    gen.add_argument("--out", type=Path, default=None, help="JSON 출력 경로")

    ingest = sub.add_parser("ingest", help="음원 라이브러리 인제스트")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)

    scan = ingest_sub.add_parser("scan", help="라이브러리 스캔")
    scan.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    scan.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리")
    scan.add_argument("--force", action="store_true", help="델타 감지를 건너뛰고 전수 재스캔")
    scan.add_argument(
        "--fail-threshold",
        type=float,
        default=0.05,
        help="실패율이 이 값을 넘으면 비정상 종료",
    )

    resolve = ingest_sub.add_parser("resolve", help="정규 신원 확정 (MusicBrainz)")
    resolve.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리")
    resolve.add_argument("--limit", type=int, default=None, help="처리할 곡 수 상한 (시험용)")
    resolve.add_argument(
        "--contact",
        default=DEFAULT_CONTACT,
        help="User-Agent에 넣을 연락처. MB가 식별 가능한 값을 요구한다",
    )
    features = ingest_sub.add_parser("features", help="오디오 특징 추출 (GPU)")
    features.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    features.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리")
    features.add_argument("--limit", type=int, default=None, help="처리할 곡 수 상한 (시험용)")
    features.add_argument(
        "--force",
        action="store_true",
        help="이미 추출된 곡도 다시 처리",
    )

    compact = ingest_sub.add_parser("compact", help="특징 인덱스의 중복·고아 기록 정리 (O-7)")
    compact.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리")
    compact.add_argument(
        "--keep-missing",
        action="store_true",
        help="npz가 없는 기록도 남긴다 (기본은 버린다)",
    )
    compact.add_argument("--dry-run", action="store_true", help="쓰지 않고 결과만 보고한다")

    evaluate = sub.add_parser("eval", help="검색 평가 하네스")
    eval_sub = evaluate.add_subparsers(dest="eval_command", required=True)

    retrieval = eval_sub.add_parser("retrieval", help="M0/M1/M2 + 무작위 베이스라인")
    retrieval.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치")
    retrieval.add_argument(
        "--features",
        type=Path,
        default=None,
        help="특징 산출물 루트 (미지정 시 --out). 베이스라인 비교 시 다른 루트를 준다",
    )
    retrieval.add_argument(
        "--keys",
        default="mixture",
        help="쓸 임베딩 키 (쉼표 구분). 예: mixture / drums,bass,other,vocals",
    )
    retrieval.add_argument("--combine", choices=[m.value for m in CombineMode], default="concat")
    retrieval.add_argument("--pool", choices=[m.value for m in PoolMode], default="mean")
    retrieval.add_argument(
        "--chunk-l2",
        action="store_true",
        help="풀링 전에 청크별 L2 정규화 (곡 벡터 L2는 코사인에서 무의미하다)",
    )
    retrieval.add_argument("--k", type=int, default=DEFAULT_K, help="상위 k개")
    retrieval.add_argument("--seed", type=int, default=DEFAULT_SEED, help="무작위 베이스라인 시드")
    retrieval.add_argument("--gate", type=float, default=DEFAULT_GATE, help="M0 통과 기준")
    retrieval.add_argument(
        "--force",
        action="store_true",
        help="M0 미달에도 M1/M2를 계산한다. 조사용이며 그 수치를 인용하면 안 된다",
    )
    retrieval.add_argument("--label", default=None, help="실험 이름 (미지정 시 뷰에서 생성)")
    retrieval.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")

    mfcc = eval_sub.add_parser("mfcc", help="MFCC 베이스라인 특징 추출 (CPU)")
    mfcc.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    mfcc.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치")
    mfcc.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_MFCC_DIRNAME})",
    )
    mfcc.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    mfcc.add_argument("--force", action="store_true", help="이미 추출된 곡도 다시 처리")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "eval":
        if args.eval_command == "mfcc":
            return _run_eval_mfcc(args)
        return _run_eval_retrieval(args)
    if args.command == "ingest":
        if args.ingest_command == "resolve":
            return _run_ingest_resolve(args)
        if args.ingest_command == "features":
            return _run_ingest_features(args)
        if args.ingest_command == "compact":
            return _run_ingest_compact(args)
        return _run_ingest_scan(args)
    return _run_generate(args)


def _run_generate(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("아직 dry-run 경로만 구현되어 있다 (P0). --dry-run을 사용한다.", file=sys.stderr)
        return 2

    job = GenerationJob(seed=args.seed, stages=_parse_stages(args.stages))
    payload = json.dumps(run_dry(job), ensure_ascii=False, indent=2, sort_keys=True)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def _resolve_root(raw: Path | None) -> Path:
    """라이브러리 루트를 결정한다.

    노트북마다 드라이브 문자가 다르므로(리전 /mnt/f, 광인사 /mnt/d)
    경로를 코드에 하드코딩하지 않고 환경변수로 외부화한다(D-0009).
    """
    if raw is not None:
        return raw
    from os import environ

    value = environ.get(DEFAULT_LIBRARY_ROOT_ENV)
    if not value:
        raise SystemExit(f"--root를 지정하거나 {DEFAULT_LIBRARY_ROOT_ENV} 환경변수를 설정해야 한다")
    return Path(value)


def _run_ingest_resolve(args: argparse.Namespace) -> int:
    """스캔 산출물을 읽어 MusicBrainz로 정규 신원을 확정한다 (D-0019).

    초당 1요청 제한이라 1004곡에 20분 안팎이 걸린다. 진행 상황을
    곡 단위로 출력한다.
    """
    store = JsonlScanStore(args.out)
    tracks = list(store.read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2
    if args.limit is not None:
        tracks = tracks[: args.limit]

    agent = f"Hathor/0.1 ( {args.contact} )"
    lookup = MusicBrainzLookup(MusicBrainzClient(agent))
    use_case = ResolveIdentities(lookup, lookup)

    print(f"대상 {len(tracks)}곡, 예상 {len(tracks) * 1.1 / 60:.1f}분", flush=True)

    def _progress() -> Iterator[ResolutionRecord]:
        for index, record in enumerate(use_case.run(tracks), 1):
            state = record.recording.state.value.upper()
            label = f"{record.queried_artist} - {record.queried_title}"
            print(f"  {index:>4}/{len(tracks)} {state:<10} {label}", flush=True)
            yield record

    summary_path = JsonlResolutionStore(args.out).write(_progress(), use_case.summary)

    summary = use_case.summary
    print()
    for state in ResolutionState:
        count = summary.count_of(state)
        if count:
            print(f"  {state.value.upper():<11} {count:>4} ({summary.ratio_of(state):6.1%})")
    print(f"요약: {summary_path}")
    return 0


def _run_ingest_scan(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    if not root.is_dir():
        print(f"라이브러리 루트가 없다: {root}", file=sys.stderr)
        return 2

    store = JsonlScanStore(args.out)
    previous = None if args.force else store.latest_snapshot()

    use_case = ScanLibrary(FilesystemLibraryScanner(MutagenTagExtractor()))
    summary_path = store.write(use_case.run(root, previous), use_case.summary)

    summary = use_case.summary
    print(f"총 {summary.total_files}건 / 성공 {summary.succeeded} / 실패 {summary.failed}")
    print(
        f"델타: 신규 {summary.discovered} / 변경 {summary.modified} / "
        f"무변화 {summary.unchanged} / 소실 {summary.removed}"
    )
    print(f"요약: {summary_path}")

    if summary.removal_rate > 0.5:
        print(
            "경고: 소실 비율이 50%를 넘는다. 외장 볼륨 연결 상태를 확인해라.",
            file=sys.stderr,
        )

    failure_rate = 1.0 - summary.success_rate
    if summary.total_files > 0 and failure_rate > args.fail_threshold:
        print(
            f"실패율 {failure_rate:.1%}가 임계 {args.fail_threshold:.1%}를 초과했다",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_ingest_features(args: argparse.Namespace) -> int:
    """스캔 산출물의 곡을 디코딩·분리·임베딩해 npz로 저장한다 (유닛 #4).

    GPU가 있는 기기에서만 의미가 있다. 1004곡에 다섯 시간이 걸리므로
    이미 끝난 곡은 인덱스를 보고 건너뛴다. 재개 판정은 실행 정책이라
    유스케이스가 아니라 여기에 둔다.
    """
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    try:
        with NpzFeatureStore(args.out).batch_lock():
            return _extract_features_locked(args)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        print("먼저 돌고 있는 배치를 끝내거나 죽인 뒤 다시 실행한다.", file=sys.stderr)
        return 3


def _extract_features_locked(args: argparse.Namespace) -> int:
    """배치 잠금을 쥔 상태에서 실제 추출을 돈다."""
    from hathor.infrastructure.demucs_separator import DemucsStemSeparator
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.out)
    if not args.force:
        done = store.completed_keys()
        skipped = sum(1 for track in tracks if track.source_key in done)
        tracks = [track for track in tracks if track.source_key not in done]
        if skipped:
            print(f"이미 추출된 {skipped}곡을 건너뛴다", flush=True)
    if args.limit is not None:
        tracks = tracks[: args.limit]
    if not tracks:
        print("처리할 곡이 없다")
        return 0

    use_case = ExtractFeatures(
        FfmpegAudioDecoder(),
        DemucsStemSeparator(),
        MertFeatureExtractor(),
        _resolve_root(args.root),
    )
    return _drive_extraction(use_case, store, tracks, seconds_per_track=18.0)


def _drive_extraction(
    use_case: ExtractFeatures,
    store: NpzFeatureStore,
    tracks: list[ScannedTrack],
    *,
    seconds_per_track: float,
) -> int:
    """추출을 돌리며 곡 단위로 저장하고 요약을 남긴다.

    MERT 경로와 MFCC 베이스라인 경로가 같은 루프를 쓴다. 진행 출력·실패
    처리·요약 형식이 갈라지면 두 산출물을 나란히 놓고 비교할 수 없다.
    """
    print(f"대상 {len(tracks)}곡, 예상 {len(tracks) * seconds_per_track / 60:.1f}분", flush=True)

    started = time.monotonic()
    for index, features in enumerate(use_case.run(tracks), 1):
        store.write_track(features)
        elapsed = time.monotonic() - started
        print(
            f"  {index:>4}/{len(tracks)} {features.chunk_count:>3}청크 "
            f"{elapsed / index:5.1f}초/곡 {features.source_key}",
            flush=True,
        )

    summary_path = store.write_summary(
        {
            "processed": use_case.processed,
            "failed": len(use_case.failed),
            "failures": [{"source_key": key, "reason": reason} for key, reason in use_case.failed],
        }
    )
    print()
    print(f"성공 {use_case.processed}곡, 실패 {len(use_case.failed)}곡")
    for key, reason in use_case.failed:
        print(f"  실패 {key}: {reason}", file=sys.stderr)
    print(f"요약: {summary_path}")
    return 0


def _run_ingest_compact(args: argparse.Namespace) -> int:
    """특징 인덱스의 중복·고아 기록을 정리한다 (O-7).

    배치가 겹쳐 돌아 1004곡 인덱스에 1574줄이 쌓인 상태를 되돌린다.
    정리하지 않으면 인덱스를 읽는 모든 후속 작업이 같은 곡을 여러 번
    본다. 유사도 행렬과 검색 지표가 조용히 틀어진다.
    """
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    store = NpzFeatureStore(args.out)
    if not store.index_path.exists():
        print(f"인덱스가 없다: {store.index_path}", file=sys.stderr)
        return 2

    if args.dry_run:
        records = store.read_records()
        keys = {str(record["source_key"]) for record in records}
        print(f"전체 {len(records)}줄, 고유 키 {len(keys)}개, 중복 {len(records) - len(keys)}줄")
        return 0

    try:
        with store.batch_lock():
            report = store.compact_index(drop_missing=not args.keep_missing)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        print("배치가 도는 중에는 인덱스를 정리하지 않는다.", file=sys.stderr)
        return 3

    print(f"전체 {report.total_lines}줄 -> {report.kept}줄")
    print(f"  중복 제거 {report.duplicates_removed}줄")
    print(f"  npz 없는 기록 제거 {report.missing_vectors_dropped}줄")
    print(f"  깨진 줄 제거 {report.malformed_dropped}줄")
    if not report.changed:
        print("바꿀 것이 없었다.")
    return 0


def _default_label(view: ViewSpec) -> str:
    """뷰 설정에서 실험 이름을 만든다. 산출 파일명이 조건을 말하게 한다."""
    parts = ["+".join(view.keys), view.combine.value, view.pool.value]
    if view.chunk_l2:
        parts.append("chunkl2")
    return "-".join(parts)


def _run_eval_retrieval(args: argparse.Namespace) -> int:
    """M0/M1/M2를 재고 리포트를 남긴다.

    GPU도 외부 조회도 쓰지 않는다. 1004x768 행렬에 1004x1004 코사인이면
    CPU에서 수 초다. 광인사에서 도는 것이 요건이다.
    """
    from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    keys = tuple(token.strip() for token in args.keys.split(",") if token.strip())
    if not keys:
        print("--keys에 임베딩 키를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2

    view = ViewSpec(
        keys=keys,
        combine=CombineMode(args.combine),
        pool=PoolMode(args.pool),
        chunk_l2=args.chunk_l2,
    )
    label = args.label or _default_label(view)
    config = EvaluationConfig(
        view=view,
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

    store = NpzFeatureStore(args.features or args.out)
    if not store.index_path.exists():
        print(f"특징 인덱스가 없다: {store.index_path}", file=sys.stderr)
        return 2

    records: list[TrackRecord] = []
    seen: set[str] = set()
    orphans: list[str] = []
    duplicates: list[str] = []
    for source_key, vectors in store.iter_vectors():
        if source_key in seen:
            duplicates.append(source_key)
            continue
        seen.add(source_key)
        tag = tags.get(source_key)
        if tag is None:
            orphans.append(source_key)
            continue
        records.append(
            TrackRecord(
                source_key=source_key,
                album=tag.album,
                artist=tag.artist,
                embeddings=vectors,
            )
        )

    if duplicates:
        # O-7의 재발이다. 중복을 조용히 흡수하면 유사도 행렬에 같은 곡이
        # 여러 번 들어가 지표가 틀어진 채로 그럴듯한 숫자를 낸다.
        print(f"인덱스에 중복 키가 {len(duplicates)}건 있다: {duplicates[0]} ...", file=sys.stderr)
        print("먼저 `hathor ingest compact`로 정리한다.", file=sys.stderr)
        return 2
    if orphans:
        print(f"경고: 스캔 산출물에 없는 곡 {len(orphans)}건을 제외했다", file=sys.stderr)
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
        print(
            "M0 게이트 미달. 임베딩이 곡 정체성조차 담지 못한 것이므로 "
            "M1/M2는 노이즈다. 추출 설정부터 다시 본다.",
            file=sys.stderr,
        )
        return 1
    return 0


def _print_report(report: EvaluationReport) -> None:
    view = report.config.view
    print(
        f"곡 {report.tracks}개 (제외 {len(report.skipped)}) / "
        f"뷰 {'+'.join(view.keys)} {view.combine.value}·{view.pool.value}"
        f"{'·chunk-l2' if view.chunk_l2 else ''} / {report.dimension}차원"
    )
    verdict = "통과" if report.gate_passed else "미달"
    print(
        f"  M0 자기일관성  top-1 {report.self_consistency:.4f} "
        f"(기준 {report.config.gate:.2f}) {verdict}"
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
        print("  M1/M2는 계산하지 않았다 (M0 게이트).")


def _run_eval_mfcc(args: argparse.Namespace) -> int:
    """MFCC 베이스라인 특징을 뽑는다. CPU 전용이며 스템 분리를 하지 않는다.

    MERT 산출물과 같은 (청크, 차원) 규격으로 별도 루트에 쌓는다.
    같은 `eval retrieval`을 `--features`만 바꿔 돌리면 비교가 된다.
    """
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.mfcc_feature_extractor import MfccFeatureExtractor
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.features or args.out / DEFAULT_MFCC_DIRNAME)
    try:
        with store.batch_lock():
            if not args.force:
                done = store.completed_keys()
                skipped = sum(1 for track in tracks if track.source_key in done)
                tracks = [track for track in tracks if track.source_key not in done]
                if skipped:
                    print(f"이미 추출된 {skipped}곡을 건너뛴다", flush=True)
            if args.limit is not None:
                tracks = tracks[: args.limit]
            if not tracks:
                print("처리할 곡이 없다")
                return 0

            use_case = ExtractFeatures(
                FfmpegAudioDecoder(),
                None,
                MfccFeatureExtractor(),
                _resolve_root(args.root),
            )
            return _drive_extraction(use_case, store, tracks, seconds_per_track=2.0)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3
