"""코퍼스가 **박 안 어디에 발음하나** — O-46의 비교선 (D-0399).

### 이 수가 O-46의 판정선이었다 (닫힘 D-0404)

D-0206이 *«화음 발음 집중도 — 균등 25.0% · 코퍼스 중앙 28.2% · 사분위 27.1~29.9 ·
최대 53.9% · 우리 출력 100%»*라고 적었다. **사람 곡은 균등에서 3점밖에 안 벗어난다**는
것이 그 비교선의 내용이고, 반주가 마디 머리에만 떨어지는 우리 출력이 100%였다.

그 수는 **결정 기록에만 있었다.** 126이 그랬던 것처럼 (D-0397) 아무도 다시 안 세고,
O-46 본체의 결과를 그 수와 견주므로 **판정선이 낡으면 결과도 못 믿는다** (닫힘 D-0404).

### 기록의 말이 두 가지로 읽힌다

D-0206은 *«마디 4등분»*이라 적었는데 그 수를 낸 `probe_onsets`는 **박**을 4등분한다
(`phase_profile(envelope, beat.period_seconds, hop)`). 우리 출력은 마디 머리에만
치므로 **어느 쪽으로 읽어도 100%**였고, 그래서 **그때는 갈릴 일이 없었다.**

이제는 갈린다 — 마디 안의 발음 위치를 고를 때 쓰는 분포이기 때문이다. **둘 다 센다.**

### 고른 값이 없다

`PHASE_BINS = 4`는 4/4박자라는 음악 사실이고, 마디는 박 넷이다. `phase_profile`은
*«박을 알면 나눗셈»*이며 문턱이 없다 (D-0206). **회전 불변인 양만 평균한다** — 곡마다
위상 원점이 다르므로 칸별 평균은 언제나 균등이 된다 (D-0206이 그렇게 한 번 속았다).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median, quantiles
from typing import TYPE_CHECKING

from hathor.domain.services.onset import PHASE_BINS, beat_period, phase_profile

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy as np

BEATS_PER_BAR = 4
"""마디 하나의 박 수. **4/4박자라는 음악 사실이다** (D-0206 · `bins=4`와 같은 근거)."""

FLAT = 1.5 / PHASE_BINS
"""**고르다**고 부르는 선. 균등이 `1/4`이고 그 1.5배 아래면 봉우리가 없는 것이다.

`probe_onsets`가 D-0160부터 이 선으로 「고른 곡」을 세 왔다 — **새 값이 아니라 옮겨 온
값이고**, 옮긴 것을 여기 적는다 (GR-0.7)."""


@dataclass(frozen=True, slots=True)
class PhaseVerdict:
    """코퍼스의 발음 집중도. **못 읽은 곡도 수로 든다** (GR-0.5)."""

    read: int
    """박을 읽어 분포를 낸 곡 수."""

    asked: int
    """물어본 곡 수. `read`와 다르면 그 차이가 **박을 못 읽은 곡**이다."""

    beat_top: tuple[float, ...]
    """곡마다 **박 4등분에서 가장 센 칸의 몫.** 회전 불변이라 모아도 뜻이 있다."""

    bar_top: tuple[float, ...]
    """곡마다 **마디 4등분에서 가장 센 칸의 몫.** 주기를 박 넷으로 본 것이다."""

    flat: int
    """봉우리가 없는 곡 수 (`FLAT` 아래). **반주 리듬을 못 뽑는 곡이다.**"""

    def spread(self, values: tuple[float, ...]) -> tuple[float, float, float, float]:
        """(1사분위, 중앙, 3사분위, 최대). **네 곡 미만이면 사분위가 없다.**"""
        if len(values) < 4:
            raise LookupError(f"{len(values)}곡으로는 사분위를 못 낸다")
        cut = quantiles(sorted(values), n=4)
        return cut[0], median(values), cut[2], max(values)


def phase_spread(envelopes: Sequence[tuple[np.ndarray, float]]) -> PhaseVerdict:
    """(온셋 포락선, 홉 초) 묶음에서 발음 집중도를 모은다.

    **박을 못 읽은 곡은 건너뛴다** — `beat_period`가 `None`을 내면 그게 전부다
    (D-0392의 규율: 문턱을 더하지 않는다).
    """
    beat: list[float] = []
    bar: list[float] = []
    for envelope, hop_seconds in envelopes:
        found = beat_period(envelope, hop_seconds)
        if found is None:
            continue
        beat.append(max(phase_profile(envelope, found.period_seconds, hop_seconds)))
        bar.append(max(phase_profile(envelope, found.period_seconds * BEATS_PER_BAR, hop_seconds)))
    return PhaseVerdict(
        read=len(beat),
        asked=len(envelopes),
        beat_top=tuple(beat),
        bar_top=tuple(bar),
        flat=sum(1 for value in beat if value < FLAT),
    )
