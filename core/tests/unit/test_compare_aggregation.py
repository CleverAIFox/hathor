"""평균 추출과 중앙값 추출을 맞대는 자 (D-0064 · D-0337).

D-0064가 판정 지표를 **착수 전에** 정해 뒀다 — *"곡 내 홀드아웃의 달성 가능 폭
(`uniform` → `oracle`)이 0.0187에서 오르는가."* 추출은 이미 있었고 **견주는 자리가
없었다.**

**눈으로 빼면 안 된다.** `eval harmony-prior --replay`는 폭을 한 수로 찍고, 두 번 돌려
빼면 오차가 없다 — D-0327이 그 부류로 오경보율 50%짜리 판정을 돌렸다.
"""

from __future__ import annotations

import numpy as np
import pytest

from hathor.application.compare_aggregation import (
    ACHIEVABLE_FLOOR,
    compare,
    song_widths,
    width_draws,
)
from hathor.domain.services.harmony_prior import HalfChroma, PriorCondition

DEGREES = 12
CONDITION = PriorCondition()


def _songs(count: int, *, sharpness: float, seed: int) -> list[HalfChroma]:
    """`sharpness`가 클수록 뒷반쪽이 뾰족하다 — **폭이 넓어진다.**"""
    rng = np.random.default_rng(seed)
    made: list[HalfChroma] = []
    for index in range(count):
        shape = rng.dirichlet(np.full(DEGREES, 1.0 / max(sharpness, 1e-6)))
        flat = np.full(DEGREES, 1.0 / DEGREES)
        made.append(
            HalfChroma(
                source_key=f"곡{index:03d}",
                tonic_pitch_class=0,
                margin=1.0,
                head=tuple(float(v) for v in flat),
                tail=tuple(float(v) for v in shape),
            )
        )
    return made


def test_뾰족하면_폭이_넓다() -> None:
    """**자의 방향을 먼저 고정한다.** 폭은 클수록 좋다 — 곡 고유 정보가 들어갈 자리다."""
    flat = song_widths(_songs(60, sharpness=0.2, seed=1), CONDITION)
    sharp = song_widths(_songs(60, sharpness=5.0, seed=1), CONDITION)

    assert np.median(list(sharp.values())) > np.median(list(flat.values()))


def test_배음_손잡이가_실제로_결과를_바꾼다() -> None:
    """**손잡이 셋이 동시에 안 걸려 있었다** (D-0339).

    D-0338이 식을 베끼면서 `_stack`을 안 썼고 `subtract_harmonics`가 빠졌다.
    실물에서 `--harmonic`을 **0에서 1.0까지** 돌렸는데 소수점 넷째 자리까지 같았다.

    D-0064가 열 번째로 같은 형태를 겪고 적은 규칙이 이것이다 — *"새 인자를 넣으면
    그 인자가 실제로 결과를 바꾸는지 단위 검사로 고정한다."* **읽고도 안 지켰다.**
    """
    songs = _songs(40, sharpness=2.0, seed=3)
    off = song_widths(songs, PriorCondition(harmonic=0.0))
    on = song_widths(songs, PriorCondition(harmonic=0.8))

    assert off.keys() == on.keys()
    assert any(off[name] != on[name] for name in off), "배음이 아무 일도 안 한다"


def test_애매_제외가_곡_수를_줄인다() -> None:
    """`confident_only`도 같이 죽어 있었다 (D-0339).

    `HalfChroma.is_confident`가 `margin >= 0.0`을 박아 두고 독스트링은 *"기준값은
    조건 객체가 들고 있다"*고 적었다. **격차는 음수가 안 되므로 늘 참이었다.**
    쓰는 곳이 내 코드 한 줄뿐이라 **그 속성을 지웠다.**
    """
    songs = list(_songs(10, sharpness=2.0, seed=3))
    songs[0] = HalfChroma(
        source_key=songs[0].source_key,
        tonic_pitch_class=0,
        margin=0.0,
        head=songs[0].head,
        tail=songs[0].tail,
    )
    strict = PriorCondition(confident_only=True, margin_floor=0.5)

    assert len(song_widths(songs, CONDITION)) == 10
    assert songs[0].source_key not in song_widths(songs, strict)
    assert len(song_widths(songs, strict)) == 9


def test_한쪽에만_있는_곡은_뺀다() -> None:
    """**짝이 아니면 짝지은 차이가 아니다** (D-0311)."""
    median = _songs(10, sharpness=2.0, seed=5)
    mean = _songs(7, sharpness=2.0, seed=5)

    found = compare(median, mean, CONDITION)
    assert len(found.songs) == 7
    assert len(found.median_widths) == len(found.mean_widths) == 7


def test_같은_자료면_차이가_0이다() -> None:
    """**음성 대조다.** 같은 것을 두 번 넣으면 폭 차이가 정확히 0이어야 한다."""
    songs = _songs(40, sharpness=2.0, seed=7)
    found = compare(songs, songs, CONDITION)

    assert found.paired_gap.gain == pytest.approx(0.0, abs=1e-12)
    assert found.widens is False


def test_넓어지면_잡는다() -> None:
    """중앙값 쪽이 더 뾰족하면 **폭이 넓어지고 통과한다.**"""
    found = compare(
        _songs(80, sharpness=5.0, seed=11), _songs(80, sharpness=1.0, seed=11), CONDITION
    )
    assert found.paired_gap.gain > 0.0
    assert found.widens is True


def test_좁아지면_진다() -> None:
    """**질 수 있는 자여야 한다** (O-25 (2)).

    중앙값이 창별 잡음을 깎으면서 **신호도 같이 깎으면** 폭이 준다. D-0064의 (b)는
    그때 기각된다 — 자가 그것을 말할 수 있어야 한다.
    """
    found = compare(
        _songs(80, sharpness=1.0, seed=11), _songs(80, sharpness=5.0, seed=11), CONDITION
    )
    assert found.paired_gap.gain < 0.0
    assert found.widens is False


def _flatish(count: int, *, blend: float, seed: int) -> list[HalfChroma]:
    """폭이 **실물 급(0.01~0.02)**인 코퍼스.

    위의 `_songs`는 폭이 0.08~1.08로 나와 **절대 기준 0.031을 늘 넘는다** — 그 코퍼스로는
    기준이 걸리는지 아닌지를 알 수 없다. 자를 확인한 조건이 자를 쓸 조건과 같아야 한다
    (O-25 일곱째 줄 · D-0306).
    """
    rng = np.random.default_rng(seed)
    flat = np.full(DEGREES, 1.0 / DEGREES)
    made: list[HalfChroma] = []
    for index in range(count):
        shape = (1.0 - blend) * flat + blend * rng.dirichlet(np.full(DEGREES, 0.5))
        made.append(
            HalfChroma(
                source_key=f"곡{index:03d}",
                tonic_pitch_class=0,
                margin=1.0,
                head=tuple(float(v) for v in flat),
                tail=tuple(float(v) for v in shape),
            )
        )
    return made


def test_절대_기준은_판정에_안_걸린다() -> None:
    """**걸었다가 뺐다** (D-0338). 이 검사가 그 결정을 고정한다.

    처음에 D-0064의 0.031을 `widens`의 조건으로 넣었다. **1004곡 평균의 폭이 이미
    0.0471이라 그 문턱은 아무것도 안 막고**, 더 나쁘게는 **자료가 적을 때만 막는**
    거꾸로 된 자가 된다 — 실물 급(0.01~0.02) 코퍼스에서만 걸린다.

    그래서 판정은 짝지은 차이 하나이고 절대 기준은 **찍기만 한다.**
    """
    found = compare(_flatish(120, blend=0.15, seed=3), _flatish(120, blend=0.08, seed=3), CONDITION)

    assert found.median_width is not None
    assert found.median_width < ACHIEVABLE_FLOOR, "이 코퍼스는 기준 미달이어야 한다"
    assert found.clears_floor is False, "참조선은 그대로 찍힌다"
    assert found.paired_gap.t > 10.0
    assert found.widens is True, "**절대 기준이 판정을 막으면 안 된다**"


def test_문턱을_이_판에서_고르지_않았다() -> None:
    """**D-0058이다.** 0.031은 D-0064가 K-K 장조 폭의 절반으로 등록한 값이다."""
    assert pytest.approx(0.0616 / 2, abs=0.0009) == ACHIEVABLE_FLOOR


# ------------------------------------------------------- 작은 표본에서 폭이 흔들리나


def test_뽑기_분포가_전수를_둘러싼다() -> None:
    """**자의 방향 먼저** (O-25). 전수 폭은 뽑기 분포 가운데 있어야 한다."""
    songs = _flatish(400, blend=0.15, seed=9)
    whole = float(np.median(list(song_widths(songs, CONDITION).values())))
    found = width_draws(songs, CONDITION, size=80, draws=120, target=whole)

    assert found is not None
    assert found.inside is True, "전수 값이 자기 뽑기 분포 밖이면 자가 깨진 것이다"
    assert 0.2 < found.quantile < 0.8


def test_분포_밖이면_요동이_아니라고_말한다() -> None:
    """**질 수 있는 자여야 한다** (O-25 (2)).

    D-0063의 0.0187이 1004곡의 200곡 뽑기 분포 밖이면 **표본 요동으로 설명이 안 된다** —
    그 200곡이 코퍼스를 안 대표했거나 그 사이 코드가 바뀐 것이다.
    """
    songs = _flatish(400, blend=0.15, seed=9)
    found = width_draws(songs, CONDITION, size=80, draws=120, target=0.0)

    assert found is not None
    assert found.quantile == 0.0
    assert found.inside is False
    assert "요동으로 설명이 안 된다" in found.reading()


def test_곡이_모자라면_없다고_말한다() -> None:
    """**없는 것을 0이라 하지 않는다** (GR-0.5). 뽑을 곡이 없으면 분포도 없다."""
    assert width_draws(_flatish(20, blend=0.15, seed=9), CONDITION, size=80, draws=5) is None


def test_곡이_없으면_없다고_말한다() -> None:
    """**없는 것을 0이라 하지 않는다** (GR-0.5). 폭 0은 「정보가 없다」로 읽힌다."""
    empty = compare([], [], CONDITION)

    assert empty.median_width is None
    assert empty.mean_width is None
    assert empty.widens is False
