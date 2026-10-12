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

프로그램 체인지, **벨로시티 곡선**, 컨트롤 체인지를 넣지 않는다. 음색은 재생기
기본값을 쓴다.

**층별 세기는 다르다** (D-0174). 곡선이 아니라 층마다 상수 하나이며, 그것이 없으면
가락과 반주가 같은 층에서 울린다 — 귀가 *"반주가 앞에서 논다"*로 판정했다.
"""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.value_objects.key import Key, Mode

TICKS_PER_BEAT = 480
"""4분음표 하나의 틱 수. 480은 대부분의 DAW가 쓰는 값이다."""

DEFAULT_TEMPO_BPM = 130
"""기본 템포 (BPM). **코퍼스 전수의 중앙값이고 `measured.toml`이 정본이다** (D-0397).

참조곡에서 박을 읽으면 그 값을 쓰고(D-0392), **못 읽을 때만 여기로 떨어진다.**

이 수는 `[onset.counts].bpm_folded_median`과 같아야 하며 `measured.py`가 대조한다 —
**임포트하지 않고 글자로 읽는다.** 도메인이 `measured.toml`을 알면 계층이 깨진다.

**배수 모호성을 읽을 때 푼다.** 사람도 120을 60으로 짚으며 `Beat`가 그것을 결함이
아니라 성질이라 적었다 (D-0054). `OCTAVE_FLOOR` 아래를 두 배로 읽은 뒤 중앙값을 낸다.

### 96 → 126 → 130

96은 근거 없이 놓여 있었고 **코퍼스 분포의 8% 지점**이었다 (D-0206). 126은 그때
사람이 옮겨 적은 수이고, **같은 측정을 두고 수가 네 곳에서 달랐다** — 여기 적혀
있던 「1003곡 실측」·「200곡 중 못 찾은 곡 없음」·「드럼 스템에서 뽑았고」가 전부
실물과 달랐다 (D-0395 · D-0397). 130은 **도구가 센 수다.**
"""
DEFAULT_VELOCITY = 72
MIDDLE_C = 60

DYNAMICS: dict[str, int] = {"pp": 32, "p": 48, "mp": 64, "mf": 80, "f": 96, "ff": 112}
"""여린소리표와 벨로시티 (D-0174). **밖에서 온 격자다.**

`TICKS_PER_BEAT = 480`이 DAW 관행인 것과 같은 자리이며 기보 프로그램이 쓰는 눈금
그대로다. **맞추는 값이 아니다** — 이 표를 실험으로 옮기면 그 순간 D-0058이다.

층에 어느 표를 줄지는 **코드에 이미 적힌 역할을 따른다** — 가락이 전경(D-0141),
베이스가 받침(D-0139), 화음이 배경(D-0137)이다. 새로 판단하지 않는다.
"""

METRIC_STRESS: tuple[int, ...] = (0, 2, 1, 2)
"""4/4의 **강 · 약 · 중 · 약** (D-0177). 값은 `DYNAMICS`에서 내릴 칸 수다.

**밖에서 온 것이다** — 박자 강세는 음악 이론의 표준이고 `BEATS_PER_BAR = 4`가 이미
그 격자를 쓰고 있다. 맞추는 값이 아니다.

**내리기만 한다.** 강박을 올리면 곡 전체가 세지는데, 귀가 이미 *"소리가 크고
거슬린다"*로 판정했다 (D-0174). 올릴 근거가 없다.
"""


OFFBEAT_STRESS = max(METRIC_STRESS) + 1
"""**박 사이는 어느 박보다 여리다** (D-0402).

새 표를 손으로 적지 않는다 (D-0043) — `METRIC_STRESS`에서 **한 칸 더 내린 자리**이고,
그것이 8분 격자의 음악 표준이다: 강 · (사이) · 중 · (사이) …
"""

EIGHTH_STRESS: tuple[int, ...] = tuple(
    one for stress in METRIC_STRESS for one in (stress, OFFBEAT_STRESS)
)
"""8분 여덟 자리의 강세 — `(0, 3, 2, 3, 1, 3, 2, 3)`.

**`METRIC_STRESS`에서 끌어낸다.** 두 벌로 적으면 어긋나고, 그때 어느 쪽이 참인지
아무도 모른다 (D-0043 · GR-0.7).
"""


def softer(level: int, steps: int) -> int:
    """여린소리표에서 `steps`칸 아래. **표 밖으로 안 나간다.**

    한 층 안에서 세기가 전부 같으면 **초보가 모든 음을 같은 힘으로 치는 소리**가
    난다 — D-0177이 귀에서 받은 판정이 그것이다. 층 사이는 D-0174가 갈랐고 여기서
    층 안을 가른다.

    표의 맨 아래보다 더 내려가면 맨 아래에 머문다. **문턱이 아니라 표의 끝이다.**
    """
    ladder = sorted(DYNAMICS.values())
    if level not in ladder:
        raise ValueError(f"여린소리표 밖의 세기다: {level}")
    return ladder[max(0, ladder.index(level) - steps)]


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
    channel: int = 0
    """어느 층인가 (D-0405). **역할이 곧 채널이다** — `VOICES`가 악기를 준다.

    기본이 0인 것은 **예전 노트가 그대로 돌게** 하기 위해서다. 0은 가락이고,
    층을 안 적는 부름은 전경으로 난다."""

    def __post_init__(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError(f"MIDI 음높이는 0~127이다: {self.pitch}")
        if not 0 <= self.channel <= 15 or self.channel == DRUM_CHANNEL:
            raise ValueError(f"채널은 0~15이고 {DRUM_CHANNEL}은 타악 전용이다: {self.channel}")
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


DRUM_CHANNEL = 9
"""GM이 타악에 못 박아 둔 채널. **밖에서 온 격자다** — 여기에 피아노를 넣으면 북이 난다."""

VOICES: dict[int, tuple[str, int]] = {
    0: ("가락", 0),
    1: ("배경", 4),
    2: ("받침", 33),
}
"""채널 → (층 이름, **GM 프로그램 번호**) (D-0405 · O-51).

세 층은 **코드에 이미 있었다** — 전경(D-0141) · 배경(D-0137) · 받침(D-0139). 그런데
`program_change`를 안 써서 **재생기 기본값으로 셋 다 피아노로 났다.** 사람이 세 번
물었고(*«베이스가 내가 아는 그 콘트라베이스?»*), **층이 안 갈리면 귀가 판정을 못 한다.**

번호는 GM 표준이다 — 0 어쿠스틱 피아노 · 4 일렉트릭 피아노 · 33 핑거 베이스.
**어느 층에 무슨 악기인지는 취향이고 이 표가 그 취향의 전부다** (O-51 · 닫힘 D-0405). 바꾸려면
여기 셋을 고치면 되고, **고르기 쉬운 자리에 둔 것이 이 판의 요점이다.**
"""


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
        on, off = 0x90 | note.channel, 0x80 | note.channel
        events.append((note.start_tick, 1, note.pitch, bytes((on, note.pitch, note.velocity))))
        events.append((note.end_tick, 0, note.pitch, bytes((off, note.pitch, 0))))
    events.sort()

    microseconds = round(60_000_000 / tempo_bpm)
    body = bytearray()
    body += _variable_length(0)
    body += bytes((0xFF, 0x51, 0x03)) + microseconds.to_bytes(3, "big")

    # **쓰는 층에만 악기를 준다** (D-0405). 안 쓰는 채널까지 적으면 바이트가 늘고,
    # 늘어난 바이트는 **아무 소리도 안 낸다.**
    for channel in sorted({note.channel for note in notes}):
        body += _variable_length(0)
        body += bytes((0xC0 | channel, VOICES[channel][1]))

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
