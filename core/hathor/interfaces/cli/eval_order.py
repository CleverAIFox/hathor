"""`eval harmony-order` — 출력의 배열이 그 참조곡을 닮았는가 (O-32 · D-0112).

**`main.py`에서 내려왔다** (D-0127). D-0124가 유지 확률 배선으로 `main.py`를 3880에서
3955줄로 늘렸고, D-0117의 래칫이 D-0116 이래 처음으로 위로 움직였다.
**되돌리는 방법은 쪼개는 것뿐이다** — 출력을 줄이면 표를 못 읽는다.

이 파일은 **출력만 한다.** 판정도 통계도 `application/evaluate_order_conditioning`에
있다 (GR-2.2).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from hathor.infrastructure.chroma_series_store import (
    find_series_root,
    load_hold_probabilities,
    load_transition_priors,
)
from hathor.infrastructure.keys_jsonl_store import find_keys_store, load_degree_priors, load_tonics
from hathor.interfaces.cli.tables import parse_key, render_table

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from hathor.application.evaluate_order_conditioning import OrderReference, OrderReport


def run_eval_harmony_order(args: argparse.Namespace) -> int:
    """출력의 배열이 **그 참조곡의** 배열을 닮았는지 잰다 (O-32 · D-0112).

    **쌍 거리로는 안 된다.** 전이 사전을 주기만 하면 두 출력이 순서에서 달라진다 —
    곡 짝을 뒤섞은 사전을 줘도 그렇다. **"쓰이고 있다"와 "맞는 것을 쓴다"는 다르다.**
    """
    from hathor.application.evaluate_harmony_output import OutputCondition, ReferencePrior
    from hathor.application.evaluate_order_conditioning import (
        EvaluateOrderConditioning,
        references_from,
        sweep_self_transition,
    )
    from hathor.shared.config.paths import repo_root as _root

    store = args.priors
    if store is None:
        store = find_keys_store(_root(), args.stem_set)
    series_root = args.series
    if series_root is None:
        series_root = find_series_root(_root(), args.stem_set)
    if store is None or not store.exists() or series_root is None:
        print("사전 또는 시계열 산출물을 찾지 못했다.", file=sys.stderr)
        return 1

    table = load_degree_priors(store, args.stem_set)
    names = sorted(table)[: args.songs]
    priors = [ReferencePrior(name, table[name]) for name in names]
    transitions = load_transition_priors(
        series_root, args.stem_set, names, tonics=load_tonics(store)
    )
    holds = load_hold_probabilities(series_root, args.stem_set, names) if args.use_hold else None
    references = references_from(priors, transitions, holds)
    if len(references) < 2:
        print(
            f"도수 사전과 전이 사전이 둘 다 있는 곡이 {len(references)}개다.",
            file=sys.stderr,
        )
        return 1

    condition = OutputCondition(
        seed_count=args.seeds,
        bar_count=args.bars,
        key=parse_key(args.key),
        seed=args.seed,
    )
    harness = EvaluateOrderConditioning(condition)
    print(
        f"곡 {len(references)}개 · 시드 {condition.seed_count} · {condition.bar_count}마디"
        f" · {condition.key} · 출처 {args.stem_set}\n"
        f"사전: {store.name} · 시계열: {series_root.name}\n"
    )
    rows: list[tuple[object, ...]] = []
    reports = {}
    lines = [("전이 없음", False, False), ("전이 있음", True, False)]
    if args.use_hold:
        lines.append(("전이+유지", True, True))
    for label, use, hold in lines:
        report = harness.run(references, use_transition=use, use_hold=hold)
        reports[label] = report
        rows.append(
            (
                label,
                report.mean_self,
                report.mean_other,
                report.gap,
                report.standard_error,
                report.t_statistic,
                report.win_rate,
            )
        )
    for text in render_table(
        (
            ("선", "<10"),
            ("self", ">9.4f"),
            ("other", ">9.4f"),
            ("other-self", ">12.4f"),
            ("표준오차", ">10.4f"),
            ("t", ">8.2f"),
            ("곡승률", ">9.1%"),
        ),
        rows,
    ):
        print(text)
    verdict = reports["전이 있음"].carries_reference_order
    print(f"\n판정: **{'출력이 참조곡의 배열을 담는다' if verdict else '안 담는다'}**\n")
    if args.use_hold:
        _report_hold(references, reports["전이 있음"], reports["전이+유지"])
    if args.self_transition_sweep is not None:
        probabilities = tuple(
            float(token) for token in args.self_transition_sweep.split(",") if token.strip()
        )
        bars = tuple(int(token) for token in args.sweep_bars.split(",") if token.strip())
        _report_self_transition_sweep(
            args, sweep_self_transition(references, probabilities, bars, condition)
        )
    print("--- 읽는 법 ---")
    print("**쌍 거리로는 안 된다.** 전이 사전을 주기만 하면 두 출력이 순서에서 달라진다 —")
    print('곡 짝을 뒤섞은 사전을 줘도 그렇다. **"쓰이고 있다"와 "맞는 것을 쓴다"는 다르다**')
    print("(어휘를 넓히기만 해도 거리가 +0.054 공짜로 오른 D-0094와 같은 함정이다).")
    print("**`self`는 출력의 전이와 그 곡의 전이 사전의 거리**이고 `other`는 다른 곡의 것이다.")
    print("D-0062가 화성 어휘에서 쓴 구조를 그대로 쓴다.")
    print("**`전이 없음` 줄이 음성 대조다** — 순서를 시드가 정하면 둘이 같아야 한다.")
    print("**문턱이 t > 3이다.** 이 판정이 O-32를 닫으므로 승인 문턱이다 (D-0098).")
    if args.use_hold:
        print("**`전이+유지`는 곡마다 그 곡의 유지 확률을 건 선이다** (O-37 · D-0123).")
        print("`전이 있음`이 그 음성 대조이며 같은 참조곡·같은 시드다. **내려간다** (D-0125) —")
        print("감소분 전체가 유효 마디 수이고 **이 지표는 유지를 원리적으로 못 잰다** (O-26).")
        print("**유지 확률을 고르지 않았다** — 곡의 시계열이 낸 값이라 손잡이가 아니다.")
    return 0


def _report_hold(
    references: Sequence[OrderReference], plain: OrderReport, held: OrderReport
) -> None:
    """`use_hold`가 판정을 어디로 옮겼는가 (O-37 · D-0125).

    **음성 대조는 `전이 있음` 선이다** — 같은 참조곡·같은 시드에서 `hold`만 0.0으로
    둔 줄이며, 검사가 그 둘이 한 비트도 다르지 않음을 고정했다.

    `p = 0`인 곡을 따로 낸다. **D-0123이 남긴 것이다** — 실측 49곡(4.9%)이 뒤섞음보다
    낮았고 그 곡들은 `use_hold`를 켜도 안 움직여 **차이를 희석한다.**
    """
    from statistics import median

    from hathor.application.evaluate_order_conditioning import holding_indices

    moving = holding_indices(references)
    values = [item.hold for item in references]
    print("--- 곡별 유지 확률 (O-37 · D-0125) ---")
    print(
        f"움직이는 곡 {len(moving)} / {len(values)} · p=0 {len(values) - len(moving)}곡"
        f" · 중앙 {median(values):.4f} · 최대 {max(values):.4f}"
    )
    print("**`p=0`인 곡은 매 마디 바뀐다.** 두 선에 같은 곡들이 들어가 있고 그 곡들만")
    print("아무것도 안 바뀌므로 전체 표의 차이는 **희석된 값이다.**\n")
    if not moving:
        print("움직이는 곡이 없다. **유지 확률이 판정에 닿지 않았다** — 표를 읽지 않는다.\n")
        return
    for text in render_table(
        (
            ("선", "<12"),
            ("곡", ">5d"),
            ("self", ">9.4f"),
            ("other", ">9.4f"),
            ("other-self", ">12.4f"),
            ("t", ">8.2f"),
            ("곡승률", ">9.1%"),
        ),
        [
            (
                label,
                item.reference_count,
                item.mean_self,
                item.mean_other,
                item.gap,
                item.t_statistic,
                item.win_rate,
            )
            for label, item in (
                ("전이 있음", plain.restricted_to(moving)),
                ("전이+유지", held.restricted_to(moving)),
            )
        ],
    ):
        print(text)
    print()


def _report_self_transition_sweep(
    args: argparse.Namespace, rows: Sequence[tuple[float, int, float, float, float]]
) -> None:
    """자기 전이 훑기를 찍는다 (O-38 닫힘 · D-0114).

    **짐작은 이미 죽었다** — `p`를 올리자 값이 내려갔다. 이 표는 재현용이다.
    """
    print("--- 자기 전이 훑기 (O-38 닫힘 · D-0114) ---")
    print("**진단 전용이다.** 이 값을 골라 제품에 박으면 그것이 D-0058이다.")
    for text in render_table(
        (
            ("자기전이", ">9.2f"),
            ("마디", ">6d"),
            ("other-self", ">12.4f"),
            ("t", ">8.2f"),
            ("곡승률", ">9.1%"),
        ),
        [tuple(row) for row in rows],
    ):
        print(text)
    print("")
    print("**짐작**: 매 마디 바꾸는 제약이 짧은 구간에서 관측 거리를 누른다 (D-0109).")
    print("참이면 짧은 마디에서 `자기전이`가 오를수록 `other-self`가 **오른다.**")
    print("**D-0114가 이 표로 짐작을 기각했다.** 표본 부족이며 재현용으로 남긴다.")
    print(f"귀무 대조: 같은 훑기를 `--stem-set {args.stem_set}`에서 전이 없이 돌린다.")
