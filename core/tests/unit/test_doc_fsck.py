"""문서 ↔ 실물 대조 검사 (D-0189)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def cast_list(value: object) -> list[str]:
    """경로로 실은 모듈의 반환은 `Any`다 (D-0264). 한 자리에서 좁힌다."""
    assert isinstance(value, list)
    return [str(one) for one in value]


CHECKER = tool_module("doc_fsck")


def _axis(name: str) -> object:
    """축을 **이름으로** 집는다 (D-0349). 자리로 집으면 축을 넣을 때마다 시험이 깨진다."""
    for axis in CHECKER.COUNTED:
        if axis[0] == name:
            return axis
    raise LookupError(f"«{name}» 축이 없다")


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
        CHECKER,
        "COUNTED",
        (("import-linter 계약", _axis("import-linter 계약")[1], lambda: 6),),  # type: ignore[index]
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
        CHECKER,
        "COUNTED",
        (("import-linter 계약", _axis("import-linter 계약")[1], lambda: 6),),  # type: ignore[index]
    )

    assert CHECKER.check_counts() == []


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


def test_실물_워크플로가_문서에_다_있다() -> None:
    """**`fire-lane`의 `readmecheck`를 가져왔다** — 실물과 README 표를 대조한다.

    `check_paths`는 *"문서가 가리키는 것이 실물로 있나"*만 본다. 거꾸로는 안 봐서
    **`codeql.yml`이 스무 판 넘게 `MASTER`의 CI 표에 없었다.** 문서→실물만 보면
    **실물이 늘어난 것은 영원히 안 보인다.**
    """
    assert cast_list(CHECKER.check_orphan_workflows()) == []


def test_심은_워크플로를_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**카나리아다.** 문서가 모르는 워크플로를 심고 우는지 본다."""
    base = tmp_path / ".github" / "workflows"
    base.mkdir(parents=True)
    (base / "심은것.yml").write_text("name: 심은것\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [])
    monkeypatch.setattr(CHECKER, "compose_services", lambda: [])
    # **관문 표도 못으로 박는다** — 합성 트리에 `MASTER`가 없다.
    monkeypatch.setattr(CHECKER, "gate_tools", lambda: [])
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "MASTER.md").write_text(CHECKER.GATE_TABLE + "\n", encoding="utf-8")

    problems = cast_list(CHECKER.check_orphan_workflows())

    assert any("심은것" in one for one in problems)


def test_워크플로가_0개면_통과시키지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [])
    monkeypatch.setattr(CHECKER, "compose_services", lambda: [])
    # **관문 표도 못으로 박는다** — 합성 트리에 `MASTER`가 없다.
    monkeypatch.setattr(CHECKER, "gate_tools", lambda: [])
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "MASTER.md").write_text(CHECKER.GATE_TABLE + "\n", encoding="utf-8")
    assert cast_list(CHECKER.check_orphan_workflows())

    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    assert cast_list(CHECKER.check_orphan_workflows())


def test_실물_서비스가_문서에_다_있다() -> None:
    """**컨테이너 표에 일곱이고 `compose`에 열이었다** (D-0349).

    `labelstudio`·`prometheus`·`grafana` 셋이 표에 없었다. `check_compose`는 **메모리만**
    보고 이름은 안 본다 — *"서비스 10개"*를 찍으면서 문서가 일곱만 적은 것은 못 봤다.
    """
    assert cast_list(CHECKER.check_orphan_workflows()) == []
    assert len(CHECKER.compose_services()) >= 10


def test_심은_서비스를_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**카나리아다.** 첫 판에 한글 이름으로 심었더니 **안 울었다** — 정규식이
    `[a-z]`만 보기 때문이다. `compose` 서비스 이름은 실물이 전부 ASCII다."""
    monkeypatch.setattr(CHECKER, "compose_services", lambda: ["plantedcanary"])
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [])
    monkeypatch.setattr(CHECKER, "gate_tools", lambda: [])
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "MASTER.md").write_text(CHECKER.GATE_TABLE + "\n", encoding="utf-8")

    problems = cast_list(CHECKER.check_orphan_workflows())

    assert any("plantedcanary" in one for one in problems)


def test_틀린_수를_잡는다(monkeypatch, tmp_path):
    """**라벨 옆의 수를 읽는다.** 파일 어딘가에 정답이 있으면 통과하던 꼴이 아니다."""
    path = tmp_path / "PLAN.md"
    path.write_text("대장 201건 중 합성 24 · 나머지\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    pattern = _axis("결정 대장")[1]  # type: ignore[index]
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", pattern, lambda: 223),))
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
    ledger = _axis("결정 대장")[1]  # type: ignore[index]
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", ledger, lambda: 224),))

    (changed,) = CHECKER.fix_counts()

    assert "224" in changed
    assert path.read_text(encoding="utf-8") == "| 빚 | 대장 **224**건 중 합성 24 · 나머지 |\n"


def test_고친_뒤에는_검사가_조용하다(monkeypatch, tmp_path):
    """**쓰는 쪽과 보는 쪽이 같은 축을 읽는다.** 아니면 고쳐도 계속 빨갛다."""
    path = tmp_path / "PLAN.md"
    path.write_text("대장 1건 중 합성 24 · 나머지\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "living_documents", lambda: [path])
    ledger = _axis("결정 대장")[1]  # type: ignore[index]
    monkeypatch.setattr(CHECKER, "COUNTED", (("결정 대장", ledger, lambda: 224),))

    assert CHECKER.check_counts()
    CHECKER.fix_counts()
    assert CHECKER.check_counts() == []


def test_관문_표가_실물을_다_든다() -> None:
    """**§11의 「검사 체계」 표가 손으로 적힌 목록이라 넷이 빠져 있었다** (D-0350).

    CI 표가 `codeql`을 스무 판 넘게 빠뜨린 것과 같은 꼴이다.
    """
    assert cast_list(CHECKER.check_orphan_workflows()) == []


def test_그_표에만_겨눈다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**살아 있는 문서 전체로 보면 README의 도구표가 대신 만족시킨다** (D-0350).

    첫 판이 그랬고 **§11이 넷을 빠뜨린 채로 통과했다.** 표를 콕 집어야 한다.
    """
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")

    assert CHECKER.GATE_TABLE in master
    table = master.split(CHECKER.GATE_TABLE, 1)[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in cast_list(CHECKER.gate_tools()):
        assert f"tools/{name}.py" in table, name
    # README도 들지만 **그것으로는 통과시키지 않는다** — 표가 정본이다.
    assert "tools/check_args.py" in readme


def test_읽는_자리가_없는_축을_잡는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**카나리아다.** 아무 문서도 안 읽는 축을 심고 우는지 본다 (D-0350)."""
    import re

    axis = ("심은축", re.compile(r"아무데도없는말\s*(\d+)개"), lambda: 1)
    monkeypatch.setattr(CHECKER, "COUNTED", (axis,))

    problems = cast_list(CHECKER.check_counts())

    assert problems and "0곳" in problems[0]
