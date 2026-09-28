"""`ingest keys`의 분포 보고 (D-0277).

**정답 라벨이 없으므로 분포와 베이스라인으로 검사한다** (O-22 닫힘 D-0201). 맞다는 증명은
할 수 없고 틀렸다는 신호만 잡을 수 있다.

**추출과 보고를 갈랐다.** `--replay`는 보고만 돌리고 배치는 추출까지 돌린다 — 한 함수에
둘이 있으면 «어디까지가 실측이고 어디부터가 해석인가»가 안 보인다. 352줄이 그래서 352줄이었다.
"""

from __future__ import annotations

import sys
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.key_estimation import (
    BLACK_KEYS,
    KEY_MARGIN_FLOOR,
    random_baseline,
    relative_key,
)
from hathor.domain.value_objects.key import Key, Mode
from hathor.interfaces.cli.eval_output import report_harmonic_sweep
from hathor.interfaces.cli.tables import ambiguity_report

if TYPE_CHECKING:
    import argparse


def report(rows: list[dict[str, object]], args: argparse.Namespace) -> int:
    """분포 · 교차표 · 무작위 베이스라인 대조를 찍는다. 종료 코드를 낸다."""
    if not rows:
        print("추정된 곡이 없다.", file=sys.stderr)
        return 1

    if args.harmonic_sweep:
        return report_harmonic_sweep(rows, args.profile)

    total = len(rows)
    correlations = np.asarray([float(str(row["correlation"])) for row in rows])
    margins = np.asarray([float(str(row["margin"])) for row in rows])

    def parse(text: str) -> Key:
        tonic, mode = str(text).rsplit(" ", 1)
        return Key(tonic=tonic, mode=Mode(mode))

    keys = [parse(str(row["key"])) for row in rows]
    runner_ups = [parse(str(row["runner_up"])) for row in rows]

    modes: Counter[str] = Counter(key.mode.value for key in keys)
    tonics: Counter[str] = Counter(key.tonic for key in keys)
    is_relative = [relative_key(key) == other for key, other in zip(keys, runner_ups, strict=True)]
    ambiguous_flags = margins < KEY_MARGIN_FLOOR

    print(f"곡 {total}개\n")
    print("선법")
    for mode, count in modes.most_common():
        print(f"  {mode:<6} {count:5d}  {count / total:6.1%}")

    black = sum(1 for key in keys if key.tonic in BLACK_KEYS)
    print(f"  검은건반 으뜸음  {black:5d}  {black / total:6.1%}   ← O-23 지표 (D-0061)")

    print("\n조성 교차표 (으뜸음 / 선법)")
    print(f"  {'':<4}{'major':>7}{'minor':>7}{'합계':>7}")
    for tonic, _ in tonics.most_common():
        major = sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MAJOR)
        minor = sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MINOR)
        print(f"  {tonic:<4}{major:>7}{minor:>7}{major + minor:>7}")

    # **베이스라인도 같은 프로파일로 잰다** (D-0059). 하한이 프로파일마다 달라
    # (Krumhansl 0.6192 · Temperley 0.5488) 고정값을 쓰면 비교가 성립하지 않는다.
    base_profile = str(rows[0].get("profile", "krumhansl"))
    base_correlation, base_margin = random_baseline(profile=base_profile, harmonic=args.harmonic)
    print("\n지표 대 무작위 베이스라인")
    print(f"  {'':<10}{'코퍼스':>10}{'무작위':>10}{'차이':>10}")
    for name, actual, base in (
        ("상관", correlations, base_correlation),
        ("격차", margins, base_margin),
    ):
        gap = float(np.median(actual) - np.median(base))
        print(
            f"  {name:<10}{float(np.median(actual)):>10.4f}"
            f"{float(np.median(base)):>10.4f}{gap:>+10.4f}"
        )

    print(
        "\n".join(
            ambiguity_report(
                modes=[key.mode.value for key in keys],
                ambiguous=ambiguous_flags,
                relative=is_relative,
                floor=float((base_margin < KEY_MARGIN_FLOOR).mean()),
                tunings=[float(str(row["tuning_cents"])) for row in rows if "tuning_cents" in row],
            )
        )
    )
    return 0
