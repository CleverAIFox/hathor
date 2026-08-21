"""화성 진행 생성. P0 스텁 — 다이어토닉 도수 중 결정적 선택."""

from __future__ import annotations

import random
from collections.abc import Sequence

import numpy as np

from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode

DIATONIC_DEGREES: dict[Mode, tuple[str, ...]] = {
    Mode.MAJOR: ("I", "ii", "iii", "IV", "V", "vi"),
    Mode.MINOR: ("i", "III", "iv", "v", "VI", "VII"),
}

DIATONIC_ROOT_SEMITONES: dict[Mode, tuple[int, ...]] = {
    Mode.MAJOR: (0, 2, 4, 5, 7, 9),
    Mode.MINOR: (0, 3, 5, 7, 8, 10),
}
"""각 도수의 **근음**이 으뜸음에서 몇 반음 위인가. `DIATONIC_DEGREES`와 같은 순서다.

3화음 전체(근음·3음·5음)의 에너지를 쓰지 않고 근음만 쓴다. I와 vi는 3음 중 2음을
공유하므로 3화음 평균을 쓰면 둘이 거의 같은 가중치를 받아 **판별력이 사라진다.**
근음만 쓰는 쪽이 참조곡 간 차이를 남긴다.

**어느 쪽이 음악적으로 옳은지는 재지 않았다** (O-26). 판별력을 근거로 고른 것이다.
"""


def degree_weights(prior: Sequence[float], mode: Mode) -> tuple[float, ...]:
    """도수 사전(12차원, 인덱스 0이 으뜸음)을 다이어토닉 6도수 가중치로 좁힌다.

    비음계음 6칸을 버리고 남은 6칸을 정규화한다. 버리는 쪽이 균등 성분을 상당히
    걷어낸다 — 잡음 바닥이 12칸에 고루 퍼져 있기 때문이다.
    """
    vector = np.asarray(prior, dtype=np.float64)
    if vector.shape != (DEGREE_COUNT,):
        raise ValueError(f"도수 사전은 12차원이어야 한다: {vector.shape}")
    picked = np.maximum(vector[list(DIATONIC_ROOT_SEMITONES[mode])], 0.0)
    total = float(picked.sum())
    if total <= 0.0:
        return tuple(1.0 / len(picked) for _ in picked)
    return tuple(float(value) for value in picked / total)


def generate_harmony(
    seed: int,
    key: Key,
    bar_count: int = 4,
    *,
    prior: Sequence[float] | None = None,
) -> ChordProgression:
    """시드와 조성이 같으면 항상 같은 진행을 반환한다.

    `prior`를 주면 **참조곡의 도수 분포로 가중 추출한다** (O-21 · D-0063).
    주지 않으면 이전과 완전히 같다 — 기존 산출물이 바뀌지 않는다.

    ### 무엇을 조건화하고 무엇을 안 하는가

    **화음의 어휘와 빈도만 바뀌고 배열은 시드가 정한다.** 크로마는 곡 전체 평균이라
    순서 정보가 없기 때문이다 (D-0062). 종지도 반복 구조도 여기서 나오지 않는다.

    ### 효과의 크기는 사전이 어디서 왔느냐로 갈린다

    **어느 사전을 주느냐가 크기를 정한다.** K-K 장조 프로파일이 갖는 대비를 1로 놓고
    참조곡 조건화가 버는 몫을 재면 이렇다 (D-0063 · D-0074 실측, 200곡).

    | 사전의 출처 | 조건화 이득 | 달성 가능 폭 |
    |---|---|---|
    | 전체 믹스 크로마 | 14.1% | 30.4% |
    | **`other` 스템 크로마** | **44.3%** | **86.7%** |

    **타악이 균등 성분의 주범이었다** (O-27 · D-0074). 드럼을 뺀 사전에서는 조건화가
    세 배 세고, 최적 혼합 계수도 0.90에서 **1.00**으로 간다 — 코퍼스 평균을 섞을 이유가 없다.

    **전체 믹스 사전을 주면 두 참조곡의 진행이 몇 마디만 다르거나 같을 수도 있다.**
    그것은 결함이 아니라 측정된 크기다. 온도나 지수로 대비를 부풀리지 않는다 —
    그렇게 하면 정보를 늘리는 것이 아니라 잡음을 증폭하고, 귀로 판정하며 손잡이를
    돌리는 자리로 되돌아간다 (D-0058~D-0061에서 네 세션을 쓴 곳). **크기를 키우려면
    사전의 출처를 바꾼다** — 그것이 (a)가 한 일이다.

    P4에서 A* 탐색 기반 화성 생성으로 교체된다.
    """
    if bar_count < 1:
        raise ValueError("마디 수는 1 이상이어야 한다")
    rng = random.Random(seed ^ key.tonic_pitch_class)
    pool = DIATONIC_DEGREES[key.mode]
    if prior is None:
        degrees = tuple(rng.choice(pool) for _ in range(bar_count))
    else:
        weights = degree_weights(prior, key.mode)
        degrees = tuple(rng.choices(pool, weights=weights, k=1)[0] for _ in range(bar_count))
    return ChordProgression(key=key, degrees=degrees)
