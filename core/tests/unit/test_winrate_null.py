"""`승률 > 0.5` 항이 든 사전 등록 규칙 다섯이 **차이 0에서 얼마나 통과하는가** (D-0474).

D-0447이 `evaluate_degree_restriction`의 셋에서 쟀던 것을 **나머지 넷**에 한다. 참 차이가
0인 합성(두 선이 같은 분포)에서 규칙 전체와 승률 항만을 따로 센다. 승률 항만으로는
어느 규칙이든 동전이다 — **오경보를 막는 것이 무엇인가**를 가르는 시험이다.
"""

from __future__ import annotations

import os

import numpy as np

from hathor.application import evaluate_harmony_output as harmony
from hathor.application.evaluate_onsets import BeatGain, BeatLine
from hathor.application.evaluate_order_conditioning import OrderReport
from hathor.application.evaluate_time_drift import EvaluateTimeDrift
from hathor.domain.services.chroma_drift import DriftObservation

TRIALS = int(os.environ.get("NULL_TRIALS", "400"))
DRIFT_TRIALS = max(TRIALS // 10, 60)
SONGS = 60


def _rng() -> np.random.Generator:
    return np.random.default_rng(20261026)


def test_온셋_규칙은_t_문턱이_승률_항의_동전을_막는다() -> None:
    rng = _rng()
    full = win_only = 0
    for _ in range(TRIALS):
        a = rng.normal(0.5, 0.1, SONGS)
        b = rng.normal(0.5, 0.1, SONGS)
        gain = BeatGain(BeatLine("m", tuple(a), SONGS), BeatLine("c", tuple(b), SONGS))
        full += gain.carries_beat
        win_only += gain.gain > 0.0 and gain.win_rate > 0.5

    print(f"onsets: 규칙 전체 {full}/{TRIALS} · 승률 항만 {win_only}/{TRIALS}")
    assert full / TRIALS < 0.02, f"규칙 전체가 차이 0에서 {full}/{TRIALS} 통과한다"
    assert win_only / TRIALS > 0.2, "승률 항만으로는 막지 못한다 — 막는 것은 t 항이다"


def test_순서_규칙은_t_문턱이_승률_항의_동전을_막는다() -> None:
    rng = _rng()
    full = win_only = 0
    for _ in range(TRIALS):
        own = tuple(rng.normal(0.3, 0.1, SONGS))
        other = tuple(rng.normal(0.3, 0.1, SONGS))
        report = OrderReport(None, SONGS, own, other)  # type: ignore[arg-type]
        full += report.carries_reference_order
        win_only += report.gap > 0.0 and report.win_rate > 0.5

    print(f"order_conditioning: 규칙 전체 {full}/{TRIALS} · 승률 항만 {win_only}/{TRIALS}")
    assert full / TRIALS < 0.02, f"규칙 전체가 차이 0에서 {full}/{TRIALS} 통과한다"
    assert win_only / TRIALS > 0.2, "승률 항만으로는 막지 못한다 — 막는 것은 t 항이다"


def test_시간_변화_규칙은_t_문턱이_칸_과반_항의_동전을_막는다() -> None:
    rng = _rng()
    evaluator = EvaluateTimeDrift(seed=1, null_repeats=10, bootstrap=20)
    full = share_only = 0
    trials = DRIFT_TRIALS
    for _ in range(trials):
        observed = [
            DriftObservation("s", tuple(rng.normal(0, 1, 12)), tuple(rng.normal(0, 1, 12)))
            for _ in range(SONGS)
        ]
        report = evaluator.run(observed, "null")
        full += report.time_drift_is_song_specific
        share_only += report.excess > 0.0 and report.cell_share > 0.5

    print(f"time_drift: 규칙 전체 {full}/{trials} · 칸 과반 항만 {share_only}/{trials}")
    assert full / trials < 0.05, f"규칙 전체가 차이 0에서 {full}/{trials} 통과한다"
    assert share_only / trials > 0.1, "칸 과반 항만으로는 막지 못한다 — 막는 것은 t 항이다"


def test_출력_갈림_규칙은_t_항이_없어_차이_0에서_동전이다() -> None:
    """**알고 두는 것이다** (D-0474). 사전 등록 규칙이라 지우지 않는다.

    규칙에 `t` 항이 없고 3항(`paired <= random`)은 두 선이 같은 분포이면 동전이다.
    그래서 이 규칙은 **주 판정이 아니다** — 주 판정은 `t`(`PairedGap.beats`)다. 이 시험은
    누가 이 규칙을 주 판정으로 되돌리면 그 사실이 시험에 남도록 현재 상태를 못 박는다.
    """
    rng = _rng()
    zeros = tuple([0.0] * 400)
    full = 0
    for _ in range(TRIALS):
        lines = tuple(
            harmony.OutputLine(name, tuple(abs(rng.normal(0.3, 0.1, 400))), zeros, zeros)
            for name in ("paired", "random")
        )
        report = harmony.OutputReport("null", harmony.OutputCondition(), 400, lines)
        full += report.is_output_conditioned

    print(f"harmony_output: 규칙 전체 {full}/{TRIALS}")
    assert 0.35 < full / TRIALS < 0.65, f"동전이 아니다: {full}/{TRIALS}"
