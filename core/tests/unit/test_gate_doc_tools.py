"""문서를 굽고 검사하는 관문 도구 (D-0258).

`encoding_check` · `proposal_source` · `build_proposal` · `release_notes` 넷이 관문에
서는데 자기 시험이 없었다 (D-0257이 셌다). **정본에서 기획서와 릴리스 노트가 나오는
길**이고, 여기가 조용히 틀리면 밖으로 나가는 문서가 틀린다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hathor.shared.config.paths import repo_root


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, repo_root() / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ENCODING = _tool("encoding_check")
SOURCE = _tool("proposal_source")
NOTES = _tool("release_notes")


# ------------------------------------------------------------------ encoding_check


def test_BOM과_CRLF와_끝개행을_본다() -> None:
    assert "BOM" in ENCODING.faults(ENCODING.BOM + b"x\n", ".py")
    assert "CRLF" in ENCODING.faults(b"a\r\nb\n", ".py")
    assert "끝 개행 없음" in ENCODING.faults(b"a", ".py")
    assert ENCODING.faults(b"a\n", ".py") == []


def test_윈도_스크립트는_CRLF가_정상이다() -> None:
    """`.bat`을 LF로 바꾸면 **윈도가 그 줄을 못 읽는다.**"""
    assert "CRLF" not in ENCODING.faults(b"echo\r\n", ".bat")
    assert "CRLF" in ENCODING.faults(b"echo\r\n", ".sh")


def test_빈_파일은_흠이_없다() -> None:
    """0바이트에 «끝 개행 없음»을 붙이면 **빈 자리표시자마다 빨개진다.**"""
    assert ENCODING.faults(b"", ".py") == []


def test_고친_것에는_흠이_없다() -> None:
    """**고쳤다는 그 검사가 초록이 된 것으로만 확인한다** (D-0244)."""
    broken = ENCODING.BOM + b"a\r\nb"

    fixed = ENCODING.repaired(broken, ".py")

    assert ENCODING.faults(fixed, ".py") == []


def test_바이너리는_안_본다(tmp_path: Path) -> None:
    """`.docx`·`.npz`를 텍스트로 «고치면» **바이트가 망가진다.**"""
    binary = tmp_path / "a.docx"
    binary.write_bytes(b"PK\x03\x04")
    text = tmp_path / "a.py"
    text.write_text("x\n", encoding="utf-8")

    assert not ENCODING.looked_at(binary)
    assert ENCODING.looked_at(text)
    assert not ENCODING.looked_at(tmp_path / "없는파일.py"), "없는 파일은 볼 것이 없다"


# ------------------------------------------------------------------ proposal_source


MASTER = """# 문서

## 취향 잠재 표현 기반 종단간 AI 음악 창작 시스템

### 표 하나

| 이름 | 값 |
|---|---|
| 가 | 3.7 |
| 나 | - |

```python
print("본문")
```

## 부록 A. 색인
여기부터는 안 본다.
"""


def test_정본_구간만_자른다(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MASTER.md").write_text(MASTER, encoding="utf-8")

    text = SOURCE.source(root=tmp_path)

    assert "본문" in text
    assert "여기부터는 안 본다" not in text, "부록 A부터는 기획서가 아니다"


def test_지문이_내용을_따라간다(tmp_path: Path) -> None:
    """**지문이 안 바뀌면 `docx_check`가 낡은 기획서를 통과시킨다.**"""
    (tmp_path / "docs").mkdir()
    master = tmp_path / "docs" / "MASTER.md"
    master.write_text(MASTER, encoding="utf-8")
    before = SOURCE.fingerprint(root=tmp_path)

    master.write_text(MASTER.replace("3.7", "9.9"), encoding="utf-8")

    assert SOURCE.fingerprint(root=tmp_path) != before


def test_표를_머리와_줄로_읽는다() -> None:
    (table,) = SOURCE.tables("| 이름 | 값 |\n|---|---|\n| 가 | 3.7 |\n")

    assert table.header == ["이름", "값"]
    assert table.column("값") == ["3.7"]


def test_수가_없는_칸은_터진다() -> None:
    """`-`를 0으로 읽으면 **기획서에 없는 수가 실린다.**"""
    with pytest.raises(SOURCE.SourceError):
        SOURCE.number("-")


def test_없는_절을_찾으면_터진다() -> None:
    """빈 문자열을 돌려주면 **기획서에 빈 절이 실리고 아무도 모른다.**"""
    with pytest.raises(SOURCE.SourceError):
        SOURCE.section(MASTER, "### 없는 절")


# ------------------------------------------------------------------ release_notes


DECISIONS = """# 결정

## D-0100. 첫째

- **배경**: 있다.
- **결과**: 하나를 고쳤다.

### 남기는 것

- 배운 것 하나.

재현
    echo 1

강제자  `x.py`

---

## D-0101. 둘째

- **배경**: 있다.
- **결과**: 둘을 고쳤다.

재현 없음 — 사유: 수치가 없다

강제자 없음 — 사유: 없다
"""


def test_최신_결정을_태그로_고른다() -> None:
    assert NOTES.latest(DECISIONS) == "D-0101"


def test_기준_뒤의_결정만_싣는다() -> None:
    body = NOTES.notes(DECISIONS, since="D-0100")

    assert "D-0101" in body
    assert "D-0100" not in body, "이미 낸 판을 다시 싣지 않는다"


def test_기준이_없으면_최신_하나만_싣는다() -> None:
    """**판마다 전체를 싣지 않는다.** 그러면 릴리스 노트가 결정 기록의 사본이 된다."""
    body = NOTES.notes(DECISIONS)

    assert "D-0101" in body
    assert "D-0100" not in body


def test_결과와_배운_것을_싣는다() -> None:
    body = NOTES.notes(DECISIONS, since="D-0099")

    assert "하나를 고쳤다" in body
    assert "배운 것 하나" in body
    assert "강제자" not in body, "사람이 읽는 노트에 강제자 경로는 안 싣는다"


def test_기준_뒤에_결정이_없으면_터진다() -> None:
    """**빈 노트를 조용히 내면 릴리스가 내용 없이 나간다.**"""
    with pytest.raises(LookupError):
        NOTES.notes(DECISIONS, since="D-0101")


def test_결정이_없으면_터진다() -> None:
    """**빈 노트를 조용히 내면 릴리스가 내용 없이 나간다.**"""
    with pytest.raises(LookupError):
        NOTES.latest("# 결정\n\n아무것도 없다.\n")
