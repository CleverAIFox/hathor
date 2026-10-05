"""**아티스트 표기의 상류** (D-0371).

D-0366이 `docs/measured.toml`을 정본으로 내릴 때 `[artist.counts]` 여섯 개는
**백분율에서 거꾸로 푼 수**였고, 그날부터 아무도 다시 센 적이 없었다. `--emit`을
붙여 그 빚을 갚는다.

**전수는 그의 기기에서만 돈다** — 입력이 `var/ingest/scan-*.jsonl`이고 거기에 곡별
태그가 들어 있다 (D-0015). 여기 시험은 **세는 법**과 **배선**을 본다: 심은 표본으로
수를 맞추고, 산출물이 없을 때 막는지 보고, `--emit`이 정본까지 닿는지 본다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_artist")
MEASURED = tool_module("measured")

# 여덟 곡. **구분자가 겹치는 곡을 일부러 넣는다** — 합이 곡 수를 넘는 것이 정상이다.
ARTISTS = (
    "아이유",  # 구분자 없음
    "아이유",  # 같은 문자열 — unique 는 하나로 센다
    "BTS (방탄소년단)",  # 괄호
    "Red Velvet [Irene]",  # 대괄호
    "박효신, 이수",  # 쉼표
    "Jay & Silent Bob",  # 앰퍼샌드
    "Zion.T feat. 크러쉬",  # feat. + 구분자말
    "A / B",  # 슬래시 — 구분자말
    "밴드 (feat. 손님), 게스트",  # 셋을 한 곡이 가진다 — 합이 곡 수를 넘는 까닭
)


def _records(artists: tuple[str, ...]) -> list[dict[str, object]]:
    return [
        {"source_key": f"{one}-제목{index}.mp3", "tags": {"artist": one}}
        for index, one in enumerate(artists)
    ]


def test_세는_법이_정의대로다() -> None:
    """**정의를 수와 함께 적는다** (D-0371). 수가 바뀐 날 자인지 음원인지 가른다."""
    counts = cast("dict[str, int]", TOOL.tally(list(ARTISTS)))

    assert counts["unique"] == 8, "같은 문자열은 하나로 센다"
    assert counts["bracket"] == 3, "괄호와 대괄호를 같이 센다"
    assert counts["comma"] == 2
    assert counts["ampersand"] == 1
    assert counts["separator_words"] == 3, "`feat.` 둘과 `/` 하나"
    assert counts["plain"] == 2, "어느 구분자도 없는 곡 — 같은 문자열 둘"


def test_합이_곡_수를_넘어도_된다() -> None:
    """**곡 하나가 구분자를 여럿 가질 수 있다.** 합을 100%로 읽으면 안 된다."""
    counts = cast("dict[str, int]", TOOL.tally(list(ARTISTS)))
    kinds = ("bracket", "comma", "ampersand", "separator_words", "plain")

    assert sum(counts[one] for one in kinds) > len(ARTISTS), (
        "겹치는 곡이 없으면 이 표본으로는 그 성질을 못 보인다"
    )


def test_내는_키가_정본과_같다() -> None:
    """**양방향** (D-0371 · D-0363). `measured`가 보는 그 선언을 여기서도 본다."""
    canon = cast("dict[str, dict[str, object]]", MEASURED.canon())
    counts = cast("dict[str, int]", canon["artist"]["counts"])

    assert set(TOOL.EMITS) == set(counts)
    assert set(TOOL.tally(list(ARTISTS))) == set(TOOL.EMITS), "세는 법과 선언이 갈렸다"


def test_산출물이_없으면_막고_명령을_찍는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069 · D-0367). *«없다»*만 찍으면 왜 없는지는 안 적힌다."""
    monkeypatch.setattr(TOOL, "INGEST", tmp_path / "없다")
    monkeypatch.setattr("sys.argv", ["probe_artist.py", "--emit"])

    assert TOOL.main() == 2

    said = capsys.readouterr().err
    assert "ingest scan" in said, said
    assert "HATHOR_LIBRARY_ROOT" in said, said


def test_emit이_정본까지_닿는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069). 센 수가 `[artist.counts]`에 **써지는가.**

    D-0368 ~ D-0370이 세 판 연속으로 *«부품을 재고 배선을 안 쟀다»*였다. 여기는
    `main()`을 거쳐 **정본 파일의 글자가 바뀌는 것**까지 본다.
    """
    ingest = tmp_path / "ingest"
    ingest.mkdir()
    (ingest / "scan-20260101T000000Z.jsonl").write_text(
        "\n".join(json.dumps(one, ensure_ascii=False) for one in _records(ARTISTS)),
        encoding="utf-8",
    )
    canon = tmp_path / "measured.toml"
    canon.write_text(
        '[artist]\nstamp = "2025-09-19"\ntracks = 8\n\n[artist.counts]\n'
        "unique = 1\nbracket = 1\ncomma = 1\nampersand = 1\nplain = 1\nseparator_words = 1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(TOOL, "INGEST", ingest)
    monkeypatch.setattr(MEASURED, "CANON", canon)
    monkeypatch.setattr(MEASURED, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["probe_artist.py", "--emit"])

    assert TOOL.main() == 0

    written = canon.read_text(encoding="utf-8")
    assert "unique = 8" in written, written
    assert "bracket = 3" in written
    assert "plain = 2" in written
    spoke = capsys.readouterr().out
    assert "괄호 또는 대괄호를 품은 곡" in spoke, "정의를 안 찍었다"
    assert "unique 1 → 8" in spoke, spoke


def test_emit을_안_주면_정본을_안_건드린다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**사람이 읽는 전수는 읽기만 한다.** 돌려 보는 것이 정본을 바꾸면 못 돌린다."""
    ingest = tmp_path / "ingest"
    ingest.mkdir()
    (ingest / "scan-20260101T000000Z.jsonl").write_text(
        "\n".join(json.dumps(one, ensure_ascii=False) for one in _records(ARTISTS)),
        encoding="utf-8",
    )
    canon = tmp_path / "measured.toml"
    canon.write_text("[artist.counts]\nunique = 1\n", encoding="utf-8")
    before = canon.read_text(encoding="utf-8")
    monkeypatch.setattr(TOOL, "INGEST", ingest)
    monkeypatch.setattr(MEASURED, "CANON", canon)
    monkeypatch.setattr("sys.argv", ["probe_artist.py"])

    assert TOOL.main() == 0
    assert canon.read_text(encoding="utf-8") == before
