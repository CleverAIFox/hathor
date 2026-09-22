"""모델 가중치 라이선스 검사의 단위 검사 (D-0217).

**목표가 제품이 된 뒤에야 MERT가 비상업인 것을 봤다.** 백칠십 건 동안 아무도 안 봤다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "check_model_licenses.py"
    spec = importlib.util.spec_from_file_location("check_model_licenses", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_model_licenses"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()


def _tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    table: dict[str, tuple[str, str, str]],
) -> list[str]:
    target = tmp_path / "core" / "hathor" / "a.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "LICENSES", table)
    found: list[str] = CHECKER.check()
    return found


def test_표에_없는_모델을_부르면_잡는다(tmp_path, monkeypatch):
    problems = _tree(tmp_path, monkeypatch, 'DEFAULT_MODEL = "new/model"\n', {})
    assert len(problems) == 1
    assert "new/model" in problems[0]


def test_표에_있으면_통과한다(tmp_path, monkeypatch):
    table = {"new/model": ("MIT", "yes", "사유")}
    assert _tree(tmp_path, monkeypatch, 'DEFAULT_MODEL = "new/model"\n', table) == []


def test_안_부르는_모델이_표에_남으면_잡는다(tmp_path, monkeypatch):
    """**허용 목록이 낡으면 검사가 거짓말을 한다** — `check_egress`와 같은 규율이다."""
    table = {"gone/model": ("MIT", "yes", "사유")}
    problems = _tree(tmp_path, monkeypatch, "x = 1\n", table)
    assert any("gone/model" in text for text in problems)


def test_상업_가부는_세_값_중_하나다(tmp_path, monkeypatch):
    table = {"new/model": ("MIT", "아마", "사유")}
    problems = _tree(tmp_path, monkeypatch, 'DEFAULT_MODEL = "new/model"\n', table)
    assert any("아마" in text for text in problems)


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다():
    assert CHECKER.check() == []


def test_상업_불가는_MERT_하나다():
    """**이름으로 못 박는다.** 하나가 늘면 이 검사가 빨개지고 그것이 리뷰 대상이다.

    MERT를 빼는 날(O-68) 여기서 빈 집합이 된다.
    """
    assert CHECKER.blocked() == ["m-a-p/MERT-v1-95M"]


def test_모르는_것을_된다고_적지_않는다():
    """**코드 라이선스를 가중치에 넘기지 않는다** (GR-0.5)."""
    assert CHECKER.LICENSES["htdemucs"][1] == "unknown"
