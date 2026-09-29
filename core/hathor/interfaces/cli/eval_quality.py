"""`eval chord-quality` — 창별 화음 품질 어휘와 교란 둘 (O-64 · D-0300 · D-0302).

**계산은 `application/evaluate_chord_quality.py`가 한다.** 실측 수치와 교란 두 축의 읽기
규칙이 거기 적혀 있다 — 이 파일은 인자를 받아 표를 그릴 뿐이다 (D-0281의 계약).

`eval_priors.py`에서 내려왔다. 첫 실측이 교란 둘을 남기고 쓸기 코드가 붙으면서 한 파일에
축이 둘 이상 들어갔다.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from hathor.application.evaluate_chord_quality import (
    GROUPS,
    QualityGap,
    QualitySweep,
    sweep_groups,
    sweep_sustained,
)
from hathor.domain.services.harmony_quality import QUALITIES
from hathor.domain.services.stem_sets import POLYPHONIC_STEMS, SERIES_STEMS, stem_parts
from hathor.infrastructure.chroma_series_store import find_series_root, load_series, series_settings
from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import DEFAULT_OUTPUT_ROOT
from hathor.interfaces.cli.tables import render_table
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    from pathlib import Path

MISSING = "—"
"""잴 창이 없는 열. **`0.0000`을 찍지 않는다** (GR-0.5 · D-0302)."""


def _cell(item: QualityGap | None, quality: str) -> str:
    if item is None:
        return MISSING
    return f"{item.quality.get(quality, 0.0):+.4f}"


def _sweep_lines(sweep: QualitySweep) -> list[str]:
    """품질을 행, 쓸기 값을 열로 그린다. 마지막 두 행이 4음 차와 창 수다.

    **값을 문자열로 미리 만든다.** 창이 없는 열은 `—`이고 수 형식 명세에는 넣을 수 없다 —
    그 칸을 0으로 채우면 표가 거짓말을 한다.
    """
    spec = [("품질", "<6"), *[(name, ">9") for name in sweep.labels]]
    rows: list[list[object]] = [
        [quality, *[_cell(item, quality) for item in sweep.found]] for quality in QUALITIES
    ]
    rows.append(
        ["4음", *[MISSING if item is None else f"{item.seventh:+.4f}" for item in sweep.found]]
    )
    rows.append(["창", *[MISSING if item is None else f"{item.windows:d}" for item in sweep.found]])
    return render_table(spec, rows)


def warnings(stem: str) -> list[str]:
    """이 스템으로 화음 품질을 재는 것이 무엇을 놓치는가 (D-0302 · D-0303).

    **둘은 다른 결함이다.** 근음 누락은 판정을 3음 쪽으로 기울이고(교란 1), 단선율은
    판정 자체를 뜻 없게 만든다. 하나만 찍으면 나머지를 안 본다.
    """
    found: list[str] = []
    if stem not in POLYPHONIC_STEMS:
        found.append(
            f"  ⚠ 스템 `{stem}`은 사실상 **단선율이다** (D-0099가 겹치지 않는 관측으로 둔 것이며\n"
            "    화성 사전이 아니다). 창에 한 음만 실리면 어느 템플릿도 안 맞는데 `argmax`는\n"
            "    그래도 하나를 고른다 — **이 표의 수를 화음 어휘로 인용하지 않는다** (D-0303)."
        )
    if "bass" not in stem_parts(stem):
        found.append(
            f"  ⚠ 스템 `{stem}`은 베이스를 뺀 것이라 **근음을 버린다** (D-0073 표).\n"
            "    7화음은 근음과 7음의 대비로 갈리므로 교란이다 —"
            " `--stem mix`로 같이 재서 견준다 (D-0302)."
        )
    return found


def _resolve(args: argparse.Namespace) -> Path | None:
    from hathor.shared.config.paths import repo_root

    root = args.series
    if root is None:
        root = find_series_root(repo_root(), args.stem)
    if root is None or not root.is_dir():
        print(
            "크로마 시계열이 없다. `hathor ingest keys --series 2 --separate`를 먼저 돌린다",
            file=sys.stderr,
        )
        return None
    resolved: Path = root
    return resolved


def run_eval_chord_quality(args: argparse.Namespace) -> int:
    """창별 화음 품질 어휘와 교란 둘을 실측한다 (O-64 닫힘 D-0305).

    **O-64 (닫힘 D-0305)가 적은 측정이 아니다.** 원문은 *"7음 성분이 3화음 대비 얼마나 실리는지"*를
    재려 했는데, 다이어토닉에서 7음으로만 나오는 음정이 하나도 없어 평균 크로마로는
    원리적으로 못 가른다. 창 하나를 화음 하나로 보는 템플릿 적합으로 갈아탔다.

    **판정은 코퍼스 자기 순열 귀무와의 차로만 한다.** 절대 비율에는 자의 4음 편향이
    0.5440만큼 남아 있다 (D-0300).
    """
    root = _resolve(args)
    if root is None:
        return 2
    songs = load_series(root, args.stem)
    if not songs:
        print(f"창이 없다: {root} (스템 {args.stem})", file=sys.stderr)
        return 2

    span = series_settings(root).get("window_seconds", "?")
    total = sum(len(series) for series in songs)
    print(
        f"── 화음 품질 어휘 · {root.name} · 스템 {args.stem} · 창 {span}초 · "
        f"{len(songs)}곡 {total}창"
    )
    for warning in warnings(args.stem):
        print(warning)

    grouped = sweep_groups(songs, seed=args.seed)
    print("── 교란 2a · 창 묶기 — **뒤집히면 전환 번짐, 커지면 진짜다** (D-0104 · D-0302)")
    for line in _sweep_lines(grouped):
        print(f"  {line}")

    sustained = sweep_sustained(songs, seed=args.seed)
    print("── 교란 2b · 건너뛴 이웃이 닮은 창만 — **뒤집히면 전환 번짐이다**")
    for line in _sweep_lines(sustained):
        print(f"  {line}")

    print("  **차로만 읽는다.** 절대 비율에는 자의 4음 편향 0.5440이 섞여 있다 (D-0300).")
    JsonEvaluationStore(args.out).write(
        {
            "series_root": root.name,
            "stem_set": args.stem,
            "window_seconds": span,
            "tracks": len(songs),
            "windows": total,
            "seed": args.seed,
            "grouped": grouped.as_record(),
            "sustained": sustained.as_record(),
        },
        "chord-quality",
    )
    return 0


def _build_chord_quality(parser: argparse.ArgumentParser) -> None:
    """`hathor eval chord-quality` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--series", type=resolve_path, default=None, help="`keys-*.series` 폴더 (미지정 시 최신)"
    )
    parser.add_argument(
        "--stem",
        default="other",
        choices=SERIES_STEMS,
        help="시계열이 있는 스템만 (D-0106). `mix`는 근음을 담는다",
    )
    parser.add_argument("--seed", type=int, default=20260929, help="빈 순열 귀무 시드")


CHORD_QUALITY = Command(
    "chord-quality",
    "창별 화음 품질 어휘를 순열 귀무와 대조한다 (O-64 · D-0300)",
    _build_chord_quality,
    run_eval_chord_quality,
)
"""`eval` 표에 실리는 것. **등재는 `eval_priors.COMMANDS`가 든다** — `main.py`가 못에 박혀
있어 묶음 하나를 더 들일 자리가 없다 (D-0302)."""

__all__ = ["CHORD_QUALITY", "GROUPS", "MISSING", "run_eval_chord_quality", "warnings"]
