"""참조곡에서 뽑은 템포 (D-0392 · O-46).

**실측은 그의 기기에서만 된다.** `var/`는 gitignore이고 오디오는 기기를 떠나지 않는다
(D-0015). 여기서 보는 것은 **가르는 법**이다 — 접는 선, 중앙값, 못 읽음의 판정.
곡 1004개의 수는 `make measure`가 낸다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.reference_tempo import TempoVerdict, from_envelopes
from hathor.domain.services.onset import OCTAVE_FLOOR, folded_tempo

HOP = 0.01


def _pulse(bpm: float, seconds: float = 20.0, hop: float = HOP) -> np.ndarray:
    """그 빠르기로 또박또박 치는 포락선. **합성이라 정답을 안다.**"""
    frames = int(seconds / hop)
    period = 60.0 / bpm / hop
    envelope = np.zeros(frames, dtype=np.float64)
    envelope[:: max(1, round(period))] = 1.0
    return envelope


# ------------------------------------------------------------------ 접는 선


@pytest.mark.parametrize(
    ("given", "want"),
    [(67.0, 134.0), (60.0, 120.0), (89.9, 179.8), (90.0, 90.0), (126.0, 126.0), (180.0, 180.0)],
)
def test_선_아래만_두_배로_접는다(given: float, want: float) -> None:
    """**D-0206이 쓴 값이다.** 원값 중앙 67이 접힌 뒤 126이 됐다."""
    assert folded_tempo(given) == pytest.approx(want)


def test_두_번_접지_않는다() -> None:
    """**240은 박이 아니다.** 한 번 접은 값은 선 위에 있으므로 다시 안 접힌다."""
    once = folded_tempo(55.0)

    assert folded_tempo(once) == once
    assert once >= OCTAVE_FLOOR


# ------------------------------------------------------------------ 합산


def test_참조곡에서_템포를_읽는다() -> None:
    """**이 판의 본체다.** 합성 박에서 그 빠르기가 돌아와야 한다."""
    verdict = from_envelopes([(_pulse(120.0), HOP)])

    assert verdict.bpm is not None
    assert abs(verdict.bpm - 120) <= 3, verdict
    assert verdict.read == 1 and verdict.asked == 1


def test_절반으로_읽힌_곡은_접기가_고친다() -> None:
    """**접는 선이 먼저 일한다.** 60은 120이 되어 이웃과 나란히 선다."""
    verdict = from_envelopes([(_pulse(120.0), HOP), (_pulse(124.0), HOP), (_pulse(60.0), HOP)])

    assert verdict.bpm is not None
    assert 115 <= verdict.bpm <= 130, verdict


def test_접기로_못_고치는_이상치에_안_끌린다() -> None:
    """**왜 중앙값인가** (D-0392).

    **첫 판 시험이 이것을 못 쟀다.** 60을 이상치로 넣었는데 접기가 120으로 고쳐
    평균과 중앙값이 같아졌고, *«중앙값 → 평균»* 심은 결함에 **아무 시험도 안
    울었다** (D-0069). 접기가 손대지 않는 것은 **선 위에서 두 배로 읽힌 곡**이다.

    190을 넣으면 평균은 140대로 끌리고 중앙값은 124에 선다.
    """
    verdict = from_envelopes([(_pulse(120.0), HOP), (_pulse(124.0), HOP), (_pulse(190.0), HOP)])

    assert verdict.bpm is not None
    assert verdict.bpm <= 135, f"이상치에 끌렸다 — 평균을 쓰고 있다: {verdict}"


def test_곡마다_접고_나서_중앙값을_낸다() -> None:
    """**거꾸로 하면 엉뚱한 값이 된다** — D-0206의 원값 중앙 67이 그 상태였다."""
    verdict = from_envelopes([(_pulse(60.0), HOP), (_pulse(62.0), HOP), (_pulse(64.0), HOP)])

    assert verdict.bpm is not None
    assert verdict.bpm >= OCTAVE_FLOOR, f"접기 전 중앙값을 냈다: {verdict}"
    assert verdict.raw_median is not None and verdict.raw_median < OCTAVE_FLOOR


def test_못_읽으면_0이_아니라_None이다() -> None:
    """**못 잰 것을 0이라 말하지 않는다** (GR-0.5). 0BPM은 박이 아니라 거짓말이다."""
    verdict = from_envelopes([(np.zeros(2000, dtype=np.float64), HOP)])

    assert verdict.bpm is None
    assert verdict.read == 0 and verdict.asked == 1
    assert "못 읽었다" in verdict.source


def test_몇_곡에서_읽었는지_든다() -> None:
    """**물어본 수와 읽은 수를 둘 다 든다** (D-0269). 차이가 곧 못 읽은 곡이다."""
    verdict = from_envelopes([(_pulse(120.0), HOP), (np.zeros(2000, dtype=np.float64), HOP)])

    assert (verdict.read, verdict.asked) == (1, 2)
    assert "1/2곡" in verdict.source


def test_빈_목록도_0을_안_낸다() -> None:
    """참조가 없으면 **모르는 것**이다."""
    assert from_envelopes([]) == TempoVerdict(bpm=None, read=0, asked=0, raw_median=None)


# ------------------------------------------------------------------ 배선
#
# **부품을 재고 배선을 안 쟀다** (D-0352). 위의 열셋은 가르는 법을 보고, 아래는
# 그 값이 **산출물까지 닿는가**를 본다 — D-0353이 실측으로 두 번 물린 자리다.


def test_산출물이_템포의_출처를_든다() -> None:
    """**어디서 온 템포인지 말해야 한다** (D-0269 · GR-0.5).

    `tempo_bpm` 옆에 `tempo_from`이 없으면 126을 보고 *«코퍼스 중앙인가 이 곡의
    박인가»*를 못 가린다. 그 둘은 전혀 다른 말이다.
    """
    from hathor.application.orchestrator.generation_pipeline import render
    from hathor.domain.entities.generation_job import GenerationJob, Stage
    from hathor.domain.services.song_structure import extract_pattern

    stages: tuple[Stage, ...] = (Stage("structure"), Stage("harmony"))
    pattern = extract_pattern(["가 나 다", "가 나 다", "라 마 바", "가 나 다"])
    _data, summary = render(
        GenerationJob(seed=7, stages=stages),
        [pattern],
        tempo_bpm=143,
        tempo_from="참조 2/3곡 중앙",
    )

    assert summary["tempo_bpm"] == 143
    assert summary["tempo_from"] == "참조 2/3곡 중앙"


def test_입구가_참조곡에서_뽑는_길을_탄다() -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126 · D-0219).

    `--tempo` 기본값이 `DEFAULT_TEMPO_BPM`이면 «사람이 줬다»와 «안 줬다»가 안 갈려
    참조곡을 볼 자리가 없다. 그 기본값이 돌아오면 이 판이 통째로 죽는다.
    """
    from pathlib import Path

    where = Path(__file__).resolve().parents[2] / "hathor/interfaces/cli"
    body = (where / "main.py").read_text(encoding="utf-8")

    assert '"--tempo", type=int, default=None' in body, "기본값이 돌아왔다 — 참조곡을 안 본다"
    assert "resolve_tempo(args, [song[0] for song in chosen])" in body, "해석자를 안 부른다"
    assert "tempo_from=tempo_source" in body, "출처를 안 넘긴다"
    assert "def resolve_tempo(" in (where / "tempo_source.py").read_text(encoding="utf-8")
