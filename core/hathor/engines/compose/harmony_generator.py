"""화성 진행 생성. P0 스텁 — 다이어토닉 도수 중 결정적 선택."""

from __future__ import annotations

import random
from collections.abc import Sequence
from enum import StrEnum

import numpy as np

from hathor.domain.services.harmony_prior import DEGREE_COUNT
from hathor.domain.services.transition_prior import is_empty, transition_row
from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode

DIATONIC_DEGREES: dict[Mode, tuple[str, ...]] = {
    Mode.MAJOR: ("I", "ii", "iii", "IV", "V", "vi"),
    Mode.MINOR: ("i", "III", "iv", "v", "VI", "VII"),
}


class Vocabulary(StrEnum):
    """코드 풀을 무엇으로 할 것인가 (O-36 · D-0094).

    - `BASE` — 다이어토닉 6도수. **기존 동작이며 기본값이다.**
    - `MIXTURE` — 거기에 `♭III` · `♭VI` · `♭VII`를 더한 9도수.
    - `CONTROL` — 거기에 **뭉치지 않는 세 칸**(♭2 · ♯4 · 이끔음)을 더한 9도수.

    **`CONTROL`이 없으면 `MIXTURE`를 읽을 수 없다.** 도수를 6에서 9로 늘리는 것만으로
    히스토그램 거리가 오른다 — 칸이 늘면 두 진행이 겹칠 확률이 낮아지기 때문이다.
    탐색에서 차용이 전혀 없는 코퍼스에서도 0.2155에서 0.2696으로 **공짜로 올랐다.**
    같은 칸 수의 대조군을 빼야 진짜 몫이 남는다.
    """

    BASE = "base"
    MIXTURE = "mixture"
    CONTROL = "control"


MODAL_MIXTURE_CELLS = (3, 8, 10)
"""D-0093이 뭉침을 잰 칸. ♭3 · ♭6 · ♭7이며 **차용 3화음의 근음과 같다.**"""

BORROWED_DEGREES: dict[Mode, tuple[str, ...]] = {
    Mode.MAJOR: ("bIII", "bVI", "bVII"),
    Mode.MINOR: (),
}
BORROWED_ROOT_SEMITONES: dict[Mode, tuple[int, ...]] = {
    Mode.MAJOR: MODAL_MIXTURE_CELLS,
    Mode.MINOR: (),
}
"""단조 차용 3화음의 **근음**. D-0093이 잰 삼총사 칸과 정확히 같다.

`♭III`(3·7·10) · `♭VI`(8·0·3) · `♭VII`(10·2·5)의 근음이 3·8·10이므로 **근음만으로
들어간다.** 기존 방식을 안 바꿔도 된다는 뜻이다.

**`iv`는 뺐다.** 근음이 5로 `IV`와 같아 근음만으로는 안 갈리고, 가르는 것은 3음
(♭6 = 8)인데 그것은 이미 `♭VI`의 근음이라 **이중 계산이 된다.** 3화음 평균으로
바꾸면 되지만 그러면 `I`와 `vi`가 2음을 공유해 **판별력이 사라진다**(위 참고) —
O-26이 그 자리다. 근거가 있는 셋만 넣는다.

**단조는 비었다.** D-0093은 장조만 쟀다. **재지 않은 것을 넣지 않는다** (GR-0.5).
"""

CONTROL_DEGREES: dict[Mode, tuple[str, ...]] = {
    Mode.MAJOR: ("x-b2", "x-#4", "x-vii"),
    Mode.MINOR: (),
}
CONTROL_ROOT_SEMITONES: dict[Mode, tuple[int, ...]] = {
    Mode.MAJOR: (1, 6, 11),
    Mode.MINOR: (),
}
"""대조군 근음. **화음이 아니라 자리 표시다** — 이름에 `x-`를 붙인 이유다.

♭2 · ♯4는 D-0093에서 뭉치지 않았고 이끔음은 D-0088에서 코퍼스 공통이었다.
**셋 다 곡을 가르지 않는 칸이므로**, 여기서 오르는 몫은 전부 "칸이 늘어서"다.
"""


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


def vocabulary_degrees(mode: Mode, vocabulary: Vocabulary = Vocabulary.BASE) -> tuple[str, ...]:
    """코드 풀의 도수 이름. **근음 오름차순으로 정렬한다** — 순서가 추출을 정한다."""
    return tuple(name for _, name in _vocabulary_table(mode, vocabulary))


def vocabulary_roots(mode: Mode, vocabulary: Vocabulary = Vocabulary.BASE) -> tuple[int, ...]:
    """코드 풀의 근음 반음."""
    return tuple(root for root, _ in _vocabulary_table(mode, vocabulary))


def _vocabulary_table(mode: Mode, vocabulary: Vocabulary) -> tuple[tuple[int, str], ...]:
    entries = list(zip(DIATONIC_ROOT_SEMITONES[mode], DIATONIC_DEGREES[mode], strict=True))
    if vocabulary is Vocabulary.MIXTURE:
        entries += list(zip(BORROWED_ROOT_SEMITONES[mode], BORROWED_DEGREES[mode], strict=True))
    elif vocabulary is Vocabulary.CONTROL:
        entries += list(zip(CONTROL_ROOT_SEMITONES[mode], CONTROL_DEGREES[mode], strict=True))
    return tuple(sorted(entries))


def degree_weights(
    prior: Sequence[float], mode: Mode, vocabulary: Vocabulary = Vocabulary.BASE
) -> tuple[float, ...]:
    """도수 사전(12차원, 인덱스 0이 으뜸음)을 코드 풀의 도수 가중치로 좁힌다.

    기본값은 다이어토닉 6도수다. 비음계음 6칸을 버리고 남은 6칸을 정규화한다.
    버리는 쪽이 균등 성분을 상당히 걷어낸다 — 잡음 바닥이 12칸에 고루 퍼져 있기
    때문이다.

    **버리는 몫이 거리의 44~47%이고 그 곡 고유성이 다이어토닉과 대등하다**는 것이
    나중에 측정됐다 (D-0088). `Vocabulary.MIXTURE`가 그중 근거가 선 셋을 되살린다.
    """
    vector = np.asarray(prior, dtype=np.float64)
    if vector.shape != (DEGREE_COUNT,):
        raise ValueError(f"도수 사전은 12차원이어야 한다: {vector.shape}")
    picked = np.maximum(vector[list(vocabulary_roots(mode, vocabulary))], 0.0)
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
    vocabulary: Vocabulary = Vocabulary.BASE,
    transition: Sequence[Sequence[float]] | None = None,
    self_transition: float = 0.0,
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

    ### 어휘를 넓히면 아무것도 안 배워도 거리가 오른다

    `vocabulary`로 코드 풀을 바꾼다. **기본값은 기존 동작과 완전히 같다.**

    도수를 6에서 9로 늘리면 두 진행이 겹칠 확률이 낮아져 **히스토그램 거리가
    기계적으로 오른다** — 탐색에서 차용이 전혀 없는 코퍼스에서도 0.2155에서
    0.2696으로 올랐다. **`Vocabulary.CONTROL`과 견주지 않은 `MIXTURE` 값은 읽으면
    안 된다** (D-0094).

    ### 배열 조건화 (O-32 · D-0109)

    `transition`은 참조곡의 12x12 전이 사전이다 (D-0107). 주면 **다음 마디를 지금
    마디에 따라** 뽑는다 — 그때까지 순서는 시드만 정했다 (D-0062).

    **마디마다 반드시 바뀐다.** 전이 사전은 대각선을 버렸으므로 (D-0103) 답하는 것이
    **"바뀐다면 어디로"**뿐이고, 안 바꿀 확률은 여기 없다. 고정 확률로 유지하는 안은
    **손잡이가 하나 늘고 그것을 실험으로 고르면 D-0058이라 기각했다.** 화음을 얼마나
    오래 끄는가는 O-37이다.

    `self_transition`은 **그 기각을 뒤집는 것이 아니다.** O-38의 짐작 — "매 마디 바꾸는
    제약이 짧은 구간에서 관측 거리를 누른다" — 을 재보려면 그 제약을 끌 수 있어야 한다.
    **진단 전용이며 제품 경로는 기본값 `0.0`만 쓴다.** 0.0에서는 아래 갈래가 그대로
    돌아 산출물이 한 비트도 안 바뀐다 (검사로 고정했다). **이 값을 실험으로 골라
    제품에 박는 순간 그것이 D-0058이다.**

    **첫 마디는 `prior`가 정한다.** 전이 사전에는 시작이 없다.

    P4에서 A* 탐색 기반 화성 생성으로 교체된다.
    """
    if bar_count < 1:
        raise ValueError("마디 수는 1 이상이어야 한다")
    if not 0.0 <= self_transition < 1.0:
        raise ValueError(f"자기 전이 확률은 [0, 1)이어야 한다: {self_transition}")
    rng = random.Random(seed ^ key.tonic_pitch_class)
    pool = vocabulary_degrees(key.mode, vocabulary)
    if prior is None:
        degrees = tuple(rng.choice(pool) for _ in range(bar_count))
    elif transition is None or is_empty(transition):
        weights = degree_weights(prior, key.mode, vocabulary)
        degrees = tuple(rng.choices(pool, weights=weights, k=1)[0] for _ in range(bar_count))
    else:
        roots = vocabulary_roots(key.mode, vocabulary)
        weights = degree_weights(prior, key.mode, vocabulary)
        picked = [rng.choices(range(len(pool)), weights=list(weights), k=1)[0]]
        for _ in range(bar_count - 1):
            row = list(transition_row(transition, roots[picked[-1]], roots))
            # **자기 자리를 지운다.** 사전이 대각선을 버렸어도 행이 비어 열 합으로
            # 되돌아오면 자기 자신이 다시 들어온다 (D-0107).
            row[picked[-1]] = 0.0
            if sum(row) <= 0.0:
                row = [0.0 if index == picked[-1] else 1.0 for index in range(len(pool))]
            if self_transition > 0.0:
                row = _with_self(row, picked[-1], self_transition)
            picked.append(rng.choices(range(len(pool)), weights=row, k=1)[0])
        degrees = tuple(pool[index] for index in picked)
    return ChordProgression(key=key, degrees=degrees)


def _with_self(row: list[float], here: int, probability: float) -> list[float]:
    """바꾸는 몫을 `1 - probability`로 줄이고 그만큼 자기 자리에 준다. **진단 전용.**

    `probability = 0.0`에서 호출되지 않으므로 **기본 경로는 이 함수를 안 지난다** —
    되튐 하나 없이 예전 산출물과 같아야 하기 때문이다 (D-0109가 검사로 고정한 것).
    """
    total = sum(row)
    if total <= 0.0:
        return row
    scaled = [value * (1.0 - probability) / total for value in row]
    scaled[here] = probability
    return scaled
