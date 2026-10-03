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


def _base(declared: str, folder: Path) -> subprocess.CompletedProcess[str]:
    """기준 선언을 주고 관문을 그 저장소에서 돌린다."""
    patch = folder / "x.patch"
    patch.write_text(declared, encoding="utf-8")
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

    done = _base(f"# hathor-base: {other}\n", tmp_path / "repo")

    assert done.returncode != 0
    assert "기준이 다르다" in done.stderr
    assert other in done.stderr, "이 패치가 서는 트리를 찍는다"
    assert tree in done.stderr, "네 트리도 찍는다 — 없으면 또 손으로 좇는다"


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
