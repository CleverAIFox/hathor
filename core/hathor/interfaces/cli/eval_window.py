"""`eval window-length` — 묶은 것과 직접 뽑은 것을 실물에서 맞댄다 (D-0104 · D-0320).

**계산은 `application/evaluate_window_length.py`가 한다** (D-0281의 계약). 왜 해시로
짝짓는지, 0곡일 때 왜 `None`인지가 거기 적혀 있다.

**뽑기가 아니라 판정이다.** D-0319가 `ingest keys --series 2`를 「닫힌다」의 자리에
적었고 그것은 자료만 낸다 — 이 명령이 그 자료를 읽어 판정한다.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from hathor.application.evaluate_window_length import (
    PRODUCTION_CEILING,
    WindowMatch,
    stems,
    sweep,
)
from hathor.infrastructure.chroma_series_store import series_settings
from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import DEFAULT_OUTPUT_ROOT
from hathor.interfaces.cli.tables import render_table
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    from pathlib import Path

MISSING = "—"
"""못 잰 칸. **`0`을 찍지 않는다** (GR-0.5)."""

SECONDS_KEYS = ("window_seconds", "series_seconds")
"""창 길이가 적힌 이름 **둘**. 선언 파일은 `window_seconds`, 형제 `jsonl`은
`series_seconds`다 (D-0073 · D-0305). **하나만 보면 옛 폴더가 «선언 없음»이 된다.**"""


def window_seconds(root: Path) -> float | None:
    """폴더가 선언한 창 길이. **없으면 `None`이다** — 배수를 짐작하지 않는다.

    **여기 있는 이유는 계층이다** — 선언을 읽는 것은 `infrastructure`의 일이고
    `application`은 그것을 모른다 (`애플리케이션은 구현체를 모른다` 계약).
    """
    settings = series_settings(root)
    for key in SECONDS_KEYS:
        found = settings.get(key)
        if isinstance(found, bool):
            continue
        if isinstance(found, int | float) and float(found) > 0.0:
            return float(found)
        if isinstance(found, str):
            try:
                value = float(found)
            except ValueError:
                continue
            if value > 0.0:
                return value
    return None


def series_folders(root: Path) -> list[Path]:
    """`var/ingest`의 시계열 폴더 — **새 것부터**. 이름이 타임스탬프라 이름 순이 시간 순이다."""
    ingest = root / "var" / "ingest"
    return sorted(ingest.glob("keys-*.series"), reverse=True) if ingest.is_dir() else []


def pick_pair(root: Path) -> tuple[Path, Path, int] | None:
    """맞댈 두 폴더를 스스로 고른다 (D-0321).

    **이름을 사람이 채우게 두지 않는다.** 폴더 이름이 실행 시각이라 미리 알 수 없고,
    D-0320이 안내에 `<새로 생긴 2초 폴더>`라는 빈칸을 남겼다 — **복사해 붙일 수 없는
    명령은 안내가 아니다.**

    조건 셋을 다 만족하는 가장 **최근** 쌍을 고른다.

    1. 창 길이가 정수배다 (`group_series`가 정수배만 만든다).
    2. 스템이 하나라도 겹친다 (분리 여부가 다르면 안 겹친다).
    3. 둘 다 창 길이를 선언한다.

    **못 고르면 `None`이고 화면이 폴더 목록을 낸다** — 「없다」만 찍으면 읽는 사람이
    자기가 뭘 잘못했는지 찾기 시작한다 (D-0292와 같은 자리).
    """
    known = [
        (folder, seconds, set(stems(folder)))
        for folder in series_folders(root)
        if (seconds := window_seconds(folder)) is not None
    ]
    for long_root, long_seconds, long_stems in known:
        for short_root, short_seconds, short_stems in known:
            if short_seconds >= long_seconds or not (short_stems & long_stems):
                continue
            ratio = long_seconds / short_seconds
            factor = round(ratio)
            if factor >= 2 and abs(ratio - factor) < 1e-6:
                return short_root, long_root, factor
    return None


def folder_lines(root: Path) -> list[str]:
    """있는 폴더와 그 조건. **못 골랐을 때 눈으로 보고 정하는 표다.**"""
    found = series_folders(root)
    if not found:
        return ["`var/ingest`에 `keys-*.series`가 없다. `ingest keys --series <초>`를 먼저 돌린다"]
    lines = ["있는 시계열 폴더 (새 것부터):"]
    for folder in found:
        seconds = window_seconds(folder)
        lines.append(
            f"  {folder.name}  창 {MISSING if seconds is None else f'{seconds:g}초'}"
            f"  스템 {list(stems(folder)) or MISSING}"
        )
    lines.append(
        "**창 길이가 정수배이고 스템이 겹치는 두 폴더**가 있어야 한다 —"
        " 분리 여부가 다르면 스템이 안 겹치므로 `--separate`를 같게 주고 다시 뽑는다."
    )
    return lines


def factor_of(short_root: Path, long_root: Path, given: int | None) -> int | None:
    """긴 창이 짧은 창의 몇 배인가. **짐작하지 않는다** (D-0320).

    폴더가 창 길이를 선언하지 않으면 `None`이고, 그때는 `--factor`로 사람이 준다.
    배수가 정수가 아니면 `group_series`로 만들 수 없으므로 거부한다.
    """
    if given is not None:
        return given if given >= 1 else None
    short, long = window_seconds(short_root), window_seconds(long_root)
    if short is None or long is None:
        return None
    ratio = long / short
    rounded = round(ratio)
    return rounded if rounded >= 1 and abs(ratio - rounded) < 1e-6 else None


def empty_notice(short_root: Path, long_root: Path) -> list[str]:
    """짝이 0일 때 **왜 0인지**를 적는다 (D-0320).

    가장 흔한 원인은 **분리 여부가 달라 스템이 안 겹치는 것**이다 — `--separate` 없이
    다시 뽑으면 `other`·`bass`가 없다. 그 다음이 `--limit`으로 곡 집합이 갈린 것이다.
    """
    left, right = stems(short_root), stems(long_root)
    shared = sorted(set(left) & set(right))
    found = [f"짝지은 곡이 0이다. 스템 — 짧은 창 {left or MISSING} · 긴 창 {right or MISSING}"]
    if not shared:
        found.append(
            "**겹치는 스템이 없다.** 분리 여부가 다르면 그렇다 —"
            " 긴 창도 `--separate --stem-sets`를 같게 주고 다시 뽑는다."
        )
    else:
        found.append(
            f"스템 {shared}는 겹치는데 곡이 안 겹친다. **`--limit`이 앞에서 N곡을 자르므로**"
            " 두 실행의 곡 순서가 같아야 한다."
        )
    return found


def _row(match: WindowMatch) -> tuple[object, ...]:
    middle, top, holds = match.median_gap, match.max_gap, match.holds
    return (
        match.stem,
        match.songs,
        MISSING if middle is None else f"{middle:.4f}",
        MISSING if top is None else f"{top:.4f}",
        MISSING if holds is None else ("선다" if holds else "**흔들린다**"),
    )


def run_eval_window_length(args: argparse.Namespace) -> int:
    """짧은 창을 묶은 것과 긴 창을 직접 뽑은 것의 거리를 실물에서 낸다 (D-0104)."""
    from hathor.shared.config.paths import repo_root

    short_root, long_root = args.short, args.long
    if short_root is None or long_root is None:
        picked = pick_pair(repo_root())
        if picked is None:
            print("맞댈 두 폴더를 못 골랐다.", file=sys.stderr)
            for text in folder_lines(repo_root()):
                print(f"  {text}", file=sys.stderr)
            return 2
        short_root, long_root, _ = picked
        print(f"골랐다 — 짧은 창 {short_root.name} · 긴 창 {long_root.name}")
    for root in (short_root, long_root):
        if not root.is_dir():
            print(f"시계열 폴더가 없다: {root}", file=sys.stderr)
            return 2

    factor = factor_of(short_root, long_root, args.factor)
    if factor is None:
        print(
            "창 길이 배수를 못 정했다. 폴더 선언이 없거나 정수배가 아니다 — `--factor`로 준다",
            file=sys.stderr,
        )
        return 2

    found = sweep(short_root, long_root, factor)
    total = sum(match.songs for match in found)
    print(
        f"── 창 길이 대조 · {short_root.name} x{factor} 대 {long_root.name}"
        f" · {total}곡 · 천장 {PRODUCTION_CEILING}"
    )
    if not total:
        for text in empty_notice(short_root, long_root):
            print(f"  {text}")
        print("\n판정: **못 쟀다**  (짝지은 곡이 없다 · GR-0.5)\n")
        return 2

    for text in render_table(
        (("스템", "<8"), ("곡", ">5d"), ("중앙거리", ">10"), ("최대거리", ">10"), ("전제", ">10")),
        [_row(match) for match in found if match.songs],
    ):
        print(f"  {text}")

    holds = [match.holds for match in found if match.holds is not None]
    passed = "창 길이는 분석 인자다" if holds and all(holds) else "**전제가 흔들린다**"
    print(f"\n판정: **{passed}**  (최대 거리 < {PRODUCTION_CEILING} · D-0104 · D-0320)\n")

    print("--- 읽는 법 ---")
    print("**D-0104의 전제다** — 짧게 뽑아 두고 묶어서 늘릴 수 있어야 «창 길이는 분석")
    print("인자다»가 선다. 무너지면 창 길이마다 다시 뽑아야 하고 그것이 1004곡 배치다.")
    print(f"**천장 {PRODUCTION_CEILING}은 합성에서 온 값이다** (D-0319) — 배음·강약이 있는")
    print("파형에서 x2 0.0078 · x4 0.0062였다. **순음에서는 0.0002였고 배음을 넣자 30배")
    print("커졌으므로 실물은 더 클 수 있다.** 그것을 재는 것이 이 명령이다.")
    print("**최대를 든다.** 평균은 곡 하나가 무너진 것을 감춘다.")

    JsonEvaluationStore(args.out).write(
        {
            "short_root": short_root.name,
            "long_root": long_root.name,
            "factor": factor,
            "songs": total,
            "ceiling": PRODUCTION_CEILING,
            "stems": [match.as_record() for match in found],
        },
        "window-length",
    )
    return 0


def _build_window_length(parser: argparse.ArgumentParser) -> None:
    """`hathor eval window-length` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--short",
        type=resolve_path,
        default=None,
        help="짧은 창 `keys-*.series`. **안 주면 스스로 고른다** (D-0321)",
    )
    parser.add_argument(
        "--long",
        type=resolve_path,
        default=None,
        help="긴 창 `keys-*.series`. **안 주면 스스로 고른다**",
    )
    parser.add_argument(
        "--factor",
        type=int,
        default=None,
        help="긴 창이 짧은 창의 몇 배인가. **안 주면 폴더 선언에서 읽는다**",
    )


WINDOW_LENGTH = Command(
    "window-length",
    "묶은 것과 직접 뽑은 것이 같은가 (D-0104 · D-0320)",
    _build_window_length,
    run_eval_window_length,
)
"""`eval` 표에 실리는 것. **등재는 `eval_priors.COMMANDS`가 든다** (D-0302와 같은 자리)."""

__all__ = [
    "WINDOW_LENGTH",
    "empty_notice",
    "factor_of",
    "folder_lines",
    "pick_pair",
    "run_eval_window_length",
    "series_folders",
    "window_seconds",
]
