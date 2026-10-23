#!/usr/bin/env python3
"""**문턱 `t>=2`의 오경보율과 검출율** (D-0460).

    cd core && uv run python ../tools/probe_threshold.py --dry-run      # 비용만 찍는다
    cd core && uv run python ../tools/probe_threshold.py --trials 6     # 돌린다

### 왜 이 자가 필요한가

D-0327이 문턱을 고르며 *«음성 4% · 양성 100%»*를 쟀다. **그 코퍼스를 짓는 코드가
커밋되지 않았다.** 그래서 D-0453이 쌍 100을 400으로 올렸을 때 **문턱을 다시 못 걸었고**,
PLAN §3.1에 *«갚는 법: 도구 없음»*이 한 줄 섰다.

D-0456이 재서 알아낸 것: **참 차이가 정확히 0일 때만 쌍 수가 오경보율을 안 건드린다.**
0이 아니면 `t`가 `√n`으로 자라 참 +0.004에서 쌍 100의 18%가 쌍 1600에서 96%가 된다.
**D-0327의 음성 대조는 이득 +0.0032였다** — 바로 그 구간이고, 그것이 참 치우침인지
24판의 잡음인지 **그 표로는 안 갈린다**(`±0.0020`과 `t` +0.33의 나눗셈이 안 맞는다).

**이 자가 그것을 가른다.**

### 읽는 법을 먼저 박는다

수를 보고 읽는 법을 정하면 그것이 D-0058이다. 그래서 `verdict()`가 **코드에** 있고
돌리기 전에 읽을 수 있다.

### 판마다 코퍼스를 새로 뽑는다

같은 코퍼스에 쌍만 다시 뽑으면 **그 코퍼스의 치우침이 24판에 공통으로 남아** 판 사이
흔들림이 그것을 못 본다. 묻는 것은 *«이 음성 대조 **방식**이 0을 내는가»*이므로
**코퍼스 시드와 조건 시드를 둘 다 판마다 바꾼다.**

### 비싸다 — 그래서 비용을 먼저 찍는다

한 판이 어휘 둘(`control` · `mixture`)을 각각 생성한다. 생성은 **쌍이 덮은
곡 수**에 비례하고(D-0454), 그래서 쌍을 키우면 곡당 효율이 오르지만 **쌍이 겹치면
판별 표준오차를 못 믿는다**(PLAN O-81). 판 사이 흔들림으로 재야 하므로 판 수가 든다.

**처음에는 셋이었다** — `VocabularyComparison`을 그대로 썼고 그것이 `base`까지
`run()`으로 돌렸다. `base`는 `free_gain`에만 쓰이는데 이 탐침은 그것을 안 읽고,
`run()`의 선 일곱 중 읽는 것도 `paired` 하나다. **D-0463이 그 둘을 떼었다** —
`paired_distances`가 **비트까지 같은 수**를 낸다. 같은 수가 아니면 떼기 전에 모은
판과 뗀 뒤에 모은 판을 **같이 못 센다**(GR-0.5), 그래서 그 동일성이 시험에 걸려 있다.
`free_gain`·불일치율·전이는 **여기서 안 난다** — 필요하면 `eval harmony-output`이다.

**`--dry-run`이 기본값이 아니다.** 비용은 늘 찍되 멈추지는 않는다 — 멈추면 사람이
`--dry-run`을 떼는 법을 찾다가 그만둔다.
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

from control_corpus import REAL_DIATONIC_MASS, build, diatonic_mass_of  # noqa: E402

from hathor.application.compare_output import (  # noqa: E402
    NORMAL_95,
    PAIRED_T_FLOOR,
    gap_of,
)
from hathor.application.evaluate_harmony_output import (  # noqa: E402
    DEFAULT_PAIR_COUNT,
    EvaluateHarmonyOutput,
    OutputCondition,
)
from hathor.domain.services.pair_sampling import touched_count  # noqa: E402
from hathor.engines.compose.harmony_generator import Vocabulary  # noqa: E402

SONGS = 1000
"""코퍼스 크기. **D-0327이 쓴 수다** — 새로 안 골랐다 (D-0058)."""

SIGMA = 0.9
"""양성 대조에서 차용 칸을 흔드는 폭. **D-0327의 `_corpus`가 쓴 값이다.**

이것이 양성의 크기를 정하므로 **올리면 검출율이 공짜로 오른다** — 손잡이다.
여기서 안 돌린다 (D-0058).
"""

TRIALS = 6
"""기본 판 수. **고른 값이 아니라 「여기서 시작한다」는 값이다.**

판 사이 흔들림으로 평균의 오차를 내므로 판이 적으면 그 흔들림 자체가 흔들린다
(24판에서도 상대오차 ±15%다 · D-0455). **6판은 한 시간쯤이고 「0 근처인가」를
가린다** — 갈리면 늘린다. `--trials`로 받는다.
"""


RECORDED_UNDER = {"mass": REAL_DIATONIC_MASS, "pairs": DEFAULT_PAIR_COUNT, "songs": SONGS}
"""`POSITIVE_ON_RECORD`가 **어떤 조건에서** 났나 (D-0461).

적어 두지 않으면 `--only negative --mass 0.3`이 **다른 자에서 잰 양성에 기대고도
조용히 판정을 찍는다** — 기대는 척만 하는 것이다 (D-0325).
"""

POSITIVE_ON_RECORD = "D-0461의 양성 (실물 질량 · 쌍 400 · 1000곡)"
"""`--only negative`가 **무엇에 기대는지**. 양성 없이 음성만 읽으면 안 된다 (D-0259).

**이 판에서 돌아야 한다는 뜻은 아니다** — 기록에 있으면 되고, 그러면 **어디에
기대는지 화면에 적어야** 읽는 사람이 확인할 수 있다 (D-0191 · D-0266).
"""


@dataclass(frozen=True, slots=True)
class Sweep:
    """한 대조의 판들."""

    name: str
    gains: tuple[float, ...]
    errors: tuple[float, ...]
    passed: int
    mass: float
    seconds: float

    @property
    def mean(self) -> float:
        return statistics.fmean(self.gains)

    @property
    def spread(self) -> float:
        """**판 사이** 표준편차. 쌍이 겹쳐도 이 수는 안 부푼다."""
        return statistics.stdev(self.gains) if len(self.gains) > 1 else 0.0

    @property
    def mean_error(self) -> float:
        return self.spread / len(self.gains) ** 0.5 if len(self.gains) > 1 else 0.0

    @property
    def mean_t(self) -> float:
        """**평균이 0에서 몇 오차 떨어졌나.** 판별 `t`가 아니다.

        **못 쟀으면 `nan`이다** (D-0461). 0을 내면 `verdict()`가 그것을
        *«0과 안 갈린다»*로 읽어 **봐주는 쪽으로 열린다** — `PairedGap.t`는 같은
        관례인데 `beats`가 `t>=2`라 **닫히는 쪽**으로 실패한다. 극성이 반대다.
        """
        return self.mean / self.mean_error if self.mean_error > 0 else float("nan")

    @property
    def honesty(self) -> float:
        """판 사이 흔들림 ÷ 보고된 판별 오차. 1보다 크면 보고된 오차가 작다."""
        reported = statistics.fmean(self.errors)
        return self.spread / reported if reported > 0 else 0.0

    @property
    def ceiling(self) -> float:
        """치우침의 **95% 상한.** 아래로 묶는 수이지 실측된 치우침이 아니다 (GR-0.5).

        **못 쟀으면 `nan`이다** — `mean_t`와 같은 관례다 (D-0461).
        """
        if self.mean_error <= 0.0:
            return float("nan")
        return self.mean + NORMAL_95 * self.mean_error


CEILING_FLOOR = 0.001
"""승인 쪽 가지의 문턱. **PLAN의 D-0460 행에 적혀 있던 것을 옮긴 것이다** (D-0464).

*«음성 치우침의 95% 상한이 +0.001 아래로 내려가면 쌍 1600이 승인된다»* — D-0456의
표에서 참 +0.002가 쌍 1600에서 오경보 46%이고 그 절반 아래를 고른 값이다.
**여기서 새로 안 골랐다** (D-0058).

**옮긴 까닭**: 규칙이 문서에만 있으니 읽는 사람이 **반올림된 화면 수를 곱해야** 했다.
판정 문턱이 넷째 자리인데 화면은 넷째 자리까지만 찍었고, 실제로 그렇게 읽다가
+0.000988로 **승인 쪽으로 잘못 읽었다** — 전체 자릿수는 +0.001030이다 (GR-0.7).
"""


def verdict(negative: Sweep) -> str:
    """**사전 등록한 읽는 법이다** (D-0460). 수를 보기 전에 적었다.

    음성 대조의 평균이 0에서 **문턱만큼** 떨어져 있으면 그 대조는 참 0이 아니다 —
    그러면 **쌍을 올릴수록 오경보가 따라 오른다** (D-0456). 떨어져 있지 않으면
    *«이 판 수로는 0과 안 갈린다»*이지 *«0이다»*가 아니다 (GR-0.5).

    ### 두 가지가 같이 켜질 수 있다 — 엄한 쪽을 든다

    참 치우침이 **0이 아니기만 하면** 판을 늘릴수록 상한은 점추정으로 내려가
    승인 쪽을 켜고 `t`는 `√판`으로 자라 동결 쪽을 켠다. **참이 정확히 0일 때만
    양립하는 규칙이다.** D-0464에서 이 금을 봤고 **그때 이 판의 수로는 둘 다
    안 켜져 있었다** — 그래서 순서를 지금 박는다 (GR-6.5: 결과를 보고 고르지 않는다).

    `t>=2`가 먼저다. *«작지만 확실히 0이 아니다»*는 **승인이 아니라 동결**로 읽는다.
    """
    if math.isnan(negative.mean_t):
        return "**못 쟀다** — 판 사이 흔들림이 0이라 평균의 오차가 없다 (GR-0.5)"
    if abs(negative.mean_t) >= PAIRED_T_FLOOR:
        return (
            f"**음성 대조가 0이 아니다** (평균의 `t` {negative.mean_t:+.2f}). "
            "쌍을 올리면 오경보가 따라 오른다 — **쌍 수를 못 올린다** (D-0456)"
        )
    if negative.ceiling < CEILING_FLOOR:
        return (
            f"**쌍 1600이 승인된다** (95% 상한 {negative.ceiling:+.6f} < "
            f"{CEILING_FLOOR:+.6f}). 치우침이 확정은 아니나 **쌍 1600의 오경보를 "
            "흔들 만큼 크지 않다** (D-0456의 표)"
        )
    return (
        f"**이 판 수로는 0과 안 갈린다** (평균의 `t` {negative.mean_t:+.2f} · "
        f"95% 상한 {negative.ceiling:+.6f}, 문턱 {CEILING_FLOOR:+.6f}). "
        "「0이다」가 아니라 「못 갈랐다」이며, 갈리려면 판을 늘린다 (GR-0.5)"
    )


def sweep(name: str, *, sigma: float, args: argparse.Namespace) -> Sweep:
    """한 대조를 `trials`판 돈다. **판마다 코퍼스도 새로 뽑는다.**

    `--hold-corpus`면 코퍼스와 생성 시드를 **고정하고 쌍만** 다시 뽑는다 (D-0464).
    그러면 판 사이 흔들림이 **순수한 쌍 표집**이 되어 보고된 판별 오차와 **같은 것을
    재게** 된다 — 기본 모드에서는 분자에 코퍼스 사이 흔들림이 섞여 있어 둘의 비가
    **짝이 독립이어도** 쌍 수와 함께 오른다. 그 섞임이 「쌍 겹침이 정보를 깎나」를
    가리고 있었다.
    """
    gains: list[float] = []
    errors: list[float] = []
    passed = 0
    masses: list[float] = []
    started = time.monotonic()
    for index in range(args.trials):
        drift = 0 if args.hold_corpus else index
        corpus = build(
            args.songs, seed=args.corpus_seed + drift, sigma=sigma, diatonic_mass=args.mass
        )
        masses.append(diatonic_mass_of(corpus))
        # **생성 시드도 판마다 민다** (D-0461). `seed`는 생성기에 안 닿으므로
        # 이것이 없으면 전 판이 같은 진행 1000개를 보고, 고정된 치우침이 흔들림에
        # 안 들어가 **`mean_t`가 인공물 위에서 자란다.**
        #
        # **`--hold-corpus`에서는 일부러 안 민다** — 생성 시드가 움직이면 그 흔들림도
        # 분자에 들어가 쌍 표집만 보려던 것이 다시 흐려진다 (D-0464).
        condition = OutputCondition(
            pair_count=args.pairs,
            seed=args.trial_seed + index,
            seed_offset=(args.trial_seed + drift) * args.songs,
        )
        # **`VocabularyComparison`을 안 쓴다** (D-0463). 그것이 읽는 것은 `paired`
        # 선 하나인데 `run()`이 일곱을 다 돌고, `base`는 `free_gain`에만 쓰여 여기서
        # 한 번도 안 읽힌다. 같은 수를 **비트까지 같게** 더 싸게 낸다 — 그 동일성이
        # `test_빠른_길이_느린_길과_비트까지_같다`에 걸려 있고, **그것이 걸려 있어야
        # 느린 길로 모은 판과 이 길로 모은 판을 같이 센다.**
        found = gap_of(
            *(
                EvaluateHarmonyOutput(
                    replace(condition, vocabulary=Vocabulary(word))
                ).paired_distances(corpus)
                for word in ("mixture", "control")
            )
        )
        gains.append(found.gain)
        errors.append(found.standard_error)
        passed += found.beats
        # **여섯 자리다** (D-0464). 넷째 자리로 찍었더니 **긴 판이 통 시간 제한에
        # 잘렸을 때** 남은 것이 반올림된 줄뿐이었고, 판정 문턱이 넷째 자리라
        # 거기서 요약을 되살리면 정밀도가 모자란다.
        print(
            f"  {name} 판 {index:3d} · 이득 {found.gain:+.6f} ±{found.standard_error:.6f}"
            f" · t {found.t:+.2f} · {'통과' if found.beats else '실패'}",
            flush=True,
        )
    return Sweep(
        name=name,
        gains=tuple(gains),
        errors=tuple(errors),
        passed=passed,
        mass=statistics.fmean(masses),
        seconds=time.monotonic() - started,
    )


TRIAL_LINE = re.compile(
    r"^\s+(\S+) 판\s+\d+ · 이득 ([+-][\d.]+) ±([\d.]+) · t [+-][\d.]+ · (통과|실패)\s*$"
)
"""판 줄을 되읽는 꼴. **요약 줄의 「평균 이득」과 안 겹치게** 앞 공백을 요구한다."""


def summarize(path: Path) -> Sweep:
    """**잘린 판의 로그에서 요약을 되살린다** (D-0464).

    판 120개짜리가 통 시간 제한에 **104개에서 잘렸다.** 요약은 끝에만 찍히므로
    남은 것이 판 줄뿐이었고, 그것을 손으로 합치면 GR-0.7이다.

    **잘린 지점은 벽시계가 정했지 수가 정하지 않았다** — 판 수가 줄면 오차가
    커질 뿐 어느 쪽으로도 안 민다. 그래도 **몇 판에서 잘렸는지는 적어야** 읽는
    사람이 사전 등록한 판 수와 견줄 수 있다 (GR-0.5).

    질량과 초는 로그에 판별로 없으므로 **`nan`과 0으로 둔다** — 0이나 추정값을
    넣으면 그 칸이 잰 수처럼 보인다.
    """
    gains: list[float] = []
    errors: list[float] = []
    passed = 0
    name = "요약"
    for line in path.read_text(encoding="utf-8").splitlines():
        found = TRIAL_LINE.match(line)
        if found is None:
            continue
        name = found.group(1)
        gains.append(float(found.group(2)))
        errors.append(float(found.group(3)))
        passed += found.group(4) == "통과"
    if len(gains) < 2:
        raise ValueError(f"판 줄이 둘 미만이다: {path} ({len(gains)}개)")
    return Sweep(
        name=f"{name}(로그 {len(gains)}판)",
        gains=tuple(gains),
        errors=tuple(errors),
        passed=passed,
        mass=float("nan"),
        seconds=0.0,
    )


def cost(args: argparse.Namespace) -> str:
    """돌리기 전에 **얼마나 드는지** 적는다 (D-0129는 무거운 것을 끄라고 했다)."""
    covered = touched_count(
        EvaluateHarmonyOutput(
            OutputCondition(pair_count=args.pairs, seed=args.trial_seed)
        ).pair_indices(args.songs)
    )
    sides = 2 if args.only == "both" else 1
    runs = args.trials * sides * 2
    return (
        f"코퍼스 {args.songs}곡 · 쌍 {args.pairs}(덮는 곡 {covered}) · 판 {args.trials} · "
        f"대조 {sides}개 · 어휘 2개\n"
        f"**생성 {runs}벌 · 곡 {covered * runs:,}개분.** 참고: 실물 1004곡 · 쌍 400의 "
        f"`eval harmony-output --compare-vocabulary` 한 판이 그의 기기에서 11분이다 — "
        f"**이 탐침은 그 선 일곱과 `base`를 안 돈다** (D-0463). 판당 초는 아래 요약이 찍는다"
    )


def report(one: Sweep) -> None:
    print(
        f"{one.name}: 통과 **{one.passed}/{len(one.gains)}** · "
        f"평균 이득 {one.mean:+.6f} ±{one.mean_error:.6f}(판 사이) · "
        f"평균의 t {one.mean_t:+.2f} · 95% 상한 {one.ceiling:+.6f} · "
        f"흔들림/보고오차 {one.honesty:.2f} · "
        f"온음계 질량 {one.mass:.4f} · {one.seconds:.0f}초"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="문턱의 오경보율과 검출율 (D-0460)")
    parser.add_argument("--trials", type=int, default=TRIALS, help="대조마다 몇 판")
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIR_COUNT, help="견줄 쌍 수")
    parser.add_argument("--songs", type=int, default=SONGS, help="코퍼스 곡 수")
    parser.add_argument("--mass", type=float, default=REAL_DIATONIC_MASS, help="맞출 온음계 질량")
    parser.add_argument("--sigma", type=float, default=SIGMA, help="양성에서 차용 칸 흔들림")
    parser.add_argument("--corpus-seed", type=int, default=90001, help="코퍼스 시드의 바닥")
    parser.add_argument(
        "--trial-seed",
        type=int,
        default=0,
        help="조건·생성 시드의 바닥. **판을 나눠 모을 때 반드시 겹치지 않게 준다**",
    )
    parser.add_argument(
        "--only",
        choices=("both", "negative", "positive"),
        default="both",
        help="한 대조만 돈다. 배경 작업 상한에 걸려 판을 나눠 모을 때 쓴다",
    )
    parser.add_argument("--dry-run", action="store_true", help="비용만 찍고 멈춘다")
    parser.add_argument(
        "--summarize",
        type=Path,
        help="판 줄이 남은 로그에서 요약을 되살린다 — 긴 판이 시간 제한에 잘렸을 때",
    )
    parser.add_argument(
        "--hold-corpus",
        action="store_true",
        help="코퍼스와 생성 시드를 고정하고 쌍만 다시 뽑는다 — 정직성이 쌍 표집만 본다",
    )
    args = parser.parse_args()

    if args.summarize is not None:
        revived = summarize(args.summarize)
        report(revived)
        print(f"\n판정: {verdict(revived)}")
        print(
            "\n**로그에서 되살린 요약이다.** 질량과 초는 판별로 안 찍히므로 "
            "`nan`·0이다 (GR-0.5). 판 수가 사전 등록한 수보다 적으면 **어디서 "
            "잘렸는지**를 기록에 적는다 — 벽시계가 자른 것과 수를 보고 자른 것은 다르다."
        )
        return 0

    if args.trials < 2:
        print("판이 둘 이상이어야 흔들림을 잰다 (GR-0.5)", file=sys.stderr)
        return 1

    print(cost(args))
    if args.dry_run:
        return 0
    print(f"\n문턱 `t >= {PAIRED_T_FLOOR}` · 읽는 법은 `verdict()`에 박혀 있다 (D-0058)\n")

    negative = sweep("음성", sigma=0.0, args=args) if args.only != "positive" else None
    positive = sweep("양성", sigma=args.sigma, args=args) if args.only != "negative" else None
    print()
    for one in (negative, positive):
        if one is not None:
            report(one)

    if positive is not None and positive.passed == 0:
        print(
            "\n**양성이 한 판도 안 통과했다.** 자가 안 도는 것이므로 음성 쪽을 "
            "읽지 않는다 (D-0259 · D-0230).",
            file=sys.stderr,
        )
        return 1
    if negative is None:
        return 0
    if args.hold_corpus:
        # **양성 대조를 안 찾는다** (D-0464). 양성은 *«문턱이 진짜를 놓치나»*를 묻는
        # 자인데, 이 모드가 내는 것은 **보고오차가 정직한가** 하나다. 효과를 집는
        # 능력과 무관하므로 양성이 있든 없든 그 수는 같다 — 여기서 양성을 요구하면
        # **안 쓰는 대조를 돌리라고 시키는 것**이다 (D-0126의 거울상).
        print(
            f"\n**판정 안 함 — `--hold-corpus`다.** 이 판이 내는 것은 **정직성 "
            f"{negative.honesty:.3f}** 하나이고, 코퍼스가 하나라 판 사이 흔들림이 "
            "**순수한 쌍 표집**이다. 1에 가까우면 쌍이 겹쳐도 보고오차가 정직하다는 "
            "뜻이고, 그러면 기본 모드의 초과분은 **코퍼스 사이 흔들림**이다.\n"
            "평균·`t`·통과율은 **이 코퍼스 하나의 성질**이라 쌍 수 판정에 안 쓴다."
        )
        return 0
    if positive is None:
        # **양성 없이 음성을 읽는 것이 D-0259가 막는 일이다.** 다만 양성이 **이
        # 판에서** 돌아야 한다는 뜻은 아니다 — 기록에 있으면 된다. 어디에 기대는지
        # 화면에 적어야 읽는 사람이 그것을 확인할 수 있다 (D-0191).
        print(f"\n양성은 이 판에서 안 돌았다 — **{POSITIVE_ON_RECORD}**에 기댄다 (D-0259)")
        odd = [
            f"{name} {getattr(args, name)} != {value}"
            for name, value in RECORDED_UNDER.items()
            if getattr(args, name) != value
        ]
        if odd:
            # **다른 조건에서 잰 양성에 기대면 그것은 기댄 것이 아니다** (D-0325가
            # 40곡으로 1004곡을 판정한 자리와 같은 꼴이다).
            print(f"**그런데 조건이 다르다: {' · '.join(odd)}**", file=sys.stderr)
            print("양성을 이 조건에서 다시 돌린다 — `--only both`", file=sys.stderr)
            return 1
    print(f"\n판정: {verdict(negative)}")
    print(
        "\n**양성은 「문턱이 진짜를 놓치지 않나」를 본다** — 음성만 보면 "
        "「아무것도 통과 안 시키는 문턱」이 가장 좋아 보인다 (D-0327이 `t>=3`을 "
        "기각한 까닭이다)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
