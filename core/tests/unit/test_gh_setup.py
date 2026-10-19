"""저장소 설정을 켜는 자리 (D-0226 · D-0427).

**설정은 코드가 아니라서 검사가 못 본다.** `check_secrets`도 `doc_fsck`도 GitHub
설정을 모른다 — 그래서 **켜는 자리를 명령에 두는 것이 유일한 못이다.**

`test_hygiene`에서 떼어 왔다 (D-0427). 그 파일이 700줄 상한을 넘었고, **못을
올리는 대신 쪼갰다** (D-0117).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import gh_ops  # noqa: E402


class _Gh:
    """`gh`의 자리. **무엇을 어떤 인자로 불렀는지**가 이 검사의 자료다."""

    def __init__(self, now: dict[str, object]) -> None:
        self.now = now
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *arguments: str, check: bool = True) -> str:
        del check
        self.calls.append(arguments)
        if arguments[:2] == ("repo", "view"):
            return "CleverAIFox/hathor\n"
        if arguments[0] == "api" and "-X" not in arguments:
            return json.dumps(self.now)
        return ""

    def put(self) -> tuple[str, ...]:
        (one,) = [call for call in self.calls if "-X" in call]
        return one


def _ran(monkeypatch: pytest.MonkeyPatch, now: dict[str, object]) -> tuple[_Gh, str]:
    fake = _Gh(now)
    monkeypatch.setattr(gh_ops, "gh", fake)
    return fake, gh_ops.actions_can_open_pulls()


def test_전역_쓰기를_안_켠다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**한 줄 고치러 와서 다른 줄을 넓히면 그것이 느슨해진 래칫이다** (D-0422).

    워크플로마다 `permissions:`를 적어 두므로 전역은 좁을수록 좋다.
    """
    fake, said = _ran(monkeypatch, {"default_workflow_permissions": "read"})

    assert "default_workflow_permissions=read" in fake.put()
    assert "can_approve_pull_request_reviews=true" in fake.put()
    assert "read" in said


def test_전역_권한이_write면_그대로_둔다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**읽어서 되돌린다.** 우리가 안 정한 값을 우리 기본값으로 덮지 않는다 (GR-0.5)."""
    fake, _ = _ran(monkeypatch, {"default_workflow_permissions": "write"})

    assert "default_workflow_permissions=write" in fake.put()


def test_이미_켜져_있으면_안_건드린다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**몇 번 쳐도 같다** (D-0226). 켜 둔 것을 다시 PUT 하면 감사 로그만 는다."""
    fake, said = _ran(
        monkeypatch,
        {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": True},
    )

    assert not [call for call in fake.calls if "-X" in call], "이미 켜져 있는데 PUT 했다"
    assert "이미" in said


def test_설정_켜기가_gh_setup에_걸려_있다() -> None:
    """**적어 두기만 하면 새로 클론한 날 또 막힌다** (D-0427)."""
    body = (ROOT / "tools" / "gh_ops.py").read_text(encoding="utf-8")
    block = body[body.index("def setup()") :]

    assert "actions_can_open_pulls()" in block[: block.index("\ndef ")]


# ------------------------------------------------- gpu 없는 길 (D-0439)

CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_gpu_없는_환경을_재는_잡이_있다() -> None:
    """**모든 잡이 `--all-extras`면 gpu 없는 길은 한 번도 안 돈다** (D-0126).

    맥북(M5)이 정확히 그 환경이고, 거기서 깨지는 것을 **여기서 먼저 봐야 한다**.
    실측으로 `type: ignore` 둘이 그 길에서만 죽은 표지가 됐다 (D-0439).
    """
    flow = CI.read_text(encoding="utf-8")
    assert "\n  no-gpu:\n" in flow, "gpu 없는 환경을 재는 잡이 없다"

    # **주석은 안 본다** — 이 잡의 주석이 `--all-extras`를 «안 쓴다»고 적는다.
    job = "\n".join(
        line
        for line in flow.split("\n  no-gpu:\n", 1)[1].split("\n  secret-scan:", 1)[0].splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "--all-extras" not in job, "`--all-extras`를 쓰면 이 잡이 다른 잡과 같아진다"
    assert "--extra music" in job and "--extra api" in job
    assert "mypy" in job, "무엇을 재는지가 없다"


def test_죽은_표지를_설정으로_안_덮는다() -> None:
    """**예외표는 늘리는 것이 아니라 비우는 것이다** (D-0117 · D-0439).

    D-0061이 `warn_unused_ignores = false`로 환경 차이를 덮었다. 덮으면 **그 모듈의
    진짜 죽은 ignore도 같이 안 보인다.** 원인(호출 대상을 `Any`로 받는다)을 고쳐
    예외를 지웠고, 다시 생기면 여기서 운다.
    """
    pinned = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    live = [
        line
        for line in pinned.splitlines()
        if "warn_unused_ignores" in line and not line.lstrip().startswith("#")
    ]
    assert live == [], f"죽은 ignore를 설정으로 덮는다: {live}"
