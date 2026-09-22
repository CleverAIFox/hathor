"""`make check` · CI · 커밋 훅이 같은 것을 보는가 (D-0184 · D-0219).

**둘이 갈라지면 기계가 지키는 줄 알았던 것이 안 지켜진다.** 실측으로
`check_test_types.py`가 Makefile에만 있었고 **검사 코드 타입 래칫 66건이 CI에서
빠져 있었다.** `ruff`도 CI는 `core`만 보고 `tools/`를 안 봤다 — 그 세션의 lint
오류 대부분이 `tools/`에서 났다.

### 인스턴스 가드에서 클래스 가드로 (D-0219)

첫 판은 `tools/check_*.py` 이름만 셌다. **`doc_fsck.py`는 그 그물에 안 걸린다** —
CI에서 빠져도 초록이었다. 이름 규칙으로 고르면 규칙 밖이 사각이 된다.

이제 **호출하는 검사기 전부**를 토큰으로 뽑아 셋을 맞춘다. 차집합은 **선언해야만**
허용된다 — 선언 없는 면제는 없고, 거짓이 된 선언도 실패다. fire-lane의
`gate_parity.py`에서 가져온 규율이다.

| 선언 | 자리 | 뜻 |
|---|---|---|
| `# ci-only: <토큰> <사유>` | `ci.yml` | CI만 돈다 |
| `# hook-skip: <토큰> <사유>` | `.githooks/pre-commit` | 빠른 문서 검사인데 훅이 안 돈다 |
| `# advisory: <토큰> <사유>` | `ci.yml` | 실패해도 빌드를 안 막는다 |

**주석은 호출이 아니다.** 주석에 적힌 도구 이름을 세면 *"CI가 본다"*고 적어 놓기만
한 것이 통과한다. 선언을 읽을 때만 주석을 본다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
HOOK = ROOT / ".githooks" / "pre-commit"

CHECK_TARGET = "check"
FAST_TARGETS = ("docs", "size")
"""훅이 돌아야 하는 목표. **빠른 것만이다** — pytest·mypy는 CI가 본다."""

TOKEN = re.compile(
    r"tools/([\w/]+\.py)"
    r"|uv run (ruff|mypy|lint-imports|pytest|pip-audit|actionlint|shellcheck)\b"
    r"|python3? -m ([\w.]+)"
)
DECLARE = re.compile(r"^\s*#\s*(ci-only|hook-skip|advisory):\s*(\S+)\s+(\S.*)$", re.M)


def tokens(text: str) -> set[str]:
    """**주석 줄을 걷어낸 뒤** 호출된 검사기를 센다."""
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return {next(group for group in match.groups() if group) for match in TOKEN.finditer(body)}


def declared(text: str, kind: str) -> dict[str, str]:
    """`# <kind>: <토큰> <사유>` → `{토큰: 사유}`. **사유가 없으면 선언이 아니다.**"""
    return {token: reason for found, token, reason in DECLARE.findall(text) if found == kind}


def recipes(makefile: str) -> dict[str, str]:
    """목표 → 레시피 본문. 들여쓴 줄이 앞 목표에 붙는다."""
    found: dict[str, list[str]] = {}
    current = ""
    for line in makefile.splitlines():
        head = re.match(r"^([\w-]+):", line)
        if head:
            current = head.group(1)
            found[current] = []
        elif line.startswith("\t") and current:
            found[current].append(line)
    return {target: "\n".join(lines) for target, lines in found.items()}


def check_deps(makefile: str) -> list[str]:
    line = next(row for row in makefile.splitlines() if row.startswith(f"{CHECK_TARGET}:"))
    return line.split(":", 1)[1].split("##", 1)[0].split()


def parity(makefile: str, workflow: str, hook: str) -> list[str]:
    """세 관문의 차집합을 **선언과 대조한다.** 빈 목록이 초록이다."""
    problems: list[str] = []
    table = recipes(makefile)
    local = set().union(*(tokens(table.get(target, "")) for target in check_deps(makefile)))
    fast = set().union(*(tokens(table.get(target, "")) for target in FAST_TARGETS))
    ci = tokens(workflow)
    hooked = tokens(hook)
    ci_only = declared(workflow, "ci-only")
    skips = declared(hook, "hook-skip")
    advisory = declared(workflow, "advisory")

    for name in sorted(local - ci):
        problems.append(f"make check가 돌고 CI가 안 돈다: {name}")
    for name in sorted(ci - local - set(ci_only)):
        problems.append(f"CI만 돌고 선언이 없다: {name} — `# ci-only: {name} <사유>`")
    for name in sorted(set(ci_only) - (ci - local)):
        problems.append(f"거짓 선언: {name}은 CI 전용이 아니다")
    for name in sorted(hooked - local):
        problems.append(f"훅이 make check 밖의 것을 돈다: {name}")
    for name in sorted(fast - hooked - set(skips)):
        problems.append(f"빠른 검사를 훅이 안 돈다: {name} — `# hook-skip: {name} <사유>`")
    for name in sorted(set(skips) - (fast - hooked)):
        problems.append(f"거짓 선언: {name}은 훅이 이미 돌거나 빠른 검사가 아니다")

    code = [row for text in (workflow, hook) for row in text.splitlines()]
    silenced = [row for row in code if "|| true" in row and not row.lstrip().startswith("#")]
    for line in silenced:
        problems.append(f"`|| true`는 실패를 삼킨다. `continue-on-error` + advisory 선언: {line}")
    soft = workflow.count("continue-on-error: true")
    if soft != len(advisory):
        problems.append(f"continue-on-error {soft}곳 · advisory 선언 {len(advisory)}개")
    for name in sorted(set(advisory) - ci):
        problems.append(f"거짓 선언: advisory {name}을 CI가 안 부른다")
    return problems


def _repo() -> tuple[str, str, str]:
    return (
        MAKEFILE.read_text(encoding="utf-8"),
        WORKFLOW.read_text(encoding="utf-8"),
        HOOK.read_text(encoding="utf-8"),
    )


# ------------------------------------------------------------------ 저장소


def test_세_관문이_선언과_맞는다():
    """**D-0219의 강제자.** 차집합은 선언으로만 존재한다."""
    assert parity(*_repo()) == []


def test_그물이_비지_않았다():
    """**찾을 것이 없는 정규식은 0건을 내고, 0건은 초록이다** (fire-lane `plan_renumber`)."""
    makefile, workflow, hook = _repo()
    table = recipes(makefile)
    assert len(tokens(workflow)) >= 10
    assert len(tokens(hook)) >= 5
    assert "doc_fsck.py" in tokens(table["docs"])
    assert set(FAST_TARGETS) <= set(check_deps(makefile))


def test_CI도_tools를_본다():
    """`working-directory: core`라 **`.`만 주면 `tools/`가 빠진다.**"""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    lint = [line for line in workflow.splitlines() if "ruff " in line]
    assert lint, "CI에 ruff 단계가 없다"
    assert all("../tools" in line for line in lint), f"tools를 안 보는 줄: {lint}"


def test_저장소_훅이_있고_실행_가능하다():
    """전역 `~/.githooks/pre-commit`이 **이 파일을 찾아 부른다** (D-0184).

    배선은 원래 있었고 파일만 없었다. **없으면 전역 훅이 조용히 지나간다.**
    """
    assert HOOK.is_file(), f"{HOOK}가 없다"
    assert os.access(HOOK, os.X_OK), f"{HOOK}에 실행 권한이 없다"


def test_훅은_느린_검사를_안_돌린다():
    """**커밋마다 99초를 물리면 `--no-verify`를 쓰게 된다.**

    `doctor`가 *"느려지면 안 돌리게 된다"*고 적은 그 함정이다. 실측으로 문서
    검사와 `ruff`가 2.6초, `pytest`가 99초였다.
    """
    hooked = tokens(HOOK.read_text(encoding="utf-8"))
    assert "pytest" not in hooked
    assert "mypy" not in hooked


# ------------------------------------------------------------------ 양성 대조

MAKE = (
    "check: docs lint  ## x\n\n"
    "docs:\n\tpython3 tools/doc_fsck.py --check\n"
    "lint:\n\tuv run ruff check .\n"
)
HOOKED = "run a python3 tools/doc_fsck.py --check\nrun b uv run ruff check .\n"


def test_이름_규칙_밖의_검사가_CI에서_빠지면_잡는다():
    """**첫 판의 사각이다.** `doc_fsck.py`는 `check_*` 규칙 밖이었다."""
    problems = parity(MAKE, "run: uv run ruff check .\n", HOOKED)
    assert any("doc_fsck.py" in text for text in problems)


def test_주석에_적은_것은_호출이_아니다():
    workflow = "# python3 tools/doc_fsck.py --check\nrun: uv run ruff check .\n"
    assert any("doc_fsck.py" in text for text in parity(MAKE, workflow, HOOKED))


def test_선언_없는_CI_전용을_잡고_선언하면_통과한다():
    base = "run: python3 tools/doc_fsck.py\nrun: uv run ruff check .\nrun: uv run pip-audit\n"
    assert any("pip-audit" in text for text in parity(MAKE, base, HOOKED))
    declared_ci = "# ci-only: pip-audit 상류 취약점 알림\n" + base
    assert parity(MAKE, declared_ci, HOOKED) == []


def test_거짓이_된_선언을_잡는다():
    """**거짓말하는 강제자는 없는 강제자보다 나쁘다** (fire-lane)."""
    workflow = "# ci-only: ruff 옛날엔 CI만 돌았다\nrun: python3 tools/doc_fsck.py\n"
    workflow += "run: uv run ruff\n"
    assert any("거짓 선언" in text for text in parity(MAKE, workflow, HOOKED))


def test_훅이_빠른_검사를_빼면_선언을_요구한다():
    workflow = "run: python3 tools/doc_fsck.py\nrun: uv run ruff check .\n"
    problems = parity(MAKE, workflow, "run b uv run ruff check .\n")
    assert any("doc_fsck.py" in text for text in problems)
    skipped = "# hook-skip: doc_fsck.py 사유가 있다\nrun b uv run ruff check .\n"
    assert parity(MAKE, workflow, skipped) == []


def test_실패를_삼키는_단계를_잡는다():
    """`|| true`는 **초록만 낸다.** 이름은 검사인데 한 번도 못 막는다."""
    workflow = "run: python3 tools/doc_fsck.py\nrun: uv run ruff check . || true\n"
    assert any("|| true" in text for text in parity(MAKE, workflow, HOOKED))


def test_continue_on_error는_선언과_수가_맞아야_한다():
    workflow = (
        "run: python3 tools/doc_fsck.py\nrun: uv run ruff check .\n"
        "continue-on-error: true\nrun: uv run pip-audit\n"
        "# ci-only: pip-audit 상류 취약점 알림\n"
    )
    assert any("continue-on-error" in text for text in parity(MAKE, workflow, HOOKED))
    ok = workflow + "# advisory: pip-audit 우리가 못 고친다\n"
    assert parity(MAKE, ok, HOOKED) == []


# ------------------------------------------------------------------ 배포 (D-0222)

PAGES = ROOT / ".github" / "workflows" / "proposal.yml"


@pytest.mark.parametrize("name", ["proposal.yml", "release.yml"])
def test_배포는_검사를_지난다(name: str) -> None:
    """**D-0222의 강제자.** 배포가 CI와 따로 돌면 빨간 커밋이 밖으로 나간다.

    fire-lane 실측 — 배포 넷에 `needs:`가 0건이었고 검사와 **나란히** 돌았다.
    검사를 복사하지 않고 `ci.yml`을 그대로 부른다. 릴리스 태그도 같다 (D-0223).
    """
    flow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    assert "workflow_call:" in WORKFLOW.read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/ci.yml" in flow
    assert "needs: gate" in flow


def test_기획서_배포는_지문을_본다() -> None:
    assert "tools/docx_check.py" in PAGES.read_text(encoding="utf-8")


def test_배포는_정본을_옮기기만_한다() -> None:
    """**사본을 커밋하지 않는다.** `site/`에 docx가 있으면 두 벌이 된다."""
    assert not (ROOT / "site" / "proposal.docx").exists()
    viewer = (ROOT / "site" / "proposal.html").read_text(encoding="utf-8")
    assert "./proposal.docx" in viewer
    assert "cp docs/proposal.docx _site/" in PAGES.read_text(encoding="utf-8")


SELF_HOSTED_TRIGGERS = {"workflow_dispatch"}
"""셀프호스티드 러너가 받아도 되는 방아쇠. **손으로 누르는 것 하나다.**"""


def triggers(flow: str) -> set[str]:
    """`on:` 아래 한 단계 들여 쓴 키. 한 줄 목록(`on: [push]`)도 편다."""
    head = re.search(r"^on:[ \t]*(\[[^\]]*\]|\w+)?[ \t]*$", flow, re.M)
    if head is None:
        return set()
    if head.group(1):
        return {name.strip() for name in head.group(1).strip("[]").split(",") if name.strip()}
    block = re.match(r"((?:[ \t]+.*\n|\s*\n)*)", flow[head.end() + 1 :])
    assert block is not None
    return set(re.findall(r"^  (\w+):", block.group(1), re.M))


def test_셀프호스티드는_손으로만_돈다() -> None:
    """**D-0224의 강제자.** 공개 저장소에서 러너를 push · PR에 걸면 남의 코드가 이 기기에서 돈다."""
    flows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    hosted = [path for path in flows if "self-hosted" in path.read_text(encoding="utf-8")]
    assert hosted, "셀프호스티드 흐름이 없다 — 러너를 뺐으면 이 시험도 뺀다"
    for path in hosted:
        found = triggers(path.read_text(encoding="utf-8"))
        assert found == SELF_HOSTED_TRIGGERS, f"{path.name}: {sorted(found)}"


def test_방아쇠를_읽는다() -> None:
    assert triggers("on:\n  push:\n    branches: [main]\n  pull_request:\n\njobs:\n") == {
        "push",
        "pull_request",
    }
    assert triggers("on: [push, workflow_dispatch]\n") == {"push", "workflow_dispatch"}
    assert triggers("on:\n  workflow_dispatch:\n\npermissions:\n") == {"workflow_dispatch"}


def test_러너_라벨이_흐름과_맞는다() -> None:
    """등록 도구가 붙이는 라벨을 흐름이 찾는다. 어긋나면 작업이 영원히 대기열에 선다."""
    script = (ROOT / "tools" / "register_runner.sh").read_text(encoding="utf-8")
    flow = (ROOT / ".github" / "workflows" / "gpu-smoke.yml").read_text(encoding="utf-8")
    labels = re.search(r"RUNNER_LABELS:-([\w,]+)", script)
    wanted = re.search(r"runs-on: \[([^\]]+)\]", flow)
    assert labels is not None and wanted is not None
    given = {"self-hosted", "linux", *labels.group(1).split(",")}
    assert {name.strip().lower() for name in wanted.group(1).split(",")} <= given
