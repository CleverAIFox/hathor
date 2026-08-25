"""스템 조합 어휘와 겹침 판정 (O-27 · D-0073 · D-0099).

**CLI에서 내려왔다.** 조합 이름은 저장 형식(`stems.<이름>.full`)에 그대로 박히고
겹침 판정은 D-0099가 게이트로 쓰는 규칙이다. 둘 다 인자 파싱과 무관하다.
"""

from __future__ import annotations

MIX_SOURCE = "mix"
"""전체 믹스 크로마를 가리키는 출처 이름. 스템 조합 이름과 같은 자리에 쓴다."""

DEFAULT_STEM_SET = "other"
"""생성에 쓰는 스템 조합. **실측이 고른 값이다** (D-0074).

달성 가능 폭이 `other` 0.0534 · `other+bass` 0.0497 · `other+bass+vocals` 0.0373이었다.
넣을수록 나빠진다 — 저역은 CQ 격자에서 반음이 뭉개지고(D-0056) 보컬은 비브라토로
칸 사이를 번져, 둘 다 균등 성분을 도로 넣는다.
"""

ALL_STEMS = frozenset({"other", "bass", "vocals", "drums"})
"""Demucs가 내는 네 갈래. `mix`가 담는 것이 이것이다."""

STEM_SETS: dict[str, tuple[str, ...]] = {
    "other": ("other",),
    "other+bass": ("other", "bass"),
    "other+bass+vocals": ("other", "bass", "vocals"),
    "bass": ("bass",),
    "vocals": ("vocals",),
}
"""분리 후 재 볼 스템 조합 (O-27 (a) · D-0073).

**앞 셋은 드럼을 뺀 것이 공통점이다.** `bass`와 `vocals`는 D-0099가 **겹치지 않는
두 관측**을 만들려고 더한 것이며 화성 사전으로 쓰라고 둔 것이 아니다.

타악은 음정이 없어 12칸에 고르게 퍼진 에너지를 내고, 그것이 크로마 대비를 K-K
프로파일의 30%로 누른다는 것이 (a)의 가설이다.

| 조합 | 근거 |
|---|---|
| `other` | 화성 악기만. 가장 깨끗하나 베이스 근음을 버린다 |
| `other+bass` | 근음은 화성 판정에 크다. 유력 후보 |
| `other+bass+vocals` | 멜로디도 화성음이다. 다만 비브라토가 번진다 |

**셋을 한 번에 뽑는다.** 분리가 비싸고(GPU) 크로마는 싸므로, 조합마다 다시 분리하면
같은 GPU 작업을 세 번 한다. 조합별 크로마를 저장해 두면 판정은 재분리 없이 돈다 —
D-0059가 크로마를 저장한 것과 같은 이유다.
"""


def stem_parts(name: str) -> frozenset[str]:
    """그 이름이 어떤 원천 스템을 담는가. `mix`는 전부다."""
    if name == MIX_SOURCE:
        return ALL_STEMS
    return frozenset(STEM_SETS.get(name, ()))


def stems_overlap(left: str, right: str) -> bool:
    """두 관측이 오디오를 공유하는가 (D-0099).

    **겹치면 잡음도 함께 움직여 상관이 부풀려진다.** `mix`와 `other`가 그랬고
    실측 0.5572가 그 겹침만으로 설명 가능한 값이었다 — **통과를 못 읽었다.**
    """
    return bool(stem_parts(left) & stem_parts(right))
