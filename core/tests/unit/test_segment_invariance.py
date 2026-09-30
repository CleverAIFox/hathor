"""구간 길이 불변을 **두 자로** 확인한다 (D-0103 · D-0316).

**버린 쪽만 보면 비교가 아니다** (O-25 (1)). 늘 0을 내는 자도 0을 내므로, 대각선을
포함한 자가 **같은 자료에서 무너지는 것**을 나란히 봐야 «0이 나왔다»가 뜻을 갖는다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hathor.application.evaluate_segment_invariance import (
    INVARIANCE_CEILING,
    STRETCHES,
    StretchLine,
    distance,
    line,
    self_share,
    shares,
    stretched,
    sweep,
)
from hathor.domain.services.transition_prior import transition_prior
from hathor.interfaces.cli.main import main

Capture = pytest.CaptureFixture[str]

DEGREES = 12


def walking(*, windows: int, seed: int, noise: float = 0.3) -> np.ndarray:
    """창마다 도수가 무작위로 바뀌는 곡. **자기 전이가 거의 없다.**"""
    generator = np.random.default_rng(seed)
    picked = generator.integers(0, DEGREES, windows)
    frame = np.zeros((windows, DEGREES))
    frame[np.arange(windows), picked] = 1.0
    return frame + generator.random((windows, DEGREES)) * noise


def corpus(count: int = 12) -> list[np.ndarray]:
    return [walking(windows=30 + index, seed=index) for index in range(count)]


def test_늘여도_대각선을_버린_사전은_안_움직인다() -> None:
    """**D-0103의 주장이다.** 진행은 그대로이고 끄는 길이만 배가 된다."""
    for one in sweep(corpus()):
        assert one.dropped_max <= INVARIANCE_CEILING, f"x{one.factor}에서 흔들렸다"
        assert one.invariant


def test_대각선을_포함하면_무너진다() -> None:
    """**이 줄이 없으면 위 시험은 늘 통과하는 하네스다** (D-0071 · O-25 (1))."""
    lines = sweep(corpus())
    assert lines[0].kept_max == pytest.approx(0.0), "원본끼리는 거리가 0이다"
    assert all(one.kept_mean > 0.3 for one in lines[1:])
    assert lines[-1].kept_mean > lines[1].kept_mean, "많이 늘일수록 더 무너진다"


def test_늘임은_진행을_안_바꾼다() -> None:
    """**되풀이일 뿐이다.** 비대각 셈이 한 개도 안 달라지는 것이 불변의 정의다."""
    song = walking(windows=40, seed=5)
    longer = stretched(song, 3)
    assert longer.shape == (120, DEGREES)
    assert np.array_equal(longer[0], song[0])
    assert np.array_equal(longer[1], song[0])
    assert np.array_equal(longer[3], song[1])
    assert np.array_equal(transition_prior(song), transition_prior(longer))


def test_자기_전이_몫은_정본을_부른다() -> None:
    """**베끼지 않는다** (D-0123 · D-0317).

    D-0316이 이 식을 여기 다시 썼고 **같은 저장소에 이미 있었다.** 두 벌이 되면 한쪽을
    고쳤을 때 갈린다 — 그리고 **정본에 붙은 한계 경고가 사본에는 안 붙는다.**
    """
    from hathor.domain.services import chord_rhythm

    song = walking(windows=40, seed=13)
    assert self_share(song) == chord_rhythm.self_transition_rate(song)


def test_정본은_창_하나에서_0을_내고_여기서는_None이다() -> None:
    """**둘 다 옳고 자리가 다르다** (GR-0.5 · D-0317).

    정본은 판정에 안 쓰는 진단값이라 `0.0`으로 충분하지만, **표에 찍으면 «자기 전이가
    없다»로 읽힌다.** 그래서 부르기 전에 걸러낸다.
    """
    from hathor.domain.services import chord_rhythm

    single = np.ones((1, DEGREES))
    assert chord_rhythm.self_transition_rate(single) == 0.0
    assert self_share(single) is None


def test_자기_전이_몫이_버린_것의_크기다() -> None:
    """**D-0103이 버린 것을 처음 잰다.** 끄는 곡이 높고 매 창 바뀌는 곡이 0이다."""
    moving = np.zeros((60, DEGREES))
    moving[np.arange(60), np.arange(60) % DEGREES] = 1.0
    assert self_share(moving) == 0.0, "매 창 바뀌는 곡은 0이다"
    # 네 배로 끌면 되풀이 블록 안 세 쌍이 자기 전이다 — 180 / 239.
    assert self_share(stretched(moving, 4)) == pytest.approx(180.0 / 239.0, abs=1e-9)
    assert len(shares(corpus())) == 12


def test_전이가_없으면_몫이_없다() -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5). 창 하나짜리는 전이가 없다."""
    assert self_share(np.ones((1, DEGREES))) is None
    assert shares([np.ones((1, DEGREES))]) == ()


def test_창이_둘_미만인_곡은_선에서_빠진다() -> None:
    one = line([np.ones((1, DEGREES)), walking(windows=20, seed=3)], 2)
    assert one.songs == 1


def test_빈_선은_0을_내되_불변이라_말한다() -> None:
    """**곡이 없으면 흔들릴 것도 없다.** 표에는 곡 수가 0으로 찍힌다."""
    empty = StretchLine(factor=2, dropped=(), kept=())
    assert empty.songs == 0
    assert empty.dropped_max == 0.0
    assert empty.kept_mean == 0.0
    assert empty.kept_max == 0.0
    assert empty.invariant


def test_배수는_1부터다() -> None:
    assert STRETCHES[0] == 1, "원본이 표에 없으면 비교가 아니다"
    with pytest.raises(ValueError, match="배수"):
        stretched(walking(windows=8, seed=1), 0)


def test_거리는_전변동이다() -> None:
    left = np.zeros((DEGREES, DEGREES))
    right = np.zeros((DEGREES, DEGREES))
    left[0, 1] = 1.0
    right[2, 3] = 1.0
    assert distance(left, right) == pytest.approx(1.0)
    assert distance(left, left) == pytest.approx(0.0)


# ------------------------------------------- CLI 배선 (D-0316)
#
# **기구는 `test_harmony_output_cli`에서 가져온다.** 같은 명령의 같은 자료이며, 여기
# 한 벌 더 두면 둘이 갈린다 (D-0262가 문서에서 겪은 것과 같은 자리다).


def _run(tmp_path: Path, extra: list[str]) -> int:
    from tests.unit.test_harmony_output_cli import write_keys, write_series

    path = write_keys(tmp_path / "keys.jsonl", count=12)
    names = [f"아티스트{index % 7}-곡{index:03d}.flac" for index in range(12)]
    series = tmp_path / "keys-20260823T000000Z.series"
    write_series(series, names, hold_windows=3)
    where = ["--priors", str(path), "--series", str(series)]
    return main(["eval", "harmony-order", *where, "--seeds", "20", "--bars", "32", *extra])


def test_늘임_훑기가_두_자를_나란히_낸다(tmp_path: Path, capsys: Capture) -> None:
    """**자기 전이 훑기와 다른 물음이다** (D-0316).

    저쪽은 D-0114가 이미 실물로 닫았고, 이쪽이 D-0103이 합성으로만 답한 자리다.
    """
    assert _run(tmp_path, ["--stretch-sweep", "1,2,4"]) == 0
    out = capsys.readouterr().out
    assert "구간 길이 불변" in out
    assert "대각선버림" in out and "대각선포함" in out, "한 자만 내면 비교가 아니다"
    assert "자기 전이 몫" in out
    assert "구간 길이가 사전을 안 흔든다" in out


def test_늘임을_안_켜면_표가_안_난다(tmp_path: Path, capsys: Capture) -> None:
    """**기본 경로가 안 바뀐다.** D-0109가 검사로 고정한 규율과 같은 자리다."""
    assert _run(tmp_path, []) == 0
    assert "구간 길이 불변" not in capsys.readouterr().out


def test_시계열이_비면_표_대신_그렇게_적는다(tmp_path: Path, capsys: Capture) -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5)."""
    from hathor.interfaces.cli.eval_order import _report_stretch_sweep

    empty = tmp_path / "빈시계열"
    empty.mkdir()
    _report_stretch_sweep(empty, "other", (1, 2))
    out = capsys.readouterr().out
    assert "시계열이 없다" in out
    assert "판정" not in out, "잴 것이 없으면 판정을 안 낸다"
