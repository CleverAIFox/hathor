#!/usr/bin/env python3
"""다이어토닉 제한이 버리는 몫. **`--emit`이 실측 정본을 다시 쓴다** (D-0449).

    cd core && uv run python ../tools/probe_restriction.py          # 화면만
    cd core && uv run python ../tools/probe_restriction.py --emit   # 정본을 갈아 넣는다

### 왜 블록을 늦게 만드나

`MASTER`가 **`other` 0.4357 · `mix` 0.4670**을 *실측*이라 들고 있었다 (D-0085 · D-0088).
살아남은 산출물 여섯을 전수로 훑으니 **그 수를 내는 것이 하나도 없다.** 음원이 바뀐
것도 자가 바뀐 것도 아니고 **그 수를 낸 자료가 없어진 것**이다 — D-0087이 *«D-0085의
표는 이제 재현되지 않는다»*라고 이미 적어 뒀다.

**손으로 적은 수는 자료가 사라져도 안 운다.** 그래서 블록을 만든다. 여기 들어오면
`measured`의 상류 검사가 양방향으로 물고, 자가 바뀌면 `ruler`가 어긋나 빨개진다
(D-0371 · D-0374).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

import measured  # noqa: E402

from hathor.application.evaluate_degree_restriction import (  # noqa: E402
    NULL_REPEATS,
    EvaluateDegreeRestriction,
)
from hathor.application.evaluate_harmony_output import (  # noqa: E402
    DEFAULT_PAIR_COUNT,
    DEFAULT_SEED,
    EvaluateHarmonyOutput,
    OutputCondition,
    ReferencePrior,
)
from hathor.domain.services.pair_sampling import touched_count  # noqa: E402
from hathor.infrastructure.keys_jsonl_store import (  # noqa: E402
    load_degree_priors,
    priors_stem_set,
)
from hathor.interfaces.cli.roots import resolve_priors  # noqa: E402
from hathor.interfaces.cli.tables import pair_coverage  # noqa: E402

SECTION = "restriction"

RULER = "2026-10-21 · 쌍 400 · 시드 20260822 · 귀무 20회 · 다장조 (D-0453)"
"""`[restriction.counts]`를 낸 자의 이름 (D-0374).

**쌍 수와 시드가 둘 다 자다.** 쌍을 바꾸면 표준오차가 바뀌고, 시드를 바꾸면 어느
쌍을 봤는지가 바뀐다. 귀무 반복 수도 같은 부류다 (D-0087).

**D-0449에서 내가 시드를 새로 지었다** — `DEFAULT_SEED`가 이미 있는데 `7`을 적었고,
정본에 CLI와 다른 수가 들어갔다. 그 둘의 차이가 **판정을 뒤집는 크기**였다 (D-0450).
이제 둘 다 `DEFAULT_*`를 든다 — 두 곳에 적으면 어긋난다 (D-0043 · D-0424).
"""

EMITS = (
    "other_observed_permille",
    "other_matched_permille",
    "other_mass_permille",
    "other_gap_per10k",
    "other_error_per10k",
    "mix_observed_permille",
    "mix_matched_permille",
    "mix_mass_permille",
    "mix_gap_per10k",
    "mix_error_per10k",
    "pairs",
    "tracks_touched",
)
"""`[restriction.counts]`에 넣는 수. **전부 정수다** — 곡명·경로는 안 나간다 (D-0366).

비율은 **천분율 정수**다. 대비와 오차는 **만분율**이다 — 자릿수가 다르기 때문이다.
몫은 0.4 근처라 천분율로 네 자리가 남지만 **대비는 0.007 근처**라 천분율이면 한 자리가
되고, 거기서 반올림하면 `t`가 1.85와 1.87로 갈린다.

**D-0449는 대비를 안 넣었다.** 까닭이 *«`other` -0.0005 · `mix` -0.0004로 천분율에서
둘 다 0이고, 0을 적으면 「쟀더니 0」과 「못 쟀다」가 구별이 안 된다»*(GR-0.5)였다.
**쌍 400에서 그 까닭이 사라졌다** — +0.0074와 +0.0011이다. 그동안 대비와 오차는
`MASTER`에 **손으로** 적혀 있었고, 쌍이 400이 되자 그 줄만 쌍 100의 수로 남았다
(GR-0.7 · D-0454). 까닭이 사라졌으면 그 결정도 따라간다.
"""

PAIRS = DEFAULT_PAIR_COUNT
SEED = DEFAULT_SEED


def _permille(value: float) -> int:
    return round(value * 1000)


def _per10k(value: float) -> int:
    return round(value * 10000)


def survey(source: str) -> dict[str, int] | None:
    """한 출처를 잰다. 산출물이 없으면 `None`."""
    store = resolve_priors(None, priors_stem_set(source))
    if store is None:
        return None
    table = load_degree_priors(store, source)
    if len(table) < 2:
        print(f"출처 `{source}`의 사전이 {len(table)}개다: {store.name}", file=sys.stderr)
        return None
    condition = OutputCondition(pair_count=PAIRS, seed=SEED)
    report = EvaluateDegreeRestriction(condition).run(
        [ReferencePrior(key, table[key]) for key in sorted(table)], source
    )
    observed = report.line("observed")
    print(
        f"{source:6s} {store.name} · {pair_coverage(condition, len(table))} · "
        f"실측 {observed.mean_share:.4f} · 등가선 {report.line('matched').mean_share:.4f} · "
        f"대비 {report.specificity_gap:+.4f} ±{report.specificity_standard_error:.4f} "
        f"· t {report.specificity_t:+.2f}"
    )
    return {
        f"{source}_observed_permille": _permille(observed.mean_share),
        f"{source}_matched_permille": _permille(report.line("matched").mean_share),
        f"{source}_mass_permille": _permille(float(np.mean(observed.masses))),
        f"{source}_gap_per10k": _per10k(report.specificity_gap),
        f"{source}_error_per10k": _per10k(report.specificity_standard_error),
        "tracks_touched": touched_count(EvaluateHarmonyOutput(condition).pair_indices(len(table))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="버리는 칸의 몫 전수 (D-0449)")
    parser.add_argument("--emit", action="store_true", help="실측 정본의 counts를 다시 쓴다")
    args = parser.parse_args()

    counts: dict[str, int] = {"pairs": PAIRS}
    for source in ("other", "mix"):
        found = survey(source)
        if found is None:
            print(f"`{source}`를 못 쟀다. 정본을 안 건드린다 (GR-0.5)", file=sys.stderr)
            return 1
        # **`tracks_touched`는 두 출처가 함께 쓰는 칸이다.** 그냥 덮으면 둘이 다를 때
        # 뒤엣것이 조용히 이긴다 — 사전이 다른 곡 수로 쌓인 날 거울만 틀린다 (D-0230).
        clash = {
            key: found[key] for key in counts.keys() & found.keys() if counts[key] != found[key]
        }
        if clash:
            print(f"출처마다 다른 수가 나왔다: {clash}. 정본을 안 건드린다", file=sys.stderr)
            return 1
        counts.update(found)

    print(f"\n귀무선 {NULL_REPEATS}회 · 쌍 {PAIRS} · 시드 {SEED}")
    if not args.emit:
        return 0
    changed = measured.emit(SECTION, counts)
    print(f"정본 갱신 · 바뀐 수 {len(changed)}개")
    for line in changed:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
