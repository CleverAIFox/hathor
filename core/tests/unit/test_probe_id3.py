"""**ID3 · 코퍼스 전수의 배선** (D-0376).

D-0375가 `make measure`를 만들며 이 도구를 사슬에 넣었다. 그 전에는 어느 사슬에도
없어서 `make mutate WIRING=1`이 안 봤고, 재 보니 `named()` 자리가 비어 있었다 —
**파일명 규칙을 한 곡도 안 세어도 아무 시험이 안 울었다.**

**음원은 안 만든다** (D-0015). `ID3`·`MP3`를 가짜로 세우고 **빈 `.mp3` 파일**을 둔다 —
걷는 것은 진짜 `rglob`이고, 읽는 것만 가짜다. 1004곡을 흉내 내지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_id3")
MEASURED = tool_module("measured")

# (파일명, TPE1) — 첫 둘은 규칙을 지키고 셋째는 어긴다.
FILES = (
    ("아이유-밤편지.mp3", "아이유"),
    ("G-DRAGON-무제.mp3", "G-DRAGON"),  # **이름 안의 하이픈** (D-0374)
    ("딴놈-노래.mp3", "아이유"),
)


def _library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """빈 `.mp3` 셋과, 그 이름으로 태그를 돌려주는 가짜 독자."""
    root = tmp_path / "음원"
    root.mkdir()
    tags = {}
    for name, artist in FILES:
        (root / name).write_bytes(b"")
        tags[name] = artist

    monkeypatch.setattr(TOOL, "load_dotenv", dict)
    monkeypatch.setattr(TOOL, "library_root", lambda: root)
    monkeypatch.setattr(TOOL, "ID3", lambda path: {"TPE1": tags[Path(path).name]})
    monkeypatch.setattr(
        TOOL,
        "MP3",
        lambda _path: SimpleNamespace(info=SimpleNamespace(length=1.4, sample_rate=44100)),
    )
    return tags


def _canon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    canon = tmp_path / "measured.toml"
    canon.write_text(
        '[corpus]\nstamp = "2020-01-01"\nruler = "옛자"\ntracks = 3\n\n[corpus.counts]\n'
        "mp3 = 0\nbytes = 0\nseconds = 0\n"
        '"44.1kHz" = 0\n"48kHz" = 0\nread_failures = 0\nnfd_names = 0\n'
        "filename_convention = 0\n\n"
        '[id3]\nstamp = "2020-01-01"\nruler = "옛자"\ntracks = 3\n\n[id3.counts]\nTPE1 = 0\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(MEASURED, "CANON", canon)
    monkeypatch.setattr(MEASURED, "ROOT", tmp_path)
    monkeypatch.setattr(MEASURED, "ruler_of", lambda _t, _c: "심은자")
    return canon


def test_파일명_규칙을_태그로_센다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069 · D-0374). 셋 중 둘만 `<TPE1>-…` 꼴이다.

    옛 자(「하이픈이 있나」)는 **셋 다** 통과시킨다 — 그것이 늘 100%를 내던 까닭이다.
    """
    _library(tmp_path, monkeypatch)
    canon = _canon(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["probe_id3.py", "--emit"])

    assert TOOL.main() == 0

    written = canon.read_text(encoding="utf-8")
    assert "filename_convention = 2" in written, written
    assert "mp3 = 3" in written, "걸음 자체가 안 돌았다"


def test_규칙을_어긴_파일이_없으면_전부_센다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**거짓 경보가 아니다** (GR-0.8). 규칙을 지키면 전수가 맞는다 — 그의 1004곡이 그랬다."""
    _library(tmp_path, monkeypatch)
    monkeypatch.setattr(TOOL, "ID3", lambda path: {"TPE1": Path(path).stem.split("-")[0]})
    canon = _canon(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["probe_id3.py", "--emit"])

    assert TOOL.main() == 0
    assert "filename_convention = 3" in canon.read_text(encoding="utf-8")


def test_태그가_없으면_안_센다() -> None:
    """**빈 아티스트는 아무 파일명에나 맞는다.** 그것을 세면 자가 다시 느슨해진다."""
    assert TOOL.named("아무거나-노래", {}) is False
    assert TOOL.artist_of({}) == ""


def test_라이브러리가_없으면_2를_낸다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 쟀으면 통과가 아니다** (GR-0.5 · D-0367). 0도 1도 아닌 2다."""
    monkeypatch.setattr(TOOL, "load_dotenv", dict)
    monkeypatch.setattr(TOOL, "library_root", lambda: tmp_path / "없다")
    monkeypatch.setattr("sys.argv", ["probe_id3.py"])

    assert TOOL.main() == 2
    assert "라이브러리가 없다" in capsys.readouterr().err


def test_자에_이름이_있다() -> None:
    """**세는 법이 바뀌면 여기가 바뀐다** (D-0374). `measured`가 정본과 맞댄다."""
    for const in ("ID3_RULER", "CORPUS_RULER"):
        named: Any = getattr(TOOL, const)
        assert named
        assert MEASURED.ruler_of("probe_id3", const) == named
