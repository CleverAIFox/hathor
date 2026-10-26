#!/usr/bin/env python3
"""**칸 배치가 음성 대조에 바닥을 만드나** (O-83 · D-0462).

    cd core && uv run python ../tools/probe_layout.py --dry-run
    cd core && uv run python ../tools/probe_layout.py --trials 3

### 무엇을 묻나

사전 질량이 온음계에 몰리면 `mixture`와 `control`이 **같은 무게 묶음을 다른 자리**에
놓는다 — 비온음계 셋이 `mixture`에서 2·6·8, `control`에서 1·5·8이다.
`generate_harmony`가 `rng.choices`로 **누적 무게 위에서 역변환 추출**을 하고 짝지은
두 곡이 **같은 시드 흐름**을 쓰므로, 가벼운 칸이 누적 순서의 어디에 앉느냐가
**두 곡의 뽑기가 얼마나 묶이는지**를 바꾼다.

밀기 전에는 아홉 무게가 교환가능해 두 배치가 같은 법칙이다. **민 뒤에는 아니다.**

**음성 대조에서 이 차이는 전부 인공물이다** — 어느 칸도 다른 칸보다 곡 고유하지
않게 지었으므로 `mixture`가 이길 까닭이 없다.

### 왜 `probe_threshold`를 안 쓰나

`EvaluateHarmonyOutput.run()`이 선 **일곱 개**를 다 돈다. 이 질문에 쓰는 것은
**`paired` 하나**다 — 나머지 여섯은 귀무선이고 여기서는 안 본다.

**첫 판은 그 비싼 자를 그대로 썼고 못 가렸다** (D-0460). 같은 시간에 쌍이 10분의 1,
시드가 5분의 1이었기 때문이다. **비싸서 못 잰 것이 아니라 안 쓰는 것을 같이 재고
있었다** (D-0462).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

from control_corpus import REAL_DIATONIC_MASS, build, diatonic_mass_of  # noqa: E402

from hathor.application.compare_output import NORMAL_95, gap_of  # noqa: E402
from hathor.application.evaluate_harmony_output import ReferencePrior  # noqa: E402
from hathor.application.paired_output import output_distances  # noqa: E402
from hathor.domain.services.pair_sampling import sample_index_pairs  # noqa: E402
from hathor.domain.value_objects.key import Key, Mode  # noqa: E402
from hathor.engines.compose.harmony_generator import (  # noqa: E402
    Vocabulary,
    vocabulary_degrees,
)

KEY = Key(tonic="C", mode=Mode.MAJOR)
BAR_COUNT = 8

PAIRS = 4000
"""쌍 수. **짝지은 오차를 쌍 위에서 직접 낸다** — 판 사이가 아니다.

쌍 400으로는 못 가렸다 (D-0460). 여기는 선 하나만 재므로 **같은 시간에 열 배**다.
"""

SEEDS = 600
"""곡마다 뽑는 진행 수. 생성 비용이 **쌍이 덮은 곡 곱하기 이 수 곱하기 어휘 둘**이다."""

STREAM_PAIRS = 0x9A1D
"""쌍 추첨 흐름의 태그 (D-0470).

**아무 수나 되는 자리가 아니다** — 0이면 안 된다. numpy의 `SeedSequence`가 끝의
0을 버리므로 `[seed, 0, trial]`은 `trial`이 0일 때 `[seed]`로 접힌다.
"""

FLAT_MASS = 0.5
"""밀지 않은 대조의 질량. 배수가 `m/(1-m)`이므로 **여기서 1이다.**

**이것이 음성 대조의 음성 대조다** (D-0259). 밀지 않으면 아홉 무게가 교환가능해
두 배치가 같은 법칙이고, **거기서도 차이가 나오면 기전이 배치가 아니다.**
"""


@dataclass(frozen=True, slots=True)
class Run:
    """한 질량에서 돈 판들."""

    mass: float
    gains: tuple[float, ...]
    errors: tuple[float, ...]
    realised: float

    @property
    def mean(self) -> float:
        return statistics.fmean(self.gains)

    @property
    def error(self) -> float:
        """**판 사이와 짝지은 오차 중 큰 쪽** (D-0462).

        판이 셋이면 판 사이 오차가 **운으로 작아진다** — D-0461이 한 시드로 못을
        박아 운으로 통과하던 자리에서 배운 것과 같다. 둘 중 큰 쪽을 쓴다.
        """
        across = (
            statistics.stdev(self.gains) / len(self.gains) ** 0.5 if len(self.gains) > 1 else 0.0
        )
        pooled = statistics.fmean(self.errors) / len(self.gains) ** 0.5
        return float(max(across, pooled))

    @property
    def t(self) -> float:
        return self.mean / self.error if self.error > 0 else float("nan")

    @property
    def ceiling(self) -> float:
        """인공물의 **95% 상한.** 아래로 묶는 수이지 실측된 바닥이 아니다 (GR-0.5)."""
        return self.mean + NORMAL_95 * self.error


def distances(
    corpus: Sequence[ReferencePrior],
    word: str,
    pairs: tuple[tuple[int, int], ...],
    offset: int,
) -> tuple[float, ...]:
    """그 어휘로 쌍마다 전변동 거리. **짝지은 두 곡이 같은 시드 흐름을 쓴다.**

    **이 고리를 여기에 베껴 적었었다** (D-0462). 같은 질문을 재는 `probe_threshold`와
    **다른 코드**로 돌아 한쪽을 고쳐도 다른 쪽이 안 움직였다 — D-0463이 한자리로
    모았고 이 함수는 이제 **인자를 맞춰 주는 껍데기**다 (D-0424 · D-0043).
    """
    return output_distances(
        [item.prior for item in corpus],
        pairs,
        seeds=range(offset, offset + SEEDS),
        key=KEY,
        vocabulary=Vocabulary(word),
        bar_count=BAR_COUNT,
    )


def sweep(mass: float, args: argparse.Namespace) -> Run:
    """한 질량에서 `trials`판. **판마다 코퍼스와 생성 시드를 둘 다 민다** (D-0461)."""
    gains: list[float] = []
    errors: list[float] = []
    realised: list[float] = []
    for trial in range(args.trials):
        corpus = build(args.songs, seed=args.corpus_seed + trial, sigma=0.0, diatonic_mass=mass)
        realised.append(diatonic_mass_of(corpus))
        # **흐름마다 태그를 단다** (D-0470). `default_rng([seed, 0])`은 numpy가 끝의
        # 0을 버려 `default_rng(seed)`와 **같은 흐름**이고, 코퍼스를 그 시드로 짓고
        # 있었으므로 **판 0에서 코퍼스와 쌍이 한 난수열을 나눠 썼다.**
        pairs = sample_index_pairs(
            args.songs,
            args.pairs,
            generator=np.random.default_rng([args.corpus_seed, STREAM_PAIRS, trial]),
        )
        found = gap_of(
            distances(corpus, "mixture", pairs, trial * SEEDS),
            distances(corpus, "control", pairs, trial * SEEDS),
        )
        gains.append(found.gain)
        errors.append(found.standard_error)
        print(
            f"  질량 {mass:.4f} 판 {trial} · 이득 {found.gain:+.5f} ±{found.standard_error:.5f}"
            f" · t {found.t:+.2f} · 실측 질량 {realised[-1]:.4f}",
            flush=True,
        )
    return Run(
        mass=mass,
        gains=tuple(gains),
        errors=tuple(errors),
        realised=statistics.fmean(realised),
    )


def cost(args: argparse.Namespace) -> str:
    """**무거우면 끈다** (D-0129). 끄게 하려면 얼마나 무거운지 보여야 한다."""
    covered = min(args.songs, 2 * args.pairs)
    sets = args.trials * 2 * 2
    return (
        f"코퍼스 {args.songs}곡 · 쌍 {args.pairs}(덮는 곡 최대 {covered}) · 판 {args.trials} · "
        f"질량 2개 · 어휘 2개\n"
        f"**생성 {sets}벌 · 진행 {covered * sets * SEEDS:,}개.** "
        # **「3.5배」는 한 판의 실측이었고 글자로 박혀 있었다** (D-0470 · GR-0.7).
        # 배수는 선 수·쌍 수·시드 수에 따라 움직이는데 이 줄은 안 움직였다.
        f"`run()`은 선 일곱과 `base`를 다 돌고 **여기는 `paired` 하나만 돈다** (D-0462)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="칸 배치가 음성 대조에 바닥을 만드나 (O-83)")
    parser.add_argument("--trials", type=int, default=3, help="질량마다 몇 판")
    parser.add_argument("--pairs", type=int, default=PAIRS, help="견줄 쌍 수")
    parser.add_argument("--songs", type=int, default=1000, help="코퍼스 곡 수")
    parser.add_argument("--corpus-seed", type=int, default=80000, help="코퍼스 시드의 바닥")
    parser.add_argument("--dry-run", action="store_true", help="비용만 찍고 멈춘다")
    args = parser.parse_args()

    if args.trials < 2:
        print("판이 둘 이상이어야 판 사이 흔들림을 잰다 (GR-0.5)", file=sys.stderr)
        return 1

    print(cost(args))
    for word in ("mixture", "control"):
        print(f"  {word:8s} {vocabulary_degrees(Mode.MAJOR, Vocabulary(word))}")
    if args.dry_run:
        return 0
    print()

    pushed = sweep(REAL_DIATONIC_MASS, args)
    print()
    flat = sweep(FLAT_MASS, args)
    print()
    for one in (pushed, flat):
        print(
            f"질량 {one.mass:.4f}: 평균 {one.mean:+.5f} ±{one.error:.5f} · "
            f"t {one.t:+.2f} · 95% 상한 {one.ceiling:+.5f} · 실측 질량 {one.realised:.4f}"
        )
    apart = pushed.mean - flat.mean
    spread = (pushed.error**2 + flat.error**2) ** 0.5
    print(f"두 질량 차이: {apart:+.5f} ±{spread:.5f} · t {apart / spread:+.2f}")
    # **옛 판의 결론을 결과와 무관하게 찍고 있었다** (D-0470). 「안 바뀌었다」는
    # 이번 판이 무엇을 냈든 그대로 나왔다 — 읽는 사람은 **지금 판의 판정**으로
    # 읽는다 (D-0292: 틀린 안내가 안내 없는 것보다 나쁘다).
    print(
        f"\n**인공물은 이득을 부풀리는 방향이다.** 실물 질량의 상한이 "
        f"{pushed.ceiling:+.5f}이고, 이 수를 M9의 이득에서 빼도 판정이 바뀌는지를 본다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
