"""`lyrics structure` · `lyrics extract` — 가사축 (D-0294).

**`main.py`에서 내려왔다.** D-0294가 산출물 manifest를 더하자 `main.py`가 못 박은
1477줄을 넘었고, 늘리는 대신 뗐다 — D-0277이 `ingest keys`를 뗀 것과 같은 자리다.

가사축은 **원문을 안 남긴다** (D-0046). 해시와 벡터만 남으므로 manifest 한 장이
«무엇으로 만든 벡터인가»를 아는 유일한 자리다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hathor.infrastructure.batch_lock import BatchAlreadyRunningError
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.roots import DEFAULT_OUTPUT_ROOT
from hathor.shared.config.paths import resolve_path

DEFAULT_LYRICS_DIRNAME = "lyrics-hashed"
_DETERMINISM_PROBE = (
    # 한국어·영어·혼재 각 하나. 코퍼스 실측이 혼재 40%였으므로 세 경우를 다 밟는다.
    "사랑한다는 말은 하지 못했어",
    "i never said the words out loud",
    "돌아서는 순간 you were already gone",
)


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
    from hathor.infrastructure.hashed_lyrics_extractor import (
        FEATURE_DIM,
        NGRAM_SIZES,
        HashedLyricsExtractor,
    )

    tracks = list(JsonlScanStore(args.out).read_tracks())
    if not tracks:
        print(f"스캔 산출물이 없다: {args.out}", file=sys.stderr)
        return 2

    store = NpzFeatureStore(args.features or args.out / DEFAULT_LYRICS_DIRNAME)
    # **산출물이 자기를 설명한다** (D-0203 · D-0294). 원문은 안 남기므로(D-0046) 이 한 장이
    # «무엇으로 만든 벡터인가»를 아는 유일한 자리다.
    store.write_manifest(
        DEFAULT_LYRICS_DIRNAME,
        {
            "model": f"해싱 · n-gram {','.join(str(size) for size in NGRAM_SIZES)}",
            "license": "해당 없음",
            "dimension": FEATURE_DIM,
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
