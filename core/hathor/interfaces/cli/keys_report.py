"""`ingest keys`의 분포 보고 (D-0277).

**정답 라벨이 없으므로 분포와 베이스라인으로 검사한다** (O-22 닫힘 D-0201). 맞다는 증명은
할 수 없고 틀렸다는 신호만 잡을 수 있다.

**추출과 보고를 갈랐다.** `--replay`는 보고만 돌리고 배치는 추출까지 돌린다 — 한 함수에
둘이 있으면 «어디까지가 실측이고 어디부터가 해석인가»가 안 보인다. 352줄이 그래서 352줄이었다.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from hathor.application.key_distribution import summarize
from hathor.interfaces.cli.eval_output import report_harmonic_sweep
from hathor.interfaces.cli.tables import ambiguity_report

if TYPE_CHECKING:
    import argparse


def report(rows: list[dict[str, object]], args: argparse.Namespace) -> int:
    """분포 · 교차표 · 무작위 베이스라인 대조를 찍는다. 종료 코드를 낸다.

    **수는 `application/key_distribution`이 낸다** (D-0280). 여기 `numpy`가 있었고
    표시 계층이 중앙값을 재는 자리였다.
    """
    if not rows:
        print("추정된 곡이 없다.", file=sys.stderr)
        return 1

    if args.harmonic_sweep:
        return report_harmonic_sweep(rows, args.profile)

    found = summarize(rows, harmonic=args.harmonic)
    total = found.total

    print(f"곡 {total}개\n")
    print("선법")
    for mode, count in found.modes:
        print(f"  {mode:<6} {count:5d}  {count / total:6.1%}")
    print(f"  검은건반 으뜸음  {found.black:5d}  {found.black / total:6.1%}   ← O-23 지표 (D-0061)")

    print("\n조성 교차표 (으뜸음 / 선법)")
    print(f"  {'':<4}{'major':>7}{'minor':>7}{'합계':>7}")
    for tonic, major, minor in found.cross:
        print(f"  {tonic:<4}{major:>7}{minor:>7}{major + minor:>7}")

    print("\n지표 대 무작위 베이스라인")
    print(f"  {'':<10}{'코퍼스':>10}{'무작위':>10}{'차이':>10}")
    for name, actual, base, gap in found.metrics:
        print(f"  {name:<10}{actual:>10.4f}{base:>10.4f}{gap:>+10.4f}")

    print("\n".join(ambiguity_report(found.ambiguity)))
    return 0
