"""포락선이 박을 담는지 판정하는 자 (D-0314).

**D-0311에서 배운 것을 처음부터 넣었다** — 음성 대조를 곡별로 빼고, 불변인 귀무를
미리 배제한다. 그리고 **자가 두 방향으로 움직이는지 합성 둘로 확인한다** (O-25 여섯째
줄 · D-0303 · D-0306).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hathor.application.evaluate_onsets import (
    BEAT_FLOOR,
    BeatGain,
    BeatLine,
    line,
    load_lines,
    rolled,
    shuffled,
)
from hathor.domain.services.onset import beat_period
from hathor.infrastructure.onset_store import write_envelope
from hathor.interfaces.cli.main import main

HOP = 0.01
FRAMES = 2000
PERIOD = 50
"""50프레임 x 0.01초 = 0.5초 = 120BPM."""


def clicks(*, noise: float, seed: int, period: int = PERIOD) -> np.ndarray:
    """감쇠하는 클릭 트랙. **박이 실제로 있는 자료다.**"""
    generator = np.random.default_rng(seed)
    envelope = np.zeros(FRAMES)
    for start in range(0, FRAMES, period):
        for step in range(6):
            if start + step < FRAMES:
                envelope[start + step] += float(np.exp(-step / 2.0))
    return envelope + generator.random(FRAMES) * noise


def beating(count: int = 40) -> list[tuple[np.ndarray, float]]:
    return [
        (clicks(noise=nz, seed=index), HOP)
        for index, nz in enumerate([0.0, 0.1, 0.3, 0.5, 1.0] * (count // 5))
    ]


def noiseless(count: int = 40) -> list[tuple[np.ndarray, float]]:
    """**박이 없는 자료.** 자가 여기서 져야 비교가 된다 (D-0062)."""
    return [(np.random.default_rng(seed).random(FRAMES), HOP) for seed in range(count)]


def _gain(songs: list[tuple[np.ndarray, float]]) -> BeatGain:
    return BeatGain(measured=line("실측", songs), control=line("섞음", songs, transform="shuffled"))


def test_박이_있으면_판정이_참이다() -> None:
    """클릭 트랙 40곡. **문턱을 크게 넘어야 «담는다»를 말할 수 있다.**"""
    gain = _gain(beating())
    assert gain.gain > 1.0
    assert gain.t_statistic > BEAT_FLOOR * 3
    assert gain.win_rate == pytest.approx(1.0)
    assert gain.carries_beat


def test_박이_없으면_판정이_거짓이다() -> None:
    """**질 수 있는 지표다** (O-25 (2) · D-0062). 균등 잡음에서 문턱을 못 넘는다."""
    gain = _gain(noiseless())
    assert gain.t_statistic < BEAT_FLOOR
    assert not gain.carries_beat


def test_margin은_거꾸로_간다() -> None:
    """**이것이 지표를 바꾼 이유다** (D-0314).

    진짜 주기는 배수 지연에서도 봉우리가 서므로 1등과 2등의 차가 **작아진다.**
    `margin`으로 판정했으면 «박이 있으면 낮다»는 거꾸로 선 자가 됐다.
    """
    real = clicks(noise=0.0, seed=3)
    mixed = shuffled(real, seed=7)
    hit, miss = beat_period(real, HOP), beat_period(mixed, HOP)
    assert hit is not None
    assert miss is not None
    assert hit.margin < miss.margin, "margin이 거꾸로 가지 않으면 이 시험이 뜻이 없다"
    assert hit.peak_ratio > miss.peak_ratio, "뾰족함은 바로 간다"


def test_위상_돌림은_박_축의_귀무가_아니다() -> None:
    """**자기상관은 순환 이동에 거의 불변이다** (D-0300이 화음 품질에서 겪은 것과 같다).

    돌린 것으로 재면 실측과 같은 값이 나오고, 그것을 «차이가 없다»로 읽으면 틀린다.
    """
    songs = beating()
    measured = line("실측", songs)
    turned = line("돌림", songs, transform="rolled")
    assert turned.mean_ratio == pytest.approx(measured.mean_ratio, rel=0.05)
    control = line("섞음", songs, transform="shuffled")
    assert control.mean_ratio < measured.mean_ratio * 0.7


def test_섞음은_값_분포를_남긴다() -> None:
    """**박 구조만 없앤다** (O-25 (5)). 값 다중집합이 그대로다."""
    real = clicks(noise=0.3, seed=11)
    assert np.allclose(np.sort(real), np.sort(shuffled(real, seed=1)))
    assert np.allclose(np.sort(real), np.sort(rolled(real, seed=1)))


def test_곡_수가_다르면_짝지을_수_없다() -> None:
    left = BeatLine(label="a", ratios=(1.0, 2.0, 3.0), decided=3)
    right = BeatLine(label="b", ratios=(1.0,), decided=1)
    gain = BeatGain(measured=left, control=right)
    assert not gain.aligned
    assert gain.gain == 0.0
    assert not gain.carries_beat


def test_못_고른_곡도_자리를_지킨다() -> None:
    """**빼는 쪽에서 곡을 버리면 두 선의 곡 집합이 갈린다.** 0.0으로 남긴다."""
    flat = [(np.zeros(FRAMES), HOP), *beating(5)]
    found = line("실측", flat)
    assert len(found.ratios) == len(flat)
    assert found.decided < len(flat)
    assert found.ratios[0] == 0.0


def test_포락선이_없으면_거부한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["eval", "onsets", "--out", str(tmp_path / "산출"), "--envelopes", str(tmp_path / "없음")]
    )
    assert code == 2
    assert "ingest onsets" in capsys.readouterr().err


def test_보고가_세_선과_판정을_찍는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / "keys-000001.onsets"
    for index, (envelope, hop) in enumerate(beating(10)):
        write_envelope(folder, f"곡{index}.flac", envelope, hop_seconds=hop)
    out = tmp_path / "산출"
    assert main(["eval", "onsets", "--out", str(out), "--envelopes", str(folder)]) == 0
    printed = capsys.readouterr().out
    assert "시간 섞음" in printed
    assert "위상 돌림" in printed
    assert "귀무가 아니다" in printed, "돌림이 귀무가 아니라고 화면에 적어야 한다"
    assert "박을 담는다" in printed

    record = json.loads(next((out / "eval").glob("*-onsets.eval.json")).read_text("utf-8"))
    assert record["tracks"] == 10
    assert record["paired"]["carries_beat"] is True
    assert set(record["lines"]) == {"실측", "시간 섞음", "위상 돌림"}


def test_폴더를_읽어_세_선을_낸다(tmp_path: Path) -> None:
    folder = tmp_path / "keys-000002.onsets"
    for index, (envelope, hop) in enumerate(beating(5)):
        write_envelope(folder, f"곡{index}.flac", envelope, hop_seconds=hop)
    measured, control, turned = load_lines(folder)
    assert len(measured.ratios) == len(control.ratios) == len(turned.ratios) == 5
    assert measured.mean_ratio > control.mean_ratio
