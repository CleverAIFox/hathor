"""참조곡에서 템포를 뽑는다 — O-46의 남은 절반 (D-0392).

### 부품은 다 있었고 배선이 없었다

`beat_period()`가 박 주기를 내고 `tempo_bpm()`이 BPM으로 바꾸며 **온셋 포락선 산출물**
(`keys-*.onsets`)은 1004곡에 있다. 그런데 `render()`는 **기본값 126 하나**를 모든 곡에
썼고, 제 독스트링에 *"온셋 자료가 없어 리듬을 참조곡에서 못 뽑는다"*라고 적고 있었다 —
**그 문장이 낡았다.**

**읽는 것은 믹스다.** `ExtractOnsets`가 *«온셋은 타악이 바로 그 신호이므로 분리기를
안 태운다»*라고 적고 그대로 믹스에서 뽑는다. 묶음에는 스템별 포락선도 있으나 **읽는
자리가 없고, 그쪽이 박을 더 잘 주는지 안 쟀다** (O-76 · D-0395).

D-0392가 여기에 *«`onset/drums`에서 뽑는다»*라고 적었고 (check_bundle_keys: ok 틀린
말을 인용한다) 그것이 **다섯 자리로 번졌다** — 말이 틀린 것보다 나쁜 것은 그 말이
다음 판의 근거가 되는 것이다.

D-0206이 (3) *«곡마다 참조곡에서 뽑는다»*를 **«옳지만 O-46 본체»**라며 미뤘다. 여기다.

### 왜 중앙값인가

템포 추정의 실패는 대부분 **배수 오류**다. 바깥 실측(Schreiber·Urbano·Müller 2020)이
±4%에서 **58.9 ~ 64.8%**인데 배수를 봐주면 **86.4 ~ 94.0%**로 뛴다 — 30%p가 전부
«60이냐 120이냐»다. 한 곡이 절반으로 읽히면 평균은 끌려가고 **중앙값은 안 끌려간다.**
그쪽 관행도 같다: 같은 논문이 microtiming과 이상치를 줄이려 **median inter-beat
interval**을 쓴다.

### 문턱을 더하지 않는다

첫 설계는 `beat_strength`로 «박이 약한 곡»을 거르려 했다. **철회했다** — 그것은 새
문턱이고, 하나의 값을 코퍼스 전체에 실험으로 고르는 것이 D-0058 ~ D-0061이 네 세션
태운 자리다. `beat_period()`가 `None`을 내면 **못 읽은 것**이고 그게 전부다.
D-0206도 그렇게 쟀다 — *«1004곡 중 못 찾은 곡이 하나다»*.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

from hathor.domain.services.onset import beat_period, folded_tempo, tempo_bpm

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy as np


@dataclass(frozen=True, slots=True)
class TempoVerdict:
    """참조곡에서 읽은 템포. **못 읽은 것도 수로 든다** (GR-0.5)."""

    bpm: int | None
    """접고 반올림한 중앙값. **하나도 못 읽으면 `None`** — 0이 아니다."""

    read: int
    """박을 읽은 참조곡 수."""

    asked: int
    """물어본 참조곡 수. `read`와 다르면 그 차이가 **못 읽은 곡**이다.

    **포락선 묶음의 길이가 아니라 「물어본 수」다** (D-0396). 부르는 쪽이 저장분에
    없는 곡을 먼저 걸러 내므로, 그 수를 따로 받지 않으면 **언제나 `read`와 같아지고
    「2/2」가 「셋을 물어 둘을 읽었다」를 덮는다** — 안 센 것을 0이라 말하는 꼴이다
    (GR-0.5). 시험을 쓰다가 드러났다."""

    raw_median: float | None
    """**접기 전** 중앙값. 접는 선(`OCTAVE_FLOOR`)이 틀렸는지 나중에 보려면 이것이 든다."""

    @property
    def source(self) -> str:
        """산출물에 적을 한 줄. **어디서 온 템포인지 사람이 읽는다** (D-0269)."""
        if self.bpm is None:
            return f"기본값 — 참조 {self.asked}곡에서 박을 못 읽었다"
        return f"참조 {self.read}/{self.asked}곡 중앙"


def from_envelopes(
    envelopes: Sequence[tuple[np.ndarray, float]], *, asked: int | None = None
) -> TempoVerdict:
    """(온셋 포락선, 홉 초) 묶음에서 템포 하나를 뽑는다.

    **곡마다 접고 나서 중앙값을 낸다.** 거꾸로 하면 절반으로 읽힌 곡이 중앙값을 끌어
    내린 뒤에 접혀 엉뚱한 값이 된다 — D-0206의 원값 중앙 67이 그 상태였다.

    `asked`를 주면 **물어본 수**가 그것이다 (D-0396). 안 주면 받은 묶음의 수이고,
    그때는 저장분에서 빠진 곡이 안 보인다.
    """
    wanted = len(envelopes) if asked is None else asked
    folded: list[float] = []
    raw: list[float] = []
    for envelope, hop_seconds in envelopes:
        beat = beat_period(envelope, hop_seconds)
        if beat is None:
            continue
        found = tempo_bpm(beat.period_seconds)
        raw.append(found)
        folded.append(folded_tempo(found))
    if not folded:
        return TempoVerdict(bpm=None, read=0, asked=wanted, raw_median=None)
    return TempoVerdict(
        bpm=round(median(folded)),
        read=len(folded),
        asked=wanted,
        raw_median=round(median(raw), 2),
    )
