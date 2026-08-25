"""파일 길이 래칫 도구를 **검사한다** (D-0117).

### 왜 이 파일이 따로 있는가

`make check`가 매번 부르는 도구는 그 자신이 검사받아야 한다 — D-0080이
`sync_decision_index.py`에 대해 세운 규율이고 여기도 같다.

**검사마다 일부러 결함을 만들어 빨갛게 뜨는지 본다** (GR-0.9). 래칫은 아무것도
안 물어도 늘 초록이라 **고장을 눈으로 알아챌 수 없다.**

### 왜 `core/tests`에 있는가

도구는 `tools/`에 있고 하네스는 `core/`에 있다. `sys.path` 한 줄이 하네스를 하나 더
만드는 것보다 싸다 (D-0080과 같은 판단).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import check_file_size as tool


@pytest.fixture
def pinned() -> Iterator[dict[str, int]]:
    """**빈 예외표에서 시작한다.** 검사 안에서만 바꾸고 파일은 건드리지 않는다.

    실제 예외를 남겨 두면 검사가 만든 가짜 파일 옆에서 그것들이 전부 "사라진
    파일"로 잡혀, 무엇을 재는 검사인지 알 수 없게 된다.
    """
    original = dict(tool.EXCEPTIONS)
    tool.EXCEPTIONS.clear()
    yield tool.EXCEPTIONS
    tool.EXCEPTIONS.clear()
    tool.EXCEPTIONS.update(original)


def test_저장소가_지금_규약과_맞다():
    """**이 검사가 곧 `make check`의 size 단계다.**"""
    assert tool.check(tool.measure()) == []


def test_못_박은_파일이_늘면_잡는다(pinned):
    pinned["core/hathor/x.py"] = 100
    problems = tool.check({"core/hathor/x.py": 101})
    assert len(problems) == 1
    assert "늘었다" in problems[0]


def test_못_박은_파일이_줄어도_잡는다(pinned):
    """**래칫은 양방향이다** (D-0117).

    상한만 보면 예외값에 영원히 머문다. 줄었을 때 실패시켜야 톱니가 내려간다.
    """
    pinned["core/hathor/x.py"] = 100
    problems = tool.check({"core/hathor/x.py": 99})
    assert len(problems) == 1
    assert "--update" in problems[0]


def test_못_박은_값_그대로면_통과한다(pinned):
    pinned["core/hathor/x.py"] = 100
    assert tool.check({"core/hathor/x.py": 100}) == []


def test_예외표에_없는_새_파일은_기본_상한을_받는다(pinned):
    pinned.clear()
    limit = tool.LIMITS["code"]
    assert tool.check({"core/hathor/x.py": limit}) == []
    problems = tool.check({"core/hathor/x.py": limit + 1})
    assert len(problems) == 1
    assert "상한" in problems[0]


def test_테스트는_상한이_따로다(pinned):
    """테스트는 합성 자료가 길어 코드와 같은 상한을 받을 수 없다."""
    pinned.clear()
    assert tool.LIMITS["test"] > tool.LIMITS["code"]
    assert tool.check({"core/tests/unit/x.py": tool.LIMITS["code"] + 1}) == []
    assert tool.check({"core/tests/unit/x.py": tool.LIMITS["test"] + 1}) != []


def test_대상_밖_파일은_보지_않는다(pinned):
    """`docker/`나 `infra/`의 파이썬은 규약 대상이 아니다."""
    pinned.clear()
    assert tool.kind_of("docker/mlflow/build.py") is None
    assert tool.check({"docker/mlflow/build.py": 9999}) == []


def test_사라진_파일이_예외표에_남아_있으면_잡는다(pinned):
    """**쪼갠 뒤 표를 안 지우면 래칫이 그 자리에 멈춘다.**"""
    pinned["core/hathor/사라짐.py"] = 100
    problems = tool.check({})
    assert any("예외표에 없는 파일" in problem for problem in problems)


def test_예외표를_다시_그리면_상한_초과분만_남는다():
    """`render`가 기본 상한 아래로 내려온 파일을 표에서 지운다."""
    body = tool.render(
        {
            "core/hathor/큰.py": tool.LIMITS["code"] + 1,
            "core/hathor/작은.py": 10,
            "core/tests/unit/큰.py": tool.LIMITS["test"] + 1,
            "core/tests/unit/작은.py": tool.LIMITS["code"] + 1,
        }
    )
    assert "core/hathor/큰.py" in body
    assert "core/tests/unit/큰.py" in body
    assert "작은.py" not in body


def test_경로는_항상_슬래시다():
    """**윈도우에서 `\\`가 나오면 예외표가 기기마다 다르게 읽힌다** (D-0009)."""
    assert all("\\" not in name for name in tool.measure())
    assert all("\\" not in name for name in tool.EXCEPTIONS)


def test_말없이_예외값을_올릴_수_없다(pinned, tmp_path, monkeypatch, capsys):
    """**막지 않으면 래칫이 아니다** (D-0118).

    "늘었다"가 떠도 `make resize` 한 번이면 사라진다면 상한만 있는 것과 같다.
    """
    scratch = tmp_path / "check_file_size.py"
    scratch.write_text(tool.SELF.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tool, "SELF", scratch)
    monkeypatch.setattr(tool, "measure", lambda: {"core/hathor/x.py": 900})
    pinned["core/hathor/x.py"] = 800
    before = scratch.read_text(encoding="utf-8")

    assert tool.update(allow_growth=False) == 1
    assert scratch.read_text(encoding="utf-8") == before
    assert "래칫은 기본으로 이것을 막는다" in capsys.readouterr().err

    assert tool.update(allow_growth=True) == 0
    assert '"core/hathor/x.py": 900' in scratch.read_text(encoding="utf-8")


def test_줄어든_것은_말없이_내린다(pinned, tmp_path, monkeypatch):
    """내리는 방향은 막지 않는다. **톱니가 내려가는 것이 목적이다.**"""
    scratch = tmp_path / "check_file_size.py"
    scratch.write_text(tool.SELF.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tool, "SELF", scratch)
    monkeypatch.setattr(tool, "measure", lambda: {"core/hathor/x.py": 700})
    pinned["core/hathor/x.py"] = 800

    assert tool.update(allow_growth=False) == 0
    assert '"core/hathor/x.py": 700' in scratch.read_text(encoding="utf-8")


def test_예외표_표식이_살아_있다():
    """`--update`가 표를 못 찾으면 조용히 아무것도 안 한다."""
    assert tool.BLOCK.search(tool.SELF.read_text(encoding="utf-8")) is not None
