"""후렴 구간 찾기 — 오디오 썸네일 (D-0430).

**Bartsch & Wakefield 2001 「To Catch a Chorus」를 옮겼다** (WASPAA). 크로마 프레임끼리
상관을 재 자기유사 행렬을 만들고, **대각선 방향으로 이동평균**을 걸어 *«길이 W짜리
구간이 lag만큼 떨어진 데서 반복되는 정도»*를 잰다. 그 최댓값이 후렴이다.

논문은 93곡에서 **크로마가 MFCC와 무작위를 모든 창 길이에서 이겼다**고 적는다.
재현/정밀 곡선이 **23초**(평균 후렴 길이)에서 교차하고 20~25초 창을 권고한다.

### 옮긴 것이지 재현한 것이 아니다

논문은 **박 단위 프레임**(0.25~0.5초)을 쓴다. 여기는 `chroma_series`의 창을 쓰고
그 길이는 `series_seconds`다 — **해상도가 더 거칠다.** 그래서 논문의 수가 여기서
그대로 나올 것이라 가정하지 않는다. **얼마나 맞는지는 이 저장소에서 다시 잰다**
(GR-0.5). 논문이 적은 실패 모드도 그대로 온다.

- 후렴이 편곡을 바꿔 반복되면 **벌스끼리가 더 비슷해서 벌스를 집는다.**
- 반복되는 인트로 리프가 후렴을 이긴다.
- 벌스-후렴 형식이 아닌 장르(클래식·재즈·블루스)는 안 된다.

### 못 재면 `None`이다

곡이 짧아 «지연 바닥»과 «창 길이»를 함께 만족하는 후보가 없으면 **0번 창을 돌려주지
않는다.** 조용한 기본값은 *«곡 앞 20초가 후렴»*이라는 거짓 주장이 된다 (GR-0.5).
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.harmony_quality import DEGREE_COUNT

if TYPE_CHECKING:
    from numpy.typing import NDArray

MIN_LAG_SHARE = 0.1
"""반복이 **곡 길이의 1/10보다는 떨어져** 있어야 한다 (논문의 제약).

바로 옆 창은 무엇이든 자기 자신과 비슷하다. 이 바닥이 없으면 **대각선 바로 아래가
항상 이기고**, 고른 구간은 «반복되는 곳»이 아니라 «변화가 적은 곳»이 된다.
"""

LATEST_START_SHARE = 0.75
"""시작은 **곡의 3/4 이전**이어야 한다 (논문의 제약). 아웃트로 반복을 집지 않는다."""


@dataclasses.dataclass(frozen=True, slots=True)
class Thumbnail:
    """고른 구간 하나. **자기를 설명한다** (D-0203).

    `score`와 `lag`가 없으면 *«왜 거기냐»*에 답할 수가 없고, 틀렸을 때 **어디가
    틀렸는지 못 가른다.** 점수가 낮은 곡은 사람이 먼저 들어 볼 곡이다.
    """

    start: int
    """시작 창 번호."""

    length: int
    """창 수. 요청한 창 길이와 같다."""

    score: float
    """그 구간과 `lag`만큼 떨어진 짝의 평균 코사인 유사도. 1에 가까울수록 또렷하다."""

    lag: int
    """어디서 반복되는가 — 창 수. `start - lag`가 짝의 시작이다."""


def _unit(frames: NDArray[np.float64]) -> NDArray[np.float64]:
    """행마다 L2 정규화. **길이가 0인 행은 0으로 둔다** — 무음에서 0으로 나누지 않는다."""
    norm = np.linalg.norm(frames, axis=1, keepdims=True)
    return frames / np.where(norm > 0.0, norm, 1.0)


def _moving_mean(values: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """길이 `window` 이동평균. 누적합으로 한 번에 낸다."""
    running = np.concatenate(([0.0], np.cumsum(values)))
    return (running[window:] - running[:-window]) / window


def thumbnail(
    series: object,
    *,
    window: int,
    min_lag_share: float = MIN_LAG_SHARE,
    latest_start_share: float = LATEST_START_SHARE,
) -> Thumbnail | None:
    """자기유사 행렬의 대각선에서 가장 또렷하게 반복되는 `window`창 구간.

    **차원이 다르면 죽는다** (D-0233) — 12차원이 아닌 것이 들어오면 조용히 이상한
    수를 내는 대신 여기서 멈춘다.
    """
    frames = np.asarray(series, dtype=np.float64)
    if frames.ndim != 2 or frames.shape[1] != DEGREE_COUNT:
        raise ValueError(f"크로마 시계열은 (창, {DEGREE_COUNT})이어야 한다: {frames.shape}")
    if window < 1:
        raise ValueError(f"창 길이는 1 이상이어야 한다: {window}")

    count = int(frames.shape[0])
    similarity = _unit(frames) @ _unit(frames).T
    # **엄격한 «보다 크다»다.** `ceil`을 쓰면 120창 곡에서 lag 12가 들어오는데
    # 논문의 제약은 «곡 길이의 1/10보다 떨어져 있을 것»이다. 짧은 곡에서 이 한 칸이
    # «옆 창이 후렴»을 통과시킨다.
    floor_lag = max(1, math.floor(count * min_lag_share) + 1)
    last_start = int(count * latest_start_share)

    best: Thumbnail | None = None
    for lag in range(floor_lag, count - window + 1):
        diagonal = similarity[np.arange(lag, count), np.arange(count - lag)]
        means = _moving_mean(diagonal, window)
        # **먼저 나온 쪽을 돌려준다.** 대각선 자리 `k`는 앞 구간의 시작이고 짝은
        # `k + lag`에서 시작한다. 뒤쪽을 돌려주면 논문의 «3/4 이전» 제약이 아웃트로
        # 반복을 못 막는다 — 막으려던 바로 그것이 통과한다.
        starts = np.arange(means.size)
        allowed = starts <= last_start
        if not allowed.any():
            continue
        where = int(np.argmax(np.where(allowed, means, -np.inf)))
        score = float(means[where])
        if best is None or score > best.score:
            best = Thumbnail(start=int(starts[where]), length=window, score=score, lag=lag)
    return best


def window_count(seconds: float, series_seconds: float) -> int:
    """`seconds`초를 덮는 창 수. **0을 안 돌려준다** — 창 길이가 더 길면 1이다."""
    if series_seconds <= 0.0:
        raise ValueError(f"창 길이가 0 이하다: {series_seconds}")
    return max(1, round(seconds / series_seconds))
