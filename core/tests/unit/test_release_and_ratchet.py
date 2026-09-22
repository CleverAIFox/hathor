"""커버리지 래칫 · 결정 릴리스 · 저장소 부속 (D-0223)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COVERAGE = _load("check_coverage")
RELEASE = _load("release_notes")


# ------------------------------------------------------------------ 커버리지


def test_커버리지_바닥은_한_곳에만_산다() -> None:
    """**D-0223의 강제자.** 숫자가 두 곳에 있으면 한쪽만 고친 날 로컬과 CI가 갈린다."""
    for path in (ROOT / "Makefile", ROOT / ".github" / "workflows" / "ci.yml"):
        assert "--cov-fail-under" not in path.read_text(encoding="utf-8"), path
    text = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    assert COVERAGE.floor(text) >= 83


@pytest.mark.parametrize(
    ("actual", "bottom", "fails"),
    [(86.9, 87.0, True), (87.0, 87.0, False), (89.9, 87.0, False), (90.0, 87.0, True)],
)
def test_래칫은_양방향이다(actual: float, bottom: float, fails: bool) -> None:
    assert (COVERAGE.verdict(actual, bottom) is not None) is fails


def test_바닥은_실측_빼기_1로_오른다() -> None:
    text = "[tool.coverage.report]\nfail_under = 83\n"
    assert COVERAGE.floor(COVERAGE.bumped(text, 88.61)) == 87


# ------------------------------------------------------------------ 릴리스

SAMPLE = """## D-0001. 첫째

- **결과**: 하나를 했다.

### 남기는 것

- 배웠다.

재현
    make check

---

## D-0002. 둘째

- **결과**: 둘을 했다.
  이어진다.

강제자 없음 — 사유: 예시
"""


def test_가장_최근_결정이_태그다() -> None:
    assert RELEASE.latest(SAMPLE) == "D-0002"
    assert re.fullmatch(r"D-\d{4}", RELEASE.latest((ROOT / "docs/DECISIONS.md").read_text()))


def test_본문은_결과와_남기는_것이다() -> None:
    body = RELEASE.notes(SAMPLE, "D-0000")
    assert "하나를 했다" in body and "배웠다" in body
    assert "이어진다" in body
    assert "make check" not in body


def test_지난_태그_뒤의_결정만_싣는다() -> None:
    body = RELEASE.notes(SAMPLE, "D-0001")
    assert "D-0002" in body and "D-0001. 첫째" not in body


# ------------------------------------------------------------------ 부속


def test_의존성_갱신은_uv와_액션을_본다() -> None:
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert 'package-ecosystem: "uv"' in text
    assert 'directory: "/core"' in text
    assert 'package-ecosystem: "github-actions"' in text


def test_데브_컨테이너는_CI와_같은_묶음을_깐다() -> None:
    """**묶음이 다르면 `make check`이 CI와 갈린다** — mypy가 GPU 묶음 유무로 다르게 본다."""
    raw = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    config = json.loads(re.sub(r"^\s*//.*$", "", raw, flags=re.M))
    assert "post-create.sh" in config["postCreateCommand"]
    script = (ROOT / ".devcontainer" / "post-create.sh").read_text(encoding="utf-8")
    assert "uv sync --all-extras --dev" in script
    assert "--all-extras" in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
