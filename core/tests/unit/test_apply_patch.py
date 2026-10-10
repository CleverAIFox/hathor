"""패치 고르기 (D-0249).

**이 스크립트에 시험이 없었다.** D-0199(CRLF) · D-0222(폴더 접힘) · D-0237(이름 바꾸기)
그리고 D-0249(남의 패치)까지 **넷 다 쓰다가 터졌다** — 파이프라인의 심장인데 검사가 없어서
매번 사람이 시험대였다. 여기가 그 자리를 막는다.

붙이는 것(`git apply`)은 git이 지므로 안 본다. **무엇을 고르는가**를 본다 —
`--which`는 고른 것만 찍고 끝내므로 작업 트리를 건드리지 않는다.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from hathor.shared.config.paths import repo_root

SCRIPT = repo_root() / "tools" / "apply_patch.sh"
OURS = "# hathor-commit: 기록: 무언가\n"
THEIRS = "# seshat-commit: 기록: 남의 것\n"
BODY = "diff --git a/docs/PLAN.md b/docs/PLAN.md\n"


def _which(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """`--which`로 부른다. **폴더만 보고 답하므로 저장소 상태와 무관하다.**"""
    env = dict(os.environ, HATHOR_PATCH_DIR=str(folder))
    return subprocess.run(
        ["bash", str(SCRIPT), "--which", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root(),
        timeout=60,
        check=False,
    )


def _patch(folder: Path, name: str, head: str, age: int) -> Path:
    """`age`초 전에 떨어진 패치. **고르기는 시각 순서를 보므로 못 박아 둔다.**"""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(head + BODY, encoding="utf-8")
    stamp = 1_700_000_000 - age
    os.utime(path, (stamp, stamp))
    return path


def test_남의_패치가_더_최신이어도_우리_것을_고른다(tmp_path: Path) -> None:
    """**실제로 물린 자리다.** 다운로드 폴더 하나를 여러 저장소가 나눠 쓴다."""
    _patch(tmp_path, "D0248.patch", OURS, age=600)
    _patch(tmp_path, "seshat-083.patch", THEIRS, age=10)

    done = _which(tmp_path)

    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip()).name == "D0248.patch"


def test_우리_것이_여럿이면_가장_최근을_고른다(tmp_path: Path) -> None:
    _patch(tmp_path, "D0240.patch", OURS, age=900)
    _patch(tmp_path, "D0248.patch", OURS, age=60)

    done = _which(tmp_path)

    assert Path(done.stdout.strip()).name == "D0248.patch"


def test_우리_것이_없으면_붙이려_들지_않는다(tmp_path: Path) -> None:
    """빈손보다 **남의 것을 붙이려 드는 것이 나쁘다** — 실패 메시지가 브랜치를 의심하게 한다."""
    _patch(tmp_path, "seshat-083.patch", THEIRS, age=10)

    done = _which(tmp_path)

    assert done.returncode != 0
    assert "hathor 패치가 없다" in done.stderr
    assert "seshat" not in done.stdout


def test_이름을_줘도_남의_것이면_막는다(tmp_path: Path) -> None:
    """`git apply`는 *"브랜치와 기준 커밋을 확인한다"*고 한다. **브랜치에는 문제가 없다.**"""
    _patch(tmp_path, "seshat-083.patch", THEIRS, age=10)

    done = _which(tmp_path, "seshat-083.patch")

    assert done.returncode != 0
    assert "다른 저장소의 패치다" in done.stderr
    assert "seshat-commit" in done.stderr, "어느 저장소인지 말해 준다"


def test_머리가_없는_패치는_막지_않는다(tmp_path: Path) -> None:
    """`git format-patch`로 만든 것에는 그 머리가 없다. **이름을 줬으면 사람 뜻이다.**"""
    _patch(tmp_path, "손으로.patch", "", age=10)

    done = _which(tmp_path, "손으로.patch")

    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip()).name == "손으로.patch"


def test_머리가_없는_패치를_저절로_고르지는_않는다(tmp_path: Path) -> None:
    """가르는 표식이 없으면 **우리 것인지 알 수 없다.** 이름을 주면 붙는다."""
    _patch(tmp_path, "손으로.patch", "", age=10)

    assert _which(tmp_path).returncode != 0


def test_고르기만_하고_트리는_건드리지_않는다(tmp_path: Path) -> None:
    """`--which`가 `git apply`까지 가면 이 시험이 저장소를 더럽힌다."""
    _patch(tmp_path, "D0248.patch", OURS, age=10)
    before = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root(),
        timeout=60,
        check=True,
    ).stdout

    _which(tmp_path)

    after = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root(),
        timeout=60,
        check=True,
    ).stdout
    assert before == after


def test_폴더가_없으면_그렇게_말한다(tmp_path: Path) -> None:
    done = _which(tmp_path / "없는곳")

    assert done.returncode != 0
    assert "패치 폴더가 없다" in done.stderr


# ------------------------------- 도구 체인을 바꾸면 번호를 단다 (D-0039 · D-0286)

GATE_START = 'TOOLCHAIN="$('
GATE_END = "\nfi\n"


def _gate() -> str:
    """스크립트에서 **그 관문의 실제 줄**을 떼어 온다.

    글자가 거기 있는지 보는 시험은 D-0283에서 이미 틀렸다 — 문구를 상수로 빼자 동작이
    그대로인데 빨개졌다. **떼어 와서 돌린다.**
    """
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index(GATE_START)
    return text[start : text.index(GATE_END, start) + len(GATE_END)]


def _judge(*declared: str) -> int:
    """선언 목록을 주고 관문을 돌린다. 0이면 통과, 1이면 막힘."""
    listed = "\n".join(declared)
    done = subprocess.run(
        ["bash", "-c", f'EXPECTED="{listed}"\nPATCH=x.patch\n{_gate()}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return done.returncode


def test_도구_체인만_바꾸면_막는다() -> None:
    """**D-0015가 MASTER.md를 남의 결정의 곁가지로 강등했고 아무도 못 찾았다** (D-0039).

    D-0039는 규칙을 적고 **세는 것을 안 만들었다** — 247판 동안. 실측으로 어긴 커밋이
    0건이라 못을 박는다 (D-0134).
    """
    assert _judge("Makefile", "core/hathor/x.py") == 1
    assert _judge(".github/workflows/ci.yml") == 1
    assert _judge(".githooks/pre-commit") == 1


def test_결정_기록을_같이_담으면_통과한다() -> None:
    """**바꾸지 말라는 것이 아니라 번호를 달라는 것이다.**"""
    assert _judge("Makefile", "docs/DECISIONS.md") == 0


def test_도구_체인이_아니면_묻지_않는다() -> None:
    assert _judge("core/hathor/x.py", "docs/PLAN.md") == 0


# ------------------------------------- 이 패치가 무엇 위에 서는가 (D-0287)

NEEDS_START = 'NEEDS="$('
NEEDS_END = "\nfi\n"


def _needs_gate() -> str:
    """스크립트에서 선행 검사의 **실제 줄**을 떼어 온다."""
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index(NEEDS_START)
    return text[start : text.index(NEEDS_END, start) + len(NEEDS_END)]


def _needs(declared: str, ledger: str, folder: Path) -> int:
    """선행 선언과 대장을 주고 관문을 돌린다. 0이면 통과, 1이면 막힘."""
    (folder / "docs").mkdir(parents=True, exist_ok=True)
    (folder / "docs" / "DECISIONS.md").write_text(ledger, encoding="utf-8")
    patch = folder / "x.patch"
    patch.write_text(declared, encoding="utf-8")
    done = subprocess.run(
        [
            "bash",
            "-c",
            f'die() {{ echo "$1" >&2; exit 1; }}\nPATCH="{patch}"\n{_needs_gate()}',
        ],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return done.returncode


def test_선행이_대장에_없으면_막는다(tmp_path: Path) -> None:
    """**D-0283이 이미 붙었는지 아무도 몰랐다** (D-0287).

    패치는 직전 판 위에서 뽑히는데 **그 사실이 패치 어디에도 없었다.** 그래서 이미
    푸시까지 끝난 패치를 또 붙이라는 지시가 나갔고, 사람은 자기가 뭘 지웠나 의심했다.
    """
    assert _needs("# hathor-needs: D-0283\n", "## D-0282. 제목\n", tmp_path) == 1


def test_선행이_있으면_통과한다(tmp_path: Path) -> None:
    assert _needs("# hathor-needs: D-0283\n", "## D-0283. 제목\n", tmp_path) == 0


def test_여럿을_선언하면_전부_본다(tmp_path: Path) -> None:
    ledger = "## D-0283. 하나\n\n## D-0284. 둘\n"
    assert _needs("# hathor-needs: D-0283 D-0284\n", ledger, tmp_path) == 0
    assert _needs("# hathor-needs: D-0283 D-0285\n", ledger, tmp_path) == 1


def test_선언이_없는_옛_패치는_막지_않는다(tmp_path: Path) -> None:
    """**옛 패치가 실재한다.** 표식이 없다고 막으면 되돌릴 수 없는 것이 생긴다."""
    assert _needs("# hathor-commit: 무언가\n", "## D-0001. 제목\n", tmp_path) == 0


# --------------------------------------------- 어느 판 위에 서는가 (D-0351)

BASE_START = 'BASE="$(grep'
BASE_END = "\nfi\n"


def _slice(start_at: str) -> str:
    """스크립트에서 한 관문의 **실제 줄**을 떼어 온다."""
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index(start_at)
    return text[start : text.index(BASE_END, start) + len(BASE_END)]


def _base_gate() -> str:
    """기준 머리를 **읽는 줄**과 **대조하는 블록**.

    둘 사이에 소급 바닥 블록이 끼어 있다 — 첫 판은 `\nfi\n`까지 통째로 떠서 **소급
    바닥의 `fi`에서 끊겼고**, 대조 블록이 한 줄도 안 들어와 시험이 거짓으로 통과했다.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    at = text.index(BASE_START)
    return text[at : text.index("\n", at) + 1] + _slice('if [[ -n "$BASE" ]]; then')


def _floor_gate() -> str:
    """D-0351 이후인데 기준 머리가 없는 패치를 막는 블록 (D-0352)."""
    text = SCRIPT.read_text(encoding="utf-8")
    at = text.index("BASE_FROM=")
    return text[at : text.index("\n", at) + 1] + _slice('if [[ -z "$BASE" && -n "$NEEDS" ]]; then')


def _floor(declared: str, folder: Path) -> subprocess.CompletedProcess[str]:
    """선행 선언만 주고 소급 바닥 블록을 돌린다."""
    patch = folder / "x.patch"
    patch.write_text(declared, encoding="utf-8")
    needs = ""
    for line in declared.splitlines():
        if line.startswith("# hathor-needs:"):
            needs = line.split(":", 1)[1].strip()
    return subprocess.run(
        [
            "bash",
            "-c",
            f'die() {{ echo "$1" >&2; exit 1; }}\nPATCH="{patch}"\n'
            f'NEEDS="{needs}"\nBASE=""\n{_floor_gate()}',
        ],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_소급_바닥_뒤인데_머리가_없으면_막는다(tmp_path: Path) -> None:
    """**머리 없는 것을 영원히 통과시키면 관문이 선택 사항이 된다** (D-0126 · D-0352)."""
    done = _floor("# hathor-needs: D-0351\n", tmp_path)

    assert done.returncode != 0
    assert "make patch" in done.stderr


def test_소급_바닥_앞은_안_막는다(tmp_path: Path) -> None:
    """**나간 350판에는 그 머리가 없다.** 막으면 되돌릴 수 없는 것이 생긴다."""
    assert _floor("# hathor-needs: D-0350\n", tmp_path).returncode == 0


def test_선행_선언이_없으면_안_막는다(tmp_path: Path) -> None:
    """선행조차 없는 옛 패치는 **번호를 모른다.** 모르면 막지 않는다 (GR-0.5)."""
    assert _floor("# hathor-commit: 무언가\n", tmp_path).returncode == 0


def test_여럿_중_가장_큰_번호를_본다(tmp_path: Path) -> None:
    assert _floor("# hathor-needs: D-0100 D-0351\n", tmp_path).returncode != 0


def _tiny_repo(folder: Path, content: str) -> str:
    """커밋 하나짜리 저장소를 만들고 **트리 해시**를 돌려준다."""
    folder.mkdir(parents=True, exist_ok=True)

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args, cwd=folder, capture_output=True, text=True, timeout=60, check=True
        )

    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "x@y")
    run("git", "config", "user.name", "x")
    (folder / "a.txt").write_text(content, encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "하나")
    return run("git", "rev-parse", "HEAD^{tree}").stdout.strip()


def _base(declared: str, folder: Path, body: str = "") -> subprocess.CompletedProcess[str]:
    """기준 선언을 주고 관문을 그 저장소에서 돌린다. `body`는 패치의 diff 본문."""
    patch = folder / "x.patch"
    patch.write_text(declared + body, encoding="utf-8")
    return subprocess.run(
        [
            "bash",
            "-c",
            f'die() {{ echo "$1" >&2; exit 1; }}\nPATCH="{patch}"\n{_base_gate()}',
        ],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_기준이_같으면_통과한다(tmp_path: Path) -> None:
    tree = _tiny_repo(tmp_path / "repo", "하나")

    assert _base(f"# hathor-base: {tree}\n", tmp_path / "repo").returncode == 0


def test_기준이_다르면_막고_둘_다_찍는다(tmp_path: Path) -> None:
    """**그날의 꼴이다** (D-0351).

    `D0349.patch`가 세 판 나갔고 사람은 첫째를 붙였다고 했는데 **둘째가 들어가 있었다.**
    셋 다 `# hathor-needs: D-0349`라 선행 검사는 전부 통과한다. 다음 패치가 안 붙자
    `git apply`는 *"브랜치와 기준 커밋을 확인한다"*고 했고 **어느 기준인지는 말하지
    않았다** — blob 해시를 손으로 좇아서야 알았다. 여기서는 **둘을 같이 찍는다.**
    """
    tree = _tiny_repo(tmp_path / "repo", "하나")
    other = _tiny_repo(tmp_path / "다른곳", "둘")
    assert tree != other

    # **패치가 `a.txt`를 건드리고, 그 `a.txt`가 다르다** (D-0376). 트리만 다르고
    # 패치가 건드리는 것은 다 맞는 경우는 이제 지나간다 — 아래 시험이 그것을 본다.
    done = _base(f"# hathor-base: {other}\n", tmp_path / "repo", _diff("a.txt", "0" * 7))

    assert done.returncode != 0
    assert "기준이 다르다" in done.stderr
    assert other in done.stderr, "이 패치가 서는 트리를 찍는다"
    assert tree in done.stderr, "네 트리도 찍는다 — 없으면 또 손으로 좇는다"
    assert "a.txt" in done.stderr, "**어느 경로가 어긋났는지** 찍는다 (D-0376)"


def test_트리_해시는_이력과_무관하다(tmp_path: Path) -> None:
    """**이것이 `# hathor-base:`가 서는 근거다.**

    D-0287은 *"해시가 아니다 — 미러와 실물 저장소는 이력이 달라 해시가 안 맞는다"*고
    적었다. **커밋 해시까지가 맞는 말이다.** 트리 해시는 파일 이름·모드·내용만으로
    정해져 이력이 안 들어간다 — 그래서 결정 번호처럼 어디서나 같고 번호보다 촘촘하다.
    주장이 아니라 **여기서 센다.**
    """
    first = _tiny_repo(tmp_path / "하나", "같은 내용")
    second = tmp_path / "둘"
    # 이력을 다르게 만든다 — 커밋 둘을 거쳐 같은 내용에 도달한다.
    second.mkdir(parents=True)

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args, cwd=second, capture_output=True, text=True, timeout=60, check=True
        )

    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "남@남")
    run("git", "config", "user.name", "남")
    (second / "a.txt").write_text("딴 것", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "딴 길")
    (second / "a.txt").write_text("같은 내용", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "도달")

    assert run("git", "rev-parse", "HEAD^{tree}").stdout.strip() == first
    assert run("git", "rev-parse", "HEAD").stdout.strip() != first


def test_기준이_없는_옛_패치는_막지_않는다(tmp_path: Path) -> None:
    """**이미 나간 패치 350판에는 그 머리가 없다.** 막으면 되돌릴 수 없는 것이 생긴다."""
    _tiny_repo(tmp_path / "repo", "하나")

    assert _base("# hathor-commit: 무언가\n", tmp_path / "repo").returncode == 0


# ------------------------------------------------- 훅이 막을 때 (D-0375)
#
# D-0374가 **빨간 관문을 들고 오는 패치**였다 — `[corpus]`의 수가 없는 자의 것이라
# `measured --check`이 운다. 그런데 **훅이 `make apply`의 커밋을 막는다.** 패치는
# 이미 붙었는데 화면에는 *«커밋을 중단한다»*만 뜨고, 빠져나갈 길은 안 적혔다.
#
# **훅은 옳다** — 트리가 진짜 나쁘다. 적어야 할 것은 *«그래서 뭘 하나»*다.


def test_훅이_막으면_빠져나갈_길을_적는다() -> None:
    """**막힌 사람에게 다음 한 줄이 보여야 한다** (D-0375 · D-0269)."""
    body = SCRIPT.read_text(encoding="utf-8")

    assert "if ! git commit" in body, "커밋 실패를 안 본다"
    assert "패치는 이미 붙어 있다" in body, "붙었는지 아닌지를 안 적는다"
    assert "git apply -R" in body, "되돌리는 법이 없다"


def test_훅이_막으면_0을_안_낸다() -> None:
    """**`&&`로 이어 붙인 명령이 멈춰야 한다** (D-0375).

    0을 내면 그 뒤의 `make check`·`make ship`이 **붙기만 하고 안 담긴 트리** 위에서
    돈다. 세어 보니 이 스크립트에는 붙인 채로 끝나는 길이 **넷**이고 넷 다 되돌리는
    법을 찍는다 — 수를 못으로 박지는 않는다. 새 길이 생기면 늘어도 맞다.
    """
    body = SCRIPT.read_text(encoding="utf-8")
    block = body[body.index("if ! git commit") : body.index('ok "커밋: ${MESSAGE}"')]

    assert "exit 1" in block, "훅이 막았는데 0을 낸다"
    assert "git apply -R" in block


# --------------------------------------------- 기준을 패치의 경로로 좁힌다 (D-0376)
#
# **트리 전체로 견주면 패치와 무관한 파일 하나가 전부를 막는다.** 실측: `make measure`가
# 그의 기기에서 `docs/proposal.docx`를 다시 냈다 — docx는 zip이라 같은 입력에서도 바이트가
# 다르다(graphviz 2.43.0 ↔ 14.1.2). 다음 패치는 그 파일을 **건드리지도 않았는데** 막혔다.
# D-0351의 뜻(어느 판 위에 서는가)은 그대로 두고 **범위만 좁힌다.**


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=folder, capture_output=True, text=True, timeout=60, check=True
    ).stdout


def _diff(path: str, old: str) -> str:
    """`index <옛>..<새>`를 가진 최소 diff. 관문은 **그 `<옛>`만** 본다."""
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index {old}..{'1' * 7} 100644\n"
        f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-옛\n+새\n"
    )


def _drifted(folder: Path) -> tuple[str, str]:
    """`a.txt`는 그대로 두고 `b.txt`만 바꾼 저장소. (a.txt의 blob, 지금 트리)를 낸다."""
    _tiny_repo(folder, "하나")
    (folder / "b.txt").write_text("무관", encoding="utf-8")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "둘")
    blob = _git(folder, "rev-parse", "HEAD:a.txt").strip()
    (folder / "b.txt").write_text("딴것", encoding="utf-8")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "셋")
    return blob, _git(folder, "rev-parse", "HEAD^{tree}").strip()


def test_패치_밖이_달라도_붙인다(tmp_path: Path) -> None:
    """**그날의 꼴이다** (D-0376). 기준 트리는 다르지만 `a.txt`는 그대로다.

    예전에는 여기서 막혔고, 막은 까닭은 **패치와 아무 상관 없는 `b.txt`**였다.
    """
    folder = tmp_path / "repo"
    blob, tree = _drifted(folder)
    other = _tiny_repo(tmp_path / "다른곳", "둘")
    assert tree != other

    done = _base(f"# hathor-base: {other}\n", folder, _diff("a.txt", blob[:7]))

    assert done.returncode == 0, done.stderr
    assert "패치 밖이다" in done.stderr, "**조용히 지나가지 않는다** — 적고 지나간다"


def test_패치_안이_다르면_좁혀도_막는다(tmp_path: Path) -> None:
    """**좁히는 것이 푸는 것은 아니다.** 진짜 «다른 판»은 그대로 막힌다."""
    folder = tmp_path / "repo"
    _, tree = _drifted(folder)
    other = _tiny_repo(tmp_path / "다른곳", "둘")
    assert tree != other

    done = _base(f"# hathor-base: {other}\n", folder, _diff("a.txt", "abc1234"))

    assert done.returncode != 0
    assert "a.txt — 기준 abc1234" in done.stderr, done.stderr


def test_새로_만드는_파일이_이미_있으면_막는다(tmp_path: Path) -> None:
    """**빈 blob은 「없어야 한다」는 뜻이다** (D-0376).

    `index 0000000..abc`는 새 파일이다. 그 자리에 이미 파일이 있으면 같은 번호의
    **다른 판**이 들어가 있는 것이고, `git apply`는 *"이미 있다"*만 말한다.
    """
    folder = tmp_path / "repo"
    _drifted(folder)
    other = _tiny_repo(tmp_path / "다른곳", "둘")

    done = _base(f"# hathor-base: {other}\n", folder, _diff("b.txt", "0" * 7))

    assert done.returncode != 0
    assert "네 트리에 이미 있다" in done.stderr, done.stderr


def test_좁힌_뒤에도_같은_트리는_아무_말을_안_한다(tmp_path: Path) -> None:
    """**거짓 경보를 안 만든다** (GR-0.8). 트리가 같으면 경로를 볼 일이 없다."""
    folder = tmp_path / "repo"
    tree = _tiny_repo(folder, "하나")

    done = _base(f"# hathor-base: {tree}\n", folder, _diff("a.txt", "0" * 7))

    assert done.returncode == 0
    assert done.stderr == "", done.stderr


# ------------------------------------------------- 붙인 뒤 할 일 (D-0377)
#
# **설명문에 적은 것은 관문이 아니다.** D-0376 패치가 docx를 안 담았고 「붙인 뒤
# `make proposal`」이 내 메시지에만 있었다. 그는 경로 없이 `git apply`를 쳤고(패치는 안
# 붙었다) 그다음 줄의 `make proposal`은 **옛 트리 위에서** 돌았다 — docx만 담긴 빈
# 커밋이 남았고 두 단계 뒤 `ship`에서야 막혔다. 그 사이의 `make check`은 **초록이었다.**


def _after_gate() -> str:
    """붙인 뒤 할 일 블록의 **실제 줄**."""
    return _slice('AFTER="$(grep -m1')


def _after(
    declared: str, folder: Path, fake_make: str = "exit 0"
) -> subprocess.CompletedProcess[str]:
    """머리를 주고 그 블록만 돌린다. `make`는 가짜로 세운다 — 진짜를 돌리면 분 단위다."""
    patch = folder / "x.patch"
    patch.write_text(declared, encoding="utf-8")
    bin_dir = folder / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "make").write_text(f'#!/usr/bin/env bash\necho "가짜 make $*"\n{fake_make}\n')
    (bin_dir / "make").chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    return subprocess.run(
        ["bash", "-c", f'die() {{ echo "$1" >&2; exit 1; }}\nPATCH="{patch}"\n{_after_gate()}'],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def test_머리가_없으면_아무것도_안_돈다(tmp_path: Path) -> None:
    """**거짓 경보를 안 만든다** (GR-0.8). 뒤처리가 없는 패치가 대부분이다."""
    done = _after("# hathor-commit: x\n", tmp_path)

    assert done.returncode == 0
    assert "가짜 make" not in done.stdout, done.stdout


def test_선언한_목표를_돌린다(tmp_path: Path) -> None:
    """**이것이 이 머리의 값이다.** 사람이 안 쳐도 돌아간다."""
    done = _after("# hathor-after: proposal\n", tmp_path)

    assert done.returncode == 0, done.stderr
    assert "가짜 make proposal" in done.stdout, done.stdout


def test_허용_목록_밖은_막는다(tmp_path: Path) -> None:
    """**패치 머리에서 임의 셸이 돌면 그것이 구멍이다** (D-0377)."""
    done = _after("# hathor-after: 아무거나\n", tmp_path)

    assert done.returncode != 0
    assert "허용 목록에 없다" in done.stderr, done.stderr
    assert "가짜 make" not in done.stdout, "막기 전에 돌렸다"


def test_뒤처리가_터지면_0을_안_낸다(tmp_path: Path) -> None:
    """**붙인 채로 끝나는 길이 하나 늘었다** (D-0375). 되돌리는 법을 찍는다."""
    done = _after("# hathor-after: proposal\n", tmp_path, fake_make="exit 3")

    assert done.returncode == 1
    assert "패치는 이미 붙어 있다" in done.stderr
    assert "git apply -R" in done.stderr


def test_허용_목록을_제_손으로_안_적는다() -> None:
    """**두 곳에 적으면 어긋난다** (D-0043). 셸이 `check_patch`에서 읽는다."""
    body = SCRIPT.read_text(encoding="utf-8")

    assert "check_patch.AFTER_ALLOWED" in body
    assert "proposal" not in body[body.index('AFTER="$(grep -m1') : body.index("NOCOMMIT")], (
        "목표 이름을 셸에 베꼈다"
    )


# ------------------------------------------------- 담은 것과 커밋 (D-0379)
#
# **비교를 넓히고 담기를 잊었다.** D-0377이 뒤처리 산출물을 `EXPECTED`에만 더하고
# `git add` 목록에는 안 넣었다. 그래서 `make apply`가 제출본을 다시 만들고도 **그것을
# 뺀 커밋**을 냈다 — 작업 트리는 맞고 커밋만 낡았다. 그 자리의 `make check`은 **작업
# 트리를 보므로 초록이었고**, 빨개진 것은 두 판 뒤 `HEAD`를 읽는 시험 둘이었다.


def test_한글_경로를_8진수로_안_읽는다() -> None:
    """**`core.quotepath`가 기본이면 `"\\353…"`가 나온다** (D-0379).

    그 글자는 선언의 어떤 줄과도 안 맞아 **영원히 «다른 작업이 섞였다»**가 된다.
    이 저장소에는 아직 한글 경로가 없어 **안 터졌을 뿐이다** — 유병률 0에 못을 박는다
    (D-0364와 같은 꼴).
    """
    body = SCRIPT.read_text(encoding="utf-8")

    for line in body.splitlines():
        if "git status --porcelain" in line and not line.lstrip().startswith("#"):
            assert "core.quotepath=false" in line, line


def test_담는_목록이_검증한_목록과_같다() -> None:
    """**둘이 갈리면 커밋이 트리보다 낡는다** (D-0379).

    대조는 `EXPECTED`로 하고 담기는 `declared_paths`로 하면, 그 차집합이 **조용히
    빠진다.** 차집합이 바로 뒤처리가 만든 산출물이었다.
    """
    body = SCRIPT.read_text(encoding="utf-8")
    staging = body[body.index('ACTUAL="$(git -c') : body.index("if ! git commit")]

    assert "printf '%s\\n' \"$EXPECTED\" | while" in staging, "담기가 `EXPECTED`를 안 쓴다"
    assert "declared_paths" not in staging, "담기와 대조가 다른 목록을 본다"


def _clean_gate() -> str:
    return _slice('LEFT="$(git -c')


def _clean(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f'die() {{ echo "$1" >&2; exit 1; }}\n{_clean_gate()}'],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_커밋_뒤_트리가_깨끗하면_지나간다(tmp_path: Path) -> None:
    """**거짓 경보를 안 만든다** (GR-0.8). 정상 적용은 아무 말이 없다."""
    folder = tmp_path / "repo"
    _tiny_repo(folder, "하나")

    done = _clean(folder)

    assert done.returncode == 0, done.stderr
    assert done.stderr == ""


def test_담기에서_빠진_것이_있으면_막는다(tmp_path: Path) -> None:
    """**이 못은 비교를 넓혀도 안 속는다** (D-0379).

    위 대조는 *«바뀐 것이 선언과 같은가»*만 본다 — **담겼는지는 안 본다.** 여기는
    결과만 본다: 담을 것을 다 담았으면 트리는 비어 있다.
    """
    folder = tmp_path / "repo"
    _tiny_repo(folder, "하나")
    (folder / "뒤처리가_만든것.bin").write_text("안 담겼다", encoding="utf-8")

    done = _clean(folder)

    assert done.returncode == 1
    assert "커밋이 네 트리보다 낡았다" in done.stderr, done.stderr
    assert "commit --amend" in done.stderr, "고치는 한 줄이 없다 (D-0269)"
    # **한글 경로가 8진수로 나오면 사람도 대조도 못 읽는다** (D-0379).
    assert "뒤처리가_만든것.bin" in done.stderr, "무엇이 빠졌는지 안 찍는다"
