"""**CI가 git이 안 나르는 자리를 읽으면 거기서만 터진다** (D-0369).

D-0368이 `cp var/proposal/figures/*.png`를 배포 잡에 넣었다. `make check`은 초록이었고
**배포만 빨갰다** — `var/`는 `.gitignore`에 있어서 내 기기에만 있다. 이 부류의 결함은
**로컬에서 영원히 안 보인다.**

여기 시험은 전부 **심은 결함**이다 (D-0069). 초록 상태를 확인하는 시험은 배선을
붙잡지 못한다 — D-0368이 그것으로 아홉 곳을 놓쳤다.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("check_workflow_paths")
ROOT = Path(__file__).resolve().parents[3]

PLANTED = """\
jobs:
  deploy:
    steps:
      - uses: actions/checkout@v7
      - name: Stage
        run: |
          cp var/proposal/figures/concept.png _site/
"""

MADE_HERE = """\
jobs:
  deploy:
    steps:
      - name: Draw
        run: python3 tools/render_figures.py --out _site/figures
      - name: Stage
        run: |
          cp _site/figures/concept.png _site/
"""

OTHER_JOB = """\
jobs:
  draw:
    steps:
      - run: python3 tools/render_figures.py --out var/proposal/figures
  deploy:
    steps:
      - run: cp var/proposal/figures/concept.png _site/
"""


def _problems(text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    flows = tmp_path / ".github" / "workflows"
    flows.mkdir(parents=True)
    (flows / "one.yml").write_text(text, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "\n".join(["var/", "_site/", ".venv/", "__pycache__/", "htmlcov/", "artifacts/"]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(TOOL, "ROOT", tmp_path)
    monkeypatch.setattr(TOOL, "FLOWS", flows)
    monkeypatch.setattr(TOOL, "GITIGNORE", tmp_path / ".gitignore")
    return cast("list[str]", TOOL.check())


def test_저장소가_통과한다() -> None:
    """지금 저장소가 깨끗한가. **이것만으로는 아무것도 못 잡는다** — 아래가 본다."""
    assert cast("list[str]", TOOL.check()) == []


def test_안_날아가는_자리를_읽으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**D-0368이 심은 그 줄 그대로다.** 배포가 `var/`에서 복사했다."""
    problems = _problems(PLANTED, tmp_path, monkeypatch)

    assert len(problems) == 1, problems
    assert "var/proposal/figures/concept.png" in problems[0]


def test_같은_잡이_만들면_통과한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_site/`도 덮이지만 **그 잡이 짓고 그 잡이 읽는다** — 거짓 경보가 아니다 (GR-0.8)."""
    assert _problems(MADE_HERE, tmp_path, monkeypatch) == []


def test_다른_잡이_만든_것은_안_센다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**잡이 다르면 러너가 다르다.** 앞 잡이 그려도 뒤 잡의 디스크에는 없다."""
    problems = _problems(OTHER_JOB, tmp_path, monkeypatch)

    assert len(problems) == 1, problems


def test_덮는_자리가_비면_막는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    flows = tmp_path / ".github" / "workflows"
    flows.mkdir(parents=True)
    (flows / "one.yml").write_text(PLANTED, encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    monkeypatch.setattr(TOOL, "GITIGNORE", tmp_path / ".gitignore")
    monkeypatch.setattr(TOOL, "FLOWS", flows)

    problems = cast("list[str]", TOOL.check())

    assert len(problems) == 1
    assert "그물이 비었다" in problems[0]


def test_안쪽_자리는_안_센다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`notebooks/.ipynb_checkpoints/`처럼 **위가 추적되는** 자리는 읽어도 된다."""
    (tmp_path / ".gitignore").write_text(
        "var/\n_site/\n.venv/\n__pycache__/\nhtmlcov/\nnotebooks/.ipynb_checkpoints/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(TOOL, "GITIGNORE", tmp_path / ".gitignore")

    assert "notebooks/" not in TOOL.ignored_roots()


def test_판정이_main에_닿는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069). 판정이 화면과 종료코드까지 **닿는가.**"""
    monkeypatch.setattr(TOOL, "check", lambda: ["심은 것"])
    monkeypatch.setattr("sys.argv", ["check_workflow_paths.py", "--check"])

    assert TOOL.main() == 1
    assert "심은 것" in capsys.readouterr().err


def test_세_곳에_다_걸려_있다() -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126)."""
    for where in ("Makefile", ".githooks/pre-commit", ".github/workflows/ci.yml"):
        body = (ROOT / where).read_text(encoding="utf-8")
        assert "tools/check_workflow_paths.py" in body, where


def test_읽는_자와_만드는_자가_따로_선다() -> None:
    """`reads()` · `writes()` · `covered()`. **셋이 따로 서야 거짓 경보가 안 난다** (GR-0.8)."""
    seen = TOOL.reads(MADE_HERE, ["_site/"])
    made = TOOL.writes(MADE_HERE)

    assert "_site/figures/concept.png" in seen
    assert "_site/figures" in made
    assert TOOL.covered("_site/figures/concept.png", made), "만든 자리 아래인데 걸렸다"
    assert not TOOL.covered("var/a.png", made), "안 만든 자리인데 통과했다"


def test_목록이_읽는_자리와_만드는_자리를_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--list` 길 (D-0369). **아무도 안 밟아서 배선 넷이 비어 있었다.**

    `check()`가 아무 말 없이 통과한 날 **무엇을 보고 통과했는지** 여기서 읽는다
    (D-0269). 이 길이 끊기면 사람이 손으로 볼 자료가 사라진다.
    """
    monkeypatch.setattr("sys.argv", ["check_workflow_paths.py", "--list"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    assert f"덮는 최상위 {len(TOOL.ignored_roots())}개" in spoke, spoke
    assert "proposal.yml" in spoke, "덮인 자리를 읽는 잡이 안 찍혔다"
    assert spoke.count("_site/figures") >= 2, "읽는 자리와 만드는 자리 둘 다 찍는다"
