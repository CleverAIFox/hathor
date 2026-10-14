"""쌍대비교 응답을 받는 자리 (O-10 · D-0012).

### 왜 따로 떼었나

**모르는 키가 판정으로 저장되고 있었다.** `1`·`2`·`q`가 아니면 전부 «건너뜀»이었고,
건너뜀도 기록이라 `exclude`에 들어가 **그 쌍은 다시 안 나온다.** 오타 한 번에 평가
집합에서 쌍 하나가 영구히 빠진다.

실측으로 확인했다 — 곡 5개(쌍 10개)에 `1` · `x` · `2`를 넣으면 «응답 2, 건너뜀 1»이
되고 다음 출제가 **7개**다. `x`는 아무 뜻도 아니었는데 판정 모양의 기록이 남았다.

**라벨이 이 프로젝트에서 가장 비싼 자원이다.** 모델도 가중치도 다시 받으면 되고
배치도 79분이면 다시 돈다. 사람이 누른 것만 다시 못 만든다. 그래서 **모르는 입력은
받지 않고 다시 묻는다** — 건너뜀은 `s`를 **일부러 눌렀을 때만** 기록된다.

`main.py`에 두지 않는 이유는 D-0250과 같다 — 그 파일은 이미 §3의 빚이다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - 형만 쓴다
    from collections.abc import Callable

PICK_LEFT = "1"
PICK_RIGHT = "2"
SKIP = "s"
QUIT = "q"

ANSWERS = (PICK_LEFT, PICK_RIGHT, SKIP, QUIT)
"""받는 입력 **전부**. 여기 없으면 기록하지 않고 다시 묻는다."""

RETRY = f"  {' · '.join(ANSWERS)} 중 하나를 누른다."
"""다시 물을 때 보여 주는 줄. **무엇이 틀렸는지 말한다** (D-0203)."""


def read_answer(
    ask: Callable[[str], str],
    say: Callable[[str], None],
    prompt: str = "  > ",
) -> str:
    """`ANSWERS` 중 하나가 나올 때까지 다시 묻는다.

    **EOF는 `q`다.** 파이프로 몰아 넣거나 터미널이 끊기면 입력이 영원히 안 오는데,
    거기서 다시 묻기를 반복하면 **멈추지 않는다.**

    대소문자와 앞뒤 공백은 흡수한다 — ` 1 `을 오타로 보는 것은 사람 탓이 아니다.
    """
    while True:
        try:
            answer = ask(prompt).strip().lower()
        except EOFError:
            return QUIT
        if answer in ANSWERS:
            return answer
        say(RETRY)
