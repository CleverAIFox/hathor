"""묶음 배열의 쓰는 쪽 ↔ 읽는 쪽 (D-0395).

**심은 결함으로 먼저 물렸다** (D-0069). 이 검사가 실제로 잡은 것은 라이브 저장소의
다섯 자리이며, 아래 `test_실물에서_onset만_안_읽힌다`가 그 상태를 못으로 박는다.

### 왜 픽스처로 재나

실물 저장소에 결함을 심으면 **심은 동안 다른 시험이 같이 빨개진다.** 쓰는 쪽·읽는
쪽·적힌 말을 한 나무에 모아 두면 각 규칙을 **따로** 물릴 수 있다 (D-0390과 같은 꼴).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hathor.shared.config.paths import repo_root
from tests.conftest import tool_module as _tool

if TYPE_CHECKING:
    from pathlib import Path

KEYS = _tool("check_bundle_keys")

WRITER_SOURCE = '''"""쓰는 쪽 — 이름을 짓는 자리다."""


def run(arrays, sources, stems, waveform):
    for name in sources:
        arrays[f"mert/{name}/layer00"] = name
        arrays[f"chroma/{name}"] = name
        arrays[f"chroma_series/{name}"] = name
        arrays[f"onset/{name}"] = name
        arrays[f"pitch/{name}"] = name
    arrays["silence/mixture"] = waveform
'''

READER_SOURCE = '''"""읽는 쪽. **독스트링이 아니라 코드가 이름을 부른다.**"""

PREFIXES = ("chroma/", "chroma_series/", "pitch/", "silence/")


def read(arrays):
    return [arrays[key] for key in arrays if key.startswith(PREFIXES)]
'''


QUIET = "온셋은 아직 안 읽는다.\n"
"""`onset/<스템>`을 안 부르는 문서. **바탕이 조용해야 심은 말이 보인다.**"""


def _tree(folder: Path, *, reader: str = READER_SOURCE, docs: str = QUIET) -> None:
    """픽스처 저장소. **쓰는 쪽 하나 · 읽는 쪽 하나 · 문서 셋.**"""
    writer = folder / "core" / "hathor" / "application"
    writer.mkdir(parents=True)
    (writer / "ingest_all.py").write_text(WRITER_SOURCE, encoding="utf-8")
    (writer / "keys_from_bundles.py").write_text(reader, encoding="utf-8")
    (folder / "tools").mkdir()
    (folder / "docs").mkdir()
    (folder / "README.md").write_text(docs, encoding="utf-8")
    (folder / "docs" / "MASTER.md").write_text("정본.\n", encoding="utf-8")
    (folder / "docs" / "PLAN.md").write_text("미래.\n", encoding="utf-8")


def test_픽스처가_통과한다(tmp_path: Path) -> None:
    """**통과하는 바탕이 있어야 심은 결함이 뜻을 갖는다.**"""
    _tree(tmp_path)

    assert KEYS.verdict(tmp_path) == []


def test_쓰는_계열을_정규식으로_읽는다(tmp_path: Path) -> None:
    """`f"chroma/{name}"`와 `"silence/mixture"` **둘 다** 같은 꼴로 센다."""
    _tree(tmp_path)

    assert KEYS.written(tmp_path) == {
        "mert",
        "chroma",
        "chroma_series",
        "onset",
        "pitch",
        "silence",
    }


def test_읽는_자리_0곳인_계열을_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """선언에서 빼면 **`onset`이 걸린다** — D-0350의 「읽는 자리 0곳」이다."""
    _tree(tmp_path)
    monkeypatch.setattr(KEYS, "UNREAD", {})

    problems = KEYS.verdict(tmp_path)

    assert any("`onset/*`를 쓰고" in line and "0곳" in line for line in problems)


def test_선언한_계열에_읽는_자리가_생기면_잡는다(tmp_path: Path) -> None:
    """**양방향이다** (D-0371). 읽기 시작했는데 선언이 남아 있으면 그 선언이 거짓이다."""
    _tree(tmp_path, reader=READER_SOURCE.replace('"pitch/"', '"onset/"'))

    problems = KEYS.verdict(tmp_path)

    assert any("선언을 뺀다" in line for line in problems)


def test_안_읽는_것을_읽는다고_적으면_잡는다(tmp_path: Path) -> None:
    """**이번에 틀린 자리다.** 문서가 `onset/drums`를 부르는데 읽는 코드가 없었다."""
    _tree(tmp_path, docs="참조곡의 `onset/drums`에서 박을 읽는다.\n")

    problems = KEYS.verdict(tmp_path)

    assert any("README.md:1" in line for line in problems)


def test_선언한_줄은_비킨다(tmp_path: Path) -> None:
    """안 읽는다는 것을 **적는 줄**은 걸릴 수밖에 없다 (D-0219)."""
    _tree(
        tmp_path,
        docs=f"`onset/drums`는 아무도 안 읽는다. <!-- {KEYS.OK} 안 읽는다고 적는 줄 -->\n",
    )

    assert KEYS.verdict(tmp_path) == []


def test_선언은_그_줄만_비킨다(tmp_path: Path) -> None:
    """통째로 비키면 **한 줄 선언이 그 밑의 모든 말을 덮는다.**"""
    _tree(
        tmp_path,
        docs=f"`onset/drums`는 안 읽는다. <!-- {KEYS.OK} -->\n참조곡의 `onset/bass`에서 읽는다.\n",
    )

    problems = KEYS.verdict(tmp_path)

    assert any("README.md:2" in line for line in problems)
    assert not any("README.md:1" in line for line in problems)


def test_독스트링은_읽는_자리가_아니다(tmp_path: Path) -> None:
    """**내 시험이 내 주석에 걸리는 꼴을 세 판 겪었다** (D-0385 · D-0388 · D-0393).

    독스트링이 이름을 불러도 **배선이 아니다** — 그것을 읽는 자리로 세면 D-0395가
    고친 결함이 처음부터 안 잡힌다.
    """
    said = '"""우리는 `onset/drums`를 읽는다."""\n\nPREFIXES = ("chroma/",)\n'
    _tree(tmp_path, reader=said)

    problems = KEYS.verdict(tmp_path)

    assert any("keys_from_bundles.py:1" in line for line in problems)
    assert not any("선언을 뺀다" in line for line in problems)


def test_스템이_아닌_인용은_안_잡는다(tmp_path: Path) -> None:
    """`onset/*`는 *«이런 계열이 있다»*이고 *«우리가 읽는다»*가 아니다 (GR-0.8)."""
    _tree(tmp_path, docs="`onset/*`는 스펙트럼 선속이라 음량이 아니다.\n")

    assert KEYS.verdict(tmp_path) == []


def test_그물이_비면_운다(tmp_path: Path) -> None:
    """**계열을 0개 읽으면 「문제 0건」이 통과로 읽힌다** (D-0230)."""
    _tree(tmp_path)
    (tmp_path / "core" / "hathor" / "application" / "ingest_all.py").write_text(
        '"""이름을 안 짓는다."""\n', encoding="utf-8"
    )

    problems = KEYS.verdict(tmp_path)

    assert len(problems) == 1
    assert "그물이 비었다" in problems[0]


def test_실물에서_onset만_안_읽힌다() -> None:
    """**실물 저장소의 상태를 못으로 박는다.**

    묶음은 여섯 계열을 쓰고 그중 `onset` 넷(`other` · `drums` · `bass` · `vocals`)은
    **제품에서 읽는 자리가 0곳이다** (O-76). `mert`는 사람이 `--keys`로 이름을 주므로
    코드에 문자열이 없다 — 그 둘이 선언 둘이고 **셋째가 생기면 여기가 먼저 빨개진다.**
    """
    root = repo_root()
    families = KEYS.written(root)
    reading, _ = KEYS.scan(root, families)

    assert len(families) == 6
    assert [name for name in sorted(families) if not reading[name]] == ["mert", "onset"]
    assert sorted(KEYS.UNREAD) == ["onset"]
    assert sorted(KEYS.BY_ARGUMENT) == ["mert"]


def test_실물이_통과한다() -> None:
    """관문이 지금 초록인가. **고친 뒤의 상태가 이 줄이다.**"""
    assert KEYS.verdict(repo_root()) == []


# ------------------------------------------------ 배선 (D-0400 · D-0353)
#
# **부품을 재고 배선을 안 쟀다.** 위의 열둘은 `verdict()`를 직접 부르므로, 입구에서
# 그 호출이 끊겨도 아무도 안 운다 — 전수 변이가 **안 운 배선 셋**으로 그것을 잡았다.


def test_문제가_있으면_입구가_1을_낸다(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main()` → `verdict()`. **끊기면 「문제 0건」이 되어 통과한다.**"""
    monkeypatch.setattr(KEYS, "verdict", lambda _root: ["심은 문제"])
    monkeypatch.setattr("sys.argv", ["check_bundle_keys.py", "--check"])

    assert KEYS.main() == 1


def test_통과줄이_센_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` → `written()` · `scan()`. **수가 화면에 없으면 0인 것도 모른다** (D-0269)."""
    monkeypatch.setattr(KEYS, "verdict", lambda _root: [])
    monkeypatch.setattr(KEYS, "written", lambda _root: {"가계열"})
    monkeypatch.setattr(KEYS, "scan", lambda _root, _f: ({"가계열": ["x.py:1"]}, {"가계열": []}))
    monkeypatch.setattr("sys.argv", ["check_bundle_keys.py", "--check"])

    assert KEYS.main() == 0
    spoke = capsys.readouterr().out
    assert "계열 1개" in spoke, "written()이 끊겼다"
    assert "가계열 1곳" in spoke, "scan()이 끊겼다"
