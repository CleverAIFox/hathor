"""`eval mfcc` · `eval layers` — 베이스라인과 레이어별 특징을 뽑는다 (D-0260).

**`main.py`에 있었다.** 둘 다 «평가»라는 이름을 달고 있지만 하는 일은 **추출 배치**다 —
`eval retrieval`을 `--features`만 바꿔 돌릴 수 있게 다른 루트에 쌓는다.
"""

from __future__ import annotations

import argparse
import sys

from hathor.application.extract_features import ExtractFeatures, ExtractLayerFeatures
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.interfaces.cli.extraction import drive_extraction
from hathor.interfaces.cli.roots import (
    DEFAULT_LAYERS_DIRNAME,
    DEFAULT_MFCC_DIRNAME,
    resolve_root,
)


def run_eval_mfcc(args: argparse.Namespace) -> int:
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
                resolve_root(args.root),
            )
            return drive_extraction(use_case, store, tracks, seconds_per_track=2.0)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3


def run_eval_layers(args: argparse.Namespace) -> int:
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
                resolve_root(args.root),
            )
            return drive_extraction(use_case, store, tracks, seconds_per_track=4.0)
    except BatchAlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3
