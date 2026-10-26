#!/usr/bin/env python3
"""**보고된 오차가 제 변동을 담는가** (D-0451).

    cd core && uv run python ../tools/probe_calibration.py

### 왜 필요한가

같은 자료·같은 쌍 수인데 **시드 하나로 판정이 뒤집혔다** (D-0450). `other` 등가선
대비가 시드 20260822에서 -0.0005(`t` -0.05), 시드 7에서 +0.0245(`t` +2.88)다. 각자
보고한 짝지은 표준오차는 0.0085인데 **두 판이 오차의 2.9배 떨어져 있다.**

짝지은 오차가 제 변동을 담는다면 그만큼 벌어지는 일이 드물다. 그래서 묻는다 —
**시드를 여럿 대면 대비가 실제로 얼마나 흔들리나, 그 흔들림이 보고된 오차와 같나.**

재는 법은 하나다. 시드마다 대비 하나와 오차 하나가 나오므로, **대비의 표본표준편차**와
**오차의 평균**을 견준다. 비가 1 근처면 오차가 정직하고, 1보다 크면 **과소평가**다.

### 왜 정본에 안 넣나

**이 수는 코퍼스가 아니라 그때의 자를 말한다.** `measured.toml`은 1004곡이 무엇인지
적는 곳이고, 여기 나오는 비는 *«쌍 400으로 재면 오차가 정직한가»*다 — 자를 바꾸면
뜻이 사라지는 수다. 기록이 제자리다.

시드 24판이라 **한 판의 24배**다 (D-0327이 오경보율에 쓴 그 수다 — 새로 안 골랐다).
`make measure`에 넣으면 사람이 그것을 끄게 된다 (D-0129). 자를 바꿀 때 돌린다.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

from hathor.application.evaluate_degree_restriction import (  # noqa: E402
    EvaluateDegreeRestriction,
)
from hathor.application.evaluate_harmony_output import (  # noqa: E402
    DEFAULT_PAIR_COUNT,
    OutputCondition,
    ReferencePrior,
)
from hathor.infrastructure.keys_jsonl_store import (  # noqa: E402
    load_degree_priors,
    priors_stem_set,
)
from hathor.interfaces.cli.roots import resolve_priors  # noqa: E402

SEEDS = 24
"""시드 판 수. **D-0327이 오경보율에 쓴 수다** — 새로 안 골랐다 (D-0058)."""

WIDE = 4
"""쌍을 몇 배로 늘려 볼 것인가. **넉 배면 오차가 반이 되어야 한다.**

`--wide`로 바꾼다. 두 배가 궁금하면 `--wide 2`다 — **고르는 값이 아니라 묻는 값이고,
재지 않고 답하면 그것이 D-0450에서 틀린 그 짓이다.**"""

SOURCE = "other"
"""`eval harmony-output`의 기본 출처. 판정이 걸린 쪽이다 (D-0450)."""


def _permille(value: float) -> int:
    return round(value * 1000)


def sweep(source: str, pairs: int, seeds: int) -> tuple[list[float], list[float], int]:
    """`(대비들, 오차들, 판정이 통과한 판 수)`."""
    store = resolve_priors(None, priors_stem_set(source))
    if store is None:
        raise LookupError(f"`{source}` 사전 산출물이 없다")
    table = load_degree_priors(store, source)
    if len(table) < 2:
        raise LookupError(f"출처 `{source}`의 사전이 {len(table)}개다: {store.name}")
    references = [ReferencePrior(key, table[key]) for key in sorted(table)]

    gaps: list[float] = []
    errors: list[float] = []
    passed = 0
    started = time.monotonic()
    for index in range(seeds):
        report = EvaluateDegreeRestriction(OutputCondition(pair_count=pairs, seed=index)).run(
            references, source
        )
        gaps.append(report.specificity_gap)
        errors.append(report.specificity_standard_error)
        passed += report.off_scale_exceeds_matched_by_t
        print(
            f"  시드 {index:2d} · 대비 {gaps[-1]:+.4f} ±{errors[-1]:.4f}"
            f" · t {report.specificity_t:+.2f}",
            flush=True,
        )
    print(f"  ({time.monotonic() - started:.0f}초)")
    return gaps, errors, passed


def report_on(name: str, gaps: list[float], errors: list[float], passed: int) -> dict[str, int]:
    spread = statistics.stdev(gaps)
    error = statistics.fmean(errors)
    # **못 쟀으면 `nan`이다** (D-0470). 0.0은 *«완벽히 정직하다»*로 읽혀
    # 봐주는 쪽으로 열린다 — `probe_threshold`의 `mean_t`·`ceiling`과 같은 관례다.
    honest = spread / error if error > 0 else float("nan")
    print(
        f"{name}: 대비 흔들림 {spread:.4f} · 보고된 오차 {error:.4f}"
        f" · 비 {honest:.2f} · 통과 {passed}/{len(gaps)}"
    )
    return {
        "spread": _permille(spread),
        "error": _permille(error),
        "honesty": _permille(honest),
        "flips": min(passed, len(gaps) - passed),
    }


def shrink(thin: dict[str, int], thick: dict[str, int], wide: int) -> tuple[float, float]:
    """`(실제로 줄어든 배수, 줄어들어야 하는 배수)` (D-0470).

    `WIDE`의 docstring이 **«넉 배면 오차가 반이 되어야 한다»**라고 적고 있었는데
    **아무 데서도 그 비를 안 냈다.** 시험도 `WIDE == 4`만 걸어 그 성질이 아니라
    **상수 자신**을 재고 있었다 — 리터럴을 두 번 적은 것이고, 둘이 같은 것은
    산수다 (D-0470 · GR-0.5).

    쌍이 독립이면 평균의 오차가 `1/sqrt(n)`이므로 **`sqrt(wide)`배** 줄어야 한다.
    덜 줄면 쌍이 겹쳐 새 정보를 안 가져온 것이다.
    """
    if thick["error"] <= 0:
        return (float("nan"), wide**0.5)
    return (thin["error"] / thick["error"], wide**0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description="보고된 오차가 제 변동을 담는가 (D-0451)")
    parser.add_argument("--seeds", type=int, default=SEEDS, help="시드 판 수")
    parser.add_argument("--source", default=SOURCE, help="사전 출처")
    parser.add_argument("--wide", type=int, default=WIDE, help="쌍을 몇 배로 늘려 볼까")
    args = parser.parse_args()

    if args.seeds < 2:
        # **`statistics.stdev`가 잡히지 않은 예외로 죽는다** (D-0470). 판이 하나면
        # 흔들림을 못 재는 것이고, 그것은 오류가 아니라 **거절할 입력**이다 (GR-0.5).
        print("시드 판이 둘 이상이어야 흔들림을 잰다 (GR-0.5)", file=sys.stderr)
        return 1

    narrow = DEFAULT_PAIR_COUNT
    wide = DEFAULT_PAIR_COUNT * args.wide
    try:
        print(f"쌍 {narrow} · 시드 {args.seeds}판 · 출처 {args.source}")
        thin = report_on(f"쌍 {narrow}", *sweep(args.source, narrow, args.seeds))
        print(f"\n쌍 {wide} · 시드 {args.seeds}판")
        thick = report_on(f"쌍 {wide}", *sweep(args.source, wide, args.seeds))
    except LookupError as error:
        print(f"{error}. 정본을 안 건드린다 (GR-0.5)", file=sys.stderr)
        return 1

    print(
        "\n**비가 1이면 오차가 정직하다.** 1보다 크면 보고된 오차가 흔들림을 덜 적은 것이고,"
        "\n그만큼 `t`도 부풀어 있다 — 그 `t`로 내린 판정을 그대로 못 읽는다 (D-0450)."
    )
    # **적어만 두고 안 내던 수다** (D-0470). `WIDE`가 *«넉 배면 반»*이라 적었는데
    # 그 비가 화면 어디에도 없었다 — 읽는 사람이 두 줄을 눈으로 나눠야 했다.
    got, want = shrink(thin, thick, args.wide)
    print(
        f"쌍을 {args.wide}배로 늘리자 오차가 **{got:.2f}배** 줄었다 "
        f"(독립이면 {want:.2f}배). 덜 줄면 쌍이 겹쳐 새 정보를 안 가져온 것이다."
    )
    print(
        f"\n기록에 적을 줄 — 쌍 {narrow}: 흔들림/오차 {thin['honesty'] / 1000:.2f}"
        f" · 뒤집힘 {thin['flips']}/{args.seeds} · "
        f"쌍 {wide}: {thick['honesty'] / 1000:.2f} · 뒤집힘 {thick['flips']}/{args.seeds}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
