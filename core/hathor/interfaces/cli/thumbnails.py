"""`hathor ingest thumbnails` — 곡마다 후렴 20여 초를 골라 적는다 (D-0430).

    hathor ingest thumbnails --stem-set other
    hathor ingest thumbnails --seconds 23 --sample 20

**새로 뽑는 것이 없다.** 이미 있는 `chroma_series`만 읽는다 — 1004곡 전수가 이미
있고(D-0105 계열), 논문이 요구하는 입력이 정확히 그것이다.

### 창 길이를 안 지어낸다

창이 몇 초짜리인지는 `series_settings`가 든다. 선언이 없으면 **죽는다** — 거기서
기본값을 가정하면 «몇 번째 창»을 «몇 초»로 옮기는 셈이 통째로 틀리고, 틀린 초를
사람이 들어 보면 **도구가 아니라 논문이 틀렸다고 읽는다** (GR-0.5 · D-0292).

### 점수를 같이 적는다

낮은 점수는 *«반복을 못 찾았다»*는 뜻이다 (D-0203). 사람이 들어 볼 50곡을 고를 때
**낮은 쪽부터 듣는 것이 싸다** — 맞는 것을 백 번 확인해도 새로 아는 것이 없다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple

from hathor.domain.services.thumbnail import thumbnail, window_count
from hathor.infrastructure.chroma_series_store import (
    find_series_root,
    load_named_series,
    series_settings,
)
from hathor.interfaces.cli.roots import announce_series, missing_given_path
from hathor.shared.config.paths import repo_root, resolve_path

DEFAULT_SECONDS = 23.0
"""논문의 권고. 재현/정밀 곡선이 교차하는 자리이고 **평균 후렴 길이**가 그만큼이다."""

DEFAULT_STEM_SET = "other"
DEFAULT_SAMPLE = 10


class Picked(NamedTuple):
    """곡 하나의 결과. **형이 있는 줄이다** — `dict[str, object]`는 쓰는 쪽에서 다 깨진다."""

    source_key: str
    start_sec: float
    end_sec: float
    repeat_sec: float
    score: float
    windows: int

    def record(self) -> dict[str, object]:
        """jsonl 한 줄. 칸 이름이 곧 스키마다 (D-0203)."""
        return self._asdict()


def build_thumbnails(parser: argparse.ArgumentParser) -> None:
    """`hathor ingest thumbnails` 인자."""
    parser.add_argument(
        "--series", type=resolve_path, default=None, help="시계열 폴더. 생략하면 가장 최근 것"
    )
    parser.add_argument("--stem-set", default=DEFAULT_STEM_SET, help="어느 스템의 크로마인가")
    parser.add_argument(
        "--seconds", type=float, default=DEFAULT_SECONDS, help="고를 구간 길이 (논문 권고 20~25)"
    )
    parser.add_argument("--out", type=resolve_path, default=None, help="jsonl 경로")
    parser.add_argument(
        "--sample", type=int, default=DEFAULT_SAMPLE, help="점수가 낮은 쪽부터 몇 곡을 찍나"
    )


def _series_root(args: argparse.Namespace) -> Path | None:
    if args.series is not None:
        given: Path = args.series
        if given.is_dir():
            return given
        missing_given_path(given, "--series")
        return None
    found = find_series_root(repo_root(), args.stem_set)
    if found is None:
        print(
            f"{args.stem_set} 시계열 폴더가 없다 — 먼저 뽑는다: hathor ingest keys --separate",
            file=sys.stderr,
        )
    return found


def _seconds_per_window(root: Path) -> float | None:
    """창 하나가 몇 초인가. **없으면 지어내지 않는다** (GR-0.5)."""
    said = series_settings(root).get("series_seconds")
    if isinstance(said, (int, float)) and said > 0:
        return float(said)
    print(
        f"{root.name}에 창 길이(series_seconds) 선언이 없다. 창 번호를 초로 못 옮긴다.\n"
        "  선언을 되살리거나 그 폴더를 다시 뽑는다 (D-0295 · D-0305)",
        file=sys.stderr,
    )
    return None


def run_thumbnails(args: argparse.Namespace) -> int:
    """곡마다 후렴 구간을 골라 jsonl로 적는다."""
    root = _series_root(args)
    if root is None:
        return 1
    announce_series(root, args.stem_set)
    span = _seconds_per_window(root)
    if span is None:
        return 1

    width = window_count(args.seconds, span)
    rows: list[Picked] = []
    short = 0
    for name, series in load_named_series(root, args.stem_set):
        found = thumbnail(series, window=width)
        if found is None:
            short += 1
            continue
        rows.append(
            Picked(
                source_key=name,
                start_sec=round(found.start * span, 2),
                end_sec=round((found.start + found.length) * span, 2),
                repeat_sec=round((found.start + found.lag) * span, 2),
                score=round(found.score, 4),
                windows=found.length,
            )
        )

    if not rows:
        print(f"{root.name}에서 한 곡도 못 골랐다 (너무 짧은 곡 {short}개)", file=sys.stderr)
        return 1

    out = args.out if args.out is not None else root.parent / f"{root.name}.thumbnails.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda one: one.source_key):
            stream.write(json.dumps(row.record(), ensure_ascii=False) + "\n")

    scores = sorted(row.score for row in rows)
    middle = scores[len(scores) // 2]
    print(f"{root.name} · 곡 {len(rows)} · 못 고른 곡 {short} · 창 {width}개({args.seconds:.0f}초)")
    print(f"  점수 최저 {scores[0]:.3f} · 중앙 {middle:.3f} · 최고 {scores[-1]:.3f}")
    print(f"  {out}")
    if args.sample > 0:
        print(f"\n  점수가 낮은 {args.sample}곡 — 여기부터 들어 본다")
        for row in sorted(rows, key=lambda one: one.score)[: args.sample]:
            when = f"{_clock(row.start_sec)}~{_clock(row.end_sec)}"
            print(f"    {row.score:.3f}  {when}  {row.source_key}")
    return 0


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"
