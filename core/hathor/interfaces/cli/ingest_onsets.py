"""`ingest onsets` — 곡별 온셋 포락선 산출물 (O-46 · D-0145).

**`main.py`에 두지 않는다.** D-0127 이래 새 명령은 자기 모듈로 간다.

### 이어받기가 기본이다

파일이 있으면 건너뛴다. 1004곡이고 디코딩이 곡당 수 초이므로 **중단은 예외가 아니라
전제다** (D-0075 · D-0105). `--force`를 줘야 다시 쓴다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.application.extract_onsets import HOP_SECONDS, ExtractOnsets
from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
from hathor.infrastructure.onset_store import SUFFIX, envelope_path, write_envelope
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    import argparse


def add_parser(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """`ingest onsets` 인자. **홉은 받지만 창은 안 받는다** (D-0144)."""
    parser = commands.add_parser("onsets", help="곡별 온셋 포락선을 뽑는다 (O-46)")
    # **기본값은 문자열이어야 한다** (D-0069). `Path`로 두면 `type`이 기본값에
    # 안 걸려 현재 디렉터리 기준으로 남는다.
    parser.add_argument("--out", type=resolve_path, default="var/ingest", help="산출물 루트")
    parser.add_argument("--root", type=resolve_path, default=None, help="라이브러리 루트")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한")
    parser.add_argument("--hop", type=float, default=HOP_SECONDS, help="포락선 한 칸의 초")
    parser.add_argument("--force", action="store_true", help="있어도 다시 쓴다")


def run(args: argparse.Namespace, library_root: Path) -> int:
    """포락선을 뽑아 쓴다. **곡마다 바로 쓴다** — 모아 두면 중단에 통째로 날아간다."""
    from hathor.infrastructure.jsonl_scan_store import JsonlScanStore

    out_root = Path(args.out)
    tracks = list(JsonlScanStore(out_root).read_tracks())
    if not tracks:
        print("곡이 없다. 먼저 스캔한다.", file=sys.stderr)
        return 1

    # **홉을 폴더 이름에 적는다.** 홉이 다른 파일이 섞이면 박 추정이 조용히
    # 틀린다 — D-0143이 주기 오차 0.8%로 위상이 뭉개지는 것을 실측했다.
    folder = out_root / f"keys-{args.hop:g}s{SUFFIX}"
    # **고르게 뽑는다** (D-0161). 앞에서 자르면 스캔 차례가 아티스트순이라 한
    # 아티스트만 나온다 — 20곡을 뽑았더니 전부 10CM이었고, 그 분포를 코퍼스의
    # 분포로 읽을 뻔했다.
    picked = tracks[:: max(1, len(tracks) // args.limit)][: args.limit] if args.limit else tracks
    pending = [
        track
        for track in picked
        if args.force or not envelope_path(folder, track.source_key).exists()
    ]
    print(f"곡 {len(picked)}개 · 뽑을 것 {len(pending)}개 · 홉 {args.hop:g}초")
    if not pending:
        print("전부 있다. 아무것도 하지 않았다 (멱등)")
        return 0

    extractor = ExtractOnsets(FfmpegAudioDecoder(), library_root, hop_seconds=args.hop)
    written = 0
    for found in extractor.run(pending):
        write_envelope(folder, found.source_key, found.envelope, hop_seconds=found.hop_seconds)
        written += 1
        if written % 50 == 0:
            print(f"  {written} / {len(pending)}")

    print(f"기록 {written}개 · {folder}")
    # **실패를 조용히 넘기지 않는다** (GR-0.5). 배치는 멈추지 않되 수는 남긴다.
    if extractor.failures:
        print(f"실패 {len(extractor.failures)}곡", file=sys.stderr)
        for source_key, reason in extractor.failures[:5]:
            print(f"  - {source_key}: {reason}", file=sys.stderr)
    return 0
