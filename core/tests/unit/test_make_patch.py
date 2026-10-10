"""패치를 뽑는 쪽의 단위 검사 (D-0351).

**패치를 뽑는 도구가 없었다.** 350판을 손으로 뽑았고, 머리 셋도 손으로 적었다 —
그래서 D-0350이 **틀린 부모 위에서 뽑혀 나갔고 아무것도 그것을 보지 않았다.**
받는 쪽은 *"브랜치와 기준 커밋을 확인한다"*는 한 줄을 받았다.

여기는 **뽑는 쪽**을 본다. 받는 쪽은 `test_apply_patch.py`다.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from hathor.shared.config.paths import repo_root

ROOT = repo_root()
SCRIPT = ROOT / "tools" / "make_patch.sh"


def _git(folder: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(
        ("git", *args),
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=120,
        check=check,
        env=dict(
            os.environ,
            GIT_AUTHOR_NAME="x",
            GIT_AUTHOR_EMAIL="x@y",
            GIT_COMMITTER_NAME="x",
            GIT_COMMITTER_EMAIL="x@y",
        ),
    )
    return done.stdout.strip()


def _repo(folder: Path, *, second: str = "## D-0352. 둘째 기록\n") -> Path:
    """결정 기록 둘짜리 저장소. **대장이 있어야 선행 번호를 읽는다.**"""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "docs").mkdir()
    _git(folder, "init", "-q", ".")
    (folder / "docs" / "DECISIONS.md").write_text("## D-0351. 첫 기록\n", encoding="utf-8")
    (folder / "a.txt").write_text("처음\n", encoding="utf-8")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "D-0351. 첫 기록")

    past = folder / "docs" / "DECISIONS.md"
    past.write_text(past.read_text(encoding="utf-8") + "\n" + second, encoding="utf-8")
    (folder / "a.txt").write_text("둘째\n", encoding="utf-8")
    (folder / "새것.bin").write_bytes(bytes(range(256)))
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "D-0352. 둘째 기록")
    return folder


def _make(folder: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=dict(os.environ, **env),
    )


def _headers(patch: Path) -> dict[str, str]:
    found = {}
    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("# hathor-"):
            break
        key, _, value = line[2:].partition(": ")
        found[key] = value
    return found


# ------------------------------------------------------------------ 머리 셋


def test_머리_셋을_커밋에서_뽑는다(tmp_path: Path) -> None:
    """**손으로 적지 않는다** (GR-0.7). 적으면 틀리고, 틀린 것을 아무도 안 본다."""
    where = _repo(tmp_path / "r")

    done = _make(where)

    assert done.returncode == 0, done.stderr
    got = _headers(where / "D0352.patch")
    assert got["hathor-commit"] == "D-0352. 둘째 기록"
    assert got["hathor-needs"] == "D-0351", "선행은 **부모의** 마지막 번호다"
    assert got["hathor-base"] == _git(where, "rev-parse", "HEAD^^{tree}")


def test_선행에_제_번호를_적지_않는다(tmp_path: Path) -> None:
    """제 번호를 적으면 **받는 쪽이 제 자신을 기다린다** — 영원히 안 붙는다."""
    where = _repo(tmp_path / "r")

    _make(where)

    assert _headers(where / "D0352.patch")["hathor-needs"] != "D-0352"


def test_이름을_번호에서_만든다(tmp_path: Path) -> None:
    where = _repo(tmp_path / "r")

    _make(where)

    assert (where / "D0352.patch").exists()


def test_OUT을_주면_거기에_쓴다(tmp_path: Path) -> None:
    where = _repo(tmp_path / "r")
    target = tmp_path / "밖" / "이름.patch"

    done = _make(where, OUT=str(target))

    assert done.returncode == 0, done.stderr
    assert target.exists(), "없는 폴더도 만든다"


# ------------------------------------------------------------------ 뽑은 것을 붙여 본다


def test_부모_위에서_붙여_보고_트리까지_맞춘다(tmp_path: Path) -> None:
    """**이것이 D-0350에서 빠진 단계다.**

    손으로 할 때는 지금 트리에서 역검사만 했고, 그러면 *"이미 붙어 있다"*가 통과로
    보여 **틀린 부모를 못 잡는다.** 부모를 꺼내 거기서 돌린다.
    """
    where = _repo(tmp_path / "r")

    done = _make(where)

    assert done.returncode == 0, done.stderr
    assert "정방향" in done.stdout and "트리 일치" in done.stdout


def test_이진_파일이_붙는다(tmp_path: Path) -> None:
    """**`--binary`가 없으면 docx가 *"binary files differ"* 한 줄로 나간다.**

    실물 패치마다 `docs/proposal.docx` 3.2MB가 들어 있다 — 이 자리가 비면 매 판이
    받는 쪽에서 터진다.
    """
    where = _repo(tmp_path / "r")

    _make(where)

    text = (where / "D0352.patch").read_text(encoding="utf-8", errors="replace")
    assert "GIT binary patch" in text
    assert "Binary files" not in text, "요약 한 줄로 나갔다 — 못 붙는다"


def test_검증이_실제로_도는지_본다(tmp_path: Path) -> None:
    """**검증이 조용히 건너뛰면 그것이 빈 그물이다** (D-0230).

    이 저장소를 쓰는 방식으로는 **검증이 터지는 꼴을 만들 수 없었다** — `format-patch`로
    뽑은 것은 늘 제 부모에 붙는다. 그래서 `exit 11`을 지워도 어떤 시험도 안 울었다.
    그 자리를 `VERIFY=`로 열었다 — **패치를 받아서** 검증하므로 망가진 것을 줄 수 있다.
    """
    where = _repo(tmp_path / "r")
    assert _make(where).returncode == 0
    good = (where / "D0352.patch").read_bytes()

    # 문맥 한 줄을 바꾼다. `git apply`는 문맥으로 자리를 찾으므로 거부해야 한다.
    head = good.index(b"\n--- a/")
    hunk = good.index(b"\n@@", head)
    line = good.index(b"\n ", hunk + 3)
    poisoned = where / "망가진.patch"
    poisoned.write_bytes(good[: line + 2] + b"xyzzy" + good[line + 2 :])

    done = _make(where, VERIFY=str(poisoned))

    assert done.returncode != 0, "망가진 패치를 통과시켰다 — 검증이 빈 그물이다"
    assert "안 붙는다" in done.stderr


def test_받은_패치가_어느_판_위에_서는지_말한다(tmp_path: Path) -> None:
    """**이것이 그날 네 시간을 먹은 질문이다** (D-0351).

    `git apply`는 *"브랜치와 기준 커밋을 확인한다"*고만 했다. 기준 트리로 이력을 훑으면
    **어느 커밋인지 바로 나온다.**
    """
    where = _repo(tmp_path / "r")
    assert _make(where).returncode == 0

    done = _make(where, VERIFY=str(where / "D0352.patch"))

    assert done.returncode == 0, done.stderr
    assert "D-0351. 첫 기록" in done.stdout, "그 기준이 무슨 판인지 이름을 댄다"


def test_변경을_덜_담은_패치를_잡는다(tmp_path: Path) -> None:
    """**붙기는 하는데 커밋과 다른 곳에 도착하는 패치가 있다** (D-0351).

    후상(`+` 줄)을 바꾸면 정방향은 통과한다 — 바꾼 그대로 써지고, 역검사도 통과한다.
    **트리를 대조해야만 보인다.** 심은 결함으로 재니 이 자리가 비어 있었다.
    """
    where = _repo(tmp_path / "r")
    assert _make(where).returncode == 0
    good = (where / "D0352.patch").read_bytes()

    head = good.index(b"\n--- a/")
    plus = good.index(b"\n+", good.index(b"\n@@", head) + 3)
    poisoned = where / "덜담은.patch"
    poisoned.write_bytes(good[: plus + 2] + b"zzz" + good[plus + 2 :])

    done = _make(where, VERIFY=str(poisoned), AGAINST="HEAD")

    assert done.returncode != 0, "다른 트리에 도착하는 패치를 통과시켰다"
    assert "트리와 다르다" in done.stderr


def test_기준이_이_저장소에_없으면_그렇게_말한다(tmp_path: Path) -> None:
    """**없는 것을 아무 커밋이라고 말하지 않는다** (GR-0.5)."""
    where = _repo(tmp_path / "r")
    assert _make(where).returncode == 0
    patch = where / "D0352.patch"
    text = patch.read_text(encoding="utf-8", errors="surrogateescape")
    patch.write_text(
        text.replace(_headers(patch)["hathor-base"], "0" * 40),
        encoding="utf-8",
        errors="surrogateescape",
    )

    done = _make(where, VERIFY=str(patch))

    assert done.returncode != 0
    assert "못 찾았다" in done.stderr


def test_기준_머리가_없는_패치는_검증할_수_없다고_말한다(tmp_path: Path) -> None:
    """**옛 패치 350판에는 그 머리가 없다.** 붙는다고 말하는 것이 거짓이다."""
    where = _repo(tmp_path / "r")
    old = where / "옛것.patch"
    old.write_text("# hathor-commit: 무언가\ndiff --git a/a b/a\n", encoding="utf-8")

    done = _make(where, VERIFY=str(old))

    assert done.returncode != 0
    assert "hathor-base" in done.stderr


# ------------------------------------------------------------------ 막는 자리


def test_제목에_번호가_없으면_안_뽑는다(tmp_path: Path) -> None:
    """패치 이름이 번호이고 **받는 쪽의 선행 검사도 번호로 돈다** (D-0287)."""
    where = _repo(tmp_path / "r")
    _git(where, "commit", "-q", "--amend", "-m", "그냥 고침")

    done = _make(where)

    assert done.returncode != 0
    assert "D-XXXX" in done.stderr


def test_번호를_적었다고만_하면_안_뽑는다(tmp_path: Path) -> None:
    """**제목에 번호를 달고 기록을 안 담을 수 있다** (D-0039). 대장에 표제가 있어야 한다."""
    where = _repo(tmp_path / "r", second="## D-0352. 둘째 기록\n")
    _git(where, "commit", "-q", "--amend", "-m", "D-0999. 없는 번호")

    done = _make(where)

    assert done.returncode != 0
    assert "대장에 없다" in done.stderr


def test_첫_커밋은_안_뽑는다(tmp_path: Path) -> None:
    """부모가 없으면 기준이 없다. **없는 것을 0이라고 적지 않는다** (GR-0.5)."""
    where = _repo(tmp_path / "r")
    first = _git(where, "rev-list", "--max-parents=0", "HEAD")

    done = _make(where, REV=first)

    assert done.returncode != 0
    assert "부모가 없다" in done.stderr


def test_없는_커밋을_주면_그렇게_말한다(tmp_path: Path) -> None:
    done = _make(_repo(tmp_path / "r"), REV="없는것")

    assert done.returncode != 0
    assert "그런 커밋이 없다" in done.stderr


def test_더러운_트리를_알려준다(tmp_path: Path) -> None:
    """**패치에 안 담긴 변경이 손에 남아 있으면 다음 판이 그 위에서 뽑힌다.**"""
    where = _repo(tmp_path / "r")
    (where / "a.txt").write_text("안 담긴 것\n", encoding="utf-8")

    done = _make(where)

    assert done.returncode == 0, done.stderr
    assert "커밋 안 된 변경" in done.stdout


def test_검증용_작업_트리를_남기지_않는다(tmp_path: Path) -> None:
    """**임시 작업 트리가 남으면 다음 `git status`가 더러워진다.**"""
    where = _repo(tmp_path / "r")

    _make(where)

    assert _git(where, "worktree", "list").count("\n") == 0, "검증용 트리가 남았다"


# ------------------------------------------------------------------ 저장소


@pytest.mark.parametrize("head", ["hathor-commit", "hathor-needs", "hathor-base"])
def test_받는_쪽이_같은_머리를_읽는다(head: str) -> None:
    """**두 곳에 적으면 어긋난다** (D-0043). 뽑는 쪽이 쓰는 머리를 받는 쪽이 읽어야 한다."""
    taker = (repo_root() / "tools" / "apply_patch.sh").read_text(encoding="utf-8")

    assert f"# {head}:" in SCRIPT.read_text(encoding="utf-8"), "뽑는 쪽이 안 쓴다"
    assert f"'^# {head}:'" in taker or f"'{head}:'" in taker, "받는 쪽이 안 읽는다"


@pytest.mark.parametrize("head", ["hathor-commit", "hathor-needs", "hathor-base"])
def test_기획서_그림이_머리_셋을_든다(head: str) -> None:
    """**실물 → 문서로 거꾸로 본다** (`fire-lane`의 `readmecheck`).

    그 그림은 D-0287의 선행 관문이 생긴 뒤로도 **안 따라왔다** — 한 판 놓치면 다음 판도
    놓친다. 머리가 늘면 여기가 빨개진다.
    """
    figures = (repo_root() / "tools" / "render_figures.py").read_text(encoding="utf-8")
    pipe = figures[figures.index("def patch_pipe") :]
    pipe = pipe[: pipe.index('return render(out, "patch_pipe"')]

    assert f"# {head}:" in pipe, f"파이프 그림이 `# {head}:`를 안 든다"


@pytest.mark.parametrize("target", ["apply", "patch"])
def test_Makefile이_두_쪽을_다_건다(target: str) -> None:
    """**뽑는 쪽만 있고 거는 자리가 없으면 아무도 안 쓴다** (D-0126)."""
    made = (repo_root() / "Makefile").read_text(encoding="utf-8")

    assert f"\n{target}:" in made


# ------------------------------------------------------------------ 소급 (D-0352)


def _old_patch(where: Path, folder: Path, *, subject: str, needs: str = "D-0351") -> Path:
    """**머리가 없는 옛 패치.** 350판이 이 꼴이다."""
    assert _make(where).returncode == 0
    body = (where / "D0352.patch").read_bytes()
    body = body[body.index(b"diff --git") :]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "옛것.patch"
    path.write_bytes(f"# hathor-commit: {subject}\n# hathor-needs: {needs}\n".encode() + body)
    return path


def test_나간_패치에_기준을_박는다(tmp_path: Path) -> None:
    """**D-0351은 *"소급해 넣지 않는다"*고 적었다.** 그러면 머리 없는 것을 영원히
    통과시켜야 하고, 선택 사항인 관문은 관문이 아니다 (D-0126)."""
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-0352. 둘째 기록")

    done = _make(where, STAMP=str(box), YES="1")

    assert done.returncode == 0, done.stderr
    assert _headers(old)["hathor-base"] == _git(where, "rev-parse", "HEAD^^{tree}")


def test_번호로도_찾는다(tmp_path: Path) -> None:
    """**제목이 한 글자라도 다르면 정확 일치가 안 된다.** 커밋 제목은 번호를 반드시 품는다.

    실측: 내 미러에서 제목 일치만 쓰면 11건, **번호 대체 조회로 32건**이 됐다.
    """
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-0352. 제목이 **달라졌다**")

    assert _make(where, STAMP=str(box), YES="1").returncode == 0
    assert "hathor-base" in _headers(old)


def test_본문을_한_바이트도_안_건드린다(tmp_path: Path) -> None:
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-0352. 둘째 기록")
    before = old.read_bytes()
    before = before[before.index(b"diff --git") :]

    _make(where, STAMP=str(box), YES="1")

    after = old.read_bytes()
    assert after[after.index(b"diff --git") :] == before


def test_두_번_박아도_같다(tmp_path: Path) -> None:
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-0352. 둘째 기록")

    _make(where, STAMP=str(box), YES="1")
    once = old.read_bytes()
    done = _make(where, STAMP=str(box), YES="1")

    assert old.read_bytes() == once
    assert "이미 있다 1" in done.stdout


def test_YES가_없으면_찍기만_한다(tmp_path: Path) -> None:
    """`tidy`와 같은 규약이다 (D-0225). **고치는 것은 따로 말한다.**"""
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-0352. 둘째 기록")

    done = _make(where, STAMP=str(box))

    assert "hathor-base" not in _headers(old)
    assert "박을 것 1" in done.stdout


def test_남의_패치는_안_건드린다(tmp_path: Path) -> None:
    """패치 폴더를 여러 저장소가 나눠 쓴다 (D-0249)."""
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    box.mkdir()
    theirs = box / "seshat-083.patch"
    theirs.write_text("# seshat-commit: 남의 것\ndiff --git a/x b/x\n", encoding="utf-8")

    done = _make(where, STAMP=str(box), YES="1")

    assert "hathor-base" not in theirs.read_text(encoding="utf-8")
    assert "남의 것 1" in done.stdout


def test_못_찾으면_모른다고_적는다(tmp_path: Path) -> None:
    """**없는 것을 아무 커밋이라고 말하지 않는다** (GR-0.5)."""
    where = _repo(tmp_path / "r")
    box = tmp_path / "patches"
    old = _old_patch(where, box, subject="D-9999. 이 저장소에 없는 판")

    done = _make(where, STAMP=str(box), YES="1")

    assert "hathor-base" not in _headers(old)
    assert "못 찾았다" in done.stdout and "못 찾음 1" in done.stdout


def test_폴더를_모르면_그렇게_말한다(tmp_path: Path) -> None:
    done = _make(_repo(tmp_path / "r"), STAMP="1", HATHOR_PATCH_DIR="")

    assert done.returncode != 0
    assert "패치 폴더를 모른다" in done.stderr


# ------------------------------------------- 파이프가 거짓 실패를 낸다 (D-0354)


def test_큰_대장에서도_뽑힌다(tmp_path: Path) -> None:
    """**`git show … | grep -q`는 부하가 걸리면 거짓으로 실패한다** (D-0354).

    `grep -q`가 일치하자마자 끝내고, `git show`가 아직 쓰고 있으면 `SIGPIPE`로 죽는다.
    `set -o pipefail`이 그것을 파이프라인의 실패로 읽어 **대장에 번호가 멀쩡히 있는데
    「없다」고 막았다.** 사용자 기기에서 `make check`이 터졌고, 시험을 네 갈래로 돌리자
    **3/3 재현**됐다 — 한 갈래로는 안 보인다.

    여기서는 **일치를 맨 앞에 두고 뒤에 큰 덩어리를 붙여** 경주를 없앤다. 파이프로
    되돌리면 이 시험은 반드시 빨개진다.
    """
    where = tmp_path / "r"
    where.mkdir(parents=True)
    (where / "docs").mkdir()

    def run(*args: str) -> None:
        subprocess.run(
            args,
            cwd=where,
            capture_output=True,
            text=True,
            timeout=300,
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
    past = where / "docs" / "DECISIONS.md"
    past.write_text("## D-0001. 첫 기록\n", encoding="utf-8")
    (where / "a.txt").write_text("처음\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "D-0001. 첫 기록")

    # **표제가 맨 앞, 그 뒤로 8MB.** `grep -q`는 첫 줄에서 끝나고 `git show`는 계속 쓴다.
    filler = "### 채움 — 파이프가 막히도록 길게 쓴다.\n" * 200_000
    past.write_text(f"## D-0001. 첫 기록\n## D-0002. 둘째\n{filler}", encoding="utf-8")
    (where / "a.txt").write_text("둘째\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "D-0002. 둘째")
    assert past.stat().st_size > 4_000_000, past.stat().st_size

    done = _make(where)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert "hathor-base" in _headers(where / "D0002.patch")


def test_일찍_끝내는_소비자에_파이프를_안_물린다() -> None:
    r"""**거꾸로도 본다** (D-0354).

    `set -o pipefail`이 켜진 셸에서 `… | grep -q` · `… | head`는 **언제든 거짓 실패를
    낸다.** 앞쪽이 큰 것을 쓰는 순간 터지고, 그때는 부하가 걸린 날이다. 새로 들어오면
    여기가 빨개진다.
    """
    guilty = []
    for path in sorted((ROOT / "tools").glob("*.sh")):
        text = path.read_text(encoding="utf-8")
        if "pipefail" not in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            # **주석은 안 센다.** 첫 판이 이 결함을 설명하는 제 주석에 걸렸다 — `check_args`의
            # 속성 문서 문자열과 같은 자리다 (D-0352).
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\|\s*(grep\s+-[a-zA-Z]*q|head\b|grep\s+-m\s?[0-9])", line):
                guilty.append(f"{path.name}:{number}  {line.strip()}")

    assert guilty == [], "파이프를 `<<<`나 변수로 바꾼다 (D-0354)"


def test_도구를_임포트하는_셸은_바이트코드를_안_남긴다() -> None:
    """**`.pyc`를 남기면 다음 시험이 거짓말한다** (D-0252 · D-0377).

    D-0377이 `check_patch.AFTER_RULES`를 셸에서 읽게 만들며 `tools/__pycache__`를
    남겼고, `test_도구_바이트코드를_안_남긴다`가 **증상**으로 잡았다 — 그 시험은 캐시가
    그 순간 있어야 운다. 여기는 **원인**을 본다: 임포트하는 호출은 `-B`를 쓴다.
    """
    guilty = []
    for path in sorted((ROOT / "tools").glob("*.sh")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"python3 (?!-B)\S*\s*-c\b", line):
                guilty.append(f"{path.name}:{number}  {line.strip()}")

    assert guilty == [], "`python3 -B -c`로 바꾼다 (D-0252)"


def test_뽑은_패치가_저장소에_안_담긴다() -> None:
    """**`make patch`는 뿌리에 떨군다** (D-0377). `git add -A`가 집어 가면 커밋에 딸린다.

    실측으로 한 번 들어갔다 — `D0376.patch` 52KB가 D-0377 커밋에 딸려 갔고 `--amend`로
    뺐다. 사람이 매번 기억하는 대신 `.gitignore`가 든다.
    """
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "*.patch" in [line.strip() for line in ignored]
