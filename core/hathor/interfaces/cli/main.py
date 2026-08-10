"""CLI 진입점. 비즈니스 로직은 두지 않는다 (GR-2.2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hathor.application.orchestrator.generation_pipeline import run_dry
from hathor.application.scan_library import ScanLibrary
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.infrastructure.filesystem_scanner import FilesystemLibraryScanner
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.infrastructure.mutagen_tag_extractor import MutagenTagExtractor

DEFAULT_LIBRARY_ROOT_ENV = "HATHOR_LIBRARY_ROOT"
DEFAULT_OUTPUT_ROOT = Path("var/ingest")


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
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
