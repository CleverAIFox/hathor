"""`eval musicfm` — 셋째 취향 축 후보를 같은 하네스로 잰다 (O-68 · D-0248 · D-0413).

**`main.py`에 두지 않는다.** D-0127 이래 새 명령은 자기 모듈로 간다.

### 무엇을 하나

`eval clap`과 같은 자리에서 **MusicFM 임베딩**을 뽑아 `var/ingest/musicfm`에 쌓는다.
그다음은 D-0027 하네스가 그대로 받는다 — 같은 1004곡 · 같은 분할이라 MERT·CLAP과
**나란히** 낼 수 있다.

    git clone https://github.com/minzwon/musicfm /some/where/musicfm
    # 가중치 둘을 musicfm/data/ 에 받는다 (fma_stats.json · pretrained_fma.pt)
    hathor eval musicfm --home /some/where      # 배치 · 클론한 곳의 **부모**를 준다
    hathor eval retrieval \\
      --features mert=var/ingest \\
      --features musicfm=var/ingest/musicfm \\
      --keys mert:mixture,musicfm:mixture

**층을 함께 뽑으려면 `--layers 3,7`.** 한 번의 forward에서 다 나오므로 공짜에 가깝다 —
저자의 `get_latent`을 층마다 부르면 그만큼 다시 돈다 (D-0413).

### 이어받기가 기본이다

1004곡이라 **중단은 예외가 아니라 전제다** (D-0075). 이미 뽑힌 곡은 건너뛰고 `--force`를 줘야
다시 쓴다. 배치 잠금은 `NpzFeatureStore`가 든다 — 두 배치가 겹치면 인덱스가 어긋난다 (D-0022).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.infrastructure.batch_lock import BatchAlreadyRunningError
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import resolve_root
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    import argparse

DIRNAME = "musicfm"
"""`--out` 아래 기본 산출물 폴더. MERT·CLAP 산출물과 **섞지 않는다** — 차원이 다르다."""

SECONDS_PER_TRACK = 4.7
"""진행 예상에 쓰는 값. **실측이다** — 그의 기기에서 1004곡 전수 누적 4.7초/곡 (D-0417).

`eval layers`에서 4.0을 빌려 왔었고 **18% 낮았다** (예상 66.9분 · 실제 78.6분). 빌린
수는 빌린 자리의 수다 — 한 번 돌았으면 **그 자리의 수로 바꾼다** (GR-0.7 · D-0374).
"""


def _build_musicfm(parser: argparse.ArgumentParser) -> None:
    """`eval musicfm` 인자. **기본값은 문자열이다** (D-0069)."""
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
    parser.add_argument(
        "--home",
        type=resolve_path,
        default=None,
        help="musicfm을 클론한 곳의 **부모 폴더** (pip로 안 깔린다 · D-0413)",
    )
    parser.add_argument("--layers", default="", help="함께 뽑을 은닉 층 (예: 3,7)")
    parser.add_argument("--checkpoint", default=None, help="가중치 파일 이름 (기본 {기본})")


def run(args: argparse.Namespace, library_root: Path) -> int:
    from hathor.application.extract_features import ExtractLayerFeatures
    from hathor.domain.ports.audio_analysis import CHUNK_SECONDS
    from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
    from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
    from hathor.infrastructure.musicfm_feature_extractor import (
        DEFAULT_CHECKPOINT,
        DEFAULT_MODEL,
        MUSICFM_COMMIT,
        MUSICFM_DIMENSION,
        MUSICFM_SAMPLE_RATE,
        MusicFmFeatureExtractor,
    )
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    # 진행 출력 · 실패 처리 · 요약을 여기서 다시 짜지 않는다. 형식이 갈리면 두 산출물을
    # 나란히 못 놓는다 — 그것이 이 명령의 목적이다.
    # **예전에는 `main`에서 가져왔다** — `main`이 이 모듈을 부르므로 서로를 보고 있었다 (D-0250).
    from hathor.interfaces.cli.extraction import drive_extraction

    layers = [int(one) for one in str(args.layers).split(",") if one.strip()]
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
            # **코드와 가중치를 갈라 적는다** (D-0217 · D-0413). 코드는 듀얼이고
            # 가중치는 어디에도 안 적혀 있다 — 코드 쪽을 넘겨 적으면 그것이 추측이다.
            "license": "코드 MIT+Apache-2.0 · 가중치 미명시",
            "commit": MUSICFM_COMMIT,
            "checkpoint": args.checkpoint or DEFAULT_CHECKPOINT,
            "sample_rate": MUSICFM_SAMPLE_RATE,
            "chunk_seconds": CHUNK_SECONDS,
            "dimension": MUSICFM_DIMENSION,
            "layers": layers,
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

            extractor = MusicFmFeatureExtractor(
                home=args.home,
                layers=tuple(layers),
                checkpoint=args.checkpoint or DEFAULT_CHECKPOINT,
            )
            print(
                f"MusicFM {extractor.dimension}차원 · {extractor.checkpoint} · "
                f"mixture{' + 층 ' + ','.join(map(str, layers)) if layers else ''}",
                flush=True,
            )
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
        "musicfm",
        "MusicFM 임베딩 추출 (O-68 · D-0248 — 가중치 라이선스 미명시 · D-0413)",
        _build_musicfm,
        run_command,
    ),
)
"""`eval` 표에 실리는 것 (D-0273).

**예전에는 `add_parser(eval_sub)`였다.** 그 꼴은 «등재는 이 모듈, 배선은 `main.py`»로
갈려 있었고, 그래서 `main.py`의 글자를 긁는 검사가 이 명령을 **못 봤다** — 배선을
빼먹어도 초록이었다."""
