"""`hathor taste` — 쌍대비교 라벨 수집 (O-10 · D-0012 · D-0421).

**`main.py`에 있었다.** D-0421이 되묻기를 넣으며 그 파일이 못 박은 길이를 넘었고,
**못을 올리는 대신 뺐다** — `main.py`는 §3에 적힌 빚이고 `extraction.py`가 같은
이유로 먼저 나갔다 (D-0250). 못은 늘리라고 있는 것이 아니다 (D-0117).

여기 있는 것은 **사람이 누르는 자리**다. 키 하나를 어떻게 읽을지는 `taste_input`이
따로 들고 있다 — 오타가 라벨을 먹은 자리라 시험이 붙어 있다 (D-0419).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hathor.application.evaluate_fusion import DEFAULT_SEED
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.interfaces.cli.feature_sources import open_feature_source
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import DEFAULT_FEATURE_DIRNAME, DEFAULT_OUTPUT_ROOT
from hathor.interfaces.cli.taste_input import read_answer
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:  # pragma: no cover - 검사기만 읽는다
    import argparse
    from collections.abc import Mapping

    from hathor.domain.entities.track_tags import TrackTags


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
    from hathor.domain.services.pair_sampling import (
        REPEAT_MODE,
        presentation_order,
        sample_pairs,
        with_repeats,
    )
    from hathor.infrastructure.jsonl_preference_store import JsonlPreferenceStore
    from hathor.interfaces.cli import taste_input

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
    fresh = sample_pairs(
        keys,
        args.count,
        seed=args.seed + len(answered),
        exclude=[(item.left, item.right) for item in answered],
    )
    if not fresh:
        print("낼 수 있는 새 문항이 없다")
        return 0

    # **되묻기를 섞는다** (D-0421). 안 섞으면 나중에 나올 정확도가 «모형이 나쁘다»인지
    # «판정자가 흔들린다»인지 못 가린다. 지난 세션에 **판단한** 쌍만 되묻는다.
    pairs = with_repeats(
        fresh,
        [(item.left, item.right) for item in answered if not item.skipped],
        seed=args.seed + len(answered),
    )

    repeats = sum(1 for _, again in pairs if again)
    print(
        f"곡 {len(keys)}개 / 기록된 응답 {len(answered)}건 / "
        f"이번 문항 {len(pairs)}개 (되묻기 {repeats}개)"
    )
    print("1 또는 2로 답한다. s=건너뛰기, q=중단. 답할 때마다 즉시 저장된다.")
    print("**다른 키는 안 받는다** — 오타가 「건너뜀」으로 저장되면 그 쌍은 다시 안 나온다.\n")

    recorded = 0
    for index, (pair, again) in enumerate(pairs, 1):
        first, second = presentation_order(pair, seed=args.seed + index)
        print(f"[{index}/{len(pairs)}]")
        print(f"  1) {_format_track(first, tags)}")
        print(f"  2) {_format_track(second, tags)}")
        answer = read_answer(input, print)
        if answer == taste_input.QUIT:
            print("\n중단한다. 여기까지 저장됐다.")
            break
        if answer == taste_input.PICK_LEFT:
            winner = Side.LEFT if first == pair[0] else Side.RIGHT
        elif answer == taste_input.PICK_RIGHT:
            winner = Side.LEFT if second == pair[0] else Side.RIGHT
        else:
            winner = None
        store.append(
            PreferenceComparison(
                left=pair[0],
                right=pair[1],
                winner=winner,
                recorded_at=datetime.now(UTC).isoformat(),
                mode=REPEAT_MODE if again else "random",
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
    from hathor.domain.entities.preference_comparison import agreement
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

    # **판정자의 천장** (D-0421). 어떤 모형도 이 선을 못 넘는다.
    asked, matched = agreement(store.read_all())
    if asked:
        print(f"자기일치 {matched}/{asked} ({matched / asked:.0%}) — **모형의 천장이다**")
    else:
        print("자기일치: 아직 모른다 — 되물은 쌍이 없다")
    print(f"저장: {store.path}")
    return 0


COMMANDS: tuple[Command, ...] = (
    Command(
        "compare",
        "쌍대비교 문항을 내고 응답을 기록한다",
        _build_taste_compare,
        _run_taste_compare,
    ),
    Command("status", "수집 현황", _build_taste_status, _run_taste_status),
)
"""`taste` 표에 실리는 것 (D-0273). **등재와 배선이 한 자리에 있어야** 검사가 본다."""
