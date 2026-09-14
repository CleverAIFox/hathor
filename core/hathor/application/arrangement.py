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

from collections.abc import Sequence

from hathor.domain.services.melody import sing
from hathor.domain.services.midi_writer import (
    DYNAMICS,
    METRIC_STRESS,
    MIDDLE_C,
    TICKS_PER_BEAT,
    Note,
    chord_pitches,
    softer,
)
from hathor.domain.services.song_structure import REPEATED, StructurePattern
from hathor.domain.services.voice_leading import bass, lead
from hathor.domain.value_objects.chord_progression import ChordProgression

BEATS_PER_BAR = 4
BARS_PER_SECTION = 8
"""섹션 하나가 몇 마디인가.

**여기 하나만 둔다** (D-0111). 파이프라인에도 같은 이름의 상수가 4가 아닌 8로 따로
있었고, 그래서 화성은 64마디를 뽑는데 편곡은 24마디만 썼다. **한 이름이 두 값이면
둘 중 하나는 반드시 틀린다.**
"""
TICKS_PER_BAR = TICKS_PER_BEAT * BEATS_PER_BAR


def _beat(start_tick: int) -> int:
    """마디 안 몇 번째 박인가. **나눗셈이며 고를 것이 없다.**"""
    return start_tick // TICKS_PER_BEAT % BEATS_PER_BAR


def _tie(sung: Sequence[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """이어지는 같은 음을 한 음으로 잇는다 (D-0176).

    **D-0138이 화음에서 세운 규칙을 가락에 그대로 적용한다.** 새 판단이 아니며
    문턱도 값도 없다 — 붙어 있고 음높이가 같으면 한 음이다.

    D-0141이 *"같은 음 유지 25%"*를 쟀고 실측 재현이 **23.4%**다. 이으면 타격이
    192개에서 147개로 준다.

    **밀도는 안 바뀐다.** 같은 시간에 같은 음이 울리므로 동시 5음도 쉼 0%도 그대로다
    (O-50). 주는 것은 **다시 치는 횟수**뿐이다.
    """
    found: list[tuple[int, int, int]] = []
    for start, length, pitch in sung:
        if found and found[-1][2] == pitch and found[-1][0] + found[-1][1] == start:
            before = found[-1]
            found[-1] = (before[0], before[1] + length, pitch)
        else:
            found.append((start, length, pitch))
    return found


def _runs(degrees: Sequence[str]) -> list[tuple[str, int]]:
    """이어지는 같은 도수를 하나로 묶는다 (D-0138).

    **진행이 이미 말하고 있던 것이다.** `I I`를 두 번 치는 것과 두 마디 끄는 것은
    다른 소리이며, 마디마다 다시 치는 쪽을 고른 근거가 어디에도 없었다.
    """
    found: list[tuple[str, int]] = []
    for degree in degrees:
        if found and found[-1][0] == degree:
            found[-1] = (degree, found[-1][1] + 1)
        else:
            found.append((degree, 1))
    return found


def arrange(
    pattern: StructurePattern,
    progression: ChordProgression,
    *,
    bars_per_section: int = BARS_PER_SECTION,
    seed: int | None = None,
    prior: Sequence[float] | None = None,
    transition: Sequence[Sequence[float]] | None = None,
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
    voiced: tuple[int, ...] | None = None
    sung: list[tuple[str, int]] = []

    # **진행이 충분히 길면 섹션마다 겹치지 않는 블록을 읽는다** (D-0111).
    #
    # 예전에는 한 칸씩 밀어 읽었다. 진행이 섹션과 같은 길이(4마디 진행·4마디 섹션)일
    # 때 순차 블록이 전부 같아지는 것을 고친 자리였고 그때는 옳았다. **진행이
    # 64마디가 된 지금은 그 전제가 사라졌고**, 한 칸씩 밀면 6섹션이 진행의 앞
    # 일곱 마디만 읽는다 — **배열 조건화가 소리에 거의 안 닿는다** (O-32 · D-0110).
    #
    # 짧은 진행에서는 예전처럼 한 칸씩 민다. **고칠 것을 고치되 고쳤던 것을 되돌리지
    # 않는다.**
    unique_total = sum(1 for label in pattern.labels if label != REPEATED)
    stride = bars_per_section if progression.length >= bars_per_section * (unique_total + 1) else 1

    for label in pattern.labels:
        rotation = 0 if label == REPEATED else (unique_index + 1) * stride
        if label != REPEATED:
            unique_index += 1
        # **같은 도수가 이어지면 다시 치지 않고 잇는다** (D-0138).
        #
        # 마디마다 다시 치던 동안 음길이도 발음 간격도 **종류가 하나**였다. 120초
        # 동안 같은 모양이 48번 반복됐다. 진행이 이미 말하고 있던 것을 소리가 안
        # 받고 있었을 뿐이며, **고를 값이 없다.**
        #
        # **구간을 넘어 잇지는 않는다.** 구간은 소리의 단위이고, 화음이 구간 경계를
        # 물고 넘어가면 구조를 뽑아 둔 의미가 없다 (D-0111).
        span = [
            progression.degrees[(rotation + offset) % progression.length]
            for offset in range(bars_per_section)
        ]
        sung.extend(_runs(span))
        for degree, repeats in _runs(span):
            start = bar_index * TICKS_PER_BAR
            length = TICKS_PER_BAR * repeats
            # **직전 화음에서 가장 적게 움직이는 전위를 고른다** (D-0137).
            #
            # 근음 위치로만 쌓던 동안 63번 전환 중 57번이 병행 5도였다. 세 성부가
            # 통째로 평행 이동했기 때문이며, **성부 진행이라는 것이 없었다.**
            rooted = chord_pitches(progression.key, degree)
            voiced = lead(voiced, rooted, octave_base=MIDDLE_C)
            # **베이스는 전위를 안 따른다** (D-0139). 근음은 화음의 성질이고 전위는
            # 자리다. 실측 음역이 60~77로 한 옥타브 남짓이었고 **가장 낮은 음이
            # 마디마다 바뀌어 바닥이 없었다.**
            # **층마다 세기가 다르다** (D-0174). 전부 72이던 동안 가락과 반주가 같은
            # 층에서 울렸고, 귀가 *"반주가 앞에서 논다"*로 판정했다. 표는 여린소리표이며
            # 배치는 위에 적힌 역할을 그대로 따른다 — 받침과 배경이다.
            for pitch, level in (
                (bass(rooted, octave_base=MIDDLE_C), DYNAMICS["mp"]),
                *((pitch, DYNAMICS["p"]) for pitch in voiced),
            ):
                notes.append(
                    Note(pitch=pitch, start_tick=start, duration_ticks=length, velocity=level)
                )
            bar_index += repeats

    if seed is not None:
        # **가락은 박 격자를 쓴다** (D-0141). 화음이 마디를 끄는 동안에도 움직이며,
        # 그것이 전경과 배경의 차이다. 없으면 반주만 남는다 (D-0140).
        notes.extend(
            # **가락이 전경이고 박마다 세기가 다르다** (D-0141 · D-0174 · D-0177).
            # 층 사이는 D-0174가 갈랐고 **층 안은 박자 강세가 가른다** — 전부 같은
            # 세기면 초보가 치는 소리가 난다.
            Note(
                pitch=pitch,
                start_tick=start,
                duration_ticks=length,
                velocity=softer(DYNAMICS["f"], METRIC_STRESS[_beat(start) % len(METRIC_STRESS)]),
            )
            for start, length, pitch in _tie(
                sing(
                    seed,
                    sung,
                    progression.key,
                    ceiling=MIDDLE_C + 12,
                    beats_per_bar=BEATS_PER_BAR,
                    prior=prior,
                    transition=transition,
                )
            )
        )
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
