"""곡 구조 생성. P0 스텁 — 결정성(NFR-M6)만 보장하는 최소 구현."""

from __future__ import annotations

import random

SECTION_VOCABULARY: tuple[str, ...] = (
    "intro",
    "verse",
    "prechorus",
    "chorus",
    "bridge",
    "outro",
)


def generate_structure(seed: int, section_count: int = 8) -> list[str]:
    """시드 고정 시 항상 동일한 섹션 배열을 반환한다.

    P4에서 실제 구조 모델로 교체된다. 지금 필요한 것은 파이프라인 관통과
    재현성 검증 경로이지 음악적 타당성이 아니다 (GR-6.1).
    """
    if section_count < 2:
        raise ValueError("섹션은 최소 2개가 필요하다")
    rng = random.Random(seed)
    middle = [rng.choice(SECTION_VOCABULARY[1:-1]) for _ in range(section_count - 2)]
    return ["intro", *middle, "outro"]
