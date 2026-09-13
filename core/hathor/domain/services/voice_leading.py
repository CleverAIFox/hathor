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
