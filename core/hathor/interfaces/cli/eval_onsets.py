"""`eval onsets` — 뽑아 둔 포락선이 실물에서 박을 담는가 (D-0314).

**계산은 `application/evaluate_onsets.py`가 한다.** 비교선을 왜 그렇게 골랐는지와
위상 돌림이 왜 귀무가 아닌지가 거기 적혀 있다 — 이 파일은 표를 그릴 뿐이다 (D-0281).
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from hathor.application.evaluate_onsets import BEAT_FLOOR, BeatGain, load_lines
from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore
from hathor.infrastructure.onset_store import find_envelope_root
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import DEFAULT_OUTPUT_ROOT
from hathor.interfaces.cli.tables import render_table
from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    from pathlib import Path


def warnings(gain: BeatGain) -> list[str]:
    """자가 고장났다고 신고할 것이 있는가 (D-0315).

    **`eval chord-quality`의 `warnings(stem)`과 같은 자리다** — 표시 계층이 계산하지
    않으므로 판정은 `BeatGain`이 들고, 여기서는 **무엇을 화면에 적을지**만 정한다.
    """
    if not gain.ruler_broken:
        return []
    return [
        "  ⚠ **음성 대조가 실측을 이겼다.** 박 구조를 지운 자료가 더 뾰족할 수는\n"
        "    없으므로 이것은 «박이 없다»가 아니라 **자가 박이 아닌 것을 재고 있다**는\n"
        "    뜻이다 (D-0315). 첫 실물 1004곡이 그랬고 원인은 곡의 느린 강약이었다."
    ]


def verdict(gain: BeatGain) -> str:
    """판정 한 줄. **셋이다** — 담는다 · 말할 수 없다 · 고장 (D-0315)."""
    if gain.ruler_broken:
        return "자가 고장났다 — 음성 대조가 이겼다"
    return "포락선이 박을 담는다" if gain.carries_beat else "담는다고 말할 수 없다"


def _resolve(args: argparse.Namespace) -> Path | None:
    from hathor.shared.config.paths import repo_root

    root = args.envelopes
    if root is None:
        root = find_envelope_root(repo_root())
    if root is None or not root.is_dir():
        print(
            "온셋 포락선이 없다. `hathor ingest onsets`를 먼저 돌린다",
            file=sys.stderr,
        )
        return None
    resolved: Path = root
    return resolved


def run_eval_onsets(args: argparse.Namespace) -> int:
    """포락선 세 선을 재고 짝지은 이득으로 판정한다 (D-0314)."""
    folder = _resolve(args)
    if folder is None:
        return 2
    measured, control, rolled_line = load_lines(folder, limit=args.limit, seed=args.seed)
    if not measured.ratios:
        print(f"포락선이 없다: {folder}", file=sys.stderr)
        return 2

    print(f"── 온셋 박 · {folder.name} · {len(measured.ratios)}곡")
    for text in render_table(
        (("선", "<12"), ("뾰족함", ">9.3f"), ("고른비율", ">10.1%")),
        [
            (one.label, one.mean_ratio, one.decision_rate)
            for one in (measured, control, rolled_line)
        ],
    ):
        print(f"  {text}")

    gain = BeatGain(measured=measured, control=control)
    print()
    for text in render_table(
        (
            ("짝지은이득", "<12"),
            ("이득", ">9.3f"),
            ("표준오차", ">10.4f"),
            ("t", ">8.2f"),
            ("곡승률", ">9.1%"),
        ),
        [("실측-섞음", gain.gain, gain.standard_error, gain.t_statistic, gain.win_rate)],
    ):
        print(f"  {text}")
    for notice in warnings(gain):
        print(notice)
    print(f"\n판정: **{verdict(gain)}**  (짝지은 이득 · 문턱 |t| > {BEAT_FLOOR:.0f} · D-0315)\n")

    print("--- 읽는 법 ---")
    print("**뾰족함이 지표다** — 자기상관 봉우리가 평균보다 몇 배 높은가. `margin`을 쓰면")
    print("**거꾸로 간다**: 진짜 주기는 배수 지연에서도 봉우리가 서므로 1등과 2등의 차가")
    print("작아진다. 120BPM 클릭 트랙에서 `margin`이 섞은 잡음보다 낮았다 (D-0314).")
    print("**포락선을 차분한 뒤 잰다** (D-0315) — 안 하면 곡의 느린 강약이 지연 전체에")
    print("넓은 언덕을 만들어 분모를 부풀린다. 차분 없이 잰 첫 실물에서 실측 2.782가")
    print("섞음 3.137보다 **낮았다.** 클릭 트랙에 20초 강약을 입히니 합성에서 재현됐다.")
    print("**음성 대조가 실측을 이기면 고장이다** — 구조를 지운 쪽이 이길 수는 없다.")
    print("**`시간 섞음`이 음성 대조다** — 프레임 순서만 섞어 박 구조를 없애고 값 분포는")
    print("남긴다. **`위상 돌림`은 귀무가 아니다**: 자기상관이 순환 이동에 거의 불변이라")
    print("실측과 같은 값이 나온다. 표에 두는 것은 **그것을 확인하라고**이며 판정은 안 든다.")
    print("**판정은 짝지은 차다** (D-0311) — 같은 곡에서 실측과 섞음을 빼고 그 차의")
    print("표준오차를 낸다. 두 선을 따로 합치면 짝짓기를 버린다 (D-0087 · D-0300).")

    JsonEvaluationStore(args.out).write(
        {
            "folder": folder.name,
            "tracks": len(measured.ratios),
            "seed": args.seed,
            "lines": {
                one.label: {
                    "mean_ratio": round(one.mean_ratio, 6),
                    "decision_rate": round(one.decision_rate, 4),
                }
                for one in (measured, control, rolled_line)
            },
            "paired": gain.as_record(),
        },
        "onsets",
    )
    return 0


def _build_onsets(parser: argparse.ArgumentParser) -> None:
    """`hathor eval onsets` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--envelopes", type=resolve_path, default=None, help="`keys-*.onsets` 폴더 (미지정 시 최신)"
    )
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    parser.add_argument("--seed", type=int, default=20260930, help="섞음·돌림 시드")


ONSETS = Command(
    "onsets",
    "뽑아 둔 포락선이 실물에서 박을 담는가 (D-0314)",
    _build_onsets,
    run_eval_onsets,
)
"""`eval` 표에 실리는 것. **등재는 `eval_priors.COMMANDS`가 든다** — `main.py`가 못에
박혀 있어 묶음 자리가 없다 (D-0302와 같은 자리)."""

__all__ = ["ONSETS", "run_eval_onsets", "verdict", "warnings"]
