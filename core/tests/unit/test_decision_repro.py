"""`재현` 절의 명령이 그대로 돌아가는가 (D-0431).

`test_check_decisions`에서 떼어 왔다. 그 파일이 700줄 상한을 넘었고 **못을 올리는
대신 쪼갰다** (D-0117 · D-0427과 같은 자리).

**틀린 안내는 안내가 없는 것보다 나쁘다** (D-0292). `재현`은 **여기서 다시 낼 수
있다**는 약속인데, 그 자리의 명령이 `command not found`로 끝나면 읽는 사람은
**기록이 아니라 저장소를 의심한다.**
"""

from __future__ import annotations

import sys

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import check_decisions as tool
import decision_ledger as ledger


def _record(body: str, number: int = 431) -> tool.Record:
    """본문을 통째로 주는 가짜 기록 하나."""
    return ledger.Record(identifier=f"D-{number:04d}", number=number, title="카나리아", body=body)


def _repro(number: int, line: str) -> list[tool.Record]:
    """`재현` 한 줄만 바꾼 가짜 기록 하나."""
    return [_record(f"- **배경**: 카나리아.\n\n재현\n{line}\n\n자료  해당 없음\n", number)]


def test_그대로_안_도는_재현을_잡는다():
    """**`hathor …`에는 콘솔 스크립트가 없다** (D-0431).

    세 기록이 그 짧은 꼴로 적혀 있었고 사람이 그대로 쳐서 `command not found`를 봤다.
    **틀린 안내는 안내가 없는 것보다 나쁘다** (D-0292).
    """
    bad = tool.check_runnable(_repro(431, "    hathor doctor"))
    pasted = _record(
        "- **배경**: 터미널을 그대로 붙였다.\n\n"
        "      hathor doctor\n      hathor: command not found\n\n"
        "재현\n    cd core && uv run python -m hathor.cli doctor\n"
    )
    quoted = tool.check_runnable([pasted])
    good = tool.check_runnable(_repro(431, "    cd core && uv run python -m hathor.cli doctor"))

    assert bad, "안 도는 명령인데 안 운다"
    assert quoted == [], "배경에 붙인 터미널 출력을 명령으로 읽었다"
    assert "hathor.cli" in bad[0], "돌아가는 꼴을 안 알려 준다"
    assert good == []


def test_소급_바닥_앞은_안_건다():
    """**GR-0.2는 «고쳐 쓰지 않고 새 번호로 정정한다»다** (D-0351과 같은 규율).

    앞의 셋을 소급해 고치면 추가 전용이 깨진다 — 정정은 D-0431의 본문이 한다.
    """
    old = tool.check_runnable(_repro(tool.RUNNABLE_FROM - 1, "    hathor doctor"))

    assert old == [], "소급 바닥 앞을 건드렸다"


def test_지금_저장소가_바닥_뒤로는_깨끗하다():
    """**0이어야 정상인 축이다** — 새 기록이 짧은 꼴로 들어오면 여기서 빨개진다."""
    records = tool.scan_records(tool.merge_parts(tool.load_parts()))

    assert tool.check_runnable(records) == []
