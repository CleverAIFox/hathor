"""뽑아 둔 온셋 포락선이 **실물에서 박을 담는가** (D-0314).

**판정하는 도구가 없었다.** `ingest onsets`는 뽑기만 하고, 온셋·박 판단 넷(D-0143 ·
D-0144 · D-0169 · D-0170)이 **합성 자료만으로 서 있었다.** D-0313이 그 사실을 세면서
*"갚으려면 도구를 먼저 짓는다"*라고 적었고 이 파일이 그것이다.

### 무엇을 비교선으로 두는가 (O-25 (1))

`beat_period`는 포락선의 **자기상관 봉우리**를 고른다. 봉우리가 자료의 성질인지 자의
성질인지 가르려면 **박 구조만 없애고 나머지는 남긴 자료**가 필요하다.

| 선 | 무엇을 하나 | 박 구조 |
|---|---|---|
| `실측` | 포락선 그대로 | 있다 |
| `시간 섞음` | 프레임 **순서**를 섞는다 | **없다** — 값 다중집합은 그대로다 |
| `위상 돌림` | 순환 이동 | **있다** (아래) |

### 위상 돌림은 귀무가 아니다 (O-25 (2) · D-0300과 같은 자리)

자기상관은 **순환 이동에 거의 불변이다.** 돌린 포락선으로 재면 실측과 같은 주기가
나오고, 그것을 *"차이가 없다"*로 읽으면 틀린다. **그래서 비교선으로 안 쓰고, 안 쓴다는
사실을 시험이 든다** — `test_위상_돌림은_박_축의_귀무가_아니다`.

D-0300이 화음 품질에서 순환 **회전**을 같은 이유로 버렸다. **자를 바꿔도 같은 함정이
같은 모양으로 있다.**

### 판정은 짝지은 차로 한다 (D-0311)

D-0311에서 **음성 대조가 스스로 판정 규칙을 통과했다.** 같은 일이 여기서도 날 수 있으므로
처음부터 곡별로 뺀다 — 같은 곡의 `실측` 봉우리에서 `시간 섞음` 봉우리를 뺀 값의 평균과
`t`, 그리고 곡승률.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.onset import TEMPO_RANGE, beat_period, event_scale

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from numpy.typing import NDArray

BEAT_FLOOR = 3.0
"""짝지은 `t`의 승인 문턱. **D-0098이 세운 값을 그대로 쓴다** — 축마다 다른 문턱을
고르면 그 고름이 결과를 만든다."""


@dataclass(frozen=True, slots=True)
class TrackBeat:
    """곡 하나의 박 추정. **못 고르면 `None`으로 남는다** (GR-0.5)."""

    source_key: str
    period_seconds: float | None
    margin: float
    octave_margin: float
    event_seconds: float | None

    @property
    def tempo_bpm(self) -> float | None:
        if self.period_seconds is None or self.period_seconds <= 0.0:
            return None
        return 60.0 / self.period_seconds

    @property
    def in_range(self) -> bool:
        """추정 빠르기가 탐색 범위 안인가. **밖이면 경계에 붙은 것이다.**"""
        tempo = self.tempo_bpm
        return tempo is not None and TEMPO_RANGE[0] <= tempo <= TEMPO_RANGE[1]


@dataclass(frozen=True, slots=True)
class BeatLine:
    """한 선의 곡별 **봉우리 뾰족함** (`Beat.peak_ratio`).

    **`margin`을 쓰면 거꾸로 간다** (D-0314). 진짜 주기는 배수 지연에서도 봉우리가 서므로
    1등과 2등의 차가 **작아진다** — 120BPM 클릭 트랙에서 `margin` 0.0262가 섞은 잡음의
    0.1729보다 낮았다. 두 여유는 «어느 주기를 골랐나»이고 뾰족함이 «박이 있는가»다.
    """

    label: str
    ratios: tuple[float, ...]
    decided: int
    """박을 고른 곡 수. **`ratios`의 길이와 다를 수 있다** — 못 고른 곡은 0.0이 든다."""

    @property
    def mean_ratio(self) -> float:
        return float(np.mean(self.ratios)) if self.ratios else 0.0

    @property
    def decision_rate(self) -> float:
        return self.decided / len(self.ratios) if self.ratios else 0.0


@dataclass(frozen=True, slots=True)
class BeatGain:
    """`실측 - 시간 섞음`의 **곡별 짝지은 차** (D-0311의 구조를 그대로 쓴다).

    두 선이 **같은 곡을 같은 순서로** 든다. 두 선의 표준오차를 따로 합치면 짝짓기를
    버리는 것이고, 그러면 구간이 실제보다 넓어진다 (D-0087 · D-0300).
    """

    measured: BeatLine
    control: BeatLine

    @property
    def _paired(self) -> NDArray[np.float64]:
        return np.asarray(self.measured.ratios, dtype=np.float64) - np.asarray(
            self.control.ratios, dtype=np.float64
        )

    @property
    def aligned(self) -> bool:
        return len(self.measured.ratios) == len(self.control.ratios) and bool(self.measured.ratios)

    @property
    def gain(self) -> float:
        return float(np.mean(self._paired)) if self.aligned else 0.0

    @property
    def standard_error(self) -> float:
        if not self.aligned or len(self.measured.ratios) < 2:
            return 0.0
        return float(np.std(self._paired, ddof=1) / np.sqrt(self._paired.size))

    @property
    def t_statistic(self) -> float:
        return self.gain / self.standard_error if self.standard_error > 0 else 0.0

    @property
    def win_rate(self) -> float:
        return float(np.mean(self._paired > 0.0)) if self.aligned else 0.0

    @property
    def carries_beat(self) -> bool:
        """**사전 등록한 판정 규칙이다** (D-0314).

        1. 짝지은 이득이 양수다.
        2. `t > BEAT_FLOOR`.
        3. **곡 과반**에서 그렇다.

        **질 수 있다.** 포락선이 잡음이면 섞어도 봉우리가 같은 세기로 서고 이득이
        0 근처가 된다 — 그것이 이 규칙이 비교인 이유다 (D-0062).
        """
        return self.gain > 0.0 and self.t_statistic > BEAT_FLOOR and self.win_rate > 0.5

    def as_record(self) -> dict[str, object]:
        return {
            "gain": round(self.gain, 6),
            "standard_error": round(self.standard_error, 6),
            "t_statistic": round(self.t_statistic, 4),
            "win_rate": round(self.win_rate, 4),
            "measured_ratio": round(self.measured.mean_ratio, 6),
            "control_ratio": round(self.control.mean_ratio, 6),
            "carries_beat": self.carries_beat,
        }


def shuffled(envelope: NDArray[np.float64], *, seed: int) -> NDArray[np.float64]:
    """프레임 **순서**를 섞는다. 값 다중집합은 그대로다.

    **박 구조만 사라진다** — 총 에너지·최댓값·분포가 실측과 같으므로 «봉우리가 선 것이
    자료 때문인가 자 때문인가»를 가른다 (O-25 (5)).
    """
    generator = np.random.default_rng(seed)
    return np.asarray(generator.permutation(envelope), dtype=np.float64)


def rolled(envelope: NDArray[np.float64], *, seed: int) -> NDArray[np.float64]:
    """순환 이동. **박 축의 귀무가 아니다** — 자기상관이 거의 불변이다.

    쓰라고 둔 것이 아니라 **안 쓴다는 것을 시험이 들 수 있게** 둔 것이다 (D-0300이
    화음 품질에서 순환 회전을 같은 이유로 버린 자리와 같다).
    """
    generator = np.random.default_rng(seed)
    shift = int(generator.integers(1, max(2, envelope.size)))
    return np.asarray(np.roll(envelope, shift), dtype=np.float64)


def measure(
    envelope: NDArray[np.float64], hop_seconds: float, bands: NDArray[np.float64] | None
) -> tuple[float, bool, float, float | None]:
    """한 포락선의 `(봉우리 뾰족함, 골랐나, 배수 여유, 사건 길이)`.

    **못 고르면 세기가 0.0이다.** 선끼리 곡을 짝지어 빼야 하므로 길이를 맞춘다 —
    빼는 쪽에서 곡을 버리면 두 선의 곡 집합이 갈린다.
    """
    beat = beat_period(envelope, hop_seconds)
    scale = event_scale(bands, hop_seconds) if bands is not None else None
    if beat is None:
        return 0.0, False, 0.0, scale
    return beat.peak_ratio, True, beat.octave_margin, scale


def line(
    label: str,
    envelopes: Sequence[tuple[NDArray[np.float64], float]],
    *,
    transform: str = "none",
    seed: int = 20260930,
) -> BeatLine:
    """한 선 전체. `transform`은 `none` · `shuffled` · `rolled`."""
    ratios: list[float] = []
    decided = 0
    for index, (envelope, hop) in enumerate(envelopes):
        taken = envelope
        if transform == "shuffled":
            taken = shuffled(envelope, seed=seed + index)
        elif transform == "rolled":
            taken = rolled(envelope, seed=seed + index)
        ratio, chosen, _, _ = measure(taken, hop, None)
        ratios.append(ratio)
        decided += int(chosen)
    return BeatLine(label=label, ratios=tuple(ratios), decided=decided)


def load_lines(
    folder: Path, *, limit: int | None = None, seed: int = 20260930
) -> tuple[BeatLine, BeatLine, BeatLine]:
    """포락선 폴더에서 세 선을 낸다 — `(실측, 시간 섞음, 위상 돌림)`.

    **곡 순서를 파일 이름으로 고정한다.** 세 선이 같은 곡을 같은 자리에서 들어야
    짝지어 뺄 수 있다 (D-0311).
    """
    envelopes: list[tuple[NDArray[np.float64], float]] = []
    for path in sorted(folder.glob("*.npz"))[:limit]:
        with np.load(path, allow_pickle=False) as bundle:
            values = np.asarray(bundle["envelope"], dtype=np.float64)
            hop = float(bundle["hop_seconds"])
        if values.ndim != 1 or values.size < 4 or hop <= 0.0:
            continue
        envelopes.append((values, hop))
    return (
        line("실측", envelopes, seed=seed),
        line("시간 섞음", envelopes, transform="shuffled", seed=seed),
        line("위상 돌림", envelopes, transform="rolled", seed=seed),
    )
