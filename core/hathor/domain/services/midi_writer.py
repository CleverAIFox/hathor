"""심볼릭 산출물을 표준 MIDI 파일(SMF) 바이트로 만든다. 순수 함수다.

### 왜 직접 쓰는가

`pretty_midi` · `mido` 같은 라이브러리가 있다. 쓰지 않는 이유는 **D-0009**다.

재현성 계층 1이 "같은 입력이면 산출물이 바이트 단위로 같다"를 요구하는데,
외부 라이브러리는 버전이 오르면 이벤트 순서·기본 메타·러닝 스테이터스 사용이
달라져 **바이트가 조용히 바뀐다.** 그러면 CI의 결정성 검사가 라이브러리 업데이트
때마다 깨지고, 우리는 그것을 우리 코드의 결함과 구분할 수 없다.

SMF 포맷 0은 단순하다. 헤더 14바이트에 트랙 하나이며, 여기서 쓰는 이벤트는
템포 · 노트온 · 노트오프 · 트랙끝 넷뿐이다. **의존성을 지는 것보다 싸다.**

### 무엇을 만들지 않는가

프로그램 체인지, 벨로시티 곡선, 컨트롤 체인지를 넣지 않는다. 지금 필요한 것은
**파이프라인 관통**이지 음악적 완성도가 아니다 (GR-6.1). 음색은 재생기 기본값을 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.value_objects.key import Key, Mode

TICKS_PER_BEAT = 480
"""4분음표 하나의 틱 수. 480은 대부분의 DAW가 쓰는 값이다."""

DEFAULT_TEMPO_BPM = 96
DEFAULT_VELOCITY = 72
MIDDLE_C = 60

MAJOR_SCALE: tuple[int, ...] = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE: tuple[int, ...] = (0, 2, 3, 5, 7, 8, 10)
"""자연 단음계. 화성·가락 단음계는 도입하지 않는다 — 선택이 늘면 근거가 필요하다."""

DEGREE_INDEX: dict[str, int] = {
    "i": 0,
    "ii": 1,
    "iii": 2,
    "iv": 3,
    "v": 4,
    "vi": 5,
    "vii": 6,
}


@dataclass(frozen=True, slots=True)
class Note:
    """한 음. 시각과 길이는 틱이다."""

    pitch: int
    start_tick: int
    duration_ticks: int
    velocity: int = DEFAULT_VELOCITY

    def __post_init__(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError(f"MIDI 음높이는 0~127이다: {self.pitch}")
        if not 1 <= self.velocity <= 127:
            raise ValueError(f"벨로시티는 1~127이다: {self.velocity}")
        if self.start_tick < 0:
            raise ValueError("시작 틱은 음수일 수 없다")
        if self.duration_ticks < 1:
            raise ValueError("길이는 1틱 이상이어야 한다")

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.duration_ticks


def chord_pitches(key: Key, degree: str, *, octave_base: int = MIDDLE_C) -> tuple[int, ...]:
    """도수 표기를 절대 음높이 3화음으로 바꾼다.

    로마숫자의 대소문자는 장·단 3화음을 뜻하지만 **여기서는 조성의 음계를
    그대로 쌓는다.** 다이어토닉 3화음은 음계 위에서 한 칸 건너뛰기만 하면
    나오며, 대소문자는 그 결과를 다시 적은 것뿐이다. 대소문자로 화음 품질을
    따로 계산하면 두 진실 공급원이 생긴다.
    """
    index = DEGREE_INDEX.get(degree.lower())
    if index is None:
        raise ValueError(f"알 수 없는 도수: {degree}")

    scale = MAJOR_SCALE if key.mode is Mode.MAJOR else MINOR_SCALE
    root = octave_base + key.tonic_pitch_class
    pitches = []
    for step in (0, 2, 4):
        position = index + step
        # 음계를 넘어가면 한 옥타브 올린다. 3화음이 뒤집히지 않게 한다.
        pitches.append(root + scale[position % 7] + 12 * (position // 7))
    return tuple(pitches)


def _variable_length(value: int) -> bytes:
    """SMF 가변 길이 수량. 델타 타임과 메타 길이에 쓴다."""
    if value < 0:
        raise ValueError("가변 길이 수량은 음수일 수 없다")
    chunk = [value & 0x7F]
    value >>= 7
    while value:
        chunk.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunk))


def render_smf(
    notes: list[Note],
    *,
    tempo_bpm: int = DEFAULT_TEMPO_BPM,
    ticks_per_beat: int = TICKS_PER_BEAT,
) -> bytes:
    """노트 목록을 SMF 포맷 0 바이트로 만든다.

    **정렬 규칙이 결정성의 핵심이다.** 같은 틱에 여러 사건이 있을 때 순서가
    흔들리면 바이트가 달라진다. `(틱, 노트오프 우선, 음높이)`로 완전 정렬해
    입력 순서와 무관하게 같은 바이트가 나오도록 한다.

    노트오프를 먼저 두는 이유는 같은 음이 이어질 때 뒤 음이 앞 음의 오프에
    잘리지 않게 하기 위해서다.
    """
    if tempo_bpm < 1:
        raise ValueError("템포는 1 이상이어야 한다")
    if ticks_per_beat < 1:
        raise ValueError("틱 해상도는 1 이상이어야 한다")

    events: list[tuple[int, int, int, bytes]] = []
    for note in notes:
        events.append((note.start_tick, 1, note.pitch, bytes((0x90, note.pitch, note.velocity))))
        events.append((note.end_tick, 0, note.pitch, bytes((0x80, note.pitch, 0))))
    events.sort()

    microseconds = round(60_000_000 / tempo_bpm)
    body = bytearray()
    body += _variable_length(0)
    body += bytes((0xFF, 0x51, 0x03)) + microseconds.to_bytes(3, "big")

    previous = 0
    for tick, _, _, payload in events:
        body += _variable_length(tick - previous)
        body += payload
        previous = tick

    body += _variable_length(0) + bytes((0xFF, 0x2F, 0x00))

    header = b"MThd" + (6).to_bytes(4, "big")
    header += (0).to_bytes(2, "big")  # 포맷 0
    header += (1).to_bytes(2, "big")  # 트랙 1개
    header += ticks_per_beat.to_bytes(2, "big")
    return header + b"MTrk" + len(body).to_bytes(4, "big") + bytes(body)
