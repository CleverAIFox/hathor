"""`ingest keys` — 코퍼스 조성 분포 실측 (O-22 닫힘 D-0201 · D-0277).

**`main.py`에 `_run_ingest_keys` 352줄로 있었다.** D-0127 이래 새 명령은 자기 모듈로 가는데
이것은 그 규칙보다 오래된 자리이고, `main.py`에서 가장 큰 함수였다.

### 쪼개니 잠금의 근거가 무너졌다

`BatchLock`이 «`try/finally`로 감싸려면 본문 전체를 들여써야 하고, 그 재들여쓰기가 이
함수에서는 위험이 더 크다»고 적혀 있다 (D-0077). **352줄이라서 그랬던 것**이고 그것이
`acquire()`/`release()`를 손으로 부르는 꼴을 낳았다. 쪼갠 지금은 그 제약이 없다 —
잠금 자체는 이 판에서 안 건드린다 (섞으면 578줄 이동에서 뜻이 바뀐 곳을 못 가른다).

### 조각의 경계

| 조각 | 무엇 |
|---|---|
| `_replayed` | 저장된 크로마로 다시 판정한다. 음원도 GPU도 없다 (D-0059) |
| `_target` | 이어받을 파일 · 잠금 확인 · 깨진 줄 판정 (D-0075 · D-0077) |
| `_separator` | Demucs를 **한 번만** 적재한다 |
| `_measure` | 곡 하나의 크로마 · 조성 · 조율 편차 |
| `_record` | 곡 하나의 행. 조건을 행에 적는다 (D-0073) |
| `_stem_bundle` | 스템 조합별 크로마 (D-0073 · D-0074) |

**종료 코드는 `_Stop`이 들고 다닌다.** 쪼개기 전에는 `return 1`·`return 2`가 한 함수 안
여덟 자리에 있었고, 조각으로 나누면서 «행이 없다»와 «몇으로 끝났나»를 한 값에 접으면
**코드가 조용히 바뀐다.**
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import numpy as np

from hathor.domain.services.key_estimation import (
    HARMONIC_STRENGTH,
    PROFILE_TEMPERLEY,
    KeyEstimate,
    chroma_series,
    estimate_key,
    estimate_tuning_cents,
    subtract_harmonics,
    to_mono,
)
from hathor.domain.services.key_estimation import (
    chroma as chroma_of,
)
from hathor.domain.services.stem_sets import STEM_SETS
from hathor.infrastructure.batch_lock import BatchAlreadyRunningError, batch_lock
from hathor.infrastructure.chroma_series_store import write_series
from hathor.infrastructure.ffmpeg_audio_decoder import FfmpegAudioDecoder
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.interfaces.cli import ingest_keys_bundles
from hathor.interfaces.cli.keys_report import report
from hathor.interfaces.cli.keys_resume import (
    BROKEN_LINE_TOLERANCE,
    keys_settings,
    resume_target,
)
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import resolve_root
from hathor.interfaces.cli.tables import replay_refusal
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    import argparse

    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.domain.ports.audio_analysis import StemSeparator, StereoWaveform


LOCK_NAME = "ingest-keys"
"""잠금 이름. 파일은 `var/ingest/.ingest-keys.lock`이고 **대장에 등재돼 있다** (D-0278)."""


class _StopError(Exception):
    """이 명령을 여기서 끝낸다. **종료 코드를 들고 다닌다** (D-0277).

    `SystemExit`을 안 쓴다 — `main`은 정수를 돌려주는 함수이고 시험이 그 값을 본다
    (`main([...]) == 1`). `SystemExit`이 새면 프로세스가 죽어 시험이 값을 못 본다.

    이름의 `Error`는 `ruff`(N818)가 요구한다. 오류가 아니라 이른 종료지만 **선언 없는
    면제를 두지 않는 것**이 이 저장소의 규율이라 이름을 맞춘다."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _Target(NamedTuple):
    """이어받기가 정한 것. 산출물 이름과 시계열 폴더가 **짝이다** (D-0105)."""

    saved: Path
    series_root: Path
    done: set[str]
    settings: dict[str, object]
    remaining: list[ScannedTrack]
    tracks: list[ScannedTrack]
    root: Path


class _Measured(NamedTuple):
    """곡 하나에서 잰 것."""

    chroma: np.ndarray
    estimate: KeyEstimate
    cents: float


def _replayed(args: argparse.Namespace) -> list[dict[str, object]]:
    """저장된 크로마로 다시 판정한다 (D-0059). **디코딩하지 않는다.**"""
    rows: list[dict[str, object]] = []
    if refusal := replay_refusal(args):
        print(refusal, file=sys.stderr)
        raise _StopError(2)

    with args.replay.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if (strength := ingest_keys_bundles.replay_strength(rows, args)) is None:
        raise _StopError(2)  # 이미 뺀 배음을 또 빼지 않는다 (D-0211)
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
        estimate = estimate_key(np.asarray(vector / total, dtype=np.float32), profile=args.profile)
        row.update(estimate.as_record())
        row["profile"] = args.profile
        recomputed += 1
    note = (
        f" · {recomputed}곡을 프로파일 {args.profile} · 배음 {args.harmonic:g}로 재판정"
        if recomputed
        else " · 저장된 크로마가 없어 기록된 판정을 그대로 쓴다"
    )
    print(f"재분석: {args.replay} ({len(rows)}곡){note}. 디코딩하지 않는다.\n")
    return rows


def _target(args: argparse.Namespace, out_root: Path) -> _Target:
    """이어받을 파일을 정한다 (D-0075). **잠금은 부르는 쪽이 쥔다** (D-0278).

    예전에는 이 안에서 잠금을 잡고 나가는 길마다 `lock.release()`를 손으로 불렀다 — 세
    자리였고 하나만 빠뜨려도 유령 잠금이 남았다. 컨텍스트 매니저가 그 셋을 없앤다.
    """
    root = resolve_root(args.root)
    tracks = list(JsonlScanStore(out_root).read_tracks())
    if args.limit is not None:
        tracks = tracks[: args.limit]
    if not tracks:
        print("스캔 산출물이 없다. --out 경로를 확인한다.", file=sys.stderr)
        raise _StopError(1)

    # **이어받을 파일을 먼저 정한다** (D-0075). 조건이 같은 최근 산출물이 있으면
    # 거기에 붙이고, 이미 처리한 곡은 건너뛴다.
    settings = keys_settings(args)
    saved, done, broken = resume_target(out_root, settings)
    # **시계열은 산출물 이름을 따라간다** (D-0105). 이어받기가 정한 파일과 짝이
    # 안 맞으면 어느 jsonl의 시계열인지 알 수 없다.
    series_root = out_root / saved.name.replace(".keys.jsonl", ".series")
    if broken > max(1, int(len(done) * BROKEN_LINE_TOLERANCE)):
        print(
            f"{saved.name}에 깨진 줄이 {broken}개다. **동시 실행으로 섞였을 수 있다.**\n"
            f"  조용히 건너뛰면 처리한 곡 수를 잘못 세고 그 위에 이어 쓴다.\n"
            f"  파일을 확인하고 지운 뒤 다시 실행한다: {saved}",
            file=sys.stderr,
        )
        raise _StopError(1)
    if done:
        print(f"이어받는다: {saved.name} · 이미 {len(done)}곡", file=sys.stderr, flush=True)
    remaining = [track for track in tracks if track.source_key not in done]
    if not remaining:
        print(f"이미 전부 처리했다: {saved}\n")
        raise _StopError(0)
    return _Target(saved, series_root, done, settings, remaining, tracks, root)


def _separator(args: argparse.Namespace) -> StemSeparator | None:
    """`--separate`면 Demucs를 **한 번만** 적재한다. 못 낼 스템을 요구하면 멈춘다."""
    separator = None
    if args.separate:
        # **모델을 한 번만 적재한다.** 곡마다 적재하면 8초씩 200번을 버린다.
        from hathor.infrastructure.demucs_separator import DemucsStemSeparator

        separator = DemucsStemSeparator()
        missing = [
            part for parts in STEM_SETS.values() for part in parts if part not in separator.sources
        ]
        if missing:
            print(
                f"모델이 내지 않는 스템을 요구한다: {sorted(set(missing))} "
                f"(가진 것: {separator.sources})",
                file=sys.stderr,
            )
            raise _StopError(1)
    return separator


def _measure(
    args: argparse.Namespace, waveform: StereoWaveform, series_root: Path, source_key: str
) -> _Measured:
    """곡 하나의 크로마 · 조성 · 조율 편차. 시계열도 같은 디코드로 뽑는다."""
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
            source_key,
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
    cents = estimate_tuning_cents(to_mono(waveform)) if args.tuning and args.chroma == "cq" else 0.0
    return _Measured(extracted, estimate, cents)


def _stem_bundle(
    args: argparse.Namespace,
    waveform: StereoWaveform,
    separator: StemSeparator,
    series_root: Path,
    source_key: str,
) -> dict[str, dict[str, list[float]]]:
    """스템 조합별 크로마 (D-0073 · D-0074)."""
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
                source_key,
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
    return bundle


def _record(
    args: argparse.Namespace,
    target: _Target,
    source_key: str,
    waveform: StereoWaveform,
    measured: _Measured,
    separator: StemSeparator | None,
) -> dict[str, object]:
    """곡 하나의 행. **조건을 행에 적는다** (D-0073)."""
    settings = target.settings
    extracted = measured.chroma
    estimate = measured.estimate
    cents = measured.cents
    record: dict[str, object] = {
        # **행마다 조건을 적는다** (D-0073). 파일 이름만 봐서는 `mean`인지
        # `median`인지, 몇 곡인지, 분리했는지 알 수 없었다. 실제로 리전에
        # 여섯 개가 쌓인 채 어느 것이 무엇인지 모르는 상태가 됐다.
        **settings,
        "window_seconds": args.window_seconds if args.aggregate == "median" else None,
        "limit": args.limit,
        "source_key": source_key,
        **estimate.as_record(),
        "tuning_cents": cents,
        "profile": args.profile,
        "chroma": [round(float(value), 6) for value in extracted],
    }
    if args.separate:
        assert separator is not None
        record["stems"] = _stem_bundle(args, waveform, separator, target.series_root, source_key)
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
    return record


def _extracted(args: argparse.Namespace, out_root: Path) -> list[dict[str, object]]:
    """음원을 디코드해 행을 쌓는다. **행마다 즉시 쓴다.**"""
    # **같은 산출물에 둘이 못 쓰게 한다** (D-0077). 이어받기가 같은 파일에 append하므로,
    # 동시에 돌면 줄이 섞여 파일이 통째로 깨진다. **나가는 길이 몇이든 커널이 풀어 준다.**
    with batch_lock(out_root, LOCK_NAME):
        return _rows(args, out_root)


def _rows(args: argparse.Namespace, out_root: Path) -> list[dict[str, object]]:
    """잠금을 쥔 채 행을 쌓는다."""
    target = _target(args, out_root)
    separator = _separator(args)
    saved, series_root = target.saved, target.series_root
    done, remaining, tracks, root = target.done, target.remaining, target.tracks, target.root
    decoder = FfmpegAudioDecoder()
    rows: list[dict[str, object]] = []
    failed = 0
    saved.parent.mkdir(parents=True, exist_ok=True)
    # **행마다 즉시 쓴다.** 전에는 1004곡을 메모리에 쌓고 마지막에 한 번 썼다.
    # 중간에 끊기면 전부 사라졌고, GPU로 한 시간 반짜리 작업에서 실제로 겪었다.
    stream = saved.open("a", encoding="utf-8")
    for index, track in enumerate(remaining, start=1):
        source_key = track.source_key
        path = root / source_key
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
            measured = _measure(args, waveform, series_root, source_key)
        except Exception:
            failed += 1
            continue
        record = _record(args, target, source_key, waveform, measured, separator)
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
    print(
        f"저장: {saved} · 크로마 {args.chroma} · 프로파일 {args.profile}"
        f" · gamma {args.gamma:g} · 배음 {args.harmonic:g} · 집계 {args.aggregate}"
        f"{f'({args.window_seconds:g}초 창)' if args.aggregate == 'median' else ''}"
        f" (실패·부재 {failed})\n"
    )
    return rows


def run(args: argparse.Namespace) -> int:
    """`hathor ingest keys`. 세 갈래가 같은 보고로 모인다."""
    out_root = Path(args.out)
    try:
        if args.from_bundles:  # 옛 규격을 다시 쓰고 같은 보고로 이어 간다 (O-63 · D-0211)
            rows = ingest_keys_bundles.run(args) or []
            if not rows:
                return 2
        elif args.replay is not None:
            rows = _replayed(args)
        else:
            rows = _extracted(args, out_root)
    except BatchAlreadyRunningError as exc:
        print(f"{exc}. 끝나기를 기다리거나 그 쪽을 멈춘다.", file=sys.stderr)
        return 1
    except _StopError as stop:
        return stop.code
    return report(rows, args)


def build(parser: argparse.ArgumentParser) -> None:
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


COMMANDS: tuple[Command, ...] = (
    Command(
        "keys",
        "코퍼스 조성 분포 실측 (D-0054 · O-22(닫힘 D-0201))",
        build,
        run,
    ),
)
"""`ingest` 표에 실리는 것 (D-0273)."""
