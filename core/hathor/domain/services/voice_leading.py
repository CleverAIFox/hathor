"""화음을 어떻게 쌓고 어떻게 이을 것인가 (D-0137).

### 왜 필요한가

`chord_pitches`는 **언제나 근음 위치로 쌓는다.** 화음이 바뀌면 세 성부가 통째로
평행 이동하고, 실측하니 **63번 전환 중 57번(90.5%)이 병행 5도**였다. 공통음을
유지하는 비율은 **9.5%**이며 성부 이동 최빈값이 **7반음 도약**이다.

병행 5도는 화성학 첫 주에 배우는 금지 사항이고, 귀에는 *"화음이 아니라 한 덩어리가
오르내리는"* 소리로 들린다. **성부 진행이라는 것이 아예 없었다.**

### 손잡이가 없다

D-0058이 기각한 것은 *값을 실험으로 고르는 것*이다. 여기에는 **고를 값이 없다.**

- 후보는 3화음의 **전위 셋**이다. 더도 덜도 아니다.
- 고르는 규칙은 **직전 화음에서 성부 이동 합이 최소**다. 문턱도 가중치도 없다.
- 동점이면 **사전순으로 작은 것**을 쓴다. 결정성을 위한 것이며 음악적 선택이 아니다.
- 첫 화음은 **근음 위치**다. 직전이 없으므로 비교할 것이 없다.

`octave_base`를 빼면 매개변수가 하나도 없다. 그리고 그것은 이미 `chord_pitches`가
쓰던 값이다.

### 왜 병행 5도를 직접 세지 않는가

*"병행 5도가 생기는 후보를 버린다"*가 더 곧아 보인다. **그러면 문턱이 생긴다** —
버릴 것이 다 버려지면 무엇을 쓸 것인가, 5도만 볼 것인가 8도도 볼 것인가.

이동 최소화는 **부수 효과로** 병행을 줄인다. 공통음을 붙들면 두 성부가 같은 방향
같은 간격으로 갈 수 없기 때문이다. **규칙 하나가 둘을 함께 고치면 그 규칙을 쓴다.**

병행 5도 비율은 **고르는 값이 아니라 재는 값이다** (O-42).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

OCTAVE = 12


def voicings(pitches: Sequence[int], *, octave_base: int) -> tuple[tuple[int, ...], ...]:
    """3화음의 전위 전부. **가장 낮은 음이 기준 옥타브 안에 오도록 놓는다.**

    전위는 화음의 성질이고 옥타브는 자리다. 둘을 함께 고르면 후보가 무한히 늘고
    **무엇을 고를지 정하는 값이 필요해진다.** 자리를 고정하면 후보가 딱 셋이다.
    """
    if not pitches:
        raise ValueError("빈 화음은 쌓을 수 없다")

    ordered = sorted(pitches)
    found: list[tuple[int, ...]] = []
    for turn in range(len(ordered)):
        raised = [*ordered[turn:], *(pitch + OCTAVE for pitch in ordered[:turn])]
        shift = octave_base - raised[0]
        offset = (shift // OCTAVE + (1 if shift % OCTAVE else 0)) * OCTAVE
        found.append(tuple(pitch + offset for pitch in raised))
    return tuple(sorted(set(found)))


def distance(before: Sequence[int], after: Sequence[int]) -> int:
    """두 화음 사이 성부 이동의 합. **같은 자리끼리 짝짓는다.**

    낮은 음은 낮은 음으로 간다. 성부가 서로를 넘나들면 사람이 따라갈 수 없고,
    따라갈 수 없으면 성부가 아니다.
    """
    return sum(abs(a - b) for a, b in zip(sorted(before), sorted(after), strict=True))


def lead(
    before: Sequence[int] | None, pitches: Sequence[int], *, octave_base: int
) -> tuple[int, ...]:
    """직전 화음에서 가장 적게 움직이는 전위를 고른다.

    `before`가 없으면 **근음 위치**다 — 비교할 것이 없다.
    """
    found = voicings(pitches, octave_base=octave_base)
    if before is None:
        return found[0]
    return min(found, key=lambda option: (distance(before, option), option))


THIRDS = (3, 4)
"""3화음을 쌓는 음정 (단3도 · 장3도).

**근음 자리면 이웃 간격이 전부 여기 든다.** 전위는 어딘가에 4도(5반음) 이상을 만든다 —
`bass`가 근음 자리를 요구하는지 보는 자가 이것이다.
"""


def rooted(pitches: Sequence[int]) -> bool:
    """근음 자리인가. **3도만 쌓여 있으면 맨 아래가 근음이다** (D-0446).

    **전제: 옥타브 중복음이 없다** (D-0470). 같은 음이 둘이면 그 사이가 0 또는
    12반음이라 `THIRDS`에 없고, **근음 자리여도 거짓**이 나온다. 지금 부르는
    자리는 전부 3음이라 무해하지만, 네 성부로 늘리는 날 **조용히 틀린다** —
    그 날 고칠 것은 이 함수이지 부르는 쪽이 아니다.
    """
    return all(high - low in THIRDS for low, high in pairwise(sorted(pitches)))


def bass(pitches: Sequence[int], *, octave_base: int) -> int:
    """**근음 자리** 화음의 근음을 아래 옥타브에 놓는다 (D-0139 · D-0446).

    **근음은 전위와 무관하다** — 그런데 이 함수는 그렇게 안 돌았다. 문서는 *«가장 낮은
    음이 아니라 음이름 집합이 근음을 정한다»*, *«그래서 근음을 인자로 받는다»*라고
    적었는데 **서명에 그 인자가 없고 구현은 `min(pitches)`**였다. 전위를 넣으면
    **21개 중 14개(67%)가 근음 아닌 음**을 깐다 (실측, 다장조 7도수 곱하기 전위 3).

    쓰는 곳이 `arrangement`의 `rooted` 하나뿐이라 **소리는 멀쩡했다.** 적히지 않은
    전제였고, 그것을 지키는 자가 없었다 — 「전위를 안 따른다」는 시험은 **같은 근음
    자리 화음을 세 번 넣고** 결과가 같다고 적고 있었다 (D-0230).

    그래서 전제를 **글이 아니라 자로 둔다** (D-0126). 전위를 넣으면 운다.

    자리는 `octave_base` 바로 아래 옥타브다. **새 값이 아니다** — 화음이 쓰는 것을
    한 옥타브 내린 것뿐이고, 베이스가 화음과 겹치면 베이스가 아니다.
    """
    if not pitches:
        raise ValueError("빈 화음은 근음이 없다")
    if not rooted(pitches):
        raise ValueError(
            f"근음 자리가 아니다: {tuple(sorted(pitches))}. "
            "맨 아래 음을 근음으로 읽으므로 전위를 넣으면 틀린다 (D-0446)"
        )
    root = min(pitches) % OCTAVE
    low = octave_base - OCTAVE
    return low + (root - low % OCTAVE) % OCTAVE


def parallel_fifths(before: Sequence[int], after: Sequence[int]) -> int:
    """두 성부가 5도를 유지한 채 같이 움직인 횟수 (O-42).

    **고르는 값이 아니라 재는 값이다.** `lead`는 이 수를 안 보고, 이 함수는
    판정에만 쓴다. 보게 하면 그 순간 문턱이 생긴다.
    """
    first, second = sorted(before), sorted(after)
    found = 0
    for low in range(len(first)):
        for high in range(low + 1, len(first)):
            if first[low] == second[low] or first[high] == second[high]:
                continue
            if abs(first[high] - first[low]) % OCTAVE == 7 and (
                abs(second[high] - second[low]) % OCTAVE == 7
            ):
                found += 1
    return found
