"""뒤처리가 **아무것도 안 바꿔도 된다** (D-0387).

D-0377의 반대 실수를 막는 자리다. 그 판은 뒤처리 산출물을 `EXPECTED`에 더하고
**담지는 않아서** 커밋이 낡았고(D-0379가 고쳤다), 이번에는 더하기만 해서
**«바뀌어야 한다»가 됐다** — 뒤처리가 결정적이면 같은 내용이 다시 쓰이고 git은
변경으로 안 본다. 실측: D-0384~0386 합본이 생성기를 하나도 안 건드려
`site/proposal.lock.json`이 그대로였고, 받는 쪽이 *«패치에만: …»*으로 막혔다.

**새 파일로 둔다.** `test_apply_patch.py`는 708줄이고 여기까지 담으면 못을 넘는다
(D-0257). 옛 기록의 강제자가 저 파일의 함수를 가리키므로 **옛 시험은 안 옮긴다** —
옮기면 `check_decisions`가 *«강제자가 없는 함수를 가리킨다»*로 운다.

`SCRIPT`와 `_slice`는 **저쪽이 정본이다** (D-0117 · D-0043).
"""

from __future__ import annotations

import shlex
import subprocess

from hathor.shared.config.paths import repo_root
from tests.unit.test_apply_patch import SCRIPT, _slice


def _weigh(expected: str, actual: str, after_paths: str) -> subprocess.CompletedProcess[str]:
    """선언 ↔ 실제 대조 블록만 돌린다. 세 목록을 **직접 준다.**"""
    block = _slice('WEIGHED="$(comm -23')
    script = (
        f"PATCH=x.patch\nMESSAGE=제목\n"
        f"EXPECTED={shlex.quote(expected)}\n"
        f"ACTUAL={shlex.quote(actual)}\n"
        f"AFTER_PATHS={shlex.quote(after_paths)}\n{block}"
    )
    return subprocess.run(
        ["bash", "-c", script],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


BOTH = "site/proposal.docx\nsite/proposal.lock.json"
"""뒤처리가 낼 수 있는 경로 둘. **제출본은 zip이라 늘 바뀌고 자물쇠는 안 바뀔 수 있다.**"""


def test_뒤처리가_아무것도_안_바꿔도_통과한다() -> None:
    """**이 판이 막힌 자리다** (D-0387). 생성기를 안 건드리면 자물쇠는 그대로다."""
    done = _weigh(
        expected=f"docs/MASTER.md\n{BOTH}",
        actual="docs/MASTER.md\nsite/proposal.docx",
        after_paths=BOTH,
    )

    assert done.returncode == 0, done.stderr


def test_뒤처리가_바꾸면_그것도_통과한다() -> None:
    """**양쪽에서 빼므로 있어도 없어도 된다.** 그것이 「선택」의 뜻이다."""
    done = _weigh(
        expected=f"docs/MASTER.md\n{BOTH}", actual=f"docs/MASTER.md\n{BOTH}", after_paths=BOTH
    )

    assert done.returncode == 0, done.stderr


def test_섞인_작업은_여전히_막는다() -> None:
    """**심은 결함** (D-0069 · GR-0.8). 넓히다가 그물을 뚫으면 D-0376 이전이다."""
    done = _weigh(
        expected="docs/MASTER.md",
        actual="docs/MASTER.md\n남의작업.py",
        after_paths="site/proposal.docx",
    )

    assert done.returncode == 1
    assert "트리에만:  남의작업.py" in done.stderr, done.stderr


def test_선언했는데_안_바뀌면_막는다() -> None:
    """**뒤처리 경로가 아닌 것은 그대로 본다.** 면제가 옆을 깨면 그 면제가 틀렸다."""
    done = _weigh(
        expected="docs/MASTER.md\ndocs/PLAN.md",
        actual="docs/MASTER.md",
        after_paths="site/proposal.docx",
    )

    assert done.returncode == 1
    assert "패치에만:  docs/PLAN.md" in done.stderr, done.stderr


def test_담을_때는_뒤처리_경로를_안_뺀다() -> None:
    """**담기는 `EXPECTED`를 그대로 쓴다** (D-0379). 뺐다가는 또 낡은 커밋이 된다."""
    body = SCRIPT.read_text(encoding="utf-8")
    staging = body[body.index("D-0377은 뒤처리 산출물을") : body.index("커밋했는데 트리가")]

    assert '"$EXPECTED"' in staging, "담기가 좁혀진 목록을 쓴다 — D-0379로 되돌아간다"
    assert "WEIGHED" not in staging, "견주는 목록으로 담는다"
