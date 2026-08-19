"""CLI 진입점. 비즈니스 로직은 두지 않는다 (GR-2.2)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.application.evaluate_fusion import EvaluateFusion
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
from hathor.application.extract_features import ExtractFeatures, ExtractLayerFeatures
from hathor.application.orchestrator.generation_pipeline import run_dry
from hathor.application.resolve_identities import ResolutionRecord, ResolveIdentities
from hathor.application.scan_library import ScanLibrary
from hathor.application.search_similar import SearchSimilar, SearchTrack
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.domain.services.embedding_pooling import CombineMode, PoolMode
from hathor.domain.services.key_estimation import KeyEstimate
from hathor.domain.services.seed_search import FusionMode
from hathor.domain.value_objects.key import Key
from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
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
    from hathor.domain.entities.track_tags import TrackTags
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

DEFAULT_LIBRARY_ROOT_ENV = "HATHOR_LIBRARY_ROOT"
DEFAULT_OUTPUT_ROOT = Path("var/ingest")
DEFAULT_CONTACT = "https://github.com/CleverAIFox/hathor"
DEFAULT_MFCC_DIRNAME = "baseline-mfcc"
DEFAULT_LAYERS_DIRNAME = "mert-layers"
DEFAULT_LAYERS = "0,1,2,6"
DEFAULT_SEARCH_KEY = "layer00"
DEFAULT_LYRICS_DIRNAME = "lyrics-hashed"
_DETERMINISM_PROBE = (
    # 한국어·영어·혼재 각 하나. 코퍼스 실측이 혼재 40%였으므로 세 경우를 다 밟는다.
    "사랑한다는 말은 하지 못했어",
    "i never said the words out loud",
    "돌아서는 순간 you were already gone",
)
"""D-0027 정본 뷰."""
"""D-0026 실측 후 기본값. layer00이 최선이었고 1·2는 미탐색이다 (O-9)."""


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
    gen.add_argument("--midi", type=Path, default=None, help="MIDI 출력 경로 (D-0052)")
    gen.add_argument(
        "--reference",
        action="append",
        default=None,
        help="참조곡 제목 일부. 여러 번 줄 수 있다. 그 곡의 구조를 조건으로 쓴다",
    )
    gen.add_argument("--scan-out", default="var/ingest", help="스캔 산출물 루트")
    gen.add_argument("--tempo", type=int, default=96, help="템포 (BPM)")
    gen.add_argument("--sections", type=int, default=None, help="구간 수. 기본은 참조곡 평균")
    gen.add_argument(
        "--root", type=Path, default=None, help="라이브러리 루트. 조성 추정에 음원이 필요하다"
    )
    gen.add_argument(
        "--key",
        help='출력 조성을 고정한다 (예: "C major"). 참조곡 화성 조건화는 그대로 걸린다. '
        "조성 차이를 뺀 채 화성만 비교해 들을 때 쓴다",
    )
    gen.add_argument(
        "--no-key-estimation",
        action="store_true",
        help="조성 추정을 끄고 C장조를 쓴다. 음원 없이 돌릴 때. 화성 조건화도 함께 꺼진다",
    )
    gen.add_argument("--max-references", type=int, default=5, help="참조곡 상한 (D-0011)")
    gen.add_argument(
        "--chroma", choices=("cq", "linear"), default="cq", help="조성 추정 크로마 방식"
    )

    ingest = sub.add_parser("ingest", help="음원 라이브러리 인제스트")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)

    keys = ingest_sub.add_parser("keys", help="코퍼스 조성 분포 실측 (D-0054 · O-22)")
    keys.add_argument("--out", default="var/ingest", help="스캔 산출물 루트")
    keys.add_argument("--root", type=Path, default=None, help="라이브러리 루트")
    keys.add_argument(
        "--chroma",
        choices=("cq", "linear"),
        default="cq",
        help="크로마 방식. linear는 D-0056 이전 베이스라인이다",
    )
    keys.add_argument("--limit", type=int, default=None, help="앞에서 N곡만")
    keys.add_argument(
        "--replay", type=Path, default=None, help="저장된 keys.jsonl을 재분석. 디코딩하지 않는다"
    )
    keys.add_argument(
        "--tuning",
        action="store_true",
        help="조율 편차도 잰다 (D-0057). 11배 느려지므로 표본에만 쓴다",
    )
    keys.add_argument(
        "--profile",
        choices=("krumhansl", "temperley"),
        default="krumhansl",
        help="조성 프로파일. krumhansl이 베이스라인이다 (D-0058)",
    )
    keys.add_argument(
        "--gamma", type=float, default=0.0, help="로그 압축. 0이 끔이며 기본이다 (D-0058)"
    )
    keys.add_argument(
        "--harmonic",
        type=float,
        default=0.0,
        help="배음 감산 강도. 0이 끔이며 기본이다 (D-0059)",
    )
    keys.add_argument(
        "--harmonic-sweep",
        action="store_true",
        help="배음 강도 0~1을 한 번에 훑어 표로 낸다 (D-0060). --replay와 함께 쓴다",
    )
    keys.add_argument(
        "--halves",
        action="store_true",
        help="앞뒤 반쪽 크로마도 뽑는다 (D-0062). `eval harmony-prior`가 이것을 요구한다",
    )
    keys.add_argument(
        "--aggregate",
        choices=("mean", "median"),
        default="mean",
        help="전곡을 한 번에 변환할지(mean) 창별 중앙값을 낼지(median). O-27 후보 (b)",
    )
    keys.add_argument(
        "--window-seconds",
        type=float,
        default=10.0,
        help="--aggregate median의 창 길이(초)",
    )

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
        action="append",
        default=None,
        metavar="[이름=]경로",
        help=(
            "특징 산출물 루트 (미지정 시 --out). 여러 번 줄 수 있으며, 둘 이상이면 "
            "각각에 이름이 필요하고 키를 `이름:mixture`로 지정한다"
        ),
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
    retrieval.add_argument(
        "--raw",
        action="store_true",
        help="중심화를 끈다. 허브 곡이 상위를 차지한다 (비교용, D-0031)",
    )
    retrieval.add_argument(
        "--block-l2",
        action="store_true",
        help="블록별 단위 정규화 후 결합. 서로 다른 추출기를 섞을 때 필수다",
    )
    retrieval.add_argument(
        "--split",
        choices=[m.value for m in SplitMode],
        default=SplitMode.ODD_EVEN.value,
        help="M0 분할 규칙. odd-even은 결정적이며 오디오축 정본이다 (D-0040)",
    )
    retrieval.add_argument(
        "--split-ratio",
        type=float,
        default=0.5,
        help="random 분할에서 쿼리 조각의 비율. 0.5가 홀짝과 직접 비교된다",
    )
    retrieval.add_argument(
        "--split-repeats",
        type=int,
        default=1,
        help="random 분할 반복 횟수. 1회 값은 표본 하나라 그대로 인용하면 안 된다",
    )
    retrieval.add_argument("--split-seed", type=int, default=DEFAULT_SPLIT_SEED, help="분할 시드")
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

    fusion = eval_sub.add_parser("fusion", help="시드 결합 규칙 비교 (M4)")
    fusion.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    fusion.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LAYERS_DIRNAME})",
    )
    fusion.add_argument("--keys", default=DEFAULT_SEARCH_KEY, help="쓸 임베딩 키")
    fusion.add_argument("-k", type=int, default=10, help="상위 k개")
    fusion.add_argument("--pairs", type=int, default=200, help="시드 쌍 표본 수")
    fusion.add_argument("--seed", type=int, default=20260817, help="쌍 추출 시드")
    fusion.add_argument("--penalty", type=float, default=1.0, help="penalized 모드의 편차 계수")
    fusion.add_argument("--raw", action="store_true", help="중심화를 끈다")

    harmony = eval_sub.add_parser(
        "harmony-prior", help="화성 도수 사전의 정보량 판정 (O-21 · D-0062)"
    )
    harmony.add_argument(
        "--replay",
        type=Path,
        required=True,
        help="`ingest keys --halves`가 만든 keys.jsonl. 음원도 GPU도 필요 없다",
    )
    harmony.add_argument(
        "--harmonic", type=float, default=0.0, help="배음 감산 강도. 네 선 전부에 적용된다"
    )
    harmony.add_argument("--smoothing", type=float, default=0.01, help="예측 분포 평활 비율")
    harmony.add_argument(
        "--margin-floor", type=float, default=KEY_MARGIN_FLOOR, help="조성 추정 애매 기준"
    )
    harmony.add_argument(
        "--confident-only", action="store_true", help="격차가 하한 미만인 곡을 뺀다"
    )
    harmony.add_argument("--seed", type=int, default=20260819, help="귀무선 짝짓기 시드")
    harmony.add_argument("--blend-steps", type=int, default=11, help="λ 격자 수")

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

    layers = eval_sub.add_parser("layers", help="MERT 레이어별 특징 추출 (GPU, 스템 없음)")
    layers.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    layers.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치")
    layers.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LAYERS_DIRNAME})",
    )
    layers.add_argument(
        "--layers",
        default=DEFAULT_LAYERS,
        help=(
            "뽑을 은닉 레이어 인덱스 (쉼표 구분). 0은 트랜스포머 블록 이전이며 "
            "마지막 레이어는 mixture 키로 항상 저장된다"
        ),
    )
    layers.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    layers.add_argument("--force", action="store_true", help="이미 추출된 곡도 다시 처리")

    taste = sub.add_parser("taste", help="취향 라벨 수집")
    taste_sub = taste.add_subparsers(dest="taste_command", required=True)

    compare = taste_sub.add_parser("compare", help="쌍대비교 문항을 내고 응답을 기록한다")
    compare.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    compare.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LAYERS_DIRNAME})",
    )
    compare.add_argument("--count", type=int, default=20, help="이번 세션 문항 수")
    compare.add_argument("--seed", type=int, default=DEFAULT_SEED, help="쌍 추출 시드")

    status = taste_sub.add_parser("status", help="수집 현황")
    status.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")

    lyrics = sub.add_parser("lyrics", help="가사축")
    lyrics_sub = lyrics.add_subparsers(dest="lyrics_command", required=True)
    lyrics_structure = lyrics_sub.add_parser(
        "structure", help="가사 반복 패턴에서 곡 구조 분포 실측 (D-0049)"
    )
    lyrics_structure.add_argument("--out", default="var/ingest", help="스캔 산출물 루트")
    lyrics_structure.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="반복 판정 자카드 하한. 근거로 정한 값이 아니다 (실측 필요)",
    )
    lyrics_structure.add_argument(
        "--sweep",
        action="store_true",
        help="임계값을 0.3~0.7로 훑어 민감도를 본다. 하나의 값으로 결론내지 않기 위해서다",
    )
    lyrics_structure.add_argument("--samples", type=int, default=5, help="예시로 보일 곡 수")
    lyrics_extract = lyrics_sub.add_parser("extract", help="가사 특징 추출 (CPU, 수 초)")
    lyrics_extract.add_argument(
        "--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치"
    )
    lyrics_extract.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LYRICS_DIRNAME})",
    )
    lyrics_extract.add_argument(
        "--encoder",
        choices=("hashed", "bge-m3"),
        default="hashed",
        help="가사 인코더. hashed는 베이스라인이자 기본값이다 (D-0036 · D-0045)",
    )
    lyrics_extract.add_argument(
        "--device", default="cuda", help="bge-m3 추론 장치. GPU가 없으면 cpu"
    )
    lyrics_extract.add_argument("--batch-size", type=int, default=16, help="bge-m3 배치 크기")
    lyrics_extract.add_argument(
        "--pooling",
        choices=("cls", "mean"),
        default="cls",
        help="bge-m3 풀링. cls는 모델의 dense 정의와 일치한다 (D-0046)",
    )
    lyrics_extract.add_argument("--dim", type=int, default=1024, help="해싱 차원")
    lyrics_extract.add_argument("--ngrams", default="2,3,4", help="문자 n-gram 크기 (쉼표 구분)")
    lyrics_extract.add_argument(
        "--collapse-space",
        action="store_true",
        help="공백을 제거한다. `보고싶어`와 `보고 싶어`를 같게 본다",
    )
    lyrics_extract.add_argument(
        "--repeat-damping",
        type=float,
        default=0.0,
        help="곡 안에서 반복되는 n-gram 감쇠 (0=없음, 1=곡내 문서빈도 역수)",
    )
    lyrics_extract.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    lyrics_extract.add_argument("--force", action="store_true", help="이미 추출된 곡도 다시 처리")

    search = sub.add_parser("search", help="시드곡 조합으로 유사곡을 찾는다")
    search.add_argument(
        "--like",
        action="append",
        default=None,
        metavar="검색어",
        help="시드곡. 아티스트·제목·경로 일부로 찾는다. 여러 번 주면 퓨전한다",
    )
    search.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    search.add_argument(
        "--features",
        type=Path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LAYERS_DIRNAME})",
    )
    search.add_argument("--keys", default=DEFAULT_SEARCH_KEY, help="쓸 임베딩 키")
    search.add_argument("-k", type=int, default=10, help="결과 개수")
    search.add_argument(
        "--fusion",
        choices=[m.value for m in FusionMode],
        default=FusionMode.MEAN.value,
        help="시드 결합 규칙. min은 모든 시드와 가까울 것을 요구한다 (D-0033)",
    )
    search.add_argument("--penalty", type=float, default=1.0, help="penalized 모드의 편차 계수")
    search.add_argument(
        "--raw",
        action="store_true",
        help="중심화를 끈다. 허브 곡이 어떤 질의에도 상위에 온다 (비교용)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "lyrics":
        if args.lyrics_command == "structure":
            return _run_lyrics_structure(args)
        return _run_lyrics_extract(args)
    if args.command == "search":
        return _run_search(args)
    if args.command == "taste":
        if args.taste_command == "status":
            return _run_taste_status(args)
        return _run_taste_compare(args)
    if args.command == "eval":
        if args.eval_command == "mfcc":
            return _run_eval_mfcc(args)
        if args.eval_command == "layers":
            return _run_eval_layers(args)
        if args.eval_command == "fusion":
            return _run_eval_fusion(args)
        if args.eval_command == "harmony-prior":
            return _run_eval_harmony_prior(args)
        return _run_eval_retrieval(args)
    if args.command == "ingest":
        if args.ingest_command == "keys":
            return _run_ingest_keys(args)
        if args.ingest_command == "resolve":
            return _run_ingest_resolve(args)
        if args.ingest_command == "features":
            return _run_ingest_features(args)
        if args.ingest_command == "compact":
            return _run_ingest_compact(args)
        return _run_ingest_scan(args)
    return _run_generate(args)


def _run_generate(args: argparse.Namespace) -> int:
    if args.midi is not None:
        return _run_generate_midi(args)
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


KEY_MARGIN_FLOOR = 0.05
"""이보다 격차가 작으면 조성 추정을 신뢰하지 않고 표시한다 (D-0054).

Krumhansl-Schmuckler는 나란한 장·단조를 구분하기 어렵다(C장조 ↔ A단조).
구성음이 같기 때문이며 원리적 한계다. **1등만 남기면 그 사실이 사라진다.**
"""


def _estimate_key(
    args: argparse.Namespace, source_keys: list[str]
) -> tuple[Key, dict[str, KeyEstimate]]:
    """참조곡 음원에서 조성을 추정한다. 실패하면 C장조로 간다.

    **배치가 필요 없다.** 참조곡은 1~5개뿐이라 그 자리에서 디코딩한다.
    1004곡 전량 추출은 조성이 실제로 값을 한다고 확인된 뒤에 판단한다.

    여럿이면 **격차가 가장 큰 곡의 조성**을 쓴다. 평균을 낼 수 없는 값이고
    (C장조와 F#장조의 평균은 없다), 다수결은 2곡일 때 무의미하다.
    가장 확신도 높은 추정을 따르는 것이 그중 낫다.
    """
    from hathor.domain.services.key_estimation import estimate_key_from_waveform
    from hathor.domain.value_objects.key import Key, Mode

    fallback = Key(tonic="C", mode=Mode.MAJOR)
    if args.no_key_estimation:
        return fallback, {}

    try:
        root = _resolve_root(args.root)
    except (SystemExit, ValueError, KeyError):
        print("라이브러리 루트를 찾지 못해 C장조를 쓴다.", file=sys.stderr)
        return fallback, {}

    decoder = FfmpegAudioDecoder()
    estimates: dict[str, KeyEstimate] = {}
    for source_key in source_keys:
        path = root / source_key
        try:
            present = path.exists()
        except OSError as error:
            # WSL에서 드라이브 마운트가 끊기면 `exists()`가 False가 아니라
            # OSError(Errno 19)를 던진다. 복구 가능한 상황이 트레이스백이 되면
            # 안 된다 — 바로 아래 디코딩은 이미 감싸 두었다.
            print(f"음원 경로를 열 수 없다({error}): {source_key[:40]}", file=sys.stderr)
            continue
        if not present:
            print(f"음원이 없어 건너뛴다: {source_key[:60]}", file=sys.stderr)
            continue
        try:
            estimates[source_key] = estimate_key_from_waveform(
                decoder.decode(path), mode=args.chroma
            )
        except Exception as error:
            print(f"조성 추정 실패({source_key[:40]}): {error}", file=sys.stderr)

    if not estimates:
        print("조성을 추정하지 못해 C장조를 쓴다.", file=sys.stderr)
        return fallback, {}

    best = max(estimates.values(), key=lambda estimate: estimate.margin)
    return best.key, estimates


def _parse_key(text: str) -> Key:
    """`"C major"` 같은 문자열을 조성으로 바꾼다."""
    from hathor.domain.value_objects.key import PITCH_CLASSES, Key, Mode

    parts = text.strip().rsplit(" ", 1)
    if len(parts) != 2 or parts[0] not in PITCH_CLASSES:
        raise SystemExit(f'--key는 "C major" 형식이어야 한다: {text}')
    try:
        mode = Mode(parts[1].lower())
    except ValueError:
        raise SystemExit(f"--key의 선법은 major 또는 minor여야 한다: {parts[1]}") from None
    return Key(tonic=parts[0], mode=mode)


def _harmony_prior(estimates: dict[str, KeyEstimate]) -> tuple[float, ...] | None:
    """참조곡들의 크로마를 도수 사전 하나로 합친다 (O-21 · D-0063).

    **각 곡을 자기 으뜸음으로 회전시킨 뒤 평균한다.** 피치클래스 공간에서 더하면
    서로 다른 조성이 겹쳐 뭉개진다.

    조성을 추정하지 못했으면 `None`이고, 그러면 화성은 이전처럼 시드만 따른다 —
    조건화가 조용히 반쯤 걸리는 것보다 아예 안 걸리는 편이 낫다.
    """
    from hathor.domain.services.harmony_prior import merge_degree_priors
    from hathor.domain.value_objects.key import PITCH_CLASSES

    usable = [
        (estimate.chroma, PITCH_CLASSES.index(estimate.key.tonic))
        for estimate in estimates.values()
        if len(estimate.chroma) == 12
    ]
    if not usable:
        return None
    return tuple(float(value) for value in merge_degree_priors(usable))


def _report_harmonic_sweep(rows: list[dict[str, object]], profile: str) -> int:
    """배음 감산 강도를 훑어 한 표로 낸다 (D-0060).

    셸 반복문으로 다섯 번 돌리고 눈으로 비교하던 것을 도구로 옮긴다.
    **베이스라인도 강도마다 다시 잰다** — 코퍼스만 감산하고 하한을 고정하면
    판별력이 낮게 보고된다.
    """
    import numpy as np

    from hathor.domain.services.key_estimation import (
        BLACK_KEYS,
        estimate_key,
        random_baseline,
        relative_key,
        subtract_harmonics,
    )
    from hathor.domain.value_objects.key import Key, Mode

    saved = [row.get("chroma") for row in rows]
    if any(item is None for item in saved):
        print("저장된 크로마가 없다. 먼저 크로마를 포함해 추출한다.", file=sys.stderr)
        return 1

    def parse(text: str) -> Key:
        tonic, mode = str(text).rsplit(" ", 1)
        return Key(tonic=tonic, mode=Mode(mode))

    print(f"곡 {len(rows)}개 · 프로파일 {profile}\n")
    header = (
        f"{'강도':>5}{'상관차':>10}{'격차차':>10}{'애매차':>10}"
        f"{'검은건반':>10}{'장조':>8}{'애매내 나란한조':>17}"
    )
    print(header)
    print("-" * len(header))

    for strength in (0.0, 0.3, 0.5, 0.7, 1.0):
        estimates = []
        for item in saved:
            vector = subtract_harmonics(np.asarray(item, dtype=np.float64), strength)
            total = float(vector.sum())
            if total <= 0:
                continue
            estimates.append(
                estimate_key(np.asarray(vector / total, dtype=np.float32), profile=profile)
            )
        if not estimates:
            continue

        correlations = np.asarray([item.correlation for item in estimates])
        margins = np.asarray([item.margin for item in estimates])
        base_correlation, base_margin = random_baseline(profile=profile, harmonic=strength)

        total_songs = len(estimates)
        black = sum(1 for item in estimates if item.key.tonic in BLACK_KEYS)
        major = sum(1 for item in estimates if item.key.mode is Mode.MAJOR)
        ambiguous = [item for item in estimates if item.margin < KEY_MARGIN_FLOOR]
        relative_in_ambiguous = sum(
            1 for item in ambiguous if relative_key(item.key) == item.runner_up
        )
        ambiguous_gap = (
            len(ambiguous) / total_songs - float((base_margin < KEY_MARGIN_FLOOR).mean())
        ) * 100
        if ambiguous:
            share = relative_in_ambiguous / len(ambiguous)
            relative_ratio = f"{share:.1%} ({relative_in_ambiguous}/{len(ambiguous)})"
        else:
            relative_ratio = "-"
        print(
            f"{strength:>5.1f}"
            f"{float(np.median(correlations)) - float(np.median(base_correlation)):>+10.4f}"
            f"{float(np.median(margins)) - float(np.median(base_margin)):>+10.4f}"
            f"{ambiguous_gap:>+9.1f}p"
            f"{black / total_songs:>10.1%}"
            f"{major / total_songs:>8.1%}"
            f"{relative_ratio:>17}"
        )

    print("\n--- 읽는 법 ---")
    print("**검은건반이 핵심이다** (O-23). 33.5%가 실제 대중가요보다 명백히 높다.")
    print("줄지 않으면 배음도 원인이 아니며 O-23의 후보가 전부 소진된다.")
    print("애매차는 무작위 대비다. 음수가 클수록 판정이 결정적이다.")
    print("애매내 나란한조가 오르면 남은 애매함이 원리적 한계 쪽으로 이동한 것이다.")
    return 0


def _run_ingest_keys(args: argparse.Namespace) -> int:
    """코퍼스 조성 분포를 실측한다 (O-22).

    **정답 라벨이 없으므로 분포와 베이스라인으로 검사한다.** 맞다는 증명은
    할 수 없고 틀렸다는 신호만 잡을 수 있다.

    결과를 JSONL로 남긴다. 디코딩이 곡당 수 초라 재분석 때마다 다시 돌리면
    실험 회전이 느려진다 — 지표를 만들어두고 보지 않게 되는 원인이다 (D-0030).
    """
    import json
    from collections import Counter
    from datetime import UTC, datetime

    import numpy as np

    from hathor.domain.services.key_estimation import (
        BLACK_KEYS,
        estimate_key,
        estimate_tuning_cents,
        random_baseline,
        relative_key,
        subtract_harmonics,
        to_mono,
    )
    from hathor.domain.services.key_estimation import (
        chroma as chroma_of,
    )
    from hathor.domain.value_objects.key import Key, Mode

    out_root = Path(args.out)
    rows: list[dict[str, object]] = []

    if args.replay is not None:
        with args.replay.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        recomputed = 0
        for row in rows:
            saved = row.get("chroma")
            if saved is None:
                continue
            # **저장된 크로마로 다시 판정한다** (D-0059). 프로파일과 배음 감산을
            # 바꿔 가며 실험할 수 있고 음원도 GPU도 필요 없다. 크로마를 뽑는
            # 것만 리전이고 알고리즘 실험은 어느 기기에서든 돈다.
            vector = subtract_harmonics(np.asarray(saved, dtype=np.float64), args.harmonic)
            total = float(vector.sum())
            if total <= 0:
                continue
            estimate = estimate_key(
                np.asarray(vector / total, dtype=np.float32), profile=args.profile
            )
            row.update(estimate.as_record())
            row["profile"] = args.profile
            recomputed += 1
        note = (
            f" · {recomputed}곡을 프로파일 {args.profile} · 배음 {args.harmonic:g}로 재판정"
            if recomputed
            else " · 저장된 크로마가 없어 기록된 판정을 그대로 쓴다"
        )
        print(f"재분석: {args.replay} ({len(rows)}곡){note}. 디코딩하지 않는다.\n")
    else:
        root = _resolve_root(args.root)
        tracks = list(JsonlScanStore(out_root).read_tracks())
        if args.limit is not None:
            tracks = tracks[: args.limit]
        if not tracks:
            print("스캔 산출물이 없다. --out 경로를 확인한다.", file=sys.stderr)
            return 1

        decoder = FfmpegAudioDecoder()
        failed = 0
        for index, track in enumerate(tracks, start=1):
            path = root / track.source_key
            if not path.exists():
                failed += 1
                continue
            try:
                waveform = decoder.decode(path)
                # **크로마를 함께 저장한다** (D-0059). 디코딩이 곡당 수 초라
                # 프로파일·배음 실험마다 다시 돌리면 실험 회전이 느려진다.
                # 크로마만 있으면 음원 없는 기기에서도 알고리즘을 바꿔 볼 수 있다.
                extracted = chroma_of(
                    to_mono(waveform),
                    mode=args.chroma,
                    gamma=args.gamma,
                    harmonic=args.harmonic,
                    aggregate=args.aggregate,
                    window_seconds=args.window_seconds,
                )
                estimate = estimate_key(extracted, profile=args.profile)
                cents = (
                    estimate_tuning_cents(to_mono(waveform))
                    if args.tuning and args.chroma == "cq"
                    else 0.0
                )
            except Exception:
                failed += 1
                continue
            record: dict[str, object] = {
                "source_key": track.source_key,
                **estimate.as_record(),
                "tuning_cents": cents,
                "profile": args.profile,
                "chroma": [round(float(value), 6) for value in extracted],
            }
            if args.halves:
                # **조성을 앞반쪽에서만 추정한다** (D-0062). 곡 전체에서 추정하면
                # 뒷반쪽이 회전 정렬에 관여해 홀드아웃이 성립하지 않는다.
                mono = to_mono(waveform)
                middle = mono.size // 2
                halves = {}
                for name, segment in (("head", mono[:middle]), ("tail", mono[middle:])):
                    halves[name] = chroma_of(
                        segment,
                        mode=args.chroma,
                        gamma=args.gamma,
                        harmonic=args.harmonic,
                        aggregate=args.aggregate,
                        window_seconds=args.window_seconds,
                    )
                head_estimate = estimate_key(halves["head"], profile=args.profile)
                record["chroma_head"] = [round(float(value), 6) for value in halves["head"]]
                record["chroma_tail"] = [round(float(value), 6) for value in halves["tail"]]
                record["key_head"] = str(head_estimate.key)
                record["margin_head"] = round(head_estimate.margin, 4)
            rows.append(record)
            if index % 50 == 0:
                print(f"  {index}/{len(tracks)}", file=sys.stderr, flush=True)

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        saved = out_root / f"keys-{stamp}.keys.jsonl"
        saved.parent.mkdir(parents=True, exist_ok=True)
        with saved.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"저장: {saved} · 크로마 {args.chroma} · 프로파일 {args.profile}"
            f" · gamma {args.gamma:g} · 배음 {args.harmonic:g} · 집계 {args.aggregate}"
            f"{f'({args.window_seconds:g}초 창)' if args.aggregate == 'median' else ''}"
            f" (실패·부재 {failed})\n"
        )

    if not rows:
        print("추정된 곡이 없다.", file=sys.stderr)
        return 1

    if args.harmonic_sweep:
        return _report_harmonic_sweep(rows, args.profile)

    total = len(rows)
    correlations = np.asarray([float(str(row["correlation"])) for row in rows])
    margins = np.asarray([float(str(row["margin"])) for row in rows])

    def parse(text: str) -> Key:
        tonic, mode = str(text).rsplit(" ", 1)
        return Key(tonic=tonic, mode=Mode(mode))

    keys = [parse(str(row["key"])) for row in rows]
    runner_ups = [parse(str(row["runner_up"])) for row in rows]

    modes: Counter[str] = Counter(key.mode.value for key in keys)
    tonics: Counter[str] = Counter(key.tonic for key in keys)
    is_relative = [relative_key(key) == other for key, other in zip(keys, runner_ups, strict=True)]
    ambiguous_flags = margins < KEY_MARGIN_FLOOR
    relative_confusions = sum(is_relative)
    # **애매함의 원인은 애매한 곡 안에서 재야 한다** (D-0057). 전체 대비로 재면
    # 확신도 높은 곡의 2등까지 섞여 희석된다 — 분모가 틀린 지표였다.
    ambiguous_relative = sum(
        1 for flag, rel in zip(ambiguous_flags, is_relative, strict=True) if flag and rel
    )

    print(f"곡 {total}개\n")
    print("선법")
    for mode, count in modes.most_common():
        print(f"  {mode:<6} {count:5d}  {count / total:6.1%}")

    black = sum(1 for key in keys if key.tonic in BLACK_KEYS)
    print(f"  검은건반 으뜸음  {black:5d}  {black / total:6.1%}   ← O-23 핵심 지표")

    print("\n조성 교차표 (으뜸음 / 선법)")
    print(f"  {'':<4}{'major':>7}{'minor':>7}{'합계':>7}")
    for tonic, _ in tonics.most_common():
        major = sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MAJOR)
        minor = sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MINOR)
        print(f"  {tonic:<4}{major:>7}{minor:>7}{major + minor:>7}")

    # **베이스라인도 같은 프로파일로 잰다** (D-0059). 하한이 프로파일마다 달라
    # (Krumhansl 0.6192 · Temperley 0.5488) 고정값을 쓰면 비교가 성립하지 않는다.
    base_profile = str(rows[0].get("profile", "krumhansl"))
    base_correlation, base_margin = random_baseline(profile=base_profile, harmonic=args.harmonic)
    print("\n지표 대 무작위 베이스라인")
    print(f"  {'':<10}{'코퍼스':>10}{'무작위':>10}{'차이':>10}")
    for name, actual, base in (
        ("상관", correlations, base_correlation),
        ("격차", margins, base_margin),
    ):
        gap = float(np.median(actual) - np.median(base))
        print(
            f"  {name:<10}{float(np.median(actual)):>10.4f}"
            f"{float(np.median(base)):>10.4f}{gap:>+10.4f}"
        )

    ambiguous = int(ambiguous_flags.sum())
    base_ambiguous = float((base_margin < KEY_MARGIN_FLOOR).mean())
    print(
        f"\n애매({KEY_MARGIN_FLOOR} 미만)  코퍼스 {ambiguous / total:.1%}"
        f"  무작위 {base_ambiguous:.1%}"
    )
    print(f"2등이 나란한조 — 전체 대비          {relative_confusions / total:.1%}")
    if ambiguous:
        print(
            f"2등이 나란한조 — 애매한 곡 안에서   {ambiguous_relative / ambiguous:.1%}"
            f"  ({ambiguous_relative}/{ambiguous})"
        )

    # **`if row.get(...)`를 쓰지 않는다.** 0.0이 거짓이라 정확히 0센트인 곡이
    # 통째로 빠진다 — D-0057에서 분모 오류를 적어놓고 같은 세션에 또 냈다.
    tunings = [float(str(row["tuning_cents"])) for row in rows if "tuning_cents" in row]
    if tunings:
        array = np.asarray(tunings)
        off = int((np.abs(array) > 10).sum())
        print(
            f"\n조율 편차  중앙값 {float(np.median(array)):+.1f}센트 · "
            f"|편차|>10센트 {off}곡 ({off / len(tunings):.1%})"
        )

    print("\n--- 읽는 법 ---")
    print("상관·격차가 무작위와 비슷하면 그 지표는 판별력이 없다. 절대값에 속지 않는다.")
    print("2등이 나란한조인 비율이 높으면 애매함은 K-S의 원리적 한계다 (고칠 수 없다).")
    print("낮으면 크로마 추출이나 프로파일 쪽 문제이므로 고칠 여지가 있다.")
    print("**맞다는 증명은 아니다. 틀렸다는 신호를 잡는 장치다 (O-22).**")
    return 0


def _run_generate_midi(args: argparse.Namespace) -> int:
    """참조곡 구조를 조건으로 MIDI를 만든다 (D-0052).

    참조를 주지 않으면 코퍼스에서 시드로 골라 쓴다. **형용사가 아니라 실제 곡이
    조건이라는 것**이 주기능의 핵심이며(D-0011), 여기서 처음으로 그 경로가 선다.
    """
    import random

    from hathor.application.orchestrator.generation_pipeline import render
    from hathor.domain.services.lyrics_segmentation import split_segments
    from hathor.domain.services.song_structure import extract_pattern

    songs: list[tuple[str, list[str]]] = []
    for track in JsonlScanStore(Path(args.scan_out)).read_tracks():
        segments = split_segments(track.tags.lyrics_text)
        if len(segments) >= 2:
            songs.append((track.source_key, segments))
    if not songs:
        print("가사 구간이 있는 곡이 없다. --scan-out 경로를 확인한다.", file=sys.stderr)
        return 1

    if args.reference:
        chosen = [
            song
            for song in songs
            if any(needle.lower() in song[0].lower() for needle in args.reference)
        ]
        if not chosen:
            print(f"참조곡을 찾지 못했다: {args.reference}", file=sys.stderr)
            return 1
    else:
        # 참조가 없으면 시드로 고른다. 무작위가 아니라 시드 함수여야 재현된다.
        chosen = [random.Random(args.seed).choice(songs)]

    if len(chosen) > args.max_references:
        # D-0011이 참조곡을 1~5개로 정했다. 33곡 평균은 퓨전이 아니라 코퍼스
        # 평균에 가까워진다 — D-0029의 "coverage 1.0은 필터다"와 같은 함정이다.
        print(
            f"참조곡이 {len(chosen)}개다. 상한은 {args.max_references}개다 (D-0011).",
            file=sys.stderr,
        )
        for listed, _ in chosen[:10]:
            print(f"  {listed[:70]}", file=sys.stderr)
        if len(chosen) > 10:
            print(f"  ... 외 {len(chosen) - 10}곡", file=sys.stderr)
        print("--reference를 더 좁히거나 --max-references를 올린다.", file=sys.stderr)
        return 1

    references = [extract_pattern(segments) for _, segments in chosen]
    estimated_key, estimates = _estimate_key(args, [song[0] for song in chosen])
    output_key = _parse_key(args.key) if args.key else estimated_key
    harmony_prior = _harmony_prior(estimates)
    job = GenerationJob(seed=args.seed, stages=_parse_stages(args.stages))
    data, summary = render(
        job,
        references,
        key=output_key,
        tempo_bpm=args.tempo,
        harmony_prior=harmony_prior,
    )

    args.midi.parent.mkdir(parents=True, exist_ok=True)
    args.midi.write_bytes(data)

    print("참조곡")
    for (source_key, _), pattern in zip(chosen, references, strict=True):
        estimate = estimates.get(source_key)
        tag = ""
        if estimate is not None:
            flag = " (애매)" if estimate.margin < KEY_MARGIN_FLOOR else ""
            tag = f"  [{estimate.key}{flag}]"
        print(f"  {pattern.as_text():<20} {source_key[:52]}{tag}")
    conditioned = "참조곡 반영" if summary["harmony_conditioned"] else "시드만"
    print(
        f"\n구조 {summary['structure']} / 화성 {' '.join(summary['harmony'])} ({conditioned}) / "
        f"{summary['key']} {summary['tempo_bpm']}BPM"
    )
    print(
        f"{summary['bars']}마디 · {summary['notes']}음 · "
        f"{summary['duration_seconds']}초 · {summary['bytes']}바이트"
    )
    print(f"MIDI: {args.midi}")
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
    use_case: ExtractFeatures | ExtractLayerFeatures,
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


def _parse_feature_stores(raw: list[str] | None, fallback: Path) -> list[tuple[str, Path]]:
    """`--features` 값을 (이름, 경로) 목록으로 만든다.

    하나뿐이면 이름을 비워 키를 그대로 쓴다. 기존 단일 저장소 사용법이 그대로
    유지된다. 둘 이상이면 두 저장소가 모두 `mixture` 키를 갖고 있어 충돌하므로
    이름을 강제하고 키를 `이름:mixture`로 네임스페이스한다.
    """
    if not raw:
        return [("", fallback)]
    parsed: list[tuple[str, Path]] = []
    for entry in raw:
        name, separator, path = entry.partition("=")
        if separator:
            parsed.append((name.strip(), Path(path)))
        else:
            parsed.append(("", Path(entry)))
    if len(parsed) > 1 and any(not name for name, _ in parsed):
        raise SystemExit("저장소를 둘 이상 줄 때는 전부 `이름=경로` 형식이어야 한다")
    names = [name for name, _ in parsed]
    if len(set(names)) != len(names):
        raise SystemExit("저장소 이름이 중복됐다")
    return parsed


def _namespaced(name: str, key: str) -> str:
    return f"{name}:{key}" if name else key


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

    stores = _parse_feature_stores(args.features, args.out)
    merged: dict[str, dict[str, object]] = {}
    coverage: dict[str, int] = {}
    for name, root in stores:
        store = NpzFeatureStore(root)
        if not store.index_path.exists():
            print(f"특징 인덱스가 없다: {store.index_path}", file=sys.stderr)
            return 2
        seen: set[str] = set()
        for source_key, vectors in store.iter_vectors():
            if source_key in seen:
                # O-7의 재발이다. 중복을 조용히 흡수하면 유사도 행렬에 같은 곡이
                # 여러 번 들어가 지표가 틀어진 채로 그럴듯한 숫자를 낸다.
                print(f"인덱스에 중복 키가 있다: {source_key} ({root})", file=sys.stderr)
                print("먼저 `hathor ingest compact`로 정리한다.", file=sys.stderr)
                return 2
            seen.add(source_key)
            slot = merged.setdefault(source_key, {})
            for key, vector in vectors.items():
                slot[_namespaced(name, key)] = vector
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
    gate = report.config.gate
    # **R@10 하나로 가르면 경계에서 틀린다.** BGE-M3 홀짝 조건이 실패 순위 중앙값
    # 5.5인데 R@10 0.9442로 0.95에 못 미쳐 "상위권에도 없다"로 보고됐다 (D-0046).
    # 순위 중앙값이 k 안에 있으면 그것만으로 근접 실패다.
    near_miss = consistency.recall_at_10 >= gate or 0 < consistency.miss_median_rank <= (
        report.config.k
    )
    if near_miss:
        return (
            f"M0 게이트 미달 (top-1 {report.self_consistency:.4f}). "
            f"다만 R@10 {consistency.recall_at_10:.4f}, 실패 순위 중앙값 "
            f"{consistency.miss_median_rank:.1f}(무작위 {consistency.random_median_rank:.1f})다. "
            "정답이 상위권에 있으므로 표현이 무너진 것이 아니라 top-1을 못 넘는 것이다. "
            "추출 설정을 갈아엎기 전에 무엇이 부족한지부터 본다."
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


def _run_eval_layers(args: argparse.Namespace) -> int:
    """MERT 은닉 레이어별 특징을 뽑는다 (O-8, D-0025).

    스템 분리를 하지 않으므로 1004곡 배치가 6~7시간이 아니라 1시간 안팎이다.
    레이어별로 추출을 반복하지 않는다. 한 번의 추론에서 전 레이어가 나온다.
    """
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    try:
        indices = tuple(int(token) for token in args.layers.split(",") if token.strip())
    except ValueError:
        print("--layers는 쉼표로 구분한 정수여야 한다", file=sys.stderr)
        return 2
    if not indices:
        print("--layers에 레이어를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.features or args.out / DEFAULT_LAYERS_DIRNAME)
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

            extractor = MertFeatureExtractor(layers=indices)
            invalid = [index for index in indices if not 0 <= index < extractor.layer_count]
            if invalid:
                print(
                    f"레이어 인덱스가 범위를 벗어났다: {invalid} (0 ~ {extractor.layer_count - 1})",
                    file=sys.stderr,
                )
                return 2
            print(
                f"레이어 {','.join(str(index) for index in indices)} + mixture(마지막) 저장",
                flush=True,
            )
            use_case = ExtractLayerFeatures(
                FfmpegAudioDecoder(),
                extractor,
                _resolve_root(args.root),
            )
            return _drive_extraction(use_case, store, tracks, seconds_per_track=4.0)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3


def _format_track(source_key: str, tags: Mapping[str, TrackTags]) -> str:
    """`아티스트 — 제목` 형태. 태그가 없으면 경로를 그대로 쓴다."""
    tag = tags.get(source_key)
    if tag is None:
        return source_key
    artist = tag.artist or "(아티스트 없음)"
    title = tag.title or source_key
    return f"{artist} — {title}"


def _run_taste_compare(args: argparse.Namespace) -> int:
    """쌍대비교 문항을 내고 응답을 기록한다 (O-10, D-0012).

    이번 단계는 **무작위 쌍만** 낸다. 적응적 선택은 모델이 있어야 성립하고,
    모델로 고른 쌍으로 평가하면 시험 분포가 모델에 의존한다. 무작위 쌍을
    고정 평가 집합으로 먼저 확보한다.
    """
    from hathor.domain.entities.preference_comparison import PreferenceComparison, Side
    from hathor.domain.services.pair_sampling import presentation_order, sample_pairs
    from hathor.infrastructure.jsonl_preference_store import JsonlPreferenceStore
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    tags = {track.source_key: track.tags for track in JsonlScanStore(args.out).read_tracks()}
    if not tags:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    features = NpzFeatureStore(args.features or args.out / DEFAULT_LAYERS_DIRNAME)
    if not features.index_path.exists():
        print(f"특징 인덱스가 없다: {features.index_path}", file=sys.stderr)
        return 2
    # 임베딩이 없는 곡은 출제하지 않는다. 응답을 받아도 모델에 못 쓴다.
    keys = sorted({str(record["source_key"]) for record in features.read_records()} & set(tags))
    if len(keys) < 2:
        print("출제할 수 있는 곡이 둘 미만이다", file=sys.stderr)
        return 2

    store = JsonlPreferenceStore(args.out)
    answered = list(store.read_all())
    pairs = sample_pairs(
        keys,
        args.count,
        seed=args.seed + len(answered),
        exclude=[(item.left, item.right) for item in answered],
    )
    if not pairs:
        print("낼 수 있는 새 문항이 없다")
        return 0

    print(f"곡 {len(keys)}개 / 기록된 응답 {len(answered)}건 / 이번 문항 {len(pairs)}개")
    print("1 또는 2로 답한다. s=건너뛰기, q=중단. 답할 때마다 즉시 저장된다.\n")

    recorded = 0
    for index, pair in enumerate(pairs, 1):
        first, second = presentation_order(pair, seed=args.seed + index)
        print(f"[{index}/{len(pairs)}]")
        print(f"  1) {_format_track(first, tags)}")
        print(f"  2) {_format_track(second, tags)}")
        try:
            answer = input("  > ").strip().lower()
        except EOFError:
            answer = "q"
        if answer == "q":
            print("\n중단한다. 여기까지 저장됐다.")
            break
        if answer == "1":
            winner = Side.LEFT if first == pair[0] else Side.RIGHT
        elif answer == "2":
            winner = Side.LEFT if second == pair[0] else Side.RIGHT
        else:
            winner = None
        store.append(
            PreferenceComparison(
                left=pair[0],
                right=pair[1],
                winner=winner,
                recorded_at=datetime.now(UTC).isoformat(),
                mode="random",
            )
        )
        recorded += 1
        print()

    summary = store.counts()
    print(
        f"이번 세션 {recorded}건 기록. 누적 {summary['total']}건 "
        f"(응답 {summary['answered']}, 건너뜀 {summary['skipped']})"
    )
    print(f"저장: {store.path}")
    return 0


def _run_taste_status(args: argparse.Namespace) -> int:
    from hathor.infrastructure.jsonl_preference_store import JsonlPreferenceStore

    store = JsonlPreferenceStore(args.out)
    summary = store.counts()
    if summary["total"] == 0:
        print(f"기록된 응답이 없다: {store.path}")
        return 0
    print(f"누적 {summary['total']}건 (응답 {summary['answered']}, 건너뜀 {summary['skipped']})")
    for key, value in sorted(summary.items()):
        if key.startswith("mode:"):
            print(f"  {key[5:]}: {value}건")
    print(f"저장: {store.path}")
    return 0


def _load_search_tracks(args: argparse.Namespace, keys: tuple[str, ...]) -> list[SearchTrack]:
    """스캔 태그와 임베딩을 합쳐 검색 대상을 만든다."""
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    tags = {track.source_key: track.tags for track in JsonlScanStore(args.out).read_tracks()}
    if not tags:
        raise FileNotFoundError(f"스캔 산출물이 없다: {args.out}")

    store = NpzFeatureStore(args.features or args.out / DEFAULT_LAYERS_DIRNAME)
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


def _resolve_seed(query: str, tracks: list[SearchTrack]) -> str:
    """검색어로 시드곡 하나를 특정한다.

    여러 곡이 걸리면 고르지 않고 후보를 보여준 뒤 멈춘다. 임의로 하나를
    집으면 사용자가 의도하지 않은 곡으로 퓨전이 되고, 결과를 봐도
    무엇이 잘못됐는지 알 수 없다.
    """
    needle = query.strip().casefold()
    if not needle:
        raise ValueError("빈 검색어는 쓸 수 없다")
    matches = [
        track
        for track in tracks
        if needle in track.label.casefold() or needle in track.source_key.casefold()
    ]
    if not matches:
        raise LookupError(f"'{query}'에 맞는 곡이 없다")
    if len(matches) > 1:
        exact = [track for track in matches if (track.title or "").casefold() == needle]
        if len(exact) != 1:
            preview = "\n".join(f"    {track.label}" for track in matches[:8])
            more = f"\n    ... 외 {len(matches) - 8}곡" if len(matches) > 8 else ""
            raise LookupError(f"'{query}'에 {len(matches)}곡이 걸린다:\n{preview}{more}")
        matches = exact
    return matches[0].source_key


def _run_search(args: argparse.Namespace) -> int:
    """시드곡 조합으로 유사곡을 찾는다 (D-0011).

    생성 없이 퓨전 개념을 검증한다. 조합 중점이 그럴듯한 곡을 가리키지
    않으면 생성 단계의 시드 조건도 성립하지 않는다.
    """
    if not args.like:
        print("--like로 시드곡을 최소 하나 지정해야 한다", file=sys.stderr)
        return 2
    keys = tuple(token.strip() for token in args.keys.split(",") if token.strip())
    if not keys:
        print("--keys에 임베딩 키를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2

    try:
        tracks = _load_search_tracks(args, keys)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not tracks:
        print("검색할 수 있는 곡이 없다", file=sys.stderr)
        return 2

    try:
        seeds = [_resolve_seed(query, tracks) for query in args.like]
    except (LookupError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if len(set(seeds)) != len(seeds):
        print("같은 곡을 시드로 두 번 지정했다", file=sys.stderr)
        return 2

    labels = {track.source_key: track.label for track in tracks}
    mode = "원본" if args.raw else "중심화"
    fusion = f" / 결합 {args.fusion}" if len(seeds) > 1 else ""
    print(f"코퍼스 {len(tracks)}곡 / 뷰 {'+'.join(keys)} / {mode}{fusion}")
    for seed in seeds:
        print(f"  시드  {labels[seed]}")
    print()

    hits = SearchSimilar(
        keys,
        centered=not args.raw,
        fusion=FusionMode(args.fusion),
        penalty=args.penalty,
    ).run(tracks, seeds, args.k)
    for hit in hits:
        detail = ""
        if len(seeds) > 1:
            detail = "  (" + " / ".join(f"{value:.3f}" for value in hit.per_seed) + ")"
        print(f"  {hit.rank:>2}. {hit.similarity:.4f}  {hit.label}  [반복 {hit.highlight}]{detail}")
    print()
    print("[반복 m:ss]는 곡 안에서 반복도가 가장 높은 구간이다. 후렴이라는 보장은 없다.")
    return 0


def _run_eval_fusion(args: argparse.Namespace) -> int:
    """시드 결합 규칙을 같은 쌍으로 비교한다 (M4, D-0033).

    한 사례를 눈으로 보고 규칙을 고르면 다른 조합에서 더 나빠져도 알 수 없다.
    """
    from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore

    keys = tuple(token.strip() for token in args.keys.split(",") if token.strip())
    if not keys:
        print("--keys에 임베딩 키를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2
    try:
        tracks = _load_search_tracks(args, keys)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    use_case = EvaluateFusion(
        keys,
        centered=not args.raw,
        k=args.k,
        pairs=args.pairs,
        seed=args.seed,
        penalty=args.penalty,
    )
    try:
        report = use_case.run(tracks, list(FusionMode))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"곡 {report.tracks}개 / 시드 쌍 {report.scores[0].pairs}개 / 상위 {report.k}")
    print("  규칙        시드아티스트비율  아티스트불균형  코사인불균형  평균유사도")
    for score in report.scores:
        cosine = (
            "     —"
            if score.cosine_imbalance != score.cosine_imbalance
            else (f"{score.cosine_imbalance:>13.4f}")
        )
        similarity = (
            "     —"
            if score.mean_similarity != score.mean_similarity
            else (f"{score.mean_similarity:>12.4f}")
        )
        print(
            f"  {score.mode:<11} {score.coverage:>13.4f} {score.artist_imbalance:>15.4f}"
            f" {cosine} {similarity}"
        )
    print()
    print("불균형은 낮을수록, 시드아티스트비율은 높을수록 좋다.")
    print("균형만 좋고 비율이 낮으면 두 시드 모두에서 먼 밋밋한 곡을 고른 것이다.")
    print("random은 하한, oracle은 코퍼스 구성상 도달 가능한 상한이다.")
    path = JsonEvaluationStore(args.out).write(report.as_record(), f"fusion-k{args.k}")
    print(f"리포트: {path}")
    return 0


def _run_eval_harmony_prior(args: argparse.Namespace) -> int:
    """화성 도수 사전이 참조곡 고유 정보를 담는지 판정한다 (O-21 · D-0062).

    **생성물을 채점하지 않는다.** "생성된 진행이 참조곡 크로마와 맞는가"는 조건화가
    질 수 없는 지표이며, 코퍼스 전역 베이스라인이 정의상 진다. 곡을 앞뒤로 갈라
    뒷반쪽을 홀드아웃으로 두면 네 선이 전부 질 수 있다.

    저장된 반쪽 크로마만 읽으므로 **음원도 GPU도 필요 없다** — 광인사에서 돈다.
    """
    import json

    from hathor.domain.services.harmony_prior import (
        HalfChroma,
        PriorCondition,
        compare_priors,
    )
    from hathor.domain.value_objects.key import PITCH_CLASSES

    with args.replay.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]

    observations: list[HalfChroma] = []
    for row in rows:
        head, tail, key_text = row.get("chroma_head"), row.get("chroma_tail"), row.get("key_head")
        if head is None or tail is None or key_text is None:
            continue
        tonic = str(key_text).rsplit(" ", 1)[0]
        observations.append(
            HalfChroma(
                source_key=str(row.get("source_key", "")),
                tonic_pitch_class=PITCH_CLASSES.index(tonic),
                margin=float(row.get("margin_head", 0.0)),
                head=tuple(float(value) for value in head),
                tail=tuple(float(value) for value in tail),
            )
        )

    if len(observations) < 2:
        print(
            f"반쪽 크로마가 있는 곡이 {len(observations)}개다. "
            "`ingest keys --halves`로 먼저 추출한다.",
            file=sys.stderr,
        )
        return 1

    condition = PriorCondition(
        harmonic=args.harmonic,
        smoothing=args.smoothing,
        margin_floor=args.margin_floor,
        confident_only=args.confident_only,
        seed=args.seed,
        blend_steps=args.blend_steps,
    )
    result = compare_priors(observations, condition)

    print(
        f"곡 {result.song_count}개 · 배음 {condition.harmonic:g} · 평활 {condition.smoothing:g}"
        f" · 애매 {result.ambiguous_count}곡(격차<{condition.margin_floor:g})"
        f"{' · 애매 제외' if condition.confident_only else ''}\n"
    )

    header = f"{'선':<10}{'중앙값 CE':>12}{'코퍼스 대비':>14}{'포착 비율':>12}{'곡 단위 승률':>14}"
    print(header)
    print("-" * 64)
    lines = (
        ("uniform", result.uniform_score, None),
        ("corpus", result.corpus_score, None),
        ("other", result.other_score, result.other_win_rate),
        ("self", result.self_score, result.self_win_rate),
        ("oracle", result.oracle_score, None),
    )
    for name, score, win_rate in lines:
        gap = score - result.corpus_score
        share = "-" if win_rate is None else f"{win_rate:.1%}"
        captured = result.captured_share(score)
        print(f"{name:<10}{score:>12.4f}{gap:>+14.4f}{captured:>12.1%}{share:>14}")
    print(f"\n달성 가능 폭 (uniform → oracle): {result.uniform_score - result.oracle_score:.4f}")

    print("\nλ 곡선 (자기 반쪽 혼합 비율 → 중앙값 CE)")
    for weight, score in zip(result.lambdas, result.self_curve, strict=True):
        marker = "  ←" if weight == result.best_lambda else ""
        print(f"  {weight:>4.2f}  {score:.4f}{marker}")

    verdict = "정보 있음" if result.is_conditioning_informative else "정보 없음"
    ratio = result.null_gain / result.self_gain if result.self_gain > 0 else float("inf")
    print(f"\nλ*      = {result.best_lambda:.2f}  낙폭 {result.self_gain:.4f}")
    print(
        f"귀무 λ* = {result.null_lambda:.2f}  낙폭 {result.null_gain:.4f}  (자기선의 {ratio:.1%})"
    )
    print(f"판정: **{verdict}**")

    print("\n--- 읽는 법 ---")
    print("λ*가 판정이다. 0이면 참조곡이 코퍼스 평균에 보탤 것이 없고 O-21의 크로마")
    print("접근을 기각한다. 0보다 크면 그 값이 곧 생성기의 혼합 계수다.")
    print("**귀무 λ*가 0이 아닌 것 자체는 이상이 아니다** (D-0065). 곡끼리 독립인 합성")
    print("자료에서도 0.1이 나온다. 볼 것은 위치가 아니라 낙폭이며, 자기선의 낙폭에 비해")
    print("작아야 한다. 비율이 크면 자기선의 이득도 곡 고유성이 아닐 수 있다.")
    print("`uniform`은 천장이 아니다. 구조가 없으면 균등이 최적이라 코퍼스가 진다.")
    print("**포착 비율이 크기다** (D-0063). 격차의 절대값은 크로마가 평평하면 어차피 작다.")
    print("`oracle`은 뒷반쪽으로 뒷반쪽을 맞힌 값이며 어떤 선도 이보다 낮을 수 없다.")
    print("중앙값이라 절대값의 부호는 뜻이 없다. 같은 곡 집합 안의 선끼리만 비교한다.")
    return 0


def _run_lyrics_structure(args: argparse.Namespace) -> int:
    """코퍼스의 곡 구조 분포를 실측한다 (D-0049).

    **지표를 먼저 만든다.** 생성한 구조가 그럴듯한지는 절대 기준이 없으나,
    코퍼스 분포 안에 드는지는 잴 수 있다. 그 분포가 여기서 나온다.

    임계값 0.5는 근거로 정한 값이 아니므로 `--sweep`으로 민감도를 함께 본다.
    하나의 값에서 나온 분포로 결론내면 그 값이 결론에 섞인다.
    """
    from hathor.domain.services.lyrics_segmentation import split_segments
    from hathor.domain.services.song_structure import extract_pattern, summarize

    store = JsonlScanStore(Path(args.out))
    songs: list[tuple[str, list[str]]] = []
    for track in store.read_tracks():
        segments = split_segments(track.tags.lyrics_text)
        if len(segments) >= 2:
            songs.append((track.source_key, segments))

    if not songs:
        print("가사 구간이 있는 곡이 없다. --out 경로를 확인한다.", file=sys.stderr)
        return 1

    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7] if args.sweep else [args.threshold]
    print(f"곡 {len(songs)}개\n")

    for threshold in thresholds:
        patterns = [extract_pattern(segments, threshold=threshold) for _, segments in songs]
        stats = summarize(patterns)
        all_unique = sum(1 for pattern in patterns if pattern.repeat_ratio == 0.0)
        all_repeat = sum(1 for pattern in patterns if pattern.repeat_ratio == 1.0)
        print(
            f"임계 {threshold:.1f}  평균 구간 {stats.mean_length:5.2f}  "
            f"평균 반복비율 {stats.mean_repeat_ratio:.4f}  "
            f"반복 없음 {all_unique:4d}곡 ({all_unique / len(songs):5.1%})  "
            f"전부 반복 {all_repeat:3d}곡"
        )

    threshold = thresholds[-1] if not args.sweep else args.threshold
    patterns = [extract_pattern(segments, threshold=threshold) for _, segments in songs]
    stats = summarize(patterns)

    print(f"\n--- 임계 {threshold:.1f} 분포 ---")
    print("반복 비율 구간별 곡 수")
    for edge, count in stats.ratio_histogram:
        bar = "#" * max(1, round(count / len(songs) * 60))
        print(f"  {edge:.1f}~  {count:4d}  {bar}")

    print("\n예시")
    for key, segments in songs[: args.samples]:
        pattern = extract_pattern(segments, threshold=threshold)
        print(f"  {pattern.as_text():<24} {key[:56]}")

    print("\n반복이 없는 곡은 후렴이 없거나 임계가 너무 높은 것이다. 둘을 구분하려면")
    print("--sweep 결과에서 임계를 낮출 때 그 수가 줄어드는지 본다 (실측 필요).")
    return 0


def _run_lyrics_extract(args: argparse.Namespace) -> int:
    """가사 특징을 뽑는다 (가사축 착수).

    디코딩도 GPU도 없다. 스캔 산출물의 USLT 원문만 쓰므로 1004곡이 수 초다.
    """
    from hathor.application.extract_lyrics import ExtractLyrics
    from hathor.infrastructure.hashed_lyrics_extractor import HashedLyricsExtractor
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.features or args.out / DEFAULT_LYRICS_DIRNAME)
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

            try:
                sizes = tuple(int(token) for token in args.ngrams.split(",") if token.strip())
            except ValueError:
                print("--ngrams는 쉼표로 구분한 정수여야 한다", file=sys.stderr)
                return 2
            if not sizes or any(size < 1 for size in sizes):
                print("--ngrams는 1 이상의 정수를 최소 하나 포함해야 한다", file=sys.stderr)
                return 2

            encoder: object
            if args.encoder == "bge-m3":
                from hathor.infrastructure.bge_m3_lyrics_encoder import (
                    BgeM3LyricsEncoder,
                    verify_deterministic,
                )

                print(
                    f"BGE-M3 / {args.device} / 배치 {args.batch_size} / 풀링 {args.pooling}",
                    flush=True,
                )
                encoder = BgeM3LyricsEncoder(
                    device=args.device, batch_size=args.batch_size, pooling=args.pooling
                )
                # 재현성 계층 1을 추출 전에 확인한다 (D-0009). 어긋난 산출물을
                # 1003곡 다 만든 뒤에 발견하면 전량이 버려진다.
                drift = verify_deterministic(encoder, list(_DETERMINISM_PROBE))
                print(f"결정론 검사 최대 편차 {drift:.3e}", flush=True)
                if drift > 0:
                    print(
                        "  경고: 같은 입력이 다른 값을 냈다. 산출물이 기기마다 달라진다.",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"해싱 / 차원 {args.dim} / n-gram {','.join(str(size) for size in sizes)}"
                    f"{' / 공백제거' if args.collapse_space else ''}"
                    f"{f' / 반복감쇠 {args.repeat_damping}' if args.repeat_damping else ''}",
                    flush=True,
                )
                encoder = HashedLyricsExtractor(
                    dim=args.dim,
                    sizes=sizes,
                    collapse_space=args.collapse_space,
                    repeat_damping=args.repeat_damping,
                )
            use_case = ExtractLyrics(encoder)
            segments = 0
            for features in use_case.run(tracks):
                store.write_track(features)
                segments += features.chunk_count

            summary_path = store.write_summary(
                {
                    "processed": use_case.processed,
                    "skipped": len(use_case.skipped),
                    "segments": segments,
                    "skips": [
                        {"source_key": key, "reason": reason} for key, reason in use_case.skipped
                    ],
                }
            )
            average = segments / use_case.processed if use_case.processed else 0.0
            print(f"성공 {use_case.processed}곡, 제외 {len(use_case.skipped)}곡")
            print(f"구간 합계 {segments} (곡당 평균 {average:.1f})")
            for key, reason in use_case.skipped[:5]:
                print(f"  제외 {key}: {reason}", file=sys.stderr)
            if len(use_case.skipped) > 5:
                print(f"  ... 외 {len(use_case.skipped) - 5}곡", file=sys.stderr)
            print(f"요약: {summary_path}")
            return 0
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3
