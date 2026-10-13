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
from random import Random
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


QUARTILE_FLOOR = 4
"""사분위를 내는 데 드는 점의 수. **넷 미만이면 수를 안 낸다** (GR-0.5)."""


def spread(values: tuple[float, ...]) -> tuple[float, float, float, float]:
    """(1사분위, 중앙, 3사분위, 최대). **네 곡 미만이면 사분위가 없다.**

    **두 판정이 같은 자를 쓴다** (D-0043). 반쪽 나누기가 제 손으로 사분위를 내면
    한쪽이 바닥을 바꿀 때 다른 쪽이 조용히 어긋난다.
    """
    if len(values) < QUARTILE_FLOOR:
        raise LookupError(f"{len(values)}곡으로는 사분위를 못 낸다")
    cut = quantiles(sorted(values), n=4)
    return cut[0], median(values), cut[2], max(values)


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
        """(1사분위, 중앙, 3사분위, 최대)."""
        return spread(values)


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


@dataclass(frozen=True, slots=True)
class SplitVerdict:
    """**곡마다 고유한 리듬이 있나** — 반쪽 나누기 (O-77 · D-0406).

    같은 곡의 앞 절반과 뒤 절반이 서로 닮았는데 **다른 곡과는 다르면** 그것이 신호다.
    둘이 같으면 **노이즈를 리듬이라 부르는 것**이고, 그때 쪼갬은 관례로 둬야 한다
    (D-0402가 고른 자리).
    """

    same: tuple[float, ...]
    """같은 곡 앞↔뒤 거리. 곡마다 하나."""

    other: tuple[float, ...]
    """다른 곡과의 거리. **짝은 시드로 고른다** — 무작위면 판마다 수가 흔들린다.

    **돌리지 않고 맞댄 거리다.** 곡마다 위상 원점이 다르므로 이 수에는 *«리듬이
    다르다»*와 *«녹음이 다른 자리에서 시작했다»*가 섞여 있다 (D-0407)."""

    turned: tuple[float, ...]
    """다른 곡과의 거리 — **네 칸을 돌려 가장 가까운 자리에서** 잰다.

    생성이 참조곡에서 베끼는 것은 **모양이지 원점이 아니다** — 어차피 우리 격자
    머리에 맞춰 놓는다. 그래서 귀무도 돌려서 맞대야 하고, **판정은 이쪽이다.**"""

    turned_self: tuple[float, ...]
    """**제 앞 절반**과의 거리 — 돌려서. 참조곡 조건화가 낼 수 있는 **가장 좋은 수**다.

    `same`과 거의 같지만 `turned`·`turned_mean`과 **같은 셈법으로** 재야 셋을 나란히
    놓을 수 있다 (D-0408)."""

    turned_mean: tuple[float, ...]
    """**코퍼스 평균 모양**과의 거리 — 돌려서. **이것이 관례다** (D-0408).

    우리의 대안은 「다른 곡 하나」가 아니라 **고정된 쪼갬**이고, 고정 예측자 중 가장
    좋은 것이 평균이다. 참조곡이 이것을 못 이기면 **D-0402의 관례가 맞다.**

    평균은 **제 짝을 빼고** 낸다 — 자기가 섞인 평균과 견주면 그만큼 가까워진다."""

    read: int
    """박을 읽어 양쪽 분포를 다 낸 곡 수."""

    @property
    def signal(self) -> float | None:
        """다른 곡 중앙 빼기 같은 곡 중앙. **0에 가까우면 신호가 없다.**

        양수여야 신호다 — 같은 곡이 더 가깝다는 뜻이기 때문이다. 크기는 총변동거리의
        단위이고 **0~1 사이**다. 판정선은 사람이 정하지 않는다: 귀무(다른 곡)와
        견주는 것이 판정이며 **차가 0이면 끝이다** (D-0207과 같은 꼴).
        """
        if len(self.same) < 2:
            return None
        return median(self.other) - median(self.same)

    @property
    def turned_signal(self) -> float | None:
        """**돌려서 맞댄 신호.** 원점 차이를 뺀 나머지이고 **이것이 판정이다.**

        `signal`보다 작을 수밖에 없다 — 돌리기는 귀무를 **가깝게만** 만든다. 그래서
        이 수가 살아 있으면 **보수적으로** 살아 있는 것이다.
        """
        if len(self.same) < 2:
            return None
        return median(self.turned) - median(self.same)

    @property
    def gain(self) -> tuple[float, ...]:
        """곡마다 **관례 - 참조.** 양수면 그 곡에서 참조곡이 이겼다 (D-0409).

        **짝지은 수다.** 예측자 둘이 같은 곡을 맞히므로 *«중앙값의 차»*가 아니라
        *«차의 중앙값»*이 맞다 — 두 수는 다를 수 있고, 짝을 안 지으면 **어느 곡에서
        이겼는지**가 사라진다.
        """
        return tuple(
            convention - reference
            for convention, reference in zip(self.turned_mean, self.turned_self, strict=True)
        )

    @property
    def wins(self) -> int:
        """참조곡이 **이긴 곡 수.** 비긴 곡은 진 것으로 센다 (보수적).

        **승률은 해석에 여지가 없다** — 절반이면 동전 던지기이고 신호가 없다.
        """
        return sum(1 for one in self.gain if one > 0.0)

    @property
    def beats_convention(self) -> float | None:
        """**관례 - 참조곡.** 양수여야 참조곡에서 뽑을 값이 있다 (D-0408).

        `turned_signal`은 *«곡마다 다른가»*를 묻고 이 수는 *«그 다름이 고정 쪼갬보다
        나은가»*를 묻는다. **결정은 이쪽이다** — 우리가 참조곡을 안 쓰면 무작위 한
        곡이 아니라 **관례**를 쓰기 때문이다.
        """
        if len(self.same) < 2:
            return None
        return median(self.turned_mean) - median(self.turned_self)


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """두 분포 사이 **총변동거리** — L1의 절반이라 0~1이다.

    0이면 두 분포가 같고 1이면 겹치는 곳이 없다. **백분율로 읽히는 양**이라 거울이
    천분율 정수로 들 수 있다 (D-0366 — 정본은 정수만 든다).
    """
    return sum(abs(one - two) for one, two in zip(left, right, strict=True)) / 2.0


def _turned(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """네 칸을 다 돌려 본 **가장 가까운** 거리 (D-0407).

    **고를 값이 없다.** 칸 수는 `PHASE_BINS`이고 전부 본다 — 어느 회전을 쓸지
    정하는 문턱이 없다는 뜻이다 (D-0058의 손잡이를 안 만든다).
    """
    return min(_distance(left, right[turn:] + right[:turn]) for turn in range(len(right)))


def _canonical(profile: tuple[float, ...]) -> tuple[float, ...]:
    """봉우리가 0번 칸에 오게 돌린다. **평균을 내려면 틀을 하나로 모아야 한다.**

    돌리지 않고 평균 내면 **언제나 균등이 된다** — 곡마다 원점이 다르기 때문이고
    D-0206이 그렇게 한 번 속았다. 봉우리가 둘이면 앞의 것을 쓴다(결정적).

    쌍을 견줄 때는 이 틀을 **안 쓴다** (D-0407의 기각된 후보 2) — 거기서는 돌릴
    자리를 전부 보면 되므로 고를 필요가 없다. **평균에는 고를 수밖에 없다.**
    """
    turn = profile.index(max(profile))
    return profile[turn:] + profile[:turn]


def _without(total: tuple[float, ...], one: tuple[float, ...], count: int) -> tuple[float, ...]:
    """합에서 제 몫을 뺀 평균. **자기가 섞인 평균과 견주면 그만큼 가까워진다.**"""
    return tuple((whole - mine) / (count - 1) for whole, mine in zip(total, one, strict=True))


def peaked(envelopes: Sequence[tuple[np.ndarray, float]]) -> list[tuple[np.ndarray, float]]:
    """**봉우리가 있는 곡만.** 고른 곡은 베낄 리듬이 없다 (`FLAT` · D-0401의 45.9%).

    고른 곡끼리는 같은 곡이든 다른 곡이든 거리가 0에 가깝다 — **섞여 들면 양쪽을
    똑같이 끌어내려 신호를 묽게 만든다.** 판정은 쓸 수 있는 곡에서 낸다.
    """
    found: list[tuple[np.ndarray, float]] = []
    for envelope, hop_seconds in envelopes:
        beat = beat_period(envelope, hop_seconds)
        if beat is None:
            continue
        if max(phase_profile(envelope, beat.period_seconds, hop_seconds)) >= FLAT:
            found.append((envelope, hop_seconds))
    return found


def _halves(
    envelope: np.ndarray, hop_seconds: float
) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """앞 절반 · 뒤 절반의 박 안 분포. **박은 곡 전체에서 한 번 읽는다.**

    절반마다 따로 읽으면 **다른 템포로 잰 두 분포**가 되고, 그 차이는 리듬이 아니라
    박 추정의 차이다 (D-0143이 주기 오차 0.8%로 위상이 뭉개지는 것을 실측했다).

    ### 여기 결함이 심겨 있었다 (D-0406)

    `phase_profile`은 **받은 배열의 0번 칸을 박의 머리로 본다** (`index % span`).
    그래서 한가운데서 그냥 자르면 뒤 절반의 위상 원점이 `중간 % 주기`만큼 **통째로
    돌아간다** — 리듬이 완벽히 같은 곡도 남남이 된다.

    합성으로 재 보니 40.0초(반이 박의 배수)에서 같은 곡 거리 **0.003**, 40.25초
    (나머지 12칸)에서 **0.992**였다. **길이 하나로 신호가 사라진다.** 그래서 자르는
    자리를 **박의 배수에서 가장 가까운 칸**으로 옮긴다.
    """
    found = beat_period(envelope, hop_seconds)
    if found is None:
        return None
    span = found.period_seconds / hop_seconds
    cut = round(round(envelope.size / 2 / span) * span)
    if cut < 1 or cut >= envelope.size:
        return None
    return (
        phase_profile(envelope[:cut], found.period_seconds, hop_seconds),
        phase_profile(envelope[cut:], found.period_seconds, hop_seconds),
    )


def split_half(envelopes: Sequence[tuple[np.ndarray, float]], *, seed: int = 0) -> SplitVerdict:
    """곡마다 반쪽을 나눠 **같은 곡 ↔ 다른 곡**을 견준다 (O-77 · 닫힘 D-0410).

    **귀무는 다른 곡이다.** D-0207이 *«순서를 섞은 귀무와 소수점 셋째 자리까지 같다»*로
    마디 안 위치를 기각한 그 꼴이며, 여기서는 박 안을 같은 방식으로 묻는다.

    짝은 `seed`로 고른다 — 무작위면 **같은 코퍼스에서 판마다 다른 수**가 나온다
    (GR-6.5 · D-0082).

    **귀무를 셋 낸다.** `other`는 돌리지 않고 맞댄 다른 곡이고(첫 실측 +0.177 —
    **그 안에 「녹음이 다른 자리에서 시작했다」가 섞여 있다** · D-0407), `turned`는
    돌린 다른 곡이며(+0.058), `turned_mean`은 **코퍼스 평균 모양**이다.

    **결정은 `beats_convention`이다** (D-0408). 참조곡을 안 쓰면 무작위 한 곡이 아니라
    **관례**를 쓰므로, 견줄 상대는 고정 예측자 중 가장 좋은 것이어야 한다.
    """
    halves = [one for envelope, hop in envelopes if (one := _halves(envelope, hop)) is not None]
    if len(halves) < 2:
        return SplitVerdict(
            same=(), other=(), turned=(), turned_self=(), turned_mean=(), read=len(halves)
        )
    picker = Random(seed)
    # **뒤 절반을 틀 하나로 모아 더해 둔다** — 곡마다 빼서 제 짝 없는 평균을 만든다.
    aligned = [_canonical(tail) for _head, tail in halves]
    total = tuple(sum(one[bin_] for one in aligned) for bin_ in range(PHASE_BINS))
    same: list[float] = []
    other: list[float] = []
    turned: list[float] = []
    turned_self: list[float] = []
    turned_mean: list[float] = []
    for index, (head, tail) in enumerate(halves):
        same.append(_distance(head, tail))
        turned_self.append(_turned(head, tail))
        turned_mean.append(_turned(head, _without(total, aligned[index], len(halves))))
        # **제 짝을 안 고른다.** 자기 자신과 견주면 귀무가 신호를 베낀다.
        choices = [one for one in range(len(halves)) if one != index]
        partner = halves[picker.choice(choices)][1]
        other.append(_distance(head, partner))
        turned.append(_turned(head, partner))
    return SplitVerdict(
        same=tuple(same),
        other=tuple(other),
        turned=tuple(turned),
        turned_self=tuple(turned_self),
        turned_mean=tuple(turned_mean),
        read=len(halves),
    )
