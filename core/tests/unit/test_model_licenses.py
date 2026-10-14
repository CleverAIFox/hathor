"""모델 가중치 라이선스 검사의 단위 검사 (D-0217).

**목표가 제품이 된 뒤에야 MERT가 비상업인 것을 봤다.** 백칠십 건 동안 아무도 안 봤다.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    """`tools/check_model_licenses.py`. 싣는 자리는 `tests.conftest` 하나다 (D-0272)."""
    return tool_module("check_model_licenses")


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

    **이 집합은 비지 않는다** — 상업 가능한 대체재가 없다는 것이 실측됐다 (O-68 · D-0235).
    """
    assert CHECKER.blocked() == ["m-a-p/MERT-v1-95M"]


def test_모르는_것을_된다고_적지_않는다():
    """**코드 라이선스를 가중치에 넘기지 않는다** (GR-0.5 · D-0217).

    **이름으로 못 박으면 그 이름만 지킨다.** `htdemucs` 하나를 박아 뒀더니 MusicFM을
    «미명시»로 적어 놓고 상업 가능으로 바꿔도 아무것도 안 빨개졌다 (D-0418). 규칙은
    이름이 아니라 **글자에 건다** — 가중치가 «미명시»면 가부는 «모름»이다.
    """
    said = _module().LICENSES
    unspecified = {name: row for name, row in said.items() if "미명시" in row[0]}
    assert unspecified, "«미명시»가 하나도 없다 — 이 검사가 빈 그물이다 (D-0230)"

    for name, (license_text, allowed, _) in unspecified.items():
        assert allowed == "unknown", f"{name}의 가중치가 «{license_text}»인데 가부가 «{allowed}»다"


def test_모르는_것은_쓰는지_안_쓰는지_적는다():
    """**«미확인»만 적어 두면 다음 사람이 그것을 «조사해 보자»로 읽는다** (D-0418).

    MusicFM이 그랬다. D-0248이 *«MIT다»*로 적었고 — 그것은 코드 얘기였다 — 2주 뒤
    가중치 1.3GB를 받아 **79분을 돌리고 나서야** 답이 나왔다. *«쓸 수 없다»*가 아니라
    **«쓸 값이 없다»**였다. **재 본 것은 재 봤다고 적는다.** 그래야 같은 79분을
    두 번 안 쓴다.

    `htdemucs`는 반대쪽이다 — 가중치 라이선스를 모르는 채로 **쓰고 있다.** 그것도
    적혀 있어야 한다. 모르는 것을 쓰고 있다는 사실이 표에 안 보이면 **제품 경로를
    짤 때 그 자리가 비어 보인다.**
    """
    unknown = {
        name: note
        for name, (_, allowed, note) in _module().LICENSES.items()
        if allowed == "unknown"
    }
    assert unknown, "미확인이 하나도 없다 — 이 검사가 빈 그물이다 (D-0230)"

    for name, note in unknown.items():
        assert "**쓴다**" in note or "**안 쓴다**" in note, f"{name}에 쓰기 판정이 없다: {note}"
