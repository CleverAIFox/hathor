#!/usr/bin/env python3
"""`deadcheck`의 **양성 대조** — 결함을 심은 합성 트리에서 프로브가 우는가 (D-0444).

### 왜 떼어 냈나

`deadcheck.py`가 일곱째 프로브를 받으며 **601줄로 상한을 넘겼다.** 못을 올리는 대신
쪼갠다 (D-0117). 가르는 선은 **관문이냐 아니냐**다 — `--ratchet`은 실물 저장소를 보고,
여기 있는 것은 **임시 트리를 짓는 기계**라 관문 경로가 아니다.

**실제 저장소에서 0건인 것은 «깨끗하다»이지 «프로브가 죽었다»가 아니다** (D-0259).
그 둘을 가르는 자리가 여기다.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from deadcheck import PROBES, TEST_TREE, unreadable


def _plant(folder: Path) -> None:
    """프로브마다 결함 하나씩을 심은 합성 트리. **여기서 안 울면 프로브가 죽은 것이다.**"""
    tests = folder / TEST_TREE
    tests.mkdir(parents=True)
    (tests / "test_planted.py").write_text(
        "import pytest\n\n\n"
        "def test_아무것도_안_본다():\n"
        "    value = 1 + 1\n"
        "    print(value)\n\n\n"
        "@pytest.mark.skipif(True, reason='심은 것')\n"
        "def test_건너뛴다():\n"
        "    assert True\n\n\n"
        # **이름 뒤에 숨은 건너뜀도 심는다** (D-0289). 이 꼴을 프로브가 한 건도 못 봤고,
        # 양성 대조는 인라인만 심고 있어서 **죽은 가지를 초록으로 덮고 있었다.**
        "필요하다 = pytest.mark.skipif(True, reason='이름 뒤에 숨었다')\n\n\n"
        "@필요하다\n"
        "def test_이름_뒤에_숨어_건너뛴다():\n"
        "    assert True\n\n\n"
        # **조건이 적혀 있는데 늘 통과한다** (D-0444). `무검증 시험`은 `assert`가
        # 있어서 못 잡고, 읽는 사람은 왼쪽 조건이 검사되는 줄 안다.
        "def test_늘_통과한다():\n"
        "    assert 1 == 2 or True\n",
        encoding="utf-8",
    )
    code = folder / "tools"
    code.mkdir(parents=True)
    (code / "planted.py").write_text(
        "FILES = ('tools/xxx-없는파일.py',)\n"
        '"""붙는 문서 문자열 — 이것은 정상이다."""\n'
        '"""심은 것 — 대입 뒤 둘째 문자열은 파이썬이 버린다."""\n\n\n'
        "def run() -> None:\n"
        "    try:\n"
        "        open('x')\n"
        "    except OSError:\n"
        "        pass\n\n\n"
        # **늘 참인 조건을 심는다** (D-0349). 이 꼴이 실물에서 세 번 났고 그중 둘은
        # **가지가 한 번도 안 도는** 꼴이었다 — 어떤 수 눈금에도 안 걸린다.
        "def blind(name: str) -> bool:\n"
        '    return name.startswith("")\n',
        encoding="utf-8",
    )


def planted_unreadable() -> list[str]:
    """**양성 대조** (D-0275). 어느 파이썬도 못 읽는 파일을 심어 `unreadable`이 우는지 본다."""
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw)
        (folder / "tools").mkdir(parents=True)
        (folder / "tools" / "broken.py").write_text("def (:\n", encoding="utf-8")
        return unreadable(folder)


def positive_control() -> list[str]:
    """심은 결함에 안 우는 프로브의 이름. 비어야 살아 있다."""
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw)
        _plant(folder)
        return [name for name, probe in PROBES.items() if not probe(folder)]
