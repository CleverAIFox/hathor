"""`eval clap` — 상업 가능한 임베딩으로 같은 하네스를 돌린다 (O-68 · D-0231).

**`main.py`에 두지 않는다.** D-0127 이래 새 명령은 자기 모듈로 간다.

### 무엇을 하나

`eval layers`와 같은 자리에서 **CLAP 임베딩 하나**를 뽑아 `var/ingest/clap`에 쌓는다. 그다음은
D-0027 하네스가 그대로 받는다 — 같은 1004곡 · 같은 분할이라 MERT와 **나란히** 낼 수 있다.

    hathor eval clap                      # 배치 (GPU · 1시간 안팎)
    hathor eval retrieval \\
      --features mert=var/ingest \\
      --features clap=var/ingest/clap \\
      --keys mert:mixture,clap:mixture

### 이어받기가 기본이다

1004곡이라 **중단은 예외가 아니라 전제다** (D-0075). 이미 뽑힌 곡은 건너뛰고 `--force`를 줘야
다시 쓴다. 배치 잠금은 `NpzFeatureStore`가 든다 — 두 배치가 겹치면 인덱스가 어긋난다 (D-0022).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import resolve_root
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    import argparse

DIRNAME = "clap"
"""`--out` 아래 기본 산출물 폴더. MERT 산출물과 **섞지 않는다** — 차원이 다르다."""

SECONDS_PER_TRACK = 4.0
"""진행 예상에 쓰는 값. 스템을 안 만들므로 `eval layers`와 같은 자리다."""


def _build_clap(parser: argparse.ArgumentParser) -> None:
    """`eval clap` 인자. **기본값은 문자열이다** (D-0069)."""
    parser.add_argument("--root", type=resolve_path, default=None, help="라이브러리 루트")
    parser.add_argument("--out", type=resolve_path, default="var/ingest", help="스캔 산출물 위치")
    parser.add_argument(
        "--features",
        type=resolve_path,
        default=None,
        help=f"산출물 루트 (미지정 시 --out/{DIRNAME})",
    )
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    parser.add_argument("--force", action="store_true", help="이미 뽑힌 곡도 다시 뽑는다")


def run(args: argparse.Namespace, library_root: Path) -> int:
    from hathor.application.extract_features import ExtractLayerFeatures
    from hathor.domain.ports.audio_analysis import CHUNK_SECONDS
    from hathor.infrastructure.clap_feature_extractor import (
        CLAP_DIMENSION,
        CLAP_SAMPLE_RATE,
        DEFAULT_MODEL,
        ClapFeatureExtractor,
    )
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
    from hathor.infrastructure.npz_feature_store import BatchAlreadyRunningError, NpzFeatureStore

    # 진행 출력 · 실패 처리 · 요약을 여기서 다시 짜지 않는다. 형식이 갈리면 두 산출물을
    # 나란히 못 놓는다 — 그것이 이 명령의 목적이다.
    # **예전에는 `main`에서 가져왔다** — `main`이 이 모듈을 부르므로 서로를 보고 있었다 (D-0250).
    from hathor.interfaces.cli.extraction import drive_extraction

    tracks = list(JsonlScanStore(Path(args.out)).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.features or Path(args.out) / DIRNAME)
    # **산출물이 자기를 설명한다** (D-0203). 모델을 적재하기 전에 쓴다 — 곡이 하나도
    # 안 남은 재실행에서도 `var_fsck`가 «정체 불명»을 면한다.
    store.write_manifest(
        DIRNAME,
        {
            "model": DEFAULT_MODEL,
            "license": "Apache-2.0",
            "sample_rate": CLAP_SAMPLE_RATE,
            "chunk_seconds": CHUNK_SECONDS,
            "dimension": CLAP_DIMENSION,
            "layers": [],
            "dtype": "float32",
            "stems": [],
        },
    )
    try:
        with store.batch_lock():
            if not args.force:
                done = store.completed_keys()
                skipped = sum(1 for track in tracks if track.source_key in done)
                tracks = [track for track in tracks if track.source_key not in done]
                if skipped:
                    print(f"이미 뽑은 {skipped}곡을 건너뛴다", flush=True)
            if args.limit is not None:
                tracks = tracks[: args.limit]
            if not tracks:
                print("처리할 곡이 없다")
                return 0

            extractor = ClapFeatureExtractor()
            print(f"CLAP {extractor.dimension}차원 · mixture 하나로 저장", flush=True)
            use_case = ExtractLayerFeatures(FfmpegAudioDecoder(), extractor, library_root)
            return drive_extraction(use_case, store, tracks, seconds_per_track=SECONDS_PER_TRACK)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3


# ------------------------------------------ 명령 등재 (D-0273)


def run_command(args: argparse.Namespace) -> int:
    """`Command.run`이 요구하는 한 인자 꼴.

    `run`은 라이브러리 루트를 따로 받는다 — **어디서 푸는지를 한 자리에 모아 둔 것**이고
    (D-0009), 그 자리가 이제 여기다. 예전에는 `main._dispatch_eval`이 풀어서 넘겼다.
    """
    return run(args, resolve_root(args.root))


COMMANDS: tuple[Command, ...] = (
    Command(
        "clap",
        "CLAP 임베딩 추출 (GPU · 상업 가능 · O-68 · D-0235)",
        _build_clap,
        run_command,
    ),
)
"""`eval` 표에 실리는 것 (D-0273).

**예전에는 `add_parser(eval_sub)`였다.** 그 꼴은 «등재는 이 모듈, 배선은 `main.py`»로
갈려 있었고, 그래서 `main.py`의 글자를 긁는 검사가 이 명령을 **못 봤다** — 배선을
빼먹어도 초록이었다."""
