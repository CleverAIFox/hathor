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

from hathor.application.evaluate_retrieval import (
    DEFAULT_SEED,
)
from hathor.application.extract_features import ExtractFeatures
from hathor.application.orchestrator.generation_pipeline import DEFAULT_SECTIONS, run_dry
from hathor.application.resolve_identities import ResolveIdentities
from hathor.application.scan_library import ScanLibrary
from hathor.application.search_similar import SearchSimilar, SearchTrack
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.entities.resolution_record import ResolutionRecord
from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.domain.services.key_estimation import (
    HARMONIC_STRENGTH,
    KEY_MARGIN_FLOOR,
    PROFILE_TEMPERLEY,
    KeyEstimate,
)
from hathor.domain.services.midi_writer import DEFAULT_TEMPO_BPM
from hathor.domain.services.seed_search import FusionMode
from hathor.domain.services.stem_sets import (
    DEFAULT_STEM_SET,
    STEM_SETS,
)
from hathor.domain.value_objects.key import Key
from hathor.infrastructure.chroma_series_store import (
    find_series_root,
    load_transition_priors,
    write_series,
)
from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
from hathor.infrastructure.filesystem_scanner import FilesystemLibraryScanner
from hathor.infrastructure.jsonl_resolution_store import JsonlResolutionStore
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.infrastructure.keys_jsonl_store import (
    find_keys_store,
    load_stem_priors,
    load_tonics,
)
from hathor.infrastructure.musicbrainz_lookup import (
    MusicBrainzClient,
    MusicBrainzLookup,
)
from hathor.infrastructure.mutagen_tag_extractor import MutagenTagExtractor
from hathor.interfaces.cli import (
    eval_clap,
    eval_extract,
    eval_order,
    eval_output,
    eval_priors,
    eval_retrieval,
    eval_vocabulary,
    ingest_keys_bundles,
    ingest_onsets,
)
from hathor.interfaces.cli.doctor import run_doctor
from hathor.interfaces.cli.eval_log import recorded
from hathor.interfaces.cli.eval_output import report_harmonic_sweep
from hathor.interfaces.cli.eval_retrieval import load_search_tracks
from hathor.interfaces.cli.extraction import drive_extraction
from hathor.interfaces.cli.feature_sources import open_feature_source
from hathor.interfaces.cli.registry import (
    Command,
    Entry,
    Group,
    no_arguments,
    register,
    resolve,
)
from hathor.interfaces.cli.roots import (
    DEFAULT_FEATURE_DIRNAME,
    DEFAULT_LIBRARY_ROOT_ENV,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SEARCH_KEY,
    resolve_root,
)
from hathor.interfaces.cli.tables import ambiguity_report, parse_key, replay_refusal
from hathor.shared.config.paths import (
    LIBRARY_ROOT_ENV,
    load_dotenv,
    repo_root,
    resolve_path,
)

if TYPE_CHECKING:
    from hathor.domain.entities.track_tags import TrackTags


DEFAULT_CONTACT = "https://github.com/CleverAIFox/hathor"
DEFAULT_LYRICS_DIRNAME = "lyrics-hashed"
_DETERMINISM_PROBE = (
    # 한국어·영어·혼재 각 하나. 코퍼스 실측이 혼재 40%였으므로 세 경우를 다 밟는다.
    "사랑한다는 말은 하지 못했어",
    "i never said the words out loud",
    "돌아서는 순간 you were already gone",
)


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


def _build_generate(parser: argparse.ArgumentParser) -> None:
    """`hathor generate` 인자."""
    parser.add_argument("--seed", type=int, required=True, help="난수 시드 (GR-6.5)")
    parser.add_argument("--stages", type=str, default="structure,harmony")
    parser.add_argument("--dry-run", action="store_true", help="모델 없이 결정적 산출물만")
    parser.add_argument("--out", type=resolve_path, default=None, help="JSON 출력 경로")
    parser.add_argument("--midi", type=resolve_path, default=None, help="MIDI 출력 경로 (D-0052)")
    parser.add_argument(
        "--reference",
        action="append",
        default=None,
        help="참조곡 제목 일부. 여러 번 줄 수 있다. 그 곡의 구조를 조건으로 쓴다",
    )
    parser.add_argument(
        "--scan-out", type=resolve_path, default="var/ingest", help="스캔 산출물 루트"
    )
    parser.add_argument("--tempo", type=int, default=DEFAULT_TEMPO_BPM, help="템포 (BPM)")
    parser.add_argument("--sections", type=int, default=DEFAULT_SECTIONS, help="구간 수")
    parser.add_argument(
        "--root",
        type=resolve_path,
        default=None,
        help="라이브러리 루트. 조성 추정에 음원이 필요하다",
    )
    parser.add_argument(
        "--stem-set",
        default=DEFAULT_STEM_SET,
        help="화성 사전에 쓸 스템 조합. mix면 전체 믹스를 쓴다 (D-0074)",
    )
    parser.add_argument(
        "--transitions",
        action="store_true",
        help="배열도 참조곡을 따른다 (O-32 · D-0110). 시계열 산출물이 있어야 한다",
    )
    parser.add_argument(
        "--series",
        type=resolve_path,
        default=None,
        help="시계열 폴더. 생략하면 var/ingest에서 가장 최근 것을 찾는다",
    )
    parser.add_argument(
        "--priors",
        type=resolve_path,
        default=None,
        help="스템 크로마 산출물 경로. 생략하면 var/ingest에서 가장 최근 것을 찾는다",
    )
    parser.add_argument(
        "--key",
        help='출력 조성을 고정한다 (예: "C major"). 참조곡 화성 조건화는 그대로 걸린다. '
        "조성 차이를 뺀 채 화성만 비교해 들을 때 쓴다",
    )
    parser.add_argument(
        "--no-key-estimation",
        action="store_true",
        help="조성 추정을 끄고 C장조를 쓴다. 음원 없이 돌릴 때. 화성 조건화도 함께 꺼진다",
    )
    parser.add_argument("--max-references", type=int, default=5, help="참조곡 상한 (D-0011)")
    parser.add_argument(
        "--chroma", choices=("cq", "linear"), default="cq", help="조성 추정 크로마 방식"
    )


def _build_ingest_keys(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest keys` 인자."""
    parser.add_argument("--out", type=resolve_path, default="var/ingest", help="스캔 산출물 루트")
    parser.add_argument("--root", type=resolve_path, default=None, help="라이브러리 루트")
    parser.add_argument(
        "--chroma",
        choices=("cq", "linear"),
        default="cq",
        help="크로마 방식. linear는 D-0056 이전 베이스라인이다",
    )
    parser.add_argument("--limit", type=int, default=None, help="앞에서 N곡만")
    ingest_keys_bundles.add_argument(parser)
    parser.add_argument(
        "--replay",
        type=resolve_path,
        default=None,
        help="저장된 keys.jsonl을 재분석. 디코딩하지 않는다",
    )
    parser.add_argument(
        "--tuning",
        action="store_true",
        help="조율 편차도 잰다 (D-0057). 11배 느려지므로 표본에만 쓴다",
    )
    parser.add_argument(
        "--profile",
        choices=("krumhansl", "temperley"),
        default=PROFILE_TEMPERLEY,
        help="조성 프로파일. temperley가 기본이다 (D-0201)",
    )
    parser.add_argument(
        "--gamma", type=float, default=0.0, help="로그 압축. 0이 끔이며 기본이다 (D-0058)"
    )
    parser.add_argument(
        "--harmonic",
        type=float,
        default=HARMONIC_STRENGTH,
        help=f"배음 감산 강도. 기본 {HARMONIC_STRENGTH:g} (D-0201)",
    )
    parser.add_argument(
        "--harmonic-sweep",
        action="store_true",
        help="배음 강도 0~1을 한 번에 훑어 표로 낸다 (D-0060). --replay와 함께 쓴다",
    )
    parser.add_argument(
        "--series",
        type=float,
        default=None,
        metavar="초",
        help="크로마 시계열을 이 창 길이로 함께 뽑아 npz에 저장한다 (O-32 · D-0105)",
    )
    parser.add_argument(
        "--halves",
        action="store_true",
        help="앞뒤 반쪽 크로마도 뽑는다 (D-0062). `eval harmony-prior`가 이것을 요구한다",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="타악을 분리하고 스템 조합별 크로마도 뽑는다 (O-27 (a) · D-0073). GPU 필요",
    )
    parser.add_argument(
        "--aggregate",
        choices=("mean", "median"),
        default="mean",
        help="전곡을 한 번에 변환할지(mean) 창별 중앙값을 낼지(median). O-27 후보 (b) · D-0065",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=10.0,
        help="--aggregate median의 창 길이(초)",
    )


def _build_ingest_scan(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest scan` 인자."""
    parser.add_argument(
        "--root",
        type=resolve_path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리"
    )
    parser.add_argument("--force", action="store_true", help="델타 감지를 건너뛰고 전수 재스캔")
    parser.add_argument(
        "--fail-threshold",
        type=float,
        default=0.05,
        help="실패율이 이 값을 넘으면 비정상 종료",
    )


def _build_ingest_resolve(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest resolve` 인자."""
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리"
    )
    parser.add_argument("--limit", type=int, default=None, help="처리할 곡 수 상한 (시험용)")
    parser.add_argument(
        "--contact",
        default=DEFAULT_CONTACT,
        help="User-Agent에 넣을 연락처. MB가 식별 가능한 값을 요구한다",
    )


def _build_ingest_all(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest all` 인자."""
    parser.add_argument("--root", type=resolve_path, default=None, help="라이브러리 루트")
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 루트")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    parser.add_argument("--force", action="store_true", help="끝난 곡도 다시 뽑는다")


def _build_ingest_features(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest features` 인자."""
    parser.add_argument(
        "--root",
        type=resolve_path,
        default=None,
        help=f"라이브러리 루트 (미지정 시 ${DEFAULT_LIBRARY_ROOT_ENV})",
    )
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리"
    )
    parser.add_argument("--limit", type=int, default=None, help="처리할 곡 수 상한 (시험용)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 추출된 곡도 다시 처리",
    )


def _build_ingest_compact(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest compact` 인자."""
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 디렉터리"
    )
    parser.add_argument(
        "--keep-missing",
        action="store_true",
        help="npz가 없는 기록도 남긴다 (기본은 버린다)",
    )
    parser.add_argument("--dry-run", action="store_true", help="쓰지 않고 결과만 보고한다")


def _build_taste_compare(parser: argparse.ArgumentParser) -> None:
    """`hathor taste compare` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--features",
        type=resolve_path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_FEATURE_DIRNAME})",
    )
    parser.add_argument("--count", type=int, default=20, help="이번 세션 문항 수")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="쌍 추출 시드")


def _build_taste_status(parser: argparse.ArgumentParser) -> None:
    """`hathor taste status` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")


def _build_lyrics_structure(parser: argparse.ArgumentParser) -> None:
    """`hathor lyrics structure` 인자."""
    parser.add_argument("--out", type=resolve_path, default="var/ingest", help="스캔 산출물 루트")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="반복 판정 자카드 하한. 근거로 정한 값이 아니다 (실측 필요)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="임계값을 0.3~0.7로 훑어 민감도를 본다. 하나의 값으로 결론내지 않기 위해서다",
    )
    parser.add_argument("--samples", type=int, default=5, help="예시로 보일 곡 수")


def _build_lyrics_extract(parser: argparse.ArgumentParser) -> None:
    """`hathor lyrics extract` 인자."""
    parser.add_argument(
        "--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="스캔 산출물 위치"
    )
    parser.add_argument(
        "--features",
        type=resolve_path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_LYRICS_DIRNAME})",
    )
    parser.add_argument(
        "--encoder",
        choices=("hashed", "bge-m3"),
        default="hashed",
        help="가사 인코더. hashed는 베이스라인이자 기본값이다 (D-0036 · D-0045)",
    )
    parser.add_argument("--device", default="cuda", help="bge-m3 추론 장치. GPU가 없으면 cpu")
    parser.add_argument("--batch-size", type=int, default=16, help="bge-m3 배치 크기")
    parser.add_argument(
        "--pooling",
        choices=("cls", "mean"),
        default="cls",
        help="bge-m3 풀링. cls는 모델의 dense 정의와 일치한다 (D-0046)",
    )
    parser.add_argument("--dim", type=int, default=1024, help="해싱 차원")
    parser.add_argument("--ngrams", default="2,3,4", help="문자 n-gram 크기 (쉼표 구분)")
    parser.add_argument(
        "--collapse-space",
        action="store_true",
        help="공백을 제거한다. `보고싶어`와 `보고 싶어`를 같게 본다",
    )
    parser.add_argument(
        "--repeat-damping",
        type=float,
        default=0.0,
        help="곡 안에서 반복되는 n-gram 감쇠 (0=없음, 1=곡내 문서빈도 역수)",
    )
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    parser.add_argument("--force", action="store_true", help="이미 추출된 곡도 다시 처리")


def _build_search(parser: argparse.ArgumentParser) -> None:
    """`hathor search` 인자."""
    parser.add_argument(
        "--like",
        action="append",
        default=None,
        metavar="검색어",
        help="시드곡. 아티스트·제목·경로 일부로 찾는다. 여러 번 주면 퓨전한다",
    )
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--features",
        type=resolve_path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_FEATURE_DIRNAME})",
    )
    parser.add_argument("--keys", default=DEFAULT_SEARCH_KEY, help="쓸 임베딩 키")
    parser.add_argument("-k", type=int, default=10, help="결과 개수")
    parser.add_argument(
        "--fusion",
        choices=[m.value for m in FusionMode],
        default=FusionMode.MEAN.value,
        help="시드 결합 규칙. min은 모든 시드와 가까울 것을 요구한다 (D-0033)",
    )
    parser.add_argument("--penalty", type=float, default=1.0, help="penalized 모드의 편차 계수")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="중심화를 끈다. 허브 곡이 어떤 질의에도 상위에 온다 (비교용)",
    )


def _build_setup(parser: argparse.ArgumentParser) -> None:
    """`hathor setup` 인자."""
    parser.add_argument("--force", action="store_true", help="이미 있는 값도 덮어쓴다")
    parser.add_argument("--dry-run", action="store_true", help="찾은 것만 보여주고 쓰지 않는다")


def build_parser() -> argparse.ArgumentParser:
    """등재표를 파서로 만든다. **이름은 표 한 곳에만 적힌다** (D-0273).

    예전에는 이 함수가 599줄이었고, 여기 적은 이름을 `main`과 `_dispatch_eval`이 손으로
    한 번 더 적었다. 어긋나면 argparse는 조용하고 **떨어지는 기본이 대신 돌았다** (D-0204).
    """
    parser = argparse.ArgumentParser(prog="hathor", description="HATHOR CLI")
    register(parser.add_subparsers(dest="command", required=True), entries())
    return parser


def main(argv: list[str] | None = None) -> int:
    # **`.env`를 여기서 읽는다** (D-0066). 이전에는 docker compose만 읽어서
    # `.env`에 음원 경로를 적어도 CLI에는 아무 영향이 없었다. 셸에 이미 있는
    # 값은 덮지 않으므로 한 번만 다르게 돌려 보는 것도 그대로 된다.
    load_dotenv()
    args = build_parser().parse_args(argv)
    runner = resolve(entries(), args)
    if args.command == "eval":
        # **찍은 것을 남긴다** (D-0250). 감싸는 자리가 하나이므로 하위 명령을 새로
        # 더해도 저절로 기록된다 — 여기 안 적어서 조용히 사라지는 일이 없다.
        with recorded(_eval_log_root(args), args.eval_command):
            return runner(args)
    return runner(args)


def _run_generate(args: argparse.Namespace) -> int:
    if args.midi is not None:
        return _run_generate_midi(args)
    if not args.dry_run:
        print("아직 dry-run 경로만 구현되어 있다 (P0). --dry-run을 사용한다.", file=sys.stderr)
        return 2

    job = GenerationJob(seed=args.seed, stages=_parse_stages(args.stages))
    payload = json.dumps(run_dry(job, args.sections), ensure_ascii=False, indent=2, sort_keys=True)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


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
        root = resolve_root(args.root)
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


def _run_env(args: argparse.Namespace) -> int:
    """해석된 경로를 찍는다. **기기를 옮기면 이것부터 본다** (D-0066)."""
    import os

    from hathor.shared.config.paths import PATCH_DIR_ENV

    root = repo_root()
    library = os.environ.get(LIBRARY_ROOT_ENV)
    patches = os.environ.get(PATCH_DIR_ENV)
    dotenv = root / ".env"

    print(f"저장소       {root}")
    print(f".env         {dotenv}{'' if dotenv.exists() else '  ← 없다. .env.example을 복사한다'}")
    print(f"음원 루트    {library or '(미설정) ← .env에 HATHOR_LIBRARY_ROOT를 적는다'}")
    if library and not Path(library).exists():
        print("             ← 경로가 없다. 드라이브 마운트를 확인한다")
    print(f"패치 폴더    {patches or '(미설정)'}")

    ingest = root / "var" / "ingest"
    keys = sorted(ingest.glob("*.keys.jsonl")) if ingest.exists() else []
    scans = sorted(ingest.glob("scan-*.jsonl")) if ingest.exists() else []
    print(f"산출물       {ingest}")
    print(f"  스캔 {len(scans)}건 · 조성 {len(keys)}건")
    for path in keys[-3:]:
        print(f"    {path.name}")
    return 0


def _run_setup(args: argparse.Namespace) -> int:
    """기기를 탐지해 `.env`를 쓴다. **기기당 한 번, 손으로 치지 않는다** (D-0068).

    윈도우 사용자 이름이 기기마다 다르고(광인사 `foxlo`, 리전 `Fox`) 음원 드라이브도
    다르다(`/mnt/d` · `/mnt/f`). **둘 다 탐지할 수 있는 것을 손으로 치게 했다.**

    이미 있는 값은 건드리지 않는다. `--force`로 덮는다.
    """
    from hathor.shared.config.paths import (
        PATCH_DIR_ENV,
        find_library_candidates,
        parse_dotenv,
        windows_user_dir,
    )

    root = repo_root()
    target = root / ".env"
    example = root / ".env.example"
    current = parse_dotenv(target.read_text(encoding="utf-8")) if target.exists() else {}

    print("기기를 살핀다...\n")

    user = windows_user_dir()
    patch_value = str(user / "Downloads") if user else ""
    if user:
        print(f"윈도우 사용자   {user.name}")
        print(f"패치 폴더       {patch_value}")
    else:
        print("윈도우 사용자   찾지 못했다 (WSL이 아닌가?)")

    candidates = find_library_candidates()
    library_value = str(candidates[0][0]) if candidates else ""
    if candidates:
        print("\n음원 폴더 후보 (바로 아래 파일 수)")
        for path, count in candidates[:5]:
            mark = "  ←" if str(path) == library_value else ""
            print(f"  {count:>6}곡  {path}{mark}")
    else:
        print("\n음원 폴더       찾지 못했다. 드라이브가 마운트돼 있는지 본다")

    chosen = {PATCH_DIR_ENV: patch_value, LIBRARY_ROOT_ENV: library_value}
    writable = {
        key: value
        for key, value in chosen.items()
        if value and (args.force or not current.get(key))
    }
    skipped = [key for key, value in chosen.items() if value and key in current and not args.force]

    print()
    if args.dry_run:
        for key, value in chosen.items():
            print(f"{key}={value or '(찾지 못했다)'}")
        print("\n--dry-run이라 쓰지 않았다.")
        return 0

    if not target.exists():
        if not example.exists():
            print("`.env.example`이 없다.", file=sys.stderr)
            return 1
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"{target.name}를 만들었다 (.env.example 복사)")

    lines = target.read_text(encoding="utf-8").splitlines()
    for key, value in writable.items():
        replaced = False
        for index, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[index] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            lines.insert(0, f"{key}={value}")
        print(f"  {key}={value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for key in skipped:
        print(f"  {key} 는 이미 있어 두었다 (--force로 덮는다)")

    if not library_value:
        print(f"\n\033[33m{LIBRARY_ROOT_ENV}를 못 채웠다. .env에 직접 적는다.\033[0m")
    print("\n다음:  make doctor")
    return 0


def _keys_settings(args: argparse.Namespace) -> dict[str, object]:
    """행에 적히는 조건 묶음. 이어받기 판정과 기록이 같은 값을 쓴다.

    **이것이 «이어받기가 같다고 볼 조건»이다** (D-0075). 하나라도 다르면 새 파일을 연다 —
    조건이 섞인 산출물은 무엇을 잰 것인지 알 수 없고, 그것이 D-0073에서 조건을 행에 적게
    만든 이유다. `limit`은 뺀다 — `--limit 200`으로 돌리다 전량으로 늘리는 것은 같은
    조건의 연장이다. **이 단락은 함수 위에 떠 있었고 파이썬이 버렸다** (D-0274).
    """
    return {
        # **`chroma`가 아니라 `chroma_mode`다.** 행에는 이미 `chroma`가 12차원
        # 벡터로 들어 있어 이름이 겹치면 조용히 덮이고, 그러면 이어받기가 영영
        # 안 걸린다. 실제로 그렇게 썼다가 잡았다.
        "chroma_mode": args.chroma,
        "profile": args.profile,
        "gamma": args.gamma,
        "harmonic": args.harmonic,
        "aggregate": args.aggregate,
        "separated": bool(args.separate),
        "halves": bool(args.halves),
        # **어떤 스템 조합을 뽑았는지가 조건이다** (D-0100). 예전에는 `separated`만
        # 있어서, `STEM_SETS`에 조합을 하나 더해도 "이미 전부 처리했다"로 건너뛰었다.
        # 실제로 D-0099가 `bass`를 더한 뒤 그 일이 났다 — **새 스템이 없는 파일에
        # 이어붙으려 했고, 없는 것을 찾다가 0곡이 됐다.**
        "stem_sets": sorted(STEM_SETS) if args.separate else [],
        # **시계열 창 길이도 조건이다** (D-0100). 다른 창으로 뽑은 산출물에
        # 이어붙으면 창 길이가 섞이고, 섞인 시계열은 무엇을 잰 것인지 알 수 없다.
        "series_seconds": args.series,
    }


BROKEN_LINE_TOLERANCE = 0.02
"""이어받을 때 견디는 깨진 줄 비율 (D-0077).

끊기면 **마지막 한 줄**이 잘려 있을 수 있고 그것은 정상이다. 그보다 많이 깨졌다면
동시 실행으로 줄이 섞였다는 뜻이며, **조용히 건너뛰면 49곡이 5곡으로 보인다.**
실제로 그렇게 됐고 그때는 파일이 이미 못 쓰게 된 뒤였다.
"""


class BatchLock:
    """산출물 디렉터리마다 하나만 돌게 한다 (D-0077).

    ### 왜 필요해졌나

    D-0075 이전에는 실행마다 새 타임스탬프 파일을 썼으므로 두 개가 동시에 돌아도
    겹치지 않았다. **같은 파일에 이어 쓰게 만든 순간 생긴 문제다.**

    `cd core`가 실패했는데도 뒤 명령이 실행돼 배치가 둘 떴고, 둘째가 첫째의 49곡을
    읽고 이어받아 **같은 파일에 동시에 append했다.** 줄이 섞여 파일이 깨졌다.

    ### 죽은 프로세스의 락은 자동으로 푼다

    락 파일에 PID를 적고, 그 PID가 살아 있지 않으면 가져간다. 그러지 않으면 강제
    종료 뒤 손으로 지워야 하고, **손으로 지우게 하면 결국 지우고 돌리게 된다.**

    **이것이 예외 안전을 대신한다.** 추출 도중 예외로 죽으면 락 파일이 남지만, 그
    PID는 이미 없으므로 다음 실행이 그냥 가져간다. `try/finally`로 감싸려면 본문
    전체를 들여써야 하고, 그 재들여쓰기가 이 함수에서는 위험이 더 크다.
    """

    def __init__(self, root: Path, name: str = "ingest-keys") -> None:
        self.path = root / f".{name}.lock"

    def _holder(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _alive(pid: int) -> bool:
        import os

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        return True

    def acquire(self) -> int | None:
        """잡으면 `None`, 이미 살아 있는 주인이 있으면 그 PID를 낸다."""
        import os

        self.path.parent.mkdir(parents=True, exist_ok=True)
        holder = self._holder()
        if holder is not None and holder != os.getpid() and self._alive(holder):
            return holder
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        return None

    def release(self) -> None:
        import os

        if self._holder() == os.getpid():
            self.path.unlink(missing_ok=True)


def _resume_target(out_root: Path, settings: dict[str, object]) -> tuple[Path, set[str], int]:
    """이어받을 파일과 이미 처리한 `source_key`를 낸다 (D-0075).

    **켜야 하는 옵션으로 두지 않는다.** `--resume`을 붙여야 이어받게 하면 붙이는 것을
    잊고, 잊으면 한 시간 반이 다시 사라진다. 조건이 같은 최근 파일이 있으면 그냥 잇고,
    조건이 하나라도 다르면 새 파일을 연다.

    깨진 줄은 건너뛴다. 중간에 끊기면 마지막 줄이 잘려 있을 수 있다.
    """
    import json
    from datetime import UTC, datetime

    # **후보가 열 개면 열 줄이 나온다** (D-0106). 가장 조건이 적게 다른 하나만 찍는다 —
    # 그것이 "무엇을 바꾸면 이어받는가"에 가장 가까운 답이다.
    skipped: list[tuple[str, list[str]]] = []
    if out_root.is_dir():
        for path in sorted(out_root.glob("keys-*.keys.jsonl"), reverse=True):
            done: set[str] = set()
            matched = False
            broken = 0
            total = 0
            try:
                with path.open(encoding="utf-8") as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        total += 1
                        try:
                            row = json.loads(line)
                        except ValueError:
                            broken += 1
                            continue  # 잘린 마지막 줄이면 정상, 많으면 손상이다
                        if not matched:
                            differing = [
                                key for key, value in settings.items() if row.get(key) != value
                            ]
                            if differing:
                                # **조용히 새 파일을 열지 않는다** (D-0100). 이어받기가
                                # 안 걸린 것을 모르면 한 시간 반을 다시 쓴다.
                                skipped.append((path.name, differing))
                                break
                            matched = True
                        source = row.get("source_key")
                        if source:
                            done.add(str(source))
            except OSError:
                continue
            if matched:
                return path, done, broken

    if skipped:
        name, differing = min(skipped, key=lambda entry: len(entry[1]))
        extra = f" (다른 후보 {len(skipped) - 1}개)" if len(skipped) > 1 else ""
        print(
            f"이어받지 않는다: {name} · 조건이 다르다 ({', '.join(differing)}){extra}",
            file=sys.stderr,
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return out_root / f"keys-{stamp}.keys.jsonl", set(), 0


def _resolve_harmony_prior(
    args: argparse.Namespace, source_keys: list[str], estimates: dict[str, KeyEstimate]
) -> tuple[tuple[float, ...] | None, str]:
    """화성 사전을 고른다. **스템 저장분이 있으면 그것을 쓴다** (D-0074).

    스템 크로마가 전체 믹스보다 세 배 낫다 — 조건화 이득이 K-K 폭 대비 14.1%에서
    44.3%로 올랐다 (D-0063 · D-0074, 200곡). 다만 **생성할 때 Demucs를 돌리지는
    않는다.** 미리 뽑아 둔 것을 조회하고, 없으면 전체 믹스로 물러난다.

    참조곡이 저장분에 하나도 없으면 전체 믹스를 쓴다. **일부만 있으면 그 일부만
    쓴다** — 섞으면 스템과 믹스가 한 사전 안에서 더해져 무엇을 재는지 알 수 없다.
    """
    from hathor.shared.config.paths import repo_root as _root

    if args.stem_set == "mix":
        return _harmony_prior(estimates), "전체 믹스"

    store = args.priors if args.priors else find_keys_store(_root(), args.stem_set)
    if store is not None and store.exists():
        table = load_stem_priors(store, args.stem_set)
        picked = [table[key] for key in source_keys if key in table]
        if picked:
            from hathor.domain.services.harmony_prior import merge_degree_priors

            if len(picked) < len(source_keys):
                print(
                    f"참조곡 {len(source_keys)}곡 중 {len(picked)}곡만 스템 저장분에 있다.",
                    file=sys.stderr,
                )
            merged = merge_degree_priors([(vector, tonic) for vector, tonic in picked])
            return tuple(float(value) for value in merged), f"{args.stem_set} 스템"
        print(
            f"참조곡이 스템 저장분에 없다. 전체 믹스로 물러난다: {store.name}",
            file=sys.stderr,
        )
    return _harmony_prior(estimates), "전체 믹스"


def _resolve_transition_prior(
    args: argparse.Namespace, source_keys: list[str]
) -> tuple[tuple[tuple[float, ...], ...] | None, str]:
    """배열 사전을 고른다 (O-32 · D-0110).

    **참조곡이 여럿이면 곡마다 으뜸음으로 돌린 뒤 더한다** (D-0063 · D-0213).
    *"이미 으뜸음 기준"*이라 적고 안 돌려 절대음을 도수로 읽었다. 없으면 `None`이다.
    """
    import numpy as np

    from hathor.domain.services.harmony_prior import DEGREE_COUNT
    from hathor.shared.config.paths import repo_root as _root

    if not args.transitions:
        return None, "없음"
    root = args.series if args.series else find_series_root(_root(), args.stem_set)
    if root is None or not root.is_dir():
        print("시계열 산출물을 찾지 못했다. 배열 조건화를 건너뛴다.", file=sys.stderr)
        return None, "없음"

    store = getattr(args, "priors", None) or find_keys_store(_root(), args.stem_set)
    if store is None:
        print("조성 산출물이 없어 회전 기준이 없다. 배열 조건화를 건너뛴다.", file=sys.stderr)
        return None, "없음"
    table = load_transition_priors(root, args.stem_set, source_keys, tonics=load_tonics(store))
    total = np.zeros((DEGREE_COUNT, DEGREE_COUNT), dtype=np.float64)
    for matrix in table.values():
        total += np.asarray(matrix, dtype=np.float64)
    found = len(table)
    if found == 0:
        print(f"참조곡이 시계열 저장분에 없다: {root.name}", file=sys.stderr)
        return None, "없음"
    if found < len(source_keys):
        print(
            f"참조곡 {len(source_keys)}곡 중 {found}곡만 시계열 저장분에 있다.",
            file=sys.stderr,
        )
    total /= total.sum()
    return tuple(tuple(float(v) for v in row) for row in total), f"{root.name} ({found}곡)"


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


def _run_ingest_keys(args: argparse.Namespace) -> int:
    """코퍼스 조성 분포를 실측한다 (O-22(닫힘 D-0201)).

    **정답 라벨이 없으므로 분포와 베이스라인으로 검사한다.** 맞다는 증명은
    할 수 없고 틀렸다는 신호만 잡을 수 있다.

    결과를 JSONL로 남긴다. 디코딩이 곡당 수 초라 재분석 때마다 다시 돌리면
    실험 회전이 느려진다 — 지표를 만들어두고 보지 않게 되는 원인이다 (D-0030).
    """
    import json
    from collections import Counter

    import numpy as np

    from hathor.domain.services.key_estimation import (
        BLACK_KEYS,
        chroma_series,
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

    if args.from_bundles:  # 옛 규격을 다시 쓰고 같은 보고로 이어 간다 (O-63 · D-0211)
        if not (rows := ingest_keys_bundles.run(args) or []):
            return 2
    elif args.replay is not None:
        if refusal := replay_refusal(args):
            print(refusal, file=sys.stderr)
            return 2

        with args.replay.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        if (strength := ingest_keys_bundles.replay_strength(rows, args)) is None:
            return 2  # 이미 뺀 배음을 또 빼지 않는다 (D-0211)
        recomputed = 0
        for row in rows:
            saved = row.get("chroma")
            if saved is None:
                continue
            # **저장된 크로마로 다시 판정한다** (D-0059). 프로파일과 배음 감산을
            # 바꿔 가며 실험할 수 있고 음원도 GPU도 필요 없다. 크로마를 뽑는
            # 것만 리전이고 알고리즘 실험은 어느 기기에서든 돈다.
            vector = subtract_harmonics(np.asarray(saved, dtype=np.float64), strength)
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
        root = resolve_root(args.root)
        tracks = list(JsonlScanStore(out_root).read_tracks())
        if args.limit is not None:
            tracks = tracks[: args.limit]
        if not tracks:
            print("스캔 산출물이 없다. --out 경로를 확인한다.", file=sys.stderr)
            return 1

        # **이어받을 파일을 먼저 정한다** (D-0075). 조건이 같은 최근 산출물이 있으면
        # 거기에 붙이고, 이미 처리한 곡은 건너뛴다.
        settings = _keys_settings(args)
        # **같은 산출물에 둘이 못 쓰게 한다** (D-0077). 이어받기가 같은 파일에
        # append하므로, 동시에 돌면 줄이 섞여 파일이 통째로 깨진다.
        lock = BatchLock(out_root)
        holder = lock.acquire()
        if holder is not None:
            print(
                f"이미 다른 추출이 돌고 있다 (PID {holder}). 끝나기를 기다리거나 그 쪽을 멈춘다.",
                file=sys.stderr,
            )
            return 1
        saved, done, broken = _resume_target(out_root, settings)
        # **시계열은 산출물 이름을 따라간다** (D-0105). 이어받기가 정한 파일과 짝이
        # 안 맞으면 어느 jsonl의 시계열인지 알 수 없다.
        series_root = out_root / saved.name.replace(".keys.jsonl", ".series")
        if broken > max(1, int(len(done) * BROKEN_LINE_TOLERANCE)):
            lock.release()
            print(
                f"{saved.name}에 깨진 줄이 {broken}개다. **동시 실행으로 섞였을 수 있다.**\n"
                f"  조용히 건너뛰면 처리한 곡 수를 잘못 세고 그 위에 이어 쓴다.\n"
                f"  파일을 확인하고 지운 뒤 다시 실행한다: {saved}",
                file=sys.stderr,
            )
            return 1
        if done:
            print(f"이어받는다: {saved.name} · 이미 {len(done)}곡", file=sys.stderr, flush=True)
        remaining = [track for track in tracks if track.source_key not in done]
        if not remaining:
            lock.release()
            print(f"이미 전부 처리했다: {saved}\n")
            return 0

        decoder = FfmpegAudioDecoder()
        separator = None
        if args.separate:
            # **모델을 한 번만 적재한다.** 곡마다 적재하면 8초씩 200번을 버린다.
            from hathor.infrastructure.demucs_separator import DemucsStemSeparator

            separator = DemucsStemSeparator()
            missing = [
                part
                for parts in STEM_SETS.values()
                for part in parts
                if part not in separator.sources
            ]
            if missing:
                lock.release()
                print(
                    f"모델이 내지 않는 스템을 요구한다: {sorted(set(missing))} "
                    f"(가진 것: {separator.sources})",
                    file=sys.stderr,
                )
                return 1
        failed = 0
        saved.parent.mkdir(parents=True, exist_ok=True)
        # **행마다 즉시 쓴다.** 전에는 1004곡을 메모리에 쌓고 마지막에 한 번 썼다.
        # 중간에 끊기면 전부 사라졌고, GPU로 한 시간 반짜리 작업에서 실제로 겪었다.
        stream = saved.open("a", encoding="utf-8")
        for index, track in enumerate(remaining, start=1):
            path = root / track.source_key
            try:
                present = path.exists()
            except OSError as error:
                print(f"음원 경로를 열 수 없다({error}): {track.source_key[:40]}", file=sys.stderr)
                failed += 1
                continue
            if not present:
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
                if args.series is not None:
                    # **같은 디코드·같은 분리를 쓴다.** 시계열 전용 배치를 따로 만들면
                    # 이어받기·잠금·진행 표시를 복사해야 하고, 그러면 한쪽만 고쳐진다.
                    write_series(
                        series_root,
                        track.source_key,
                        "mix",
                        chroma_series(
                            to_mono(waveform),
                            window_seconds=args.series,
                            mode=args.chroma,
                            gamma=args.gamma,
                            harmonic=args.harmonic,
                        ),
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
                # **행마다 조건을 적는다** (D-0073). 파일 이름만 봐서는 `mean`인지
                # `median`인지, 몇 곡인지, 분리했는지 알 수 없었다. 실제로 리전에
                # 여섯 개가 쌓인 채 어느 것이 무엇인지 모르는 상태가 됐다.
                **settings,
                "window_seconds": args.window_seconds if args.aggregate == "median" else None,
                "limit": args.limit,
                "source_key": track.source_key,
                **estimate.as_record(),
                "tuning_cents": cents,
                "profile": args.profile,
                "chroma": [round(float(value), 6) for value in extracted],
            }
            if args.separate:
                # **조합마다 크로마를 실제로 뽑는다.** 스템별 크로마를 저장해 두고
                # 나중에 더하는 편이 싸지만, 크로마는 크기 스펙트럼이라 신호의 합에
                # 대해 선형이 아니다 — 스템 크로마의 합은 합친 신호의 크로마와 다르다.
                # **(a)가 성립하는지 판정하는 자리에서 근사를 끼우지 않는다.**
                assert separator is not None
                stems = separator.separate(waveform)
                bundle: dict[str, dict[str, list[float]]] = {}
                for name, parts in STEM_SETS.items():
                    stacked = np.stack([stems[part] for part in parts])
                    mixed = to_mono(np.asarray(stacked.sum(axis=0), dtype=np.float32))
                    middle = mixed.size // 2
                    # **`full`은 생성 경로가, `head`/`tail`은 판정이 쓴다** (D-0074).
                    # 반쪽은 홀드아웃 전용이라 전량 배치에서는 굳이 뽑지 않아도 된다.
                    if args.series is not None and len(parts) == 1:
                        # **조합은 시계열로 안 뽑는다** (D-0106). `other+bass`류는 화성
                        # 사전을 고르려고 만든 것이고(D-0073), 순서 작업이 쓰는 것은
                        # `other`(화음)와 `bass`(독립 관측)다. 시계열 한 번이 전곡
                        # 크로마 한 번과 같은 비용이라 조합 둘이 곡당 1.7초를 버린다.
                        write_series(
                            series_root,
                            track.source_key,
                            name,
                            chroma_series(
                                mixed,
                                window_seconds=args.series,
                                mode=args.chroma,
                                gamma=args.gamma,
                                harmonic=args.harmonic,
                            ),
                        )
                    segments = [("full", mixed)]
                    if args.halves:
                        segments += [("head", mixed[:middle]), ("tail", mixed[middle:])]
                    bundle[name] = {
                        side: [
                            round(float(value), 6)
                            for value in chroma_of(
                                segment,
                                mode=args.chroma,
                                gamma=args.gamma,
                                harmonic=args.harmonic,
                                aggregate=args.aggregate,
                                window_seconds=args.window_seconds,
                            )
                        ]
                        for side, segment in segments
                    }
                record["stems"] = bundle
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
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if index % 50 == 0:
                print(
                    f"  {index}/{len(remaining)}"
                    f"{f' (누적 {len(done) + index}/{len(tracks)})' if done else ''}",
                    file=sys.stderr,
                    flush=True,
                )
        stream.close()
        lock.release()
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
        return report_harmonic_sweep(rows, args.profile)

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

    print(f"곡 {total}개\n")
    print("선법")
    for mode, count in modes.most_common():
        print(f"  {mode:<6} {count:5d}  {count / total:6.1%}")

    black = sum(1 for key in keys if key.tonic in BLACK_KEYS)
    print(f"  검은건반 으뜸음  {black:5d}  {black / total:6.1%}   ← O-23 지표 (D-0061)")

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

    print(
        "\n".join(
            ambiguity_report(
                modes=[key.mode.value for key in keys],
                ambiguous=ambiguous_flags,
                relative=is_relative,
                floor=float((base_margin < KEY_MARGIN_FLOOR).mean()),
                tunings=[float(str(row["tuning_cents"])) for row in rows if "tuning_cents" in row],
            )
        )
    )
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
    output_key = parse_key(args.key) if args.key else estimated_key
    harmony_prior, prior_source = _resolve_harmony_prior(
        args, [song[0] for song in chosen], estimates
    )
    transition, transition_source = _resolve_transition_prior(args, [song[0] for song in chosen])
    job = GenerationJob(seed=args.seed, stages=_parse_stages(args.stages))
    data, summary = render(
        job,
        references,
        key=output_key,
        tempo_bpm=args.tempo,
        harmony_prior=harmony_prior,
        transition_prior=transition,
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
    conditioned = f"참조곡 반영 · {prior_source}" if summary["harmony_conditioned"] else "시드만"
    # **배열 조건화 여부를 함께 찍는다** (D-0110). 어휘만 걸리고 배열이 안 걸린 것을
    # 모르면 "참조곡 반영"을 보고 둘 다 걸렸다고 읽는다.
    conditioned += f" · 배열 {transition_source}"
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
    root = resolve_root(args.root)
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


ALL_MERT_LAYERS = 13
"""MERT-v1-95M의 은닉 상태 수 (임베딩 출력 포함).

**열셋 전부 뽑는다.** 한 번의 forward에서 다 나오므로 골라 담는 것이 공짜이고,
D-0181은 **넷만 보고** `layer03`을 골랐다 — 이웃 층이 더 나은지 안 뽑아서
모른다. 전부 뽑으면 그 질문이 재추출 없이 풀린다 (D-0203).
"""


def _run_ingest_all(args: argparse.Namespace) -> int:
    """곡 하나를 한 번만 열어 전부 뽑는다 (D-0203).

    **분리가 곡당 비용의 대부분이고 스템은 디스크에 못 남긴다** — 4분 곡 하나가
    340MB라 1004곡이면 340GB다. 그래서 스템이 메모리에 떠 있는 그 한 번에
    스템 의존 산출물을 전부 뽑는다. 패스를 쪼개면 그만큼 Demucs를 다시 돈다.
    """
    from hathor.application.ingest_all import IngestAll
    from hathor.infrastructure.demucs_separator import DemucsStemSeparator
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.librosa_pitch_tracker import LibrosaPitchTracker
    from hathor.infrastructure.mert_feature_extractor import MertFeatureExtractor
    from hathor.infrastructure.track_bundle_store import BUNDLE_DIRNAME, TrackBundleStore

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = TrackBundleStore(args.out / BUNDLE_DIRNAME)
    pending = tracks if args.force else [t for t in tracks if not store.has(t.source_key)]
    if args.limit is not None:
        pending = pending[: args.limit]
    if not pending:
        print(f"이미 다 끝났다. {store.counts()}")
        return 0

    extractor = MertFeatureExtractor(layers=tuple(range(ALL_MERT_LAYERS)))
    job = IngestAll(
        decoder=FfmpegAudioDecoder(),
        separator=DemucsStemSeparator(),
        extractor=extractor,
        pitch=LibrosaPitchTracker(),
        library_root=resolve_root(args.root),
    )
    print(f"곡 {len(pending)}개 · 산출물 {store.root}\n")

    started = time.perf_counter()
    for index, bundle in enumerate(job.run(pending), 1):
        store.write(bundle.source_key, bundle.arrays, bundle.manifest)
        elapsed = time.perf_counter() - started
        left = (len(pending) - index) * elapsed / index
        print(
            f"  {index}/{len(pending)}  {elapsed / index:.1f}초/곡"
            f"  남은 {left / 3600:.1f}시간  {bundle.source_key}",
            flush=True,
        )
    for source_key, reason in job.failed:
        store.record_failure(source_key, reason)
        print(f"  실패 {source_key}: {reason}", file=sys.stderr)

    print(f"\n성공 {job.processed}곡 · 실패 {len(job.failed)}곡 · 누적 {store.counts()}")
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
        resolve_root(args.root),
    )
    return drive_extraction(use_case, store, tracks, seconds_per_track=18.0)


def _run_ingest_compact(args: argparse.Namespace) -> int:
    """특징 인덱스의 중복·고아 기록을 정리한다 (O-7(D-0022)).

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


def _eval_log_root(args: argparse.Namespace) -> Path:
    """평가 기록을 둘 곳. `--out`이 있으면 그 옆이고, 없으면 기본 산출물 루트다."""
    out = getattr(args, "out", None)
    return Path(out) if out is not None else resolve_path(DEFAULT_OUTPUT_ROOT)


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

    tags = {track.source_key: track.tags for track in JsonlScanStore(args.out).read_tracks()}
    if not tags:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    # **모양을 보고 고른다** (D-0233 · O-69 닫힘 D-0274). 규약에 없는 `read_records()`를
    # 불러서 **묶음을 못 읽었다.** 배열 이름은 안 준다 — `source_keys()`는 배열을 안 연다.
    features = open_feature_source(args.features or args.out / DEFAULT_FEATURE_DIRNAME, ())
    if not features.index_path.exists():
        print(f"특징 인덱스가 없다: {features.index_path}", file=sys.stderr)
        return 2
    # 임베딩이 없는 곡은 출제하지 않는다. 응답을 받아도 모델에 못 쓴다.
    keys = sorted(features.source_keys() & set(tags))
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
        tracks = load_search_tracks(args, keys)
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


# ------------------------------------------------- 등재표 (D-0273)


def entries() -> tuple[Entry, ...]:
    """하위 명령 전부. **`build_parser`와 `main`이 이것 하나를 읽는다** (D-0273).

    이름 · 도움말 · 인자 · 러너가 한 줄에 같이 선다. 예전에는 이름이 `build_parser`와
    `main`(그리고 `eval`은 `_dispatch_eval`까지) 두세 곳에 적혀 있었고, 어긋나도 아무
    소리가 안 났다 — 그것이 `ingest all`을 스캔으로 떨어뜨렸다 (D-0204).

    **함수다.** 러너들이 이 아래가 아니라 위에 있어야 하는데 모듈 수준 상수로 두면
    정의 순서에 걸린다. 파서를 만들 때마다 한 번 짜는 값이라 비용이 없다.
    """
    return (
        Command("generate", "생성 파이프라인 실행", _build_generate, _run_generate),
        Group(
            "ingest",
            "음원 라이브러리 인제스트",
            "ingest_command",
            (
                *ingest_onsets.COMMANDS,
                Command(
                    "keys",
                    "코퍼스 조성 분포 실측 (D-0054 · O-22(닫힘 D-0201))",
                    _build_ingest_keys,
                    _run_ingest_keys,
                ),
                Command("scan", "라이브러리 스캔", _build_ingest_scan, _run_ingest_scan),
                Command(
                    "resolve",
                    "정규 신원 확정 (MusicBrainz)",
                    _build_ingest_resolve,
                    _run_ingest_resolve,
                ),
                Command(
                    "all",
                    "한 패스로 전부 뽑는다 (GPU · D-0203)",
                    _build_ingest_all,
                    _run_ingest_all,
                ),
                Command(
                    "features",
                    "오디오 특징 추출 (GPU)",
                    _build_ingest_features,
                    _run_ingest_features,
                ),
                Command(
                    "compact",
                    "특징 인덱스 중복·고아 정리 (O-7 · D-0022)",
                    _build_ingest_compact,
                    _run_ingest_compact,
                ),
            ),
        ),
        Group(
            "eval",
            "검색 평가 하네스",
            "eval_command",
            (
                *eval_retrieval.COMMANDS,
                *eval_priors.COMMANDS,
                *eval_output.COMMANDS,
                *eval_vocabulary.COMMANDS,
                *eval_order.COMMANDS,
                *eval_extract.COMMANDS,
                *eval_clap.COMMANDS,
            ),
        ),
        Group(
            "taste",
            "취향 라벨 수집",
            "taste_command",
            (
                Command(
                    "compare",
                    "쌍대비교 문항을 내고 응답을 기록한다",
                    _build_taste_compare,
                    _run_taste_compare,
                ),
                Command("status", "수집 현황", _build_taste_status, _run_taste_status),
            ),
        ),
        Group(
            "lyrics",
            "가사축",
            "lyrics_command",
            (
                Command(
                    "structure",
                    "가사 반복 패턴에서 곡 구조 분포 실측 (D-0049)",
                    _build_lyrics_structure,
                    _run_lyrics_structure,
                ),
                Command(
                    "extract",
                    "가사 특징 추출 (CPU, 수 초)",
                    _build_lyrics_extract,
                    _run_lyrics_extract,
                ),
            ),
        ),
        Command("search", "시드곡 조합으로 유사곡을 찾는다", _build_search, _run_search),
        Command(
            "env",
            "해석된 경로와 설정을 찍는다. 기기를 옮겼을 때 먼저 본다",
            no_arguments,
            _run_env,
        ),
        Command(
            "doctor",
            "기록된 규약과 기기 상태가 맞는지 검사한다 (D-0067)",
            no_arguments,
            run_doctor,
        ),
        Command(
            "setup",
            "기기를 탐지해 .env를 쓴다. 기기당 한 번 (D-0068)",
            _build_setup,
            _run_setup,
        ),
    )
