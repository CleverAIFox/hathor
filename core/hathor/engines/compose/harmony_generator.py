"""화성 진행 생성. P0 스텁 — 다이어토닉 도수 중 결정적 선택."""

from __future__ import annotations

import random

from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode

DIATONIC_DEGREES: dict[Mode, tuple[str, ...]] = {
    Mode.MAJOR: ("I", "ii", "iii", "IV", "V", "vi"),
    Mode.MINOR: ("i", "III", "iv", "v", "VI", "VII"),
}


def generate_harmony(seed: int, key: Key, bar_count: int = 4) -> ChordProgression:
    """시드와 조성이 같으면 항상 같은 진행을 반환한다.

    P4에서 A* 탐색 기반 화성 생성으로 교체된다.
    """
    if bar_count < 1:
        raise ValueError("마디 수는 1 이상이어야 한다")
    rng = random.Random(seed ^ key.tonic_pitch_class)
    pool = DIATONIC_DEGREES[key.mode]
    degrees = tuple(rng.choice(pool) for _ in range(bar_count))
    return ChordProgression(key=key, degrees=degrees)
