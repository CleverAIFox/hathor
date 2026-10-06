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

RERUN = "다시 안 쟀다"
"""**자가 바뀐 블록은 다시 재야 한다** (D-0374) — 그의 기기에서만 된다.

그 판정은 **열려 있을 수 있다.** 여기 시험은 *«그것 말고 다른 문제가 없나»*를 본다 —
수를 못으로 박으면 그가 `make measure`를 돌린 날 **고친 쪽이 빨개진다.**
"""


def _other(problems: list[str]) -> list[str]:
    return [one for one in problems if RERUN not in one]


def test_거울이_정본과_같다() -> None:
    """`make check`이 보는 그 판정. **두 곳에 적으면 어긋난다** (D-0043)."""
    assert _other(TOOL.check()) == []


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

    problems = _other(TOOL.check())

    assert len(problems) == 1, f"손으로 고친 수를 못 봤다: {problems}"
    assert "개발 코퍼스" in problems[0]


def test_fix가_거울을_되돌린다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "MASTER.md"
    master = (TOOL.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    fake.write_text(master.replace("| 곡 수 | 1,004 |", "| 곡 수 | 9,999 |", 1), encoding="utf-8")
    monkeypatch.setattr(TOOL, "MASTER", fake)

    assert TOOL.fix() == ["corpus"]
    assert _other(TOOL.check()) == []
    assert "9,999" not in fake.read_text(encoding="utf-8")


def test_표식이_없으면_거울이_아니라고_한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**표식을 지우고 손으로 적는 길**을 막는다 (D-0126)."""
    fake = tmp_path / "MASTER.md"
    fake.write_text("### □ 개발 코퍼스 실측\n\n| 항목 | 값 |\n", encoding="utf-8")
    monkeypatch.setattr(TOOL, "MASTER", fake)

    problems = _other(TOOL.check())

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


# ------------------------------------------------- 상류 (D-0371)
#
# **D-0366은 블록 셋을 내리고 `--emit`을 하나만 붙였다.** `corpus` 여덟 · `artist`
# 여섯, 모두 **열넷**이 「백분율에서 거꾸로 푼 수」로 섰고 그 기록은 *«artist 집계 6개는
# 아직 상류가 없다»*라고 적었다 — **세 블록 중 둘이었다.** 세어 보지 않고 적은 수다.
#
# 여기 자는 **양방향**이다 (D-0363). 한쪽만 보면 아무도 안 세는 수가 눌러앉고,
# 반대쪽만 보면 센 수를 버리는 것이 안 보인다.


def test_정본의_수마다_세는_도구가_있다() -> None:
    """`make check`이 보는 그 판정."""
    assert _other(TOOL.check_upstream(TOOL.canon())) == []


def test_블록마다_상류가_선언돼_있다() -> None:
    """**선언이 빠지면 그 블록은 아무도 안 본다** (D-0126)."""
    assert set(TOOL.SOURCES) == set(TOOL.BLOCKS), "표는 있는데 상류 선언이 없다"


def test_아무도_안_세는_수를_잡는다() -> None:
    """**심은 결함** (D-0069). 정본에만 있고 도구가 안 내는 키."""
    data = TOOL.canon()
    data["artist"]["counts"] = {**data["artist"]["counts"], "심은것": 7}

    problems = _other(TOOL.check_upstream(data))

    assert len(problems) == 1, problems
    assert "아무도 안 센다" in problems[0]
    assert "심은것" in problems[0]


def test_센_수를_버리는_것을_잡는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 도구는 내는데 정본이 안 받는 키.

    이쪽이 더 조용하다 — 표는 멀쩡해 보이고 **새로 센 것만 사라진다.**
    """
    data = TOOL.canon()
    want = set(data["artist"]["counts"]) | {"버려진것"}
    monkeypatch.setattr(TOOL, "emitted", lambda _t, _c: want)
    monkeypatch.setattr(TOOL, "SOURCES", {"artist": TOOL.SOURCES["artist"]})

    problems = TOOL.check_upstream(data)

    assert len(problems) == 1, problems
    assert "센 수를 버린다" in problems[0] and "버려진것" in problems[0]


def test_상류_선언이_사라지면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(TOOL, "emitted", lambda _t, _c: set())

    problems = TOOL.check_upstream(TOOL.canon())

    assert len(problems) == len(TOOL.SOURCES), problems
    assert all("상류 선언이 사라졌다" in one for one in problems), problems


def test_도구의_선언을_글자로_읽는다() -> None:
    """**임포트하지 않는다** — `probe_id3`가 `mutagen`을 끌어오고 CI에 없다 (D-0256)."""
    assert "TSSE" in TOOL.emitted("probe_id3", "ID3_EMITS")
    assert "seconds" in TOOL.emitted("probe_id3", "CORPUS_EMITS")
    assert "unique" in TOOL.emitted("probe_artist", "EMITS")
    assert TOOL.emitted("probe_id3", "없는상수") == set()


def test_상류_판정이_입구까지_닿는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**심은 결함** (D-0069 · D-0352). `check()`에서 빼도 아무 시험이 안 울었다.

    위의 시험들이 `check_upstream()`을 **직접** 불렀기 때문이다 — 그 함수가 멀쩡해도
    `make check`이 안 부르면 아무 일도 안 일어난다. 여기는 `main()`을 거친다.
    """
    monkeypatch.setattr(TOOL, "check_upstream", lambda _data: ["심은 것"])
    monkeypatch.setattr("sys.argv", ["measured.py", "--check"])

    assert TOOL.main() == 1
    assert "심은 것" in capsys.readouterr().err


# ------------------------------------------------- 실측일 (D-0373)
#
# **`--emit`이 수를 쓰면서 날짜를 안 썼다.** 그래서 `[artist]`가 2025-09-19로 남았고,
# D-0371은 「마지막 실측」을 **주석에 손으로** 적었다 — 이 정본이 막으려던 바로 그
# 꼴이다 (GR-0.7). 날짜도 도구가 쓰고, 거울이 그것을 들고 다닌다.


def test_표가_언제_잰_수인지_말한다() -> None:
    """**수만 있고 날짜가 없으면 낡았는지 알 수 없다** (D-0269)."""
    data = TOOL.canon()

    for name in TOOL.BLOCKS:
        body = TOOL.table(name, data[name])
        assert f"{data[name]['stamp']} 실측" in body, name
        assert f"{data[name]['tracks']}곡 전수" in body, name


def test_날짜가_없으면_막는다() -> None:
    """**심은 결함** (D-0069 · D-0230). 날짜 없는 표는 **언제 잰 수인지 모르는 표**다."""
    data = TOOL.canon()
    broken = {**data["artist"]}
    broken.pop("stamp")

    with pytest.raises(LookupError, match="언제 잰 수인지"):
        TOOL.table("artist", broken)


def test_다시_재면_날짜가_바뀐다() -> None:
    """`restamp()` — **`--emit`이 부른다.** 수가 안 바뀌어도 날짜는 바뀐다."""
    text = '[artist]\nstamp = "2020-01-01"\ntracks = 8\n\n[artist.counts]\nunique = 1\n'

    fixed = TOOL.restamp(text, "artist", today="2026-10-05")

    assert 'stamp = "2026-10-05"' in fixed
    assert "unique = 1" in fixed, "수를 건드렸다"


def test_다른_블록의_날짜는_안_건드린다() -> None:
    """**블록 하나를 재면 그 블록만 바뀐다.** 안 그러면 안 잰 것이 재어진 척한다."""
    text = '[corpus]\nstamp = "2020-01-01"\n\n[artist]\nstamp = "2020-01-01"\ntracks = 8\n'

    fixed = TOOL.restamp(text, "artist", today="2026-10-05")

    assert fixed.count('"2020-01-01"') == 1, fixed
    assert fixed.index("[corpus]") < fixed.index('stamp = "2020-01-01"')


def test_적을_자리가_없으면_막는다() -> None:
    """**조용히 안 적는 것보다 막는 것이 낫다** (GR-0.5)."""
    with pytest.raises(LookupError, match="stamp"):
        TOOL.restamp("[artist]\ntracks = 8\n", "artist", today="2026-10-05")


def test_주석이_날짜를_또_적지_않는다() -> None:
    """**D-0371이 범한 그 자리** (GR-0.7 · D-0043).

    정본 주석에 「마지막 실측」표를 손으로 적었다. 같은 날짜가 두 곳에 살면 한쪽만
    고쳐지고, **그 한쪽이 주석이라 아무도 안 본다.**
    """
    body = TOOL.CANON.read_text(encoding="utf-8")
    head = body[: body.index("[corpus]")]

    assert "마지막 실측 |" not in head, "주석이 실측일 표를 또 든다"


# ------------------------------------------------- 자의 이름 (D-0374)
#
# **`seconds`가 10초 움직였을 때 옛 수가 어떤 자로 나왔는지 기록이 없었다.** 음원인지
# 자인지 가르려고 `bytes`를 봐야 했다 (D-0373). 자에 이름이 있으면 그 자리에서 안다.


def test_자가_바뀌면_다시_재라고_운다() -> None:
    """**심은 결함** (D-0069). 도구의 자와 정본의 자가 다르면 그 수는 **없는 자의 것**이다."""
    data = TOOL.canon()
    data["artist"] = {**data["artist"], "ruler": "옛날자"}

    problems = TOOL.check_upstream(data)

    assert any("옛날자" in one and RERUN in one for one in problems), problems


def test_자에_이름이_없으면_막는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(TOOL, "ruler_of", lambda _t, _c: "")

    problems = TOOL.check_upstream(TOOL.canon())

    assert len(problems) == len(TOOL.SOURCES), problems
    assert all("자에 이름이 없다" in one for one in problems), problems


def test_자_이름을_정본에_넣는다() -> None:
    """`reruler()` — **`--emit`이 부른다.** 없으면 `stamp` 아래에 만든다."""
    without = '[artist]\nstamp = "2026-10-05"\ntracks = 8\n'
    made = TOOL.reruler(without, "artist", "새자")
    assert 'ruler = "새자"' in made

    again = TOOL.reruler(made, "artist", "더새자")
    assert 'ruler = "더새자"' in again
    assert again.count("ruler =") == 1, "자 이름이 두 벌이 됐다"
