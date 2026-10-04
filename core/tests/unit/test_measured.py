"""**실측 집계의 정본은 한 곳이다** (D-0366 · D-0043).

세 표 — 개발 코퍼스 · ID3 프레임 · 아티스트 표기 — 가 `MASTER.md`에 **손으로 타이핑돼
있었다.** 세는 도구(`probe_id3.py` · `probe_artist.py`)는 있었고 **사람이 그 수를
옮겨 적었다.** 옮겨 적은 수는 낡는다 — D-0361이 캡션의 «계약 5종»에서 같은 꼴을 잡았다.

이제 `docs/measured.toml`이 정본이고 MASTER의 표는 **거울**이다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module

TOOL = tool_module("measured")


def test_거울이_정본과_같다() -> None:
    """`make check`이 보는 그 판정. **두 곳에 적으면 어긋난다** (D-0043)."""
    assert TOOL.check() == []


def test_세_블록이_다_거울이다() -> None:
    """표식이 없는 블록은 **손으로 적힌 표**다 — 그것을 막는 것이 이 도구다."""
    master = (TOOL.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")

    for name in TOOL.BLOCKS:
        assert TOOL.begin(name) in master, f"{name}이 거울이 아니다"
        assert TOOL.present(master, name), f"{name} 블록이 비었다"


def test_거울을_손으로_고치면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**이것이 이 관문의 값이다.** 정본을 안 고치고 문서만 고치는 길을 막는다."""
    fake = tmp_path / "MASTER.md"
    master = (TOOL.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    fake.write_text(master.replace("| 곡 수 | 1,004 |", "| 곡 수 | 9,999 |", 1), encoding="utf-8")
    monkeypatch.setattr(TOOL, "MASTER", fake)

    problems = TOOL.check()

    assert len(problems) == 1, f"손으로 고친 수를 못 봤다: {problems}"
    assert "개발 코퍼스" in problems[0]


def test_fix가_거울을_되돌린다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "MASTER.md"
    master = (TOOL.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    fake.write_text(master.replace("| 곡 수 | 1,004 |", "| 곡 수 | 9,999 |", 1), encoding="utf-8")
    monkeypatch.setattr(TOOL, "MASTER", fake)

    assert TOOL.fix() == ["corpus"]
    assert TOOL.check() == []
    assert "9,999" not in fake.read_text(encoding="utf-8")


def test_표식이_없으면_거울이_아니라고_한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**표식을 지우고 손으로 적는 길**을 막는다 (D-0126)."""
    fake = tmp_path / "MASTER.md"
    fake.write_text("### □ 개발 코퍼스 실측\n\n| 항목 | 값 |\n", encoding="utf-8")
    monkeypatch.setattr(TOOL, "MASTER", fake)

    problems = TOOL.check()

    assert len(problems) == len(TOOL.BLOCKS)
    assert all("거울이 아니다" in one for one in problems)
    # **무엇을 넣어야 하는지를 화면에 적는다.** 「표식이 없다」만 찍으면 사람이
    # 표식의 모양을 찾으러 코드를 읽는다 (D-0269와 같은 규율).
    assert any(TOOL.begin("corpus") in one for one in problems), "표식의 모양이 화면에 없다"


def test_정본이_비면_막는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「거울과 같다」가 거짓으로 참이 된다** (D-0230)."""
    fake = tmp_path / "measured.toml"
    fake.write_text(
        "\n".join(
            f'[{name}]\ntracks = 1\n[{name}.counts]\n[[{name}.display]]\nlabel = "빈 표"\n'
            f'kind = "count"\nof = "없다"\n'
            for name in TOOL.BLOCKS
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(TOOL, "CANON", fake)

    # 행이 셋(블록마다 하나)이라 바닥 20 아래다. **센 것이 없으면 통과가 거짓이다.**
    assert any("그물이 비었다" in one for one in TOOL.check())


def test_곡_수가_세_블록에서_같다() -> None:
    """**1004는 한 번만 재는 수다.** 블록마다 다르면 어느 판의 실측인지 알 수 없다."""
    data = TOOL.canon()
    tracks = {name: data[name]["tracks"] for name in ("corpus", "id3", "artist")}

    assert len(set(tracks.values())) == 1, f"곡 수가 갈렸다: {tracks}"


def test_그림이_정본을_직접_읽는다() -> None:
    """**거울을 거치면 그 사이에 손으로 고친 수를 그림이 그린다** (D-0366).

    관문이 뒤에서 잡지만 **그림은 이미 틀렸다.** 그래서 두 그림은 정본을 직접 읽는다.
    """
    source = (TOOL.ROOT / "tools" / "render_charts.py").read_text(encoding="utf-8")

    assert 'table("### □ ID3 프레임 실측' not in source, "그림이 거울을 읽는다"
    assert 'table("### □ 아티스트 표기 실측")' not in source, "그림이 거울을 읽는다"
    assert source.count("canon_source.canon()") >= 2


def test_백분율을_정본에_안_적는다() -> None:
    """**센 수와 적은 수를 가른다** (D-0366).

    처음 판은 완성된 표 행을 TOML에 넣었다 — 그러면 **손으로 적은 수를 MD에서 TOML로
    옮긴 것**뿐이고 상류 도구가 다시 쓸 수 없다. 사용자가 그 자리에서 짚었다:
    *"왜 두 벌이 되는 거야? 기존 걸 날리면 되지 않냐."*
    """
    text = TOOL.CANON.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("#"))

    assert "%" not in body, "정본에 백분율이 적혀 있다 — 계산해서 내야 한다"
    assert "rows = " not in body, "정본에 완성된 표 행이 있다"


def test_센_수에서_백분율을_계산한다() -> None:
    """`62.8%`를 내는 정수는 **631 하나뿐이다.** 그렇게 복원했고 그 복원이 검사된다."""
    data = TOOL.canon()
    rows = {row[0]: row[1] for row in TOOL.rows_of(data["id3"])}

    assert rows["TSSE (인코더)"] == "62.8%"
    assert data["id3"]["counts"]["TSSE"] == 631
    assert TOOL.pct(631, 1004) == "62.8%"
    assert TOOL.pct(630, 1004) == "62.7%", "631이 유일한 정수라는 근거"


def test_emit이_센_수만_간다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**상류가 편집을 덮지 않는다** (D-0288과 같은 규율). `display`는 사람 것이다."""
    fake = tmp_path / "measured.toml"
    fake.write_text(TOOL.CANON.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(TOOL, "CANON", fake)

    changed = TOOL.emit("id3", {"TSSE": 700, "TIT2": 1004})

    assert changed == ["TSSE 631 → 700"], f"바뀐 것이 그것만이 아니다: {changed}"
    body = fake.read_text(encoding="utf-8")
    assert "TSSE = 700" in body
    assert 'label = "TSSE (인코더)"' in body, "편집을 덮었다"
    assert "use = " in body


def test_emit이_없는_키를_조용히_안_더한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**조용히 자라는 정본은 아무도 안 읽는 정본이 된다** (D-0126)."""
    fake = tmp_path / "measured.toml"
    fake.write_text(TOOL.CANON.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(TOOL, "CANON", fake)

    changed = TOOL.emit("id3", {"TXXX": 12})

    assert any("안 더했다" in one and "TXXX" in one for one in changed)
    assert "TXXX" not in fake.read_text(encoding="utf-8")


def test_상류가_그_출구를_든다() -> None:
    """`probe_id3.py --emit`이 없으면 정본은 **다시 재어지지 않는다** (D-0121)."""
    probe = (TOOL.ROOT / "tools" / "probe_id3.py").read_text(encoding="utf-8")

    assert '"--emit"' in probe
    assert "measured.emit(" in probe


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


def test_판정이_입구에_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**부품은 재고 배선은 안 쟀다** (D-0359). 위의 시험들은 `check()`를 직접 부른다."""
    monkeypatch.setattr(TOOL, "check", lambda: ["심은 문제"])
    monkeypatch.setattr("sys.argv", ["measured.py", "--check"])

    assert TOOL.main() == 1
    assert "심은 문제" in _spoke(capsys)


def test_통과줄이_센_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`canon()` · `rows_of()` 두 자리. **수가 화면에 없으면 0인 것도 모른다** (D-0230)."""
    monkeypatch.setattr(TOOL, "check", list)
    monkeypatch.setattr("sys.argv", ["measured.py", "--check"])

    assert TOOL.main() == 0
    spoke = _spoke(capsys)
    assert "26행" in spoke, "rows_of()가 끊겼다"
    assert "곡 1004" in spoke, "canon()이 끊겼다"


def test_list가_블록마다_행_수를_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["measured.py", "--list"])

    assert TOOL.main() == 0
    spoke = _spoke(capsys)
    assert "12행" in spoke and "ID3 프레임 실측" in spoke


def test_fix가_입구에_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """끊으면 **「고친 자리 0곳」만 찍고 아무것도 안 고친다.**"""
    monkeypatch.setattr(TOOL, "fix", lambda: ["심은블록"])
    monkeypatch.setattr("sys.argv", ["measured.py", "--fix"])

    assert TOOL.main() == 0
    spoke = _spoke(capsys)
    assert "심은블록" in spoke and "고친 자리 1곳" in spoke


def test_정본을_못_읽으면_2를_낸다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 쟀으면 통과가 아니다** (GR-0.5). 0도 1도 아닌 2다."""
    monkeypatch.setattr(TOOL, "CANON", tmp_path / "없다.toml")
    monkeypatch.setattr("sys.argv", ["measured.py", "--check"])

    assert TOOL.main() == 2
    assert "못 읽었다" in _spoke(capsys)


def test_표식_이름이_정본과_같은_말을_쓴다() -> None:
    """`begin()` 자리. **표식과 블록 이름이 갈리면 거울을 영원히 못 찾는다** (D-0043)."""
    data = TOOL.canon()

    for name in TOOL.BLOCKS:
        assert name in data, f"{name} 블록이 정본에 없다"
        assert TOOL.begin(name) == f"<!-- measured:{name}:begin -->"
