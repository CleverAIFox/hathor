"""인자 대조 검사의 단위 검사 (D-0350).

**첫 판이 자기를 만든 결함을 못 잡았다.** 정규식이 `--no-print-directory`의 `no`를 타깃으로
집고 `tidy`를 지나쳤다 — 그래서 여기 **그날의 줄을 그대로 심는다.**
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_args")

THAT_DAY = """\
hygiene:
\t@$(MAKE) --no-print-directory doctor
\t@$(MAKE) --no-print-directory tidy $(if $(YES),YES=1,) $(if $(FIX),FIX=1,)

tidy:
\tpython3 tools/tidy.py $(if $(YES),--yes,)
"""
"""**그날의 Makefile 그대로다.** `FIX=1`이 `tidy`로 넘어가는데 `tidy`가 안 쓴다."""


# ------------------------------------------------------------------ 넘기는 변수


def test_받는_쪽이_안_쓰는_변수를_잡는다() -> None:
    """**사용자가 `make tidy YES=1 FIX=1`을 쳤고 아무 일도 안 났다** (D-0350).

    D-0064가 *"인자가 조용히 무시된다"*를 닫았고 D-0069가 네 시간 뒤 같은 부류를 또
    잡았다. **이번이 세 번째다.**
    """
    problems = cast("list[str]", CHECKER.check_passthrough(THAT_DAY))

    assert problems, "`FIX=1`이 사라지는데 안 운다"
    assert "FIX" in problems[0] and "tidy" in problems[0]


def test_받는_쪽이_쓰면_통과한다() -> None:
    """`YES`는 `tidy`가 쓴다 — **그것까지 잡으면 오탐이다** (GR-0.8)."""
    problems = cast("list[str]", CHECKER.check_passthrough(THAT_DAY))

    assert not any("YES" in one for one in problems)


def test_타깃을_토큰으로_집는다() -> None:
    """**`--no-print-directory`의 `no`를 타깃으로 집으면 안 된다** (D-0350).

    첫 판이 그랬고 **`tidy`를 지나쳐 이 결함을 못 잡았다.** 아는 타깃 이름과 맞는
    토큰만 쓴다.
    """
    made = cast("dict[str, list[str]]", CHECKER.recipes(THAT_DAY))

    assert set(made) == {"hygiene", "tidy"}
    assert "no" not in made


def test_모르는_타깃으로_넘기면_안_본다() -> None:
    """바깥 `make`를 부르는 자리까지 잡으면 오탐이다."""
    text = "x:\n\t@$(MAKE) -C other thing FIX=1\n"

    assert cast("list[str]", CHECKER.check_passthrough(text)) == []


# ------------------------------------------------------------------ 플래그


def test_안_받는_플래그를_잡는다() -> None:
    text = "x:\n\tpython3 tools/tidy.py --없는플래그 --fix\n"
    problems = cast("list[str]", CHECKER.check_flags(text, "시험"))

    assert any("--fix" in one for one in problems)


def test_받는_플래그는_통과한다() -> None:
    text = "x:\n\tpython3 tools/tidy.py --yes\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험")) == []


def test_줄을_넘지_않는다() -> None:
    r"""**첫 판이 `\s+`로 꼬리를 받아 다음 줄의 플래그까지 끌어왔다** (D-0350).

    `gh_ops.py`에 `--ratchet`을 준다고 **네 건을 거짓으로 냈다** — 그것이 GR-0.8이다.
    """
    text = "x:\n\tpython3 tools/tidy.py --yes\n\tpython3 tools/deadcheck.py --ratchet\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험")) == []


def test_없는_도구를_부르면_잡는다() -> None:
    text = "x:\n\tpython3 tools/no_such_tool.py --check\n"

    assert cast("list[str]", CHECKER.check_flags(text, "시험"))


# ------------------------------------------------------------------ 화면 안내


def test_문서_문자열은_안_본다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**설명과 출력은 다르다.**

    첫 판이 문서 문자열까지 훑어 **이 도구가 사고를 설명하는 문장**에 제 검사가 걸렸다.
    """
    planted = tmp_path / "tools" / "심은것.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        '"""`make tidy FIX=1`을 설명하는 문서 문자열이다."""\nX = "찍는 말"\n',
        encoding="utf-8",
    )
    found = cast("list[tuple[int, str]]", CHECKER.printed_strings(planted))

    assert [text for _, text in found] == ["찍는 말"]


def test_붙어_있지_않은_변수도_잡는다() -> None:
    """**그날의 문장이 그랬다** — *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*.

    `FIX=1`이 `make tidy`에서 **떨어져 있었고** 사용자는 둘을 같이 쳤다. 첫 판은
    붙어 있는 것만 봐서 못 잡았다. **읽는 대로 잡는다.**
    """
    import re

    advice = re.compile(r"make ([a-z][a-z0-9-]*)(.*)")
    target, tail = advice.findall("치우려면 `make tidy YES=1` · 바이트코드는 `FIX=1`")[0]

    assert target == "tidy"
    assert set(re.findall(r"([A-Z_]+)=1", tail)) == {"YES", "FIX"}


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다() -> None:
    assert cast("list[str]", CHECKER.check()) == []


def test_그물이_비지_않았다() -> None:
    """**호출을 0개 읽으면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    calls = cast("list[tuple[str, str]]", CHECKER.CALL.findall(make))

    assert len(calls) >= 30, len(calls)
    assert len({tool for tool, _ in calls}) >= 20


def test_tidy가_이제_FIX를_쓴다() -> None:
    """**화면을 말에 맞추는 것이 아니라 도구를 말에 맞췄다** (D-0350)."""
    made = cast("dict[str, list[str]]", CHECKER.recipes((ROOT / "Makefile").read_text("utf-8")))

    assert "$(FIX)" in "\n".join(made["tidy"])


# ------------------------------------- 셸 · 워크플로 · 쓰임새 주석 (D-0352)


def test_바깥_파일을_실제로_읽는다() -> None:
    """**첫 판은 `Makefile`과 훅만 봤다** — 셸·워크플로는 영원히 안 보는 자리였다.

    그물이 비면 「전부 맞다」가 거짓으로 참이 된다 (D-0230). 그래서 바닥이 넷이다.
    """
    found = cast("list[tuple[str, str]]", CHECKER.sources())
    names = [name for name, _ in found]

    assert len(found) >= CHECKER.FLOOR["바깥 파일"], names
    assert any("make_patch.sh" in one for one in names)
    assert any("ci.yml" in one for one in names)
    # **셸은 전부 본문이 있다.** 워크플로는 `run:`이 하나도 없을 수 있고(`codeql.yml`이
    # 그렇다 — 전부 `uses:`다) 그때 빈 것이 **맞다.** 그래도 **적어도 하나는** 내용이
    # 있어야 한다 — 전부 비면 추출기가 망가진 것이다 (D-0230 · GR-0.5).
    shell = [text for name, text in found if not name.endswith("(run:)")]
    flows = [text for name, text in found if name.endswith("(run:)")]
    assert all(shell) and len(shell) >= 5
    assert sum(1 for text in flows if text) >= 4, "워크플로에서 run:을 거의 못 읽었다"


def test_워크플로_꼴의_호출을_읽는다() -> None:
    """**`CALL`은 한 건도 못 읽고 있었다.** 워크플로는 `uv run python ../tools/X.py`다."""
    text = "        run: cd core && uv run python ../tools/gpu_smoke.py --check\n"
    got = cast("list[tuple[str, str]]", CHECKER.ANY_CALL.findall(text))

    assert got and got[0][0] == "tools/gpu_smoke.py"


def test_명령_치환을_넘지_않는다() -> None:
    r"""**실물에서 거짓 경보를 냈다** (GR-0.8).

        gh release create … --title "$(… release_notes.py --title)" --notes-file notes.md

    꼬리가 `)`를 넘어 `--notes-file`을 그 도구의 인자로 읽었다. 그것은 `gh`의 인자다.
    """
    text = 'x --title "$(python3 tools/release_notes.py --title)" --notes-file notes.md'
    flags = cast("list[tuple[str, str]]", CHECKER.ANY_CALL.findall(text))

    assert flags
    assert "--notes-file" not in flags[0][1]


def test_명령_자리의_make만_센다() -> None:
    """**실측으로 먼저 틀렸다** (D-0352).

    `apt-get install -y --no-install-recommends make ffmpeg graphviz`에서 `make ffmpeg`를
    집어 「없는 타깃」이라고 울었다. `ffmpeg`는 apt 꾸러미다 — `make`가 인자인 자리다.
    **`--no-print-directory`의 `no`를 집은 것과 같은 결함이다** (D-0350).
    """
    apt = "sudo apt-get install -y --no-install-recommends make ffmpeg graphviz\n"
    real = "cd core && make check\nmake sync\n"

    assert cast("list[tuple[str, str]]", CHECKER.MAKE_CALL.findall(apt)) == []
    assert {t for t, _ in cast("list[tuple[str, str]]", CHECKER.MAKE_CALL.findall(real))} == {
        "check",
        "sync",
    }


def test_없는_타깃을_부르면_잡는다() -> None:
    made = cast("dict[str, list[str]]", CHECKER.recipes("check:\n\techo\n"))
    problems = cast("list[str]", CHECKER.check_make_calls("make nosuch\n", "시험", made))

    assert problems and "그 타깃이 없다" in problems[0]


def test_쓰임새_주석이_없는_타깃을_가리키면_잡는다() -> None:
    """**사람이 그대로 치는 줄이다.** 타깃 이름을 바꾸면 스크립트 제 설명이 거짓이 된다."""
    made = cast("dict[str, list[str]]", CHECKER.recipes("patch:\n\techo\n"))

    assert cast("list[str]", CHECKER.check_usage("#   make patch REV=x\n", "시험", made)) == []
    problems = cast("list[str]", CHECKER.check_usage("#   make oldname\n", "시험", made))
    assert problems and "쓰임새 주석" in problems[0]


def test_run_블록만_읽는다() -> None:
    """**`with:`·`env:`까지 훑으면 설정 문자열을 명령으로 읽는다.**"""
    yaml = (
        "jobs:\n  a:\n    steps:\n      - uses: x\n        with:\n"
        "          args: make 없는것\n      - run: make check\n"
    )
    got = cast("str", CHECKER.run_blocks(yaml))

    assert "make check" in got
    assert "nosuch" not in got


def test_속성_문서_문자열은_출력이_아니다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**첫 판은 블록의 첫 줄만 문서로 봤다** (D-0352).

    그래서 `X = re.compile(...)` 아래 붙는 **속성 문서 문자열**을 출력으로 읽고, 이 도구가
    apt 줄을 설명하는 문장에 제 검사가 걸렸다. 찍는 문자열은 늘 인자이거나 대입된 값이다.
    """
    planted = tmp_path / "심은것.py"
    planted.write_text(
        'X = 1\n"""설명이다 — `make nosuch`을 든다."""\nY = "찍는 말"\n', encoding="utf-8"
    )
    found = cast("list[tuple[int, str]]", CHECKER.printed_strings(planted))

    assert [text for _, text in found] == ["찍는 말"]


def test_쓰임새_검사가_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**부품을 재고 배선을 안 쟀다** (D-0352).

    심은 결함으로 재니 `check()`에서 `check_usage` 한 줄을 지워도 아무 시험이 안 울었다 —
    시험이 그 함수를 **직접** 부르고 있었기 때문이다. 여기는 `check()`를 거쳐서 본다.
    """
    monkeypatch.setattr(CHECKER, "check_usage", lambda *_: ["심은 것"])

    assert "심은 것" in cast("list[str]", CHECKER.check())


def test_셸_워크플로_검사가_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "check_any_calls", lambda *_: ["심은 것"])
    monkeypatch.setattr(CHECKER, "check_make_calls", lambda *_: ["심은 둘"])
    problems = cast("list[str]", CHECKER.check())

    assert "심은 것" in problems and "심은 둘" in problems


# ------------------------------- 워크플로가 맞는 디렉터리에서 부르나 (D-0356)


def test_그날의_단계를_잡는다() -> None:
    """**CI가 빨개져서 알았다** (D-0356).

    `ci.yml`은 `defaults: working-directory: core`를 두고 관문 단계마다
    `working-directory: .`를 **다시 적는다.** 스물셋이 그렇게 적혀 있었고 **내가 더한
    하나만 빠뜨렸다** — CI는 *"No such file or directory"* 한 줄을 냈다.
    `actionlint`도 `test_ci_parity`도 이 자리를 안 본다.
    """
    that_day = (
        "defaults:\n  run:\n    working-directory: core\n\njobs:\n  x:\n    steps:\n"
        "      - name: Gates under load\n"
        "        run: python3 tools/check_under_load.py --check\n"
    )
    problems = cast("list[str]", CHECKER.check_workdir(that_day, "시험"))

    assert problems and "그 자리에 그 파일이 없다" in problems[0]


def test_선언하면_통과한다() -> None:
    fixed = (
        "defaults:\n  run:\n    working-directory: core\n\njobs:\n  x:\n    steps:\n"
        "      - name: Gates under load\n        working-directory: .\n"
        "        run: python3 tools/check_under_load.py --check\n"
    )

    assert cast("list[str]", CHECKER.check_workdir(fixed, "시험")) == []


def test_core에서는_상대경로가_맞다() -> None:
    """`core`에서 돌면 `../tools/X.py`다 — **거꾸로도 잡는다.**"""
    right = (
        "jobs:\n  x:\n    steps:\n      - name: smoke\n        working-directory: core\n"
        "        run: uv run python ../tools/gpu_smoke.py\n"
    )
    wrong = right.replace("../tools/", "tools/")

    assert cast("list[str]", CHECKER.check_workdir(right, "시험")) == []
    assert cast("list[str]", CHECKER.check_workdir(wrong, "시험"))


def test_뿌리에서_상대경로를_쓰면_잡는다() -> None:
    text = (
        "jobs:\n  x:\n    steps:\n      - name: x\n        working-directory: .\n"
        "        run: python3 ../tools/check_sight.py --check\n"
    )

    assert cast("list[str]", CHECKER.check_workdir(text, "시험"))


def test_저장소_워크플로가_전부_맞다() -> None:
    """**스물셋이 맞게 적혀 있었다.** 그 수가 줄면 여기가 빨개진다."""
    assert cast("list[str]", CHECKER.check_workflow_dirs()) == []


def test_디렉터리_검사가_배선돼_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**부품은 재고 배선은 안 쟀다** (D-0352 · D-0353 · D-0356)."""
    monkeypatch.setattr(CHECKER, "check_workflow_dirs", lambda: ["심은 것"])

    assert "심은 것" in cast("list[str]", CHECKER.check())


def test_묶음이_필요한_도구는_uv_run으로_적는다() -> None:
    """**사용자가 그 줄을 그대로 쳤고 터졌다** (D-0367).

    `probe_id3.py`의 독스트링이 `python3 tools/probe_id3.py --emit`이라 적고 있었고
    `mutagen`은 프로젝트 묶음에 있다 — 그의 터미널에서 `ModuleNotFoundError`가 났다.
    작성자는 제 컨테이너에서 `uv run`으로 돌려 보고 **그 차이를 안 적었다.**

    `check_usage`는 쓰임새의 `make` 타깃이 실재하는지만 봤다 — *«그 인터프리터가
    임포트를 할 수 있는지»*는 아무도 안 봤다.
    """
    assert CHECKER.check_venv_usage() == []


def test_늦게_들여오는_것은_안_센다() -> None:
    """**`--dry-run`은 맨 `python3`로 정말 돈다** — 그것을 세면 거짓 경보다 (GR-0.8)."""
    local = frozenset({"측정"})
    import ast as _ast

    late = _ast.parse("def go():\n    import mlflow\n    return mlflow\n")
    top = _ast.parse("import mlflow\n")

    assert CHECKER.top_level_third_party(late, local) == set()
    assert CHECKER.top_level_third_party(top, local) == {"mlflow"}


def test_표준_라이브러리를_바깥_묶음으로_안_센다() -> None:
    """**`sys`가 들고 있다** — 손으로 적으면 파이썬 판마다 어긋난다."""
    import ast as _ast

    tree = _ast.parse("import tomllib\nimport argparse\nfrom pathlib import Path\n")

    assert CHECKER.top_level_third_party(tree, frozenset()) == set()
    assert "tomllib" in CHECKER.STDLIB


def test_환경변수를_제_손으로_읽는_자리가_선언과_같다() -> None:
    """**정본 해결기를 건너뛰면 `.env`가 안 읽힌다** (D-0367 · D-0066).

    `probe_id3`가 세 번째였고 `.env`를 **아예 안 읽었다** — 그가 `.env`에 경로를
    적어도 아무 일도 안 일어났을 것이다. `paths.py`가 적어 둔 네 아픔 중 셋째가
    그대로 재발했다.
    """
    assert CHECKER.check_own_env() == []
    assert set(CHECKER.OWN_ENV_ALLOWED) == {"sync_artifacts", "tidy"}


def test_상수를_거쳐_읽는_것도_센다() -> None:
    """**첫 자가 둘을 못 봤다.** `os.environ.get(STORE_ENV)`는 글자가 아니다.

    허락 목록에 둘을 넣어 둔 채 자가 둘을 못 보면 **「좋아졌으니 허락을 빼라」가
    거짓으로 뜬다** — 실제로 그렇게 떴다.
    """
    assert CHECKER.ENV_LITERAL.search('os.environ.get("HATHOR_LIBRARY_ROOT")')
    assert not CHECKER.ENV_LITERAL.search("os.environ.get(STORE_ENV)")
    assert CHECKER.ENV_NAME.search('STORE_ENV = "HATHOR_ARTIFACT_STORE"')


def test_허락이_비어_가는_것도_잡는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**양방향이다** (D-0363). 안 읽게 됐으면 허락을 빼야 한다."""
    monkeypatch.setattr(CHECKER, "OWN_ENV_ALLOWED", ("tidy",))
    said = CHECKER.check_own_env()
    assert len(said) == 1 and "sync_artifacts" in said[0]

    monkeypatch.setattr(CHECKER, "OWN_ENV_ALLOWED", ("sync_artifacts", "tidy", "없는도구"))
    said = CHECKER.check_own_env()
    assert len(said) == 1 and "없는도구" in said[0]


def test_라이브러리_경로가_없으면_막는다() -> None:
    """`probe_id3`가 **기본값을 안 든다** (D-0367).

    예전엔 `/mnt/d/노래/노래`를 박아 두고 조용히 그것을 봤다. 드라이브 글자가 D에서
    F로 바뀌자 *«경로 없음»*만 찍혔고 **어디를 봐야 하는지는 안 적혔다.**
    """
    import ast as _ast

    probe = (ROOT / "tools" / "probe_id3.py").read_text(encoding="utf-8")
    tree = _ast.parse(probe)
    # **산문과 코드를 가른다.** 이 도구의 독스트링이 옛 경로를 인용하고, 그것을
    # 「박혔다」로 세면 거짓 경보다 (GR-0.8 · D-0361의 `doc_fsck: ok`와 같은 자리).
    planted = [
        node.value
        for node in _ast.walk(tree)
        if isinstance(node, _ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("/mnt/")
    ]

    assert planted == [], f"기기 경로가 코드에 박혔다: {planted}"
    assert "load_dotenv()" in probe and "library_root()" in probe
    assert "`make setup`" in probe, "어디에 적는지를 화면에 안 적는다"


@pytest.mark.parametrize("part", ["check_venv_usage", "check_own_env"])
def test_새_검사_둘이_check에_배선돼_있다(part: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """**부품은 재고 배선은 안 쟀다** (D-0359). 위의 시험들은 그 함수를 직접 부른다.

    D-0365가 같은 자리를 겪었다 — 새 함수를 입구에 걸 때 그것을 기억하는 것이 사람
    몫이고, **나는 두 판 연속 잊었다.**
    """
    monkeypatch.setattr(CHECKER, part, lambda: ["심은 문제"])

    assert "심은 문제" in CHECKER.check()
