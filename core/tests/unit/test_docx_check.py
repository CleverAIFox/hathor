"""기획서 대조 검사의 단위 검사 (D-0220).

**기획서는 밖이 읽는 유일한 문서다.** 강제자 없이 두면 fire-lane처럼 갱신표까지 같이 낡는다.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    path = ROOT / "tools" / "docx_check.py"
    spec = importlib.util.spec_from_file_location("docx_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["docx_check"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()


def _docx(path: Path, *paragraphs: str) -> None:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")


def _tree(tmp_path: Path) -> Path:
    """정본 셋만 복사한 합성 저장소."""
    for name in ("docs/MASTER.md", "docs/PLAN.md", "tools/check_model_licenses.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    return tmp_path


def _good() -> list[str]:
    return [value for value, _ in CHECKER.truths(ROOT)]


# ------------------------------------------------------------------ 저장소


def test_저장소_기획서가_정본과_맞는다() -> None:
    """**D-0220의 강제자.** 기획서 숫자는 저장소가 정본이다."""
    assert CHECKER.check() == []


def test_정본을_비지_않게_읽는다() -> None:
    """**찾을 것이 없는 정규식은 0건을 내고, 0건은 초록이다.**"""
    values = _good()
    assert "1004곡" in values
    assert "MERT" in values
    assert any(value.startswith("VRAM ") for value in values)


# ------------------------------------------------------------------ 양성 대조


def test_정본_값이_빠지면_잡는다(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    values = _good()
    _docx(root / CHECKER.DOCX, *values[1:])
    problems = CHECKER.check(root)
    assert len(problems) == 1
    assert values[0] in problems[0]


def test_폐기된_말이_남으면_잡는다(tmp_path: Path) -> None:
    """**있는지만 보면 옛 값과 새 값이 둘 다 있어도 통과한다.**"""
    root = _tree(tmp_path)
    _docx(root / CHECKER.DOCX, *_good(), "P1 진행 (유닛 1/4 완료)")
    problems = CHECKER.check(root)
    assert any("유닛 1/4" in text for text in problems)


def test_다_있으면_통과한다(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _docx(root / CHECKER.DOCX, *_good())
    assert CHECKER.check(root) == []


def test_기획서가_없으면_잡는다(tmp_path: Path) -> None:
    assert CHECKER.check(_tree(tmp_path)) == [f"{CHECKER.DOCX}가 없다"]


def test_정본의_모양이_바뀌면_도구가_죽었다고_말한다(tmp_path: Path) -> None:
    """**조용히 통과하지 않는다.** 재개 조건 문장이 바뀌면 대조를 못 한다."""
    root = _tree(tmp_path)
    plan = root / "docs/PLAN.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace("재개 조건", "재개"), encoding="utf-8")
    with pytest.raises(LookupError):
        CHECKER.truths(root)
