"""현재형 문서가 적은 `hathor` 명령이 실재하는가 (D-0310).

**D-0292가 같은 자리를 산출물 대장에서 잡았다** — 선언 20개 중 둘이 죽어 있었고
(`ingest lyrics` · `ingest features --layers`) 매 `make ship`마다 찍히고 있었다. 그때
`test_대장의_재생성_명령이_실재한다`를 세웠는데 **그 그물은 `artifacts.toml`만 덮었다.**

**같은 실수가 문서에서 또 났다.** D-0309가 PLAN 빚 행에 `eval order`를 적었고 그런
명령은 없다 — 실물은 `eval harmony-order`다. 더 나쁜 것은 **D-0292 자신이 그 대조표를
들고 있었다**는 것이다 (`| eval order | eval harmony-order |`). 적어 두고 또 틀렸다.

### `DECISIONS.md`는 안 본다

과거 기록에는 틀린 명령이 *"틀렸다"*는 맥락으로 실려 있다 — D-0292의 대조표가 그것이다.
거기까지 물면 **거짓 경보가 쏟아지고, 거짓 경보는 진짜 경보를 죽인다** (`fire-lane`
MASTER §18-13). `doc_fsck.LIVING`이 이미 같은 이유로 셋만 본다.

### `make docs`가 아니라 `make test`가 든다

등재표를 읽으려면 `build_parser()`를 불러야 하고 그것은 `numpy`를 끈다. 문서 검사는
빨라야 하므로 **이미 그 환경이 서 있는 시험 쪽**이 든다.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import cli_paths, dead_commands

ROOT = Path(__file__).resolve().parents[3]

LIVING = ("README.md", "docs/MASTER.md", "docs/PLAN.md")
"""**지금을 말하는 문서만 본다.** `doc_fsck.LIVING`과 같은 셋이다 — 한 값이 두 곳에
살지만, 도구는 `tools/`에 있고 이 시험은 `core/`에 있어 서로를 못 읽는다. **다르면 이
시험이 깨지므로** 어긋난 채로는 못 간다 (`test_살아_있는_문서_목록이_같다`)."""

CALL = re.compile(r"`([^`\n]+)`")
"""백틱 한 쌍 안의 내용. **줄바꿈은 안 넘는다** — 여러 줄 예시를 한 덩어리로 삼키면
첫 낱말만 보는 판정이 뒤 줄을 못 본다.

**골라 내지 않고 다 넘긴다.** `dead_commands`가 첫 낱말이 등재된 무리인지 먼저 보고
아니면 조용히 넘긴다 (D-0292) — 경로도 산문도 여기서 걸러진다. 문서에는 두 꼴이 다
있다: `hathor eval retrieval`처럼 접두가 붙은 것과 **`eval order`처럼 명령만 적은 것**.
D-0309가 틀린 것이 후자였다."""


def _calls(text: str) -> list[str]:
    return [found.strip() for found in CALL.findall(text)]


def test_현재형_문서의_명령이_실재한다() -> None:
    """**틀린 안내가 안내 없는 것보다 나쁘다** (D-0292 · D-0310).

    사람은 문서에 적힌 명령을 그대로 친다. 없는 명령이면 `argparse`가 «invalid choice»를
    내고, 읽는 사람은 **자기가 뭘 잘못했는지 찾기 시작한다.**
    """
    problems = [
        f"{name}: {why}"
        for name in LIVING
        if (ROOT / name).exists()
        for call in _calls((ROOT / name).read_text(encoding="utf-8"))
        for why in dead_commands(call)
    ]
    assert not problems, "현재형 문서가 없는 명령을 안내한다:\n" + "\n".join(problems)


def test_그물이_비지_않았다() -> None:
    """**세는 그물이 비면 «전부 맞다»가 거짓으로 참이 된다** (D-0230).

    정규식이 아무것도 못 잡으면 위 시험은 영원히 통과한다.
    """
    found = [
        call
        for name in LIVING
        if (ROOT / name).exists()
        for call in _calls((ROOT / name).read_text(encoding="utf-8"))
    ]
    assert len(found) >= 5, f"현재형 문서에서 `hathor` 명령을 {len(found)}개만 찾았다"


def test_없는_명령을_실제로_잡는다() -> None:
    """**아무것도 못 잡는 검사는 늘 통과하는 하네스와 같다** (GR-0.9 · D-0071).

    `eval order`가 D-0309가 적은 그 명령이고, `eval harmony-order`가 실물이다.
    """
    assert dead_commands("eval order")
    assert dead_commands("eval harmony-order") == []
    # 손잡이도 본다 — `ingest features --layers`가 D-0292가 잡은 꼴이다.
    assert dead_commands("eval chord-quality --stem mix") == []
    assert dead_commands("eval chord-quality --없는손잡이")


def test_산문은_명령으로_안_읽는다() -> None:
    """«hathor가 기획자라»는 명령이 아니다. **오탐은 사람이 검사를 끄게 만든다.**"""
    assert dead_commands("hathor") == [], "프로젝트 이름은 명령이 아니다"
    assert dead_commands("core/hathor/interfaces/cli/main.py") == [], "경로는 명령이 아니다"
    assert dead_commands("D-0181") == [], "결정 번호는 명령이 아니다"
    assert _calls("hathor eval order") == [], "백틱 밖은 안 본다"
    assert _calls("`hathor eval retrieval`") == ["hathor eval retrieval"]


def test_살아_있는_문서_목록이_같다() -> None:
    """`doc_fsck.LIVING`과 이 파일의 `LIVING`이 어긋나면 한쪽이 덜 본다."""
    from tests.conftest import tool_module

    assert tuple(tool_module("doc_fsck").LIVING) == LIVING


def test_지금_등재표에_그_명령들이_있다() -> None:
    """**강제자다.** 이 시험이 무엇을 대조하는지 눈으로 볼 수 있어야 한다."""
    known = cli_paths()
    assert "eval harmony-order" in known
    assert "eval order" not in known
    assert "generate" in known
