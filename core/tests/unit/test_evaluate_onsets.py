"""포락선이 박을 담는지 판정하는 자 (D-0314 · D-0315).

**D-0311에서 배운 것을 처음부터 넣었다** — 음성 대조를 곡별로 빼고, 불변인 귀무를
미리 배제한다. 그리고 **자가 두 방향으로 움직이는지 합성 둘로 확인한다** (O-25 여섯째
줄 · D-0303 · D-0306).

### 합성 둘로 모자랐다 — 셋째 축이 실물에만 있었다 (D-0315)

D-0314는 「박 있음」과 「박 없음」 둘을 지었고 **그 축에서는 옳았다.** 그런데 실물에는
셋째 축이 있었다 — **곡의 느린 강약**(절·후렴·페이드)이다. 두 합성 모두 그것이 없었고,
1004곡에서 자가 통째로 뒤집혔다.

**그래서 강약을 입힌 판을 둘 더 둔다.** 「박+강약」과 「강약만」이며, 이 넷이 **강제자**다.
자가 강약에 흔들리면 여기가 빨개진다.
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
from hathor.domain.services.onset import _lag_scores, beat_period, beat_strength
from hathor.infrastructure.onset_store import write_envelope
from hathor.interfaces.cli.main import main

HOP = 0.01
FRAMES = 2000
PERIOD = 50
"""50프레임 x 0.01초 = 0.5초 = 120BPM."""

NOISES = [0.0, 0.1, 0.3, 0.5, 1.0]


def clicks(*, noise: float, seed: int, period: int = PERIOD) -> np.ndarray:
    """감쇠하는 클릭 트랙. **박이 실제로 있는 자료다.**"""
    generator = np.random.default_rng(seed)
    envelope = np.zeros(FRAMES)
    for start in range(0, FRAMES, period):
        for step in range(6):
            if start + step < FRAMES:
                envelope[start + step] += float(np.exp(-step / 2.0))
    return envelope + generator.random(FRAMES) * noise


def swelled(envelope: np.ndarray, *, seed: int, depth: float = 1.0) -> np.ndarray:
    """곡의 **느린 강약**을 입힌다 — 절·후렴·페이드가 내는 것이다 (D-0315).

    20초 트랙에 한 주기이며 **박 범위(0.3~1.2초)보다 열 배 이상 느리다.** 음수 이득은
    물리적으로 없으므로 0에서 자른다.
    """
    phase = float(np.random.default_rng(seed).uniform(0.0, 2.0 * np.pi))
    turn = np.sin(2.0 * np.pi * np.arange(envelope.size) / envelope.size + phase)
    return envelope * np.clip(1.0 + depth * turn, 0.0, None)


def beating(count: int = 40) -> list[tuple[np.ndarray, float]]:
    levels = [NOISES[index % len(NOISES)] for index in range(count)]
    return [(clicks(noise=level, seed=index), HOP) for index, level in enumerate(levels)]


def swelling(count: int = 40) -> list[tuple[np.ndarray, float]]:
    """**박이 있고 느린 강약도 있다** — 실물이 이 부류다 (D-0315)."""
    songs = beating(count)
    return [(swelled(env, seed=index), hop) for index, (env, hop) in enumerate(songs)]


def noiseless(count: int = 40) -> list[tuple[np.ndarray, float]]:
    """**박이 없는 자료.** 자가 여기서 져야 비교가 된다 (D-0062)."""
    return [(np.random.default_rng(seed).random(FRAMES), HOP) for seed in range(count)]


def swelling_noise(count: int = 40) -> list[tuple[np.ndarray, float]]:
    """**박은 없고 느린 강약만 있다.** 자가 강약을 박으로 세면 여기가 통과한다."""
    songs = noiseless(count)
    return [(swelled(env, seed=index), hop) for index, (env, hop) in enumerate(songs)]


def _gain(songs: list[tuple[np.ndarray, float]]) -> BeatGain:
    return BeatGain(measured=line("실측", songs), control=line("섞음", songs, transform="shuffled"))


def _level_ratio(envelope: np.ndarray, hop_seconds: float) -> float:
    """**차분하지 않고** 잰 뾰족함 — D-0314가 실물에 걸었던 그 자다 (D-0315)."""
    found = _lag_scores(envelope, hop_seconds)
    if found is None:
        return 0.0
    scores, _ = found
    spread = float(np.abs(scores).mean())
    return float(scores.max() / spread) if spread > 0.0 else 0.0


def _level_gain(songs: list[tuple[np.ndarray, float]], *, seed: int = 20260930) -> BeatGain:
    lines = []
    for label, turn in (("실측", False), ("섞음", True)):
        ratios = tuple(
            _level_ratio(shuffled(envelope, seed=seed + index) if turn else envelope, hop)
            for index, (envelope, hop) in enumerate(songs)
        )
        lines.append(BeatLine(label=label, ratios=ratios, decided=len(ratios)))
    return BeatGain(measured=lines[0], control=lines[1])


def test_박이_있으면_판정이_참이다() -> None:
    """클릭 트랙 40곡. **문턱을 크게 넘어야 «담는다»를 말할 수 있다.**"""
    gain = _gain(beating())
    assert gain.gain > 1.0
    assert gain.t_statistic > BEAT_FLOOR * 3
    assert gain.win_rate == pytest.approx(1.0)
    assert gain.carries_beat


def test_느린_강약이_있어도_판정이_참이다() -> None:
    """**셋째 축이다** (D-0315). 실물에는 절·후렴이 있고 합성 둘에는 없었다.

    같은 클릭 트랙에 강약만 입힌다. 자가 강약에 흔들리면 여기서 떨어진다.
    """
    gain = _gain(swelling())
    assert gain.t_statistic > BEAT_FLOOR * 2
    assert gain.win_rate == pytest.approx(1.0)
    assert gain.carries_beat


def test_박이_없으면_판정이_거짓이다() -> None:
    """**질 수 있는 지표다** (O-25 (2) · D-0062). 균등 잡음에서 문턱을 못 넘는다."""
    gain = _gain(noiseless())
    assert gain.t_statistic < BEAT_FLOOR
    assert not gain.carries_beat


def test_강약만_있으면_판정이_거짓이다() -> None:
    """**강약을 박으로 세면 안 된다.** 느린 강약뿐인 잡음은 문턱을 못 넘는다."""
    gain = _gain(swelling_noise())
    assert gain.t_statistic < BEAT_FLOOR
    assert not gain.carries_beat
    assert not gain.ruler_broken, "고친 자는 강약에서 고장 신호도 안 내야 한다"


def test_차분을_빼면_자가_뒤집힌다() -> None:
    """**D-0314가 실물에서 왜 -0.354를 냈는지가 여기 있다** (D-0315).

    수준에서 재면 곡의 느린 강약이 지연 전체에 넓은 언덕을 만들어 **분모를 부풀린다.**
    강약만 있는 잡음에서는 음성 대조가 실측을 이겨 **고장 신호까지 뜬다.**
    """
    assert _level_gain(swelling_noise()).ruler_broken, "차분 없이는 음성 대조가 이긴다"
    assert not _gain(swelling_noise()).ruler_broken

    level, fixed = _level_gain(swelling()), _gain(swelling())
    assert level.t_statistic < fixed.t_statistic / 3.0, "차분이 강약을 걷어 내야 한다"


def test_음성_대조가_이기면_고장이다() -> None:
    """**구조를 지운 쪽이 이길 수는 없다** (D-0315). «없다»와 갈라 찍는다."""
    weak = BeatGain(
        measured=BeatLine(label="실측", ratios=(1.0, 1.1, 0.9, 1.0), decided=4),
        control=BeatLine(label="섞음", ratios=(3.0, 3.2, 2.8, 3.1), decided=4),
    )
    assert weak.ruler_broken
    assert not weak.carries_beat
    flat = _gain(noiseless())
    assert not flat.carries_beat
    assert not flat.ruler_broken, "못 넘는 것과 거꾸로 가는 것은 다른 판정이다"


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
    strong, weak = beat_strength(real, HOP), beat_strength(mixed, HOP)
    assert strong is not None
    assert weak is not None
    assert strong > weak, "뾰족함은 바로 간다"


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


def test_고장_판정이_없다_판정과_갈라진다() -> None:
    """**표시 계층은 계산하지 않는다** (D-0281). 세 갈래를 여기서 고정한다."""
    from hathor.interfaces.cli.eval_onsets import verdict, warnings

    broken = BeatGain(
        measured=BeatLine(label="실측", ratios=(1.0, 1.1, 0.9, 1.0), decided=4),
        control=BeatLine(label="섞음", ratios=(3.0, 3.2, 2.8, 3.1), decided=4),
    )
    assert "고장" in verdict(broken)
    assert warnings(broken) and "음성 대조가 실측을 이겼다" in warnings(broken)[0]

    quiet = _gain(noiseless())
    assert verdict(quiet) == "담는다고 말할 수 없다"
    assert warnings(quiet) == [], "거짓 경보는 진짜 경보를 죽인다"
    assert verdict(_gain(beating())) == "포락선이 박을 담는다"


def test_폴더를_읽어_세_선을_낸다(tmp_path: Path) -> None:
    folder = tmp_path / "keys-000002.onsets"
    for index, (envelope, hop) in enumerate(beating(5)):
        write_envelope(folder, f"곡{index}.flac", envelope, hop_seconds=hop)
    measured, control, turned = load_lines(folder)
    assert len(measured.ratios) == len(control.ratios) == len(turned.ratios) == 5
    assert measured.mean_ratio > control.mean_ratio


# ------------------------------------ 배수 격차와 위상 (D-0154가 떨어뜨린 두 축 · D-0317)


def test_배수_격차를_버리지_않는다() -> None:
    """**`measure`가 줄곧 내고 있었고 D-0314가 버렸다** (D-0317).

    D-0154가 실물 20곡에서 격차 `< 0.10`이 12곡이고 중앙 0.02라고 적었다 — 그 수를
    1004곡에서 다시 낼 수 있으려면 선이 이 값을 들고 있어야 한다.
    """
    found = line("실측", beating())
    assert len(found.margins) == found.decided
    assert found.median_margin is not None
    assert found.ambiguous_rate is not None
    assert 0.0 <= found.ambiguous_rate <= 1.0


def test_박을_못_고르면_격차가_없다() -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
    flat = line("실측", [(np.zeros(FRAMES), HOP)])
    assert flat.decided == 0
    assert flat.margins == ()
    assert flat.median_margin is None
    assert flat.ambiguous_rate is None


def test_위상은_짝지어_판정한다() -> None:
    """**절대 분포로 판정하지 않는다** (D-0311과 같은 구조 · D-0317).

    봉우리를 성기게 고르는 것만으로 분포가 뾰족해질 수 있다.
    """
    from hathor.application.evaluate_onsets import phase_line, phase_mean, phase_spread

    songs = beating(10)
    gain = BeatGain(
        measured=phase_line("실측", songs),
        control=phase_line("섞음", songs, transform="shuffled"),
    )
    assert gain.aligned
    assert gain.carries_beat, "클릭 트랙의 위상은 한 칸에 몰린다"
    assert phase_spread(*songs[0]) is not None
    found = phase_mean(songs)
    assert found is not None
    assert sum(found) == pytest.approx(1.0)
    assert max(found) > 0.4, "정박만 있는 자료는 한 칸이 무겁다"


def test_박이_없으면_위상도_균등에_머문다() -> None:
    """**질 수 있는 축이다** (O-25 (2)). 균등 잡음에서 문턱을 못 넘는다."""
    from hathor.application.evaluate_onsets import phase_line

    songs = noiseless()
    gain = BeatGain(
        measured=phase_line("실측", songs),
        control=phase_line("섞음", songs, transform="shuffled"),
    )
    assert not gain.carries_beat


def test_위상을_안_재면_안_쟀다고_적는다() -> None:
    """**«박을 담는다»가 둘 다를 말하는 것으로 읽히면 안 된다** (GR-0.5 · D-0317)."""
    from hathor.interfaces.cli.eval_onsets import margin_lines, phase_notice

    said = "\n".join(phase_notice())
    assert "안 쟀다" in said
    assert "--phase" in said
    assert "D-0154" in said and "0.257" in said
    assert "절반" in said, "이 판정이 D-0143의 절반만 말한다고 적어야 한다"

    empty = margin_lines(BeatLine(label="실측", ratios=(0.0,), decided=0))
    assert "—" in empty[0], "격차를 못 재면 0을 찍지 않는다"


def test_위상_보고가_두_선과_판정을_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "keys-000003.onsets"
    for index, (envelope, hop) in enumerate(beating(6)):
        write_envelope(folder, f"곡{index}.flac", envelope, hop_seconds=hop)
    out = tmp_path / "산출"
    code = main(["eval", "onsets", "--out", str(out), "--envelopes", str(folder), "--phase"])
    assert code == 0
    printed = capsys.readouterr().out
    assert "박 안 위상" in printed
    assert "D-0154 실물 20곡" in printed, "떨어뜨린 수를 옆에 둬야 읽을 수 있다"
    assert "배수 격차" in printed
    assert "안 쟀다" not in printed

    record = json.loads(next((out / "eval").glob("*-onsets.eval.json")).read_text("utf-8"))
    assert record["phase"] is not None
    assert record["median_margin"] is not None


# ------------------------------ 집계 수준이 판정을 뒤집는다 (O-25 일곱째 줄 · D-0318)


def offset_clicks(*, seed: int, offset: int) -> np.ndarray:
    """위상 원점을 옮긴 클릭 트랙. **원점은 파일 시작이고 으뜸박이 아니다.**"""
    envelope = np.zeros(FRAMES)
    for start in range(offset, FRAMES, PERIOD):
        for step in range(6):
            if start + step < FRAMES:
                envelope[start + step] += float(np.exp(-step / 2.0))
    return envelope + np.random.default_rng(seed).random(FRAMES) * 0.2


def _deviation(profile: tuple[float, ...]) -> float:
    flat = 1.0 / len(profile)
    return sum(abs(value - flat) for value in profile) / 2.0


def test_곡_평균_위상은_원점이_다르면_균등해진다() -> None:
    """**D-0154의 결정적 수가 해석할 수 없는 수였다** (D-0318).

    곡마다 한 칸에 몰려 있어도 몰리는 칸이 다르면 **곡 평균은 평평해진다.** D-0154는
    그 평평함을 실패로 읽었고, 견준 상대는 D-0143의 **합성 한 곡** 분포였다 —
    **자를 확인한 집계 수준과 자를 쓴 집계 수준이 달랐다** (D-0306과 같은 부류).
    """
    from hathor.application.evaluate_onsets import phase_mean, phase_spread

    spread_songs = [
        (offset_clicks(seed=index, offset=index * 7 % PERIOD), HOP) for index in range(40)
    ]
    each = [phase_spread(envelope, hop) or 0.0 for envelope, hop in spread_songs]
    assert float(np.median(each)) > 0.5, "곡별로는 한 칸에 몰려 있다"

    averaged = phase_mean(spread_songs)
    assert averaged is not None
    assert _deviation(averaged) < float(np.median(each)) / 3.0, "곡 평균이 훨씬 평평하다"


def test_원점만_맞춰도_곡_평균이_선다() -> None:
    """**균등의 원인이 원점이라는 것을 이 줄이 고정한다** (O-25 여섯째 줄 · D-0318).

    없으면 위 시험은 «위상이 원래 없다»로도 설명된다. **자료를 한 비트도 안 바꾸고
    원점만 맞춘다** — 그것만으로 곡 평균이 서면 원인은 원점이다.
    """
    from hathor.application.evaluate_onsets import phase_mean

    scattered = phase_mean(
        [(offset_clicks(seed=index, offset=index * 7 % PERIOD), HOP) for index in range(40)]
    )
    aligned = phase_mean([(offset_clicks(seed=index, offset=0), HOP) for index in range(40)])
    assert scattered is not None
    assert aligned is not None
    assert _deviation(aligned) > _deviation(scattered) * 3.0, "원점이 같으면 곡 평균도 몰린다"


def test_배수_오류는_몰림을_안_망친다() -> None:
    """**D-0317이 위상 판정을 배수 격차에 걸었고 과했다** (D-0318).

    배수 오류는 봉우리를 두 칸에 쪼갤 뿐이다. 무너지는 것은 **배수가 아닌 오류**다.
    """
    from hathor.domain.services.onset import phase_profile

    song = offset_clicks(seed=3, offset=0)
    span = PERIOD * HOP
    truth = _deviation(phase_profile(song, span, HOP))
    assert truth > 0.5
    for factor in (2.0, 0.5):
        assert _deviation(phase_profile(song, span * factor, HOP)) > truth / 2.0
    assert _deviation(phase_profile(song, span * 1.5, HOP)) < truth / 2.0, "비배수는 무너진다"


def test_몰림은_봉우리_수_탓이_아니다() -> None:
    """**적게 고르면 우연히 몰린다**가 아니라는 것을 고정한다 (O-25 (2)).

    섞은 것이 실측보다 봉우리를 **더 많이** 고르는데도 편차가 열 배 이상 낮다.
    """
    from hathor.application.evaluate_onsets import phase_spread

    song = offset_clicks(seed=5, offset=0)
    real = phase_spread(song, HOP)
    mixed = phase_spread(shuffled(song, seed=5), HOP)
    assert real is not None
    assert mixed is not None
    assert real > mixed * 5.0
