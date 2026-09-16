"""`ingest keys --from-bundles` — 곡별 묶음에서 옛 `keys` 규격을 쓴다 (O-63 · D-0211).

**`main.py`에 두지 않는다.** D-0127 이래 새 명령은 자기 모듈로 간다.

    var/ingest/audio/*.npz  →  keys-<시각>.keys.jsonl · keys-<시각>.series/

**디코딩하지 않는다.** 묶음에서 크로마만 연다. 행을 돌려주면 `ingest keys`의 분포
보고가 그대로 이어 돈다 — 옛 산출물과 같은 표를 같은 코드로 낸다.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.application.keys_from_bundles import keys_from_bundle, replay_guard
from hathor.domain.services.key_estimation import HARMONIC_STRENGTH
from hathor.infrastructure.chroma_series_store import write_series
from hathor.infrastructure.track_bundle_store import BUNDLE_DIRNAME, TrackBundleStore

if TYPE_CHECKING:
    import argparse

READ_PREFIXES = ("chroma/", "chroma_series/")


def add_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from-bundles",
        action="store_true",
        help="`ingest all` 묶음에서 keys.jsonl·series를 다시 쓴다. 음원도 GPU도 안 쓴다 (O-63)",
    )


def refusal(args: argparse.Namespace) -> str:
    """같이 못 쓰는 손잡이. **조용히 무시하면 *\"효과가 없다\"*로 읽힌다** (D-0191).

    묶음 크로마는 이미 뽑혀 있어 추출 손잡이가 안 걸린다. `--profile`만 걸린다.
    **`--harmonic`도 못 쓴다** — 묶음이 뺀 강도가 행에 적히고, 다른 강도는 `--replay`가
    그 행을 읽을 때 거절한다.
    """
    used = [
        flag
        for flag, name, default in (
            ("--replay", "replay", None),
            ("--separate", "separate", False),
            ("--halves", "halves", False),
            ("--series", "series", None),
            ("--tuning", "tuning", False),
            ("--limit", "limit", None),
            ("--aggregate", "aggregate", "mean"),
            ("--chroma", "chroma", "cq"),
            ("--gamma", "gamma", 0.0),
            ("--harmonic", "harmonic", HARMONIC_STRENGTH),
            ("--harmonic-sweep", "harmonic_sweep", False),
        )
        if getattr(args, name, default) != default
    ]
    if not used:
        return ""
    return (
        f"--from-bundles는 {' · '.join(used)}를 못 쓴다. 크로마가 이미 뽑혀 있어 --profile만 걸린다"
    )


def replay_strength(rows: list[dict[str, object]], args: argparse.Namespace) -> float | None:
    """`--replay`가 더 뺄 배음 강도. **못 하면 사유를 찍고 `None`** (D-0211)."""
    found = replay_guard(rows, args.harmonic, sweep=args.harmonic_sweep)
    if isinstance(found, str):
        print(found, file=sys.stderr)
        return None
    return found


def run(args: argparse.Namespace) -> list[dict[str, object]] | None:
    """행을 쓰고 돌려준다. **못 쓰면 `None`** — 사유는 표준 오류로 찍었다."""
    if reason := refusal(args):
        print(reason, file=sys.stderr)
        return None
    out_root = Path(args.out)
    store = TrackBundleStore(out_root / BUNDLE_DIRNAME)
    found = list(store.manifests())
    if not found:
        print(f"묶음이 없다: {store.root}. 먼저 `ingest all`을 돌린다", file=sys.stderr)
        return None

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    saved = out_root / f"keys-{stamp}.keys.jsonl"
    series_root = out_root / f"keys-{stamp}.series"
    rows: list[dict[str, object]] = []
    failed: list[tuple[str, str]] = []
    # **다 만든 뒤에 이름을 준다.** 도중에 죽은 파일이 `find_keys_store`에 걸리면
    # 절반짜리 사전으로 생성이 돈다.
    partial = saved.with_suffix(".jsonl.tmp")
    with partial.open("w", encoding="utf-8") as stream:
        for index, (source_key, path, manifest) in enumerate(found, start=1):
            try:
                made = keys_from_bundle(
                    source_key, store.read(path, READ_PREFIXES), manifest, profile=args.profile
                )
            except (KeyError, ValueError, OSError) as error:
                # **원인을 적는다** (D-0203). 행이 조용히 빠지면 곡 수로만 보인다.
                failed.append((source_key, f"{type(error).__name__}: {error}"))
                continue
            for name, series in made.series.items():
                write_series(series_root, source_key, name, series)
            stream.write(json.dumps(made.row, ensure_ascii=False) + "\n")
            rows.append(made.row)
            if index % 200 == 0:
                print(f"  {index}/{len(found)}", file=sys.stderr, flush=True)
    if not rows:
        partial.unlink(missing_ok=True)
        print(f"행을 하나도 못 만들었다. 첫 실패: {failed[:1]}", file=sys.stderr)
        return None
    partial.replace(saved)

    print(f"묶음 {len(found)}개 → {saved.name} · {series_root.name}/ · 실패 {len(failed)}")
    for source_key, reason in failed[:5]:
        print(f"  !! {source_key[:50]}  {reason}", file=sys.stderr)
    first = rows[0]
    stems = first.get("stem_sets")
    named = ", ".join(str(name) for name in stems) if isinstance(stems, list) else ""
    print(
        f"조건: 프로파일 {first['profile']} · 배음 {first['harmonic']} (묶음이 이미 뺐다)"
        f" · 스템 {named or '없음'}"
        " · 조합·반쪽 없음\n"
    )
    return rows
