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
    monkeypatch.setattr(MEASURED, "ruler_of", lambda _t, _c: "심은자")
    monkeypatch.setattr("sys.argv", ["probe_artist.py", "--emit"])

    assert TOOL.main() == 0

    written = canon.read_text(encoding="utf-8")
    assert "unique = 8" in written, written
    assert 'ruler = "심은자"' in written, "자 이름을 안 썼다 (D-0374)"
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


# ------------------------------------------------- 파일명 ↔ 태그 (D-0374)
#
# 그의 기기 전수가 **불일치 18곡(1.8%)**을 찍었고 그중 **16곡이 `G-DRAGON`** 하나였다.
# 자가 첫 하이픈에서 잘라 아티스트를 `G`로 읽은 탓이다 — **거짓 경보는 진짜 경보를
# 죽인다** (GR-0.8). 태그로 시작하는지 보면 이름 안의 하이픈과 안 싸운다.

MATCHES = (
    ("G-DRAGON-무제", "G-DRAGON", True),
    ("Anne-Marie-2002", "Anne-Marie", True),
    ("아이유-밤편지", "아이유", True),
    ("디핵(D-Hack)-OHAYO MY NIGHT", "디핵(D-Hack), PATEKO(파테코)", False),
    ("딴사람-노래", "아이유", False),
    ("아이유", "", False),
)


@pytest.mark.parametrize(("stem", "artist", "same"), MATCHES)
def test_이름_안의_하이픈과_안_싸운다(stem: str, artist: str, same: bool) -> None:
    """**그날 실물에 있던 이름 그대로다.** 넷째는 **진짜 불일치**다 — 태그가 둘인데
    파일명은 하나다. 거짓 경보 열여섯이 그것을 덮고 있었다."""
    assert TOOL.matches(stem, artist) is same


def test_자에_이름이_있다() -> None:
    """**세는 법이 바뀌면 여기가 바뀐다** (D-0374). `measured`가 정본과 맞댄다."""
    assert TOOL.RULER
    assert MEASURED.ruler_of("probe_artist", "RULER") == TOOL.RULER


# ------------------------------------------------- 배선 (D-0376)
#
# **D-0375가 `make measure`를 만들며 이 도구를 사슬에 넣었다.** 그 전에는 어느 사슬에도
# 없어서 `make mutate WIRING=1`이 안 봤고, 재 보니 `main()`의 **네 자리가 비어 있었다** —
# 세 절을 통째로 안 찍어도 아무 시험이 안 울었다. D-0368 ~ D-0370과 같은 모양이다.


def _planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """심은 스캔 산출물 하나. `latest_jsonl()`이 이것을 고르고 `load_records()`가 읽는다."""
    ingest = tmp_path / "ingest"
    ingest.mkdir()
    (ingest / "scan-20260101T000000Z.jsonl").write_text(
        "\n".join(json.dumps(one, ensure_ascii=False) for one in _records(ARTISTS)),
        encoding="utf-8",
    )
    monkeypatch.setattr(TOOL, "INGEST", ingest)
    return ingest


def test_세_절이_전부_화면에_오른다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`analyze()` · `cross_check_filenames()` · `check_bracket_script()` 자리 (D-0376).

    **절 하나를 통째로 안 찍어도 조용했다.** 사람이 읽는 전수인데 읽을 것이 사라진다.
    """
    _planted(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["probe_artist.py"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    assert "구분자 출현 빈도" in spoke, "analyze()가 안 닿았다"
    assert "파일명 대 태그 교차검증" in spoke, "cross_check_filenames()가 안 닿았다"
    assert "괄호 표기 체계 대조" in spoke, "check_bracket_script()가 안 닿았다"


def test_고른_산출물과_읽은_줄이_화면에_오른다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`latest_jsonl()` · `load_records()` 자리 (D-0376 · D-0360).

    **어느 파일을 읽었는지 안 적으면** 낡은 스캔을 보고도 모른다 (D-0269).
    """
    ingest = _planted(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["probe_artist.py"])

    assert TOOL.main() == 0

    spoke = capsys.readouterr().out
    picked = TOOL.latest_jsonl(ingest)
    assert picked is not None
    assert picked.name in spoke, "고른 산출물의 이름이 화면에 없다"
    assert f"총 {len(TOOL.load_records(picked))}곡" in spoke, "읽은 줄 수가 화면에 없다"
