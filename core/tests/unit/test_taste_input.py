"""쌍대비교 응답 받기 (O-10 · D-0012 · D-0419).

### 왜 이 시험이 생겼나

**오타 한 번이 쌍 하나를 영구히 태웠다.** `1`·`2`·`q`가 아니면 전부 «건너뜀»으로
저장됐고, 건너뜀도 기록이라 다음 출제에서 `exclude`에 들어간다.

실측으로 봤다 — 곡 5개(쌍 10개)에 `1` · `x` · `2`를 넣으니 «응답 2, 건너뜀 1»이고
다음 출제가 **7개**였다. `x`는 아무 뜻도 아니었다.

**라벨은 다시 못 만든다.** 가중치는 다시 받으면 되고 배치는 79분이면 다시 돈다
(D-0417). 사람이 누른 것만 복구가 없다.
"""

from __future__ import annotations

import pytest

from hathor.interfaces.cli.taste_input import ANSWERS, QUIT, RETRY, read_answer

CEILING = 20
"""한 시험이 물을 수 있는 횟수의 천장.

**«EOF에서 계속 묻는다»로 바꿔 봤더니 시험이 실패하지 않고 매달렸다.** 매달리는
시험은 실패하는 시험보다 나쁘다 — CI가 타임아웃까지 돌고 무엇이 틀렸는지 안 알려
준다 (GR-0.8). 천장이 그 변이를 **빠른 실패**로 바꾼다.
"""


class _Keyboard:
    """정해진 순서로 답하고, 바닥나면 `EOFError`를 낸다 — 실제 터미널과 같다."""

    def __init__(self, *keys: str) -> None:
        self._keys = list(keys)
        self.asked = 0
        self.said: list[str] = []

    def ask(self, prompt: str) -> str:
        del prompt
        self.asked += 1
        assert self.asked <= CEILING, f"{CEILING}번을 넘게 물었다 — 안 멈춘다"
        if not self._keys:
            raise EOFError
        return self._keys.pop(0)

    def say(self, line: str) -> None:
        self.said.append(line)


@pytest.mark.parametrize("key", ANSWERS)
def test_아는_키는_그대로_돌려준다(key: str) -> None:
    """네 가지 전부 받는다. **하나라도 빠지면 그 기능이 사라진다.**"""
    keyboard = _Keyboard(key)

    assert read_answer(keyboard.ask, keyboard.say) == key
    assert keyboard.asked == 1
    assert keyboard.said == [], "아는 키인데 잔소리를 했다"


def test_모르는_키는_기록하지_않고_다시_묻는다() -> None:
    """**이것이 이 파일이 있는 이유다** (D-0419).

    `x`가 «건너뜀»으로 저장되면 그 쌍은 `exclude`에 들어가 **다시 안 나온다.**
    """
    keyboard = _Keyboard("x", "ㅁ", "", "2")

    assert read_answer(keyboard.ask, keyboard.say) == "2"
    assert keyboard.asked == 4, "다시 안 물었다"
    assert keyboard.said == [RETRY] * 3


def test_빈_입력도_건너뜀이_아니다() -> None:
    """**엔터만 친 것은 판정이 아니다.** 줄 넘김 하나로 쌍이 타면 안 된다."""
    keyboard = _Keyboard("", "s")

    assert read_answer(keyboard.ask, keyboard.say) == "s"
    assert keyboard.said == [RETRY]


def test_대소문자와_공백은_흡수한다() -> None:
    """` S `를 오타로 보는 것은 사람 탓이 아니다."""
    keyboard = _Keyboard(" S ")

    assert read_answer(keyboard.ask, keyboard.say) == "s"
    assert keyboard.said == []


def test_입력이_끊기면_멈춘다() -> None:
    """**EOF에서 다시 물으면 안 멈춘다** — 파이프나 끊긴 터미널에서 무한 반복이다."""
    keyboard = _Keyboard()

    assert read_answer(keyboard.ask, keyboard.say) == QUIT
    assert keyboard.asked == 1


def test_모르는_키_뒤에_끊겨도_멈춘다() -> None:
    """두 방어가 **같이** 서야 한다 — 다시 묻기가 EOF를 잡아먹으면 안 멈춘다."""
    keyboard = _Keyboard("x")

    assert read_answer(keyboard.ask, keyboard.say) == QUIT
    assert keyboard.asked == 2
    assert keyboard.said == [RETRY]
