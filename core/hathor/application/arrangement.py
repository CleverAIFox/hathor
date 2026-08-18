"""구조와 화성을 노트 배치로 잇는다. 조합은 application이 한다 (GR-2.2).

### 구조가 배치를 결정한다

`R`(반복) 구간과 `U`(고유) 구간은 **같은 진행을 쓰지 않는다.**

- `R` 구간은 전부 진행의 **앞 4마디**를 쓴다. 후렴이 매번 같은 화성으로
  돌아오는 것을 흉내낸다.
- `U` 구간은 진행을 **한 칸씩 회전**시켜 쓴다. 절마다 다르게 흘러간다.

회전을 쓰는 이유는 실측이다. 처음에는 진행을 순차로 잘라 썼는데, **진행 길이가
섹션 마디 수의 배수이면 모든 `U` 구간이 똑같아졌다.** 진행 8마디에 섹션 4마디처럼
흔한 조합에서 바로 걸린다. 산술적 우연에 기대는 규칙이었고 테스트가 잡았다.

이것이 구조 추출(D-0049)을 실제로 소리에 연결하는 지점이다. 구조를 뽑아 두고
배치에 쓰지 않으면 **지표를 만들어두고 보지 않는 것과 같다** (D-0030에서 겪음).

### 아직 하지 않는 것

가락이 없다. 3화음을 마디마다 통째로 울릴 뿐이다. 리듬도 없다.
**지금 필요한 것은 파이프라인 관통이며, 음악적 타당성은 그 뒤다** (GR-6.1).
"""

from __future__ import annotations

from hathor.domain.services.midi_writer import TICKS_PER_BEAT, Note, chord_pitches
from hathor.domain.services.song_structure import REPEATED, StructurePattern
from hathor.domain.value_objects.chord_progression import ChordProgression

BEATS_PER_BAR = 4
BARS_PER_SECTION = 4
TICKS_PER_BAR = TICKS_PER_BEAT * BEATS_PER_BAR


def arrange(
    pattern: StructurePattern,
    progression: ChordProgression,
    *,
    bars_per_section: int = BARS_PER_SECTION,
) -> list[Note]:
    """구조와 화성 진행에서 노트를 배치한다.

    시드가 같으면 구조와 진행이 같고, 따라서 노트도 같다. 무작위성이 여기에는
    없다 — 배치는 규칙이며 선택은 앞 단계에서 이미 끝났다.
    """
    if bars_per_section < 1:
        raise ValueError("섹션당 마디는 1 이상이어야 한다")

    notes: list[Note] = []
    unique_index = 0
    bar_index = 0

    for label in pattern.labels:
        rotation = 0 if label == REPEATED else unique_index + 1
        if label != REPEATED:
            unique_index += 1
        for offset in range(bars_per_section):
            degree = progression.degrees[(rotation + offset) % progression.length]
            start = bar_index * TICKS_PER_BAR
            for pitch in chord_pitches(progression.key, degree):
                notes.append(Note(pitch=pitch, start_tick=start, duration_ticks=TICKS_PER_BAR))
            bar_index += 1

    return notes


def total_bars(pattern: StructurePattern, *, bars_per_section: int = BARS_PER_SECTION) -> int:
    return pattern.length * bars_per_section


def duration_seconds(
    pattern: StructurePattern, tempo_bpm: int, *, bars_per_section: int = BARS_PER_SECTION
) -> float:
    """길이를 초로. 곡이 몇 분짜리인지 눈으로 확인할 수 있어야 한다."""
    if tempo_bpm < 1:
        raise ValueError("템포는 1 이상이어야 한다")
    beats = total_bars(pattern, bars_per_section=bars_per_section) * BEATS_PER_BAR
    return beats * 60 / tempo_bpm
