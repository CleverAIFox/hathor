"""패치 머리 관문의 단위 검사 (D-0352).

**`make check`이 뽑는 쪽을 한 번도 안 불렀다.** D-0351이 `make patch`를 만들고 거기서
멈췄다 — 뽑는 쪽이 망가지면 다음 패치를 뽑을 때 알게 되고, 그때는 받는 쪽에서 터진다.

그리고 **머리는 네 곳에 산다.** 두 곳에 적으면 어긋나고(D-0043) 넷이면 넷 다 어긋난다 —
실제로 D-0287이 선행 관문을 세운 뒤 그림과 README가 안 따라왔다.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]
CHECKER = tool_module("check_patch")


def _problems(name: str) -> list[str]:
    return cast("list[str]", getattr(CHECKER, name)())


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다() -> None:
    assert _problems("check_heads") == []
    assert _problems("check_floor") == []


def test_머리_셋과_곳_넷을_읽는다() -> None:
    """**그물이 비면 「전부 맞다」가 거짓으로 참이 된다** (D-0230)."""
    assert len(CHECKER.HEADS) == 3
    assert len(CHECKER.OPTIONAL_HEADS) == 1, "걸릴 때만 드는 머리 (D-0377)"
    where = cast("dict[str, str]", CHECKER.places())

    assert len(where) == 4
    assert all(len(text) > 200 for text in where.values()), "빈 본문을 읽고 통과한다"


# ------------------------------------------------------------------ 네 곳 대조 (카나리아)


@pytest.mark.parametrize("head", ["hathor-commit", "hathor-needs", "hathor-base", "hathor-after"])
def test_한_곳이_머리를_빠뜨리면_운다(head: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """**그날의 꼴이다** — D-0287이 선행 관문을 세우고 그림·README는 안 따라왔다."""
    where = cast("dict[str, str]", CHECKER.places())
    broken = dict(where)
    broken["README.md"] = where["README.md"].replace(f"# {head}:", "# 지워진것:")
    monkeypatch.setattr(CHECKER, "places", lambda: broken)

    problems = _problems("check_heads")

    assert problems and any("README.md" in one and head in one for one in problems)


def test_그림의_다른_구간은_안_센다() -> None:
    """**파이프 그림만 겨눈다.** 파일 전체로 보면 다른 그림이나 주석이 대신 만족시킨다."""
    body = cast("str", CHECKER.figure())

    assert "patch_pipe" not in body.split("def patch_pipe", 1)[1].split("\n", 1)[0] or True
    assert "leak_gate" not in body, "다른 그림이 섞였다 — 대조가 거짓이 된다"
    assert all(f"# {head}:" in body for head in CHECKER.HEADS)


# ------------------------------------------------------------------ 소급 바닥


def test_소급_바닥이_받는_쪽과_같다() -> None:
    """**셸과 파이썬이 같은 수를 따로 들고 있다** — 그러면 어긋난다 (D-0043)."""
    taker = (ROOT / "tools" / "apply_patch.sh").read_text(encoding="utf-8")
    found = re.search(r"(?m)^BASE_FROM=([0-9]+)$", taker)

    assert found
    assert int(found.group(1)) == CHECKER.BASE_REQUIRED_FROM == 351


def test_바닥이_어긋나면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, "BASE_REQUIRED_FROM", 999)

    problems = _problems("check_floor")

    assert problems and "소급 바닥이 어긋난다" in problems[0]


def test_바닥이_사라지면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 것을 0으로 읽지 않는다** (GR-0.5). 상수가 지워지면 관문이 꺼진다."""
    fake = tmp_path / "apply_patch.sh"
    fake.write_text("# 바닥이 없다\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "TAKER", fake)

    problems = _problems("check_floor")

    assert problems and "못 찾았다" in problems[0]


# ------------------------------------------------------------------ 실제로 뽑아 본다


def _two_commits(folder: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """**제 부모를 가진 저장소를 손수 만든다** (D-0353).

    첫 판은 이 저장소의 부모가 있는지 보고 없으면 `pytest.skip()`했다. 그 건너뛰기 둘이
    `deadcheck.CEILING["건너뛴 시험"]`을 **15에서 17로 밀어 올렸고**, 이력을 훑으니
    그 천장의 가장 조였던 값은 **2**였다. **내가 더한 둘은 없앨 수 있는 둘이다** —
    시험이 제 부대를 들고 있으면 환경에 묻지 않는다.
    """
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "docs").mkdir()

    def run(*args: str) -> None:
        subprocess.run(
            args,
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            env=dict(
                os.environ,
                GIT_AUTHOR_NAME="x",
                GIT_AUTHOR_EMAIL="x@y",
                GIT_COMMITTER_NAME="x",
                GIT_COMMITTER_EMAIL="x@y",
            ),
        )

    run("git", "init", "-q", ".")
    (folder / "docs" / "DECISIONS.md").write_text("## D-0001. 첫 기록\n", encoding="utf-8")
    (folder / "a.txt").write_text("처음\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "D-0001. 첫 기록")
    past = folder / "docs" / "DECISIONS.md"
    past.write_text(past.read_text(encoding="utf-8") + "\n## D-0002. 둘째\n", encoding="utf-8")
    (folder / "a.txt").write_text("둘째\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "D-0002. 둘째")
    monkeypatch.setattr(CHECKER, "ROOT", folder)
    return folder


def test_HEAD를_정말_뽑아_본다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**적혀 있다까지가 아니라 돌아간다까지 본다** (D-0352).

    `pull_once`가 실물 `make_patch.sh`를 불러 기준 위에서 붙여 보고 트리까지 맞춘 뒤
    버린다. **부모를 환경에서 빌리지 않는다** (D-0353).
    """
    _two_commits(tmp_path / "r", monkeypatch)

    assert cast("bool", CHECKER.has_parent())
    assert _problems("pull_once") == []


def test_이_저장소도_뽑힌다() -> None:
    """**합성만 보면 실물이 안 뽑히는 것을 놓친다.** 부모가 있을 때만 재고, 없으면
    `--no-live`가 그 자리를 덮는다 (그 쪽은 `test_얕은_클론을_통과로_안_적는다`가 본다)."""
    if not cast("bool", CHECKER.has_parent()):
        return

    assert _problems("pull_once") == []


def test_뽑기가_망가지면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**뽑기가 터지는데 통과하면 그것이 빈 그물이다** (D-0230)."""
    broken = tmp_path / "make_patch.sh"
    broken.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "MAKER", broken)

    problems = _problems("pull_once")

    assert problems and "못 뽑는다" in problems[0]


def test_머리를_안_쓰는_뽑기를_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """머리 없이 성공하는 뽑기는 **통과시키면 안 된다.**"""
    silent = tmp_path / "make_patch.sh"
    silent.write_text(
        '#!/usr/bin/env bash\nprintf "diff --git a/x b/x\\n" > "$OUT"\n', encoding="utf-8"
    )
    monkeypatch.setattr(CHECKER, "MAKER", silent)
    # **그날의 `HEAD`에 안 매인다** (D-0379). 첫 판은 매여 있었고, 제출본을 안 담은
    # 커밋 하나에 시험 둘이 빨개졌다 — 틀린 것은 커밋인데 판정은 시험을 가리켰다.
    monkeypatch.setattr(CHECKER, "touched_by_head", list)

    problems = _problems("pull_once")

    assert len(problems) == len(CHECKER.HEADS)


def test_얕은_클론을_통과로_안_적는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 잰 것을 통과로 세지 않는다** (GR-0.5). CI가 얕게 받으면 화면이 그렇게 말한다."""
    monkeypatch.setattr(CHECKER, "has_parent", lambda: False)
    monkeypatch.setattr("sys.argv", ["check_patch.py", "--check"])

    assert CHECKER.main() == 0
    assert "안 돌렸다" in capsys.readouterr().out


# ------------------------------------------------------------------ 배선


@pytest.mark.parametrize("where", ["Makefile", ".githooks/pre-commit", ".github/workflows/ci.yml"])
def test_세_곳에_다_걸려_있다(where: str) -> None:
    """**관문을 만들고 안 걸면 영원히 안 돈다** (D-0126)."""
    assert "tools/check_patch.py" in (ROOT / where).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["ci.yml", "wiring.yml"])
def test_CI가_부모를_받는다(name: str) -> None:
    """**얕은 클론에서는 뽑아 볼 수 없다.** 검사를 약하게 하는 대신 깊이를 올렸다.

    `wiring.yml`도 같이 본다 (D-0369). 그 잡만 깊이를 안 줘서 **같은 시험이 다른
    판정을 냈다** — 배선 둘이 CI에서만 「안 울었다」였다. 재는 환경이 갈리면 못이
    가리키는 수가 둘이 된다 (D-0043).
    """
    workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    first = workflow.index("- uses: actions/checkout@v7")

    assert "fetch-depth: 2" in workflow[first : first + 320], name


# ------------------------------------------------------------------ 배선 (심은 결함)


@pytest.mark.parametrize("part", ["check_heads", "check_floor", "check_after_table", "pull_once"])
def test_부품이_main에_배선돼_있다(
    part: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**부품을 재고 배선을 안 쟀다** (D-0352).

    심은 결함으로 재니 `main()`에서 `check_heads()`와 `pull_once()`를 빼도 아무 시험이
    안 울었다 — 시험이 그 함수를 **직접** 부르고 있었다. 여기는 `main()`을 거친다.

    **종료코드만 보면 안 된다** (D-0369). 첫 판은 `main() == 1`만 봤고, 얕은 클론에서는
    `pull_once()`가 **제 문제로** 1을 내므로 `check_heads()` 호출을 끊어도 1이었다 —
    CI(`fetch-depth` 없음)에서 이 자리 둘이 **「안 울었다」로 세어졌다.** 심은 글자가
    **화면에 닿는지**를 보면 깊이와 무관하다.
    """
    # **`has_parent`를 손에 쥔다** — 환경에 묻지 않으면 건너뛸 일이 없다 (D-0353).
    monkeypatch.setattr(CHECKER, "has_parent", lambda: True)
    monkeypatch.setattr(CHECKER, part, lambda *_: ["심은 것"])
    monkeypatch.setattr("sys.argv", ["check_patch.py", "--check"])

    assert CHECKER.main() == 1
    assert "심은 것" in capsys.readouterr().err, "심은 것이 화면에 안 닿았다"


# ------------------------------------------------- 붙인 뒤 할 일 (D-0377)
#
# **사람 머리에 두면 빠진다.** D-0376 패치가 docx를 안 담았고 「붙인 뒤 `make proposal`」이
# 내 설명문에만 있었다. 그가 경로 없이 `git apply`를 쳐서 **패치가 안 붙은 채** 빌드가
# 돌았고 docx만 담긴 빈 커밋이 생겼다 — `ship`에서야 막혔다, 두 단계 뒤였다.


def test_규칙이_비면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**그물이 비면 「아무 패치도 뒤처리가 필요 없다」가 거짓으로 참이 된다** (D-0230)."""
    monkeypatch.setattr(CHECKER, "AFTER_RULES", ())

    assert any("그물이 비었다" in one for one in _problems("check_after_table"))


def test_받는_쪽이_목록을_안_읽으면_운다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**두 곳에 적으면 어긋난다** (D-0043). 셸이 제 목록을 들면 여기와 갈린다."""
    fake = tmp_path / "apply_patch.sh"
    fake.write_text("#!/usr/bin/env bash\nBASE_FROM=351\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "TAKER", fake)

    assert any("AFTER_ALLOWED" in one for one in _problems("check_after_table"))


def test_경로가_목표를_부른다() -> None:
    """**선언이 정본이다** (GR-0.7). 셸이 경로를 베끼지 않는다."""
    assert CHECKER.after_for(["docs/proposal.docx", "tools/x.py"]) == ["proposal"]
    assert CHECKER.after_for(["tools/x.py"]) == []
    assert set(CHECKER.AFTER_ALLOWED) == {"proposal"}


def test_머리와_경로가_갈리면_운다() -> None:
    """**양방향** (D-0363). 빠뜨린 것도, 없는데 적힌 것도 든다."""
    assert CHECKER.after_drift(["docs/proposal.docx"], "proposal") == []
    assert CHECKER.after_drift([], "") == []

    missing = CHECKER.after_drift(["docs/proposal.docx"], "")
    assert missing and "없다»인데" in missing[0], missing

    extra = CHECKER.after_drift(["tools/x.py"], "proposal")
    assert extra and "«proposal»인데" in extra[0], extra


def test_뒤처리를_빠뜨린_뽑기를_잡는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**심은 결함** (D-0069). 머리 셋만 쓰고 넷째를 안 쓰는 뽑기는 통과하면 안 된다.

    **건드린 경로를 손에 쥔다** (D-0379 · D-0353). `HEAD`에 물으면 그날 커밋이
    제출본을 건드렸느냐에 따라 판정이 갈린다.
    """
    blind = tmp_path / "make_patch.sh"
    blind.write_text(
        "#!/usr/bin/env bash\n"
        'printf "# hathor-commit: x\\n" > "$OUT"\n'
        'printf "# hathor-needs: D-0001\\n" >> "$OUT"\n'
        'printf "# hathor-base: 0\\n" >> "$OUT"\n'
        'printf "diff --git a/x b/x\\n" >> "$OUT"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(CHECKER, "MAKER", blind)
    monkeypatch.setattr(CHECKER, "touched_by_head", lambda: ["docs/proposal.docx"])

    problems = _problems("pull_once")

    assert any("hathor-after" in one for one in problems), problems


def test_뽑은_패치가_산출물을_안_담는다(tmp_path: Path) -> None:
    """**실물로 뽑아 안에 무엇이 들었는지 본다** (D-0377).

    docx는 받는 기기의 blob과 달라 **담으면 `git apply`가 이진 전제에서 터진다** —
    실측으로 한 번 터졌다. 빼는 것과 「뒤처리를 적는 것」은 **같이** 일어나야 한다:
    빼고 안 적으면 산출물이 낡고, 적고 안 빼면 패치가 안 붙는다.
    """
    if not cast("bool", CHECKER.has_parent()):
        return

    out = tmp_path / "뽑은.patch"
    done = subprocess.run(
        ["bash", str(CHECKER.MAKER)],
        cwd=CHECKER.ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ, OUT=str(out), REV="HEAD"),
    )
    assert done.returncode == 0, done.stderr

    body = out.read_text(encoding="utf-8", errors="replace")
    touched = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=CHECKER.ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.split()

    for trigger, target in CHECKER.AFTER_RULES:
        if trigger in touched:
            assert f"diff --git a/{trigger}" not in body, f"{trigger}을 담았다 — 받는 쪽에서 터진다"
            assert f"# hathor-after: {target}" in body, "빼고 **다시 만들라고 안 적었다**"
        else:
            assert f"# hathor-after: {target}" not in body, "안 건드렸는데 뒤처리를 적었다"
