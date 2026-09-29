"""문서 ↔ 실물 대조 검사 (D-0189)."""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("doc_fsck")


def test_저장소가_통과한다():
    """**이것이 `make docs`가 매번 보는 것이다.**"""
    assert CHECKER.check_paths() == []
    assert CHECKER.check_commands() == []
    assert CHECKER.check_orphan_tools() == []
    assert CHECKER.check_wiring() == []


def test_배선이_없는_스크립트를_부르면_잡는다(tmp_path, monkeypatch):
    """**`make apply`를 커밋 직전에 죽인 것이 이것이다** (D-0196).

    `check_orphan_tools`는 *"도구가 불리는가"*를 묻고 이쪽은 *"부르는 이름이
    실재하는가"*를 묻는다. 방향이 반대라 저쪽이 초록인 채로 이것이 났다.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "붙인다.sh").write_text(
        "python3 tools/없어진도구.py --check\n", encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring()


def test_주석_속_예시는_안_잡는다(tmp_path, monkeypatch):
    """사용법 예시가 주석에 산다. **실행되지 않으므로 없어도 안 죽는다.**"""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "붙인다.sh").write_text(
        "#   python3 tools/예시.py 처럼 쓴다\ntrue\n", encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring() == []


def test_없는_경로를_잡는다(tmp_path, monkeypatch):
    """**백틱 안의 저장소 경로만 본다** — 산문의 예시와 구분이 안 된다."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "README.md").write_text("`tools/없다.py`를 쓴다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_paths()


def test_산출물은_없어도_된다(tmp_path, monkeypatch):
    """`.park` 뒤에 있어 없는 것이 정상이다 (D-0075)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "README.md").write_text("`docs/x.jsonl`을 읽는다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_paths() == []


def test_과거_문서는_안_본다():
    """**결정 기록은 그때를 적는다.** 소급해서 고치지 않는다 (GR-0.2 · D-0081)."""
    assert "DECISIONS.md" not in CHECKER.LIVING


def test_파이썬이_인자로_부르는_도구도_본다(tmp_path, monkeypatch):
    """**`ship.py`가 `_run("python3", "tools/x.py")`로 부른다** (D-0199).

    인자가 쪼개져 있어 셸용 정규식이 못 본다. 개명하면 같은 자리에서 같은
    모양으로 죽는다 — D-0196이 겪은 그것이다.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "보낸다.py").write_text(
        'run("python3", "tools/없어진도구.py", "status")\n', encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring()


def test_문서_문자열_속_예시는_안_잡는다(tmp_path, monkeypatch):
    """`ast`로 **호출 인자만** 보므로 산문은 공짜로 빠진다."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "보낸다.py").write_text(
        '"""사용법:\n\n    python3 tools/예시.py --check\n"""\n', encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\ttrue\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    assert CHECKER.check_wiring() == []


# --------------------------------------------------------- 세어서 적은 수 (D-0263)


def test_저장소의_수가_실물과_같다():
    """**D-0263의 강제자.** `make docs`가 매번 보는 것이다."""
    assert CHECKER.check_counts() == []


def test_계약_수가_어긋나면_잡는다(tmp_path, monkeypatch):
    """**D-0261이 여섯째 계약을 넣고 «계약 5종» 네 곳을 안 고쳤다** (D-0263).

    경로도 도구도 실재하므로 이 검사의 다른 눈에는 안 걸렸다 — **숫자만 틀렸다.**
    경로가 틀리면 명령이 죽어서 알게 되지만 수가 틀리면 아무 일도 안 일어난다.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MASTER.md").write_text("**계약 5종**\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(
        CHECKER, "COUNTED", ((CHECKER.COUNTED[0][0], CHECKER.COUNTED[0][1], lambda: 6),)
    )

    problems = CHECKER.check_counts()
    assert len(problems) == 1
    assert "5" in problems[0] and "6" in problems[0]


def test_맞는_수는_안_잡는다(tmp_path, monkeypatch):
    """**맞을 때 조용해야 검사다.** 비교를 뒤집으면 여기가 운다."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MASTER.md").write_text(
        "import-linter 계약 6종 전부 KEPT\n| 계층 계약 | import-linter 6종 |\n", encoding="utf-8"
    )
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(
        CHECKER, "COUNTED", ((CHECKER.COUNTED[0][0], CHECKER.COUNTED[0][1], lambda: 6),)
    )

    assert CHECKER.check_counts() == []


def test_계약_수를_pyproject에서_센다():
    """**정본은 `core/pyproject.toml` 하나다** (D-0223). 문서가 아니라 선언을 센다."""
    assert CHECKER.contract_count() == 6


# ------------------------------- 앨범 효과 위의 수를 대표로 들지 않는다 (D-0284)


def test_M1_배수는_앨범_효과를_같이_적는다(monkeypatch, tmp_path):
    """**인용이 부푼 쪽을 골랐다** (D-0284).

    `M1`은 «같은 앨범 찾기»이고 **그 과제가 곧 앨범 효과다** — 같은 앨범은 마스터링이
    같아 쉽게 맞는다 (Mandel & Ellis, ISMIR 2005). 하네스는 그것을 알고 `M2`에서 같은
    앨범을 뺐는데, PLAN이 두 자리에서 `M1 20.4배`를 대표로 들고 있었다.

    **통제는 옳았고 인용이 틀렸다.** 선행연구를 안 봐서 그 이름조차 몰랐다.
    """
    bad = tmp_path / "PLAN.md"
    bad.write_text("검색은 M1 20.4배다.\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [bad])
    (problem,) = CHECKER.check_album_lift()
    assert "앨범 효과" in problem

    ok = tmp_path / "OK.md"
    ok.write_text("M1 20.4배 · M2 14.3배 (앨범 효과를 뺀 수)\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [ok])
    assert CHECKER.check_album_lift() == []


def test_M11은_M1이_아니다(monkeypatch, tmp_path):
    """**`M11 전이 초과`가 걸렸다** — 첫 판의 정규식이 `M1`을 접두사로 잡았다."""
    path = tmp_path / "PLAN.md"
    path.write_text("| 생성 | M11 전이 초과 | 3배 |\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    assert CHECKER.check_album_lift() == []


def test_지금_문서가_규약과_맞다():
    """**강제자다.** 살아 있는 문서가 지금 이 규칙을 지킨다."""
    assert CHECKER.check_album_lift() == []


# --------------------------------- 문서가 든 수는 사람이 세지 않는다 (D-0288)


def test_축이_다섯이다():
    """**세는 그물이 비면 «전부 맞다»가 거짓으로 참이 된다** (D-0230).

    축이 하나였다 — 문서에 손으로 적힌 수가 214개인데 기계가 보는 것은 `계약 N종`
    하나뿐이었다. 그 사이에 **「대장 201건 중」이 실물 223일 때까지** 아무도 안 셌고,
    그 줄이 사는 표의 머리말이 *"크기를 재서 적는다"*다.

    **넷에서 다섯이 됐다 (D-0307)**: `재현 불명`이 PLAN에 **16**으로 적혀 있고 실물이
    **11**이었다. 축을 놓자마자 *"11이라 적었는데 실물은 1"*로 걸렸다.
    """
    assert len(CHECKER.COUNTED) == 5, [name for name, _, _ in CHECKER.COUNTED]


def test_축마다_정본이_수를_낸다():
    """**정본이 없는 값은 축이 아니다.** 셋 다 실제로 세어져야 한다."""
    for name, _pattern, count in CHECKER.COUNTED:
        assert isinstance(count(), int), name
        assert count() > 0, f"{name}의 정본이 0을 낸다 — 세는 자리를 의심한다"


def test_대장은_표식_안만_센다():
    """**표식 밖의 `| D-xxxx |` 행이 있다** — 전부 세면 230, 대장은 223이다."""
    body = (CHECKER.ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    everywhere = len(re.findall(r"(?m)^\| D-\d{4} \|", body))
    assert CHECKER.ledger_rows() < everywhere


def test_틀린_수를_잡는다(monkeypatch, tmp_path):
    """**라벨 옆의 수를 읽는다.** 파일 어딘가에 정답이 있으면 통과하던 꼴이 아니다."""
    path = tmp_path / "PLAN.md"
    path.write_text("대장 201건 중 합성 24 · 나머지\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", CHECKER.COUNTED[1][1], lambda: 223),))
    (problem,) = CHECKER.check_counts()
    assert "201" in problem and "223" in problem


def test_지금_문서의_수가_전부_맞다():
    """**강제자다.** 이 시험이 D-0288 판에서 바로 한 건을 잡았다."""
    assert CHECKER.check_counts() == []


def test_고치는_쪽은_표기를_안_건드린다(monkeypatch, tmp_path):
    """**숫자만 간다** (D-0288). 라벨이 바뀌면 다음 판에 정규식이 제 자리를 못 찾는다."""
    path = tmp_path / "PLAN.md"
    path.write_text("| 빚 | 대장 **201**건 중 합성 24 · 나머지 |\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", CHECKER.COUNTED[1][1], lambda: 224),))

    (changed,) = CHECKER.fix_counts()

    assert "224" in changed
    assert path.read_text(encoding="utf-8") == "| 빚 | 대장 **224**건 중 합성 24 · 나머지 |\n"


def test_고친_뒤에는_검사가_조용하다(monkeypatch, tmp_path):
    """**쓰는 쪽과 보는 쪽이 같은 축을 읽는다.** 아니면 고쳐도 계속 빨갛다."""
    path = tmp_path / "PLAN.md"
    path.write_text("대장 1건 중 합성 24 · 나머지\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", CHECKER.COUNTED[1][1], lambda: 224),))

    assert CHECKER.check_counts()
    CHECKER.fix_counts()
    assert CHECKER.check_counts() == []


def _counted(pattern: str) -> int:
    """결정 기록에서 그 꼴로 시작하는 줄의 수. **도구와 다른 길로 센다.**"""
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(f"(?m){pattern}", body))


def test_재현_불명을_센다() -> None:
    """**PLAN이 16이라 적고 실물은 11이었다** (D-0307).

    `재현`은 *"지금 이 수치를 다시 내는 명령"*이라 조사하면 줄어드는 수다 (D-0136).
    줄어드는 수는 문서에서 낡고, **수가 틀려도 아무 일이 안 일어난다** (D-0263).
    """
    assert CHECKER.unknown_reproductions() == _counted("^재현 불명")
    # 축이 실제로 표에 실려 있어야 `--fix`가 그 자리를 고친다.
    assert "재현 불명" in {name for name, _, _ in CHECKER.COUNTED}


def test_재현_불명_축이_틀린_수를_잡는다() -> None:
    """**세는 그물이 비면 «0건»이 거짓으로 참이 된다** (D-0230)."""
    pattern = next(rule for name, rule, _ in CHECKER.COUNTED if name == "재현 불명")
    assert pattern.search("| 재현 불명 **11건** |") is not None
    assert pattern.search("| 재현 불명 1건 |") is not None
    assert pattern.search("재현 불명 — 이 수치를 내는 명령을 못 찾았다") is None
