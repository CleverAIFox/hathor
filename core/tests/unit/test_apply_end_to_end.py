"""`apply_patch.sh`를 **끝까지** 돌린다 (D-0390).

### 네 판이 그의 터미널에서 터졌다

D-0376 · D-0377 · D-0379 · D-0387. **넷 다 내 `make check`은 초록이었다** — 이 스크립트는
받는 쪽에서만 끝까지 돌고, 시험은 `_slice()`로 **조각만** 돌렸기 때문이다. 네 판 동안
*«받는 쪽 경로를 내가 못 돌린다»*라고 적었는데 **못 돌리는 게 아니라 안 지은 것**이었다.

### 어떻게

`apply_patch.sh`의 첫 줄이 `cd "$(git rev-parse --show-toplevel)"`다. **임시 저장소 안에서
부르면 거기가 뿌리가 된다** — 실물 저장소는 한 바이트도 안 건드린다 (D-0386).

`tools/check_patch.py`는 **실물을 복사한다.** 가짜를 쓰면 그 가짜와 실물이 갈리고
(D-0043), 이 시험이 지키려는 것이 바로 *«두 벌이 어긋난다»*이다. `make`와
`check_decisions.py`만 세운다 — 전자는 분 단위고 후자는 이 저장소의 대장을 본다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from hathor.shared.config.paths import repo_root

ROOT = repo_root()
SCRIPT = ROOT / "tools" / "apply_patch.sh"

COMMIT = "D-0002. 둘째 기록"
BODY = (
    "diff --git a/docs/DECISIONS.md b/docs/DECISIONS.md\n"
    "--- a/docs/DECISIONS.md\n"
    "+++ b/docs/DECISIONS.md\n"
    "@@ -1,1 +1,3 @@\n"
    " ## D-0001. 첫 기록\n"
    "+\n"
    "+## D-0002. 둘째 기록\n"
)


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=folder, capture_output=True, text=True, timeout=60, check=True
    ).stdout.strip()


def _fixture(folder: Path) -> None:
    """실제 스크립트가 끝까지 도는 **가장 작은 저장소**."""
    (folder / "tools").mkdir(parents=True)
    (folder / "docs").mkdir()
    (folder / "site").mkdir()
    shutil.copy(SCRIPT.parent / "check_patch.py", folder / "tools" / "check_patch.py")
    (folder / "tools" / "check_decisions.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (folder / "docs" / "DECISIONS.md").write_text("## D-0001. 첫 기록\n", encoding="utf-8")
    (folder / "site" / "proposal.docx").write_text("옛 제출본\n", encoding="utf-8")
    (folder / "site" / "proposal.lock.json").write_text("{}\n", encoding="utf-8")
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "config", "user.email", "t@example.invalid")
    _git(folder, "config", "user.name", "시험")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "D-0001. 첫 기록")


def _patch(folder: Path, after: str = "", base: str | None = None) -> Path:
    """실제 꼴의 패치. `base`를 안 주면 **부모의 트리**를 넣는다."""
    head = [
        f"# hathor-commit: {COMMIT}",
        "# hathor-needs: D-0001",
        f"# hathor-base: {base if base is not None else _git(folder, 'rev-parse', 'HEAD^{tree}')}",
    ]
    if after:
        head.append(f"# hathor-after: {after}")
    path = folder.parent / "D0002.patch"
    path.write_text("\n".join(head) + "\n" + BODY, encoding="utf-8")
    return path


def _make(folder: Path, script: str) -> Path:
    """가짜 `make`. 진짜를 부르면 분 단위이고 이 저장소에는 `Makefile`도 없다."""
    where = folder.parent / "bin"
    where.mkdir(exist_ok=True)
    (where / "make").write_text(f"#!/usr/bin/env bash\n{script}\n", encoding="utf-8")
    (where / "make").chmod(0o755)
    return where


def _run(
    folder: Path, patch: Path, bin_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HATHOR_PATCH_DIR", None)
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{os.environ['PATH']}"
    # **패치는 첫 인자다** — `Makefile`이 `bash tools/apply_patch.sh $(PATCH)`로 부른다.
    return subprocess.run(
        ["bash", str(SCRIPT), str(patch)],
        cwd=folder,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
        check=False,
    )


# ------------------------------------------------------------------ 끝까지


def test_붙이고_커밋하고_트리가_깨끗하다(tmp_path: Path) -> None:
    """**조각이 아니라 전부다.** 네 판이 터진 자리가 여기 한 번에 들어온다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    done = _run(folder, _patch(folder))

    assert done.returncode == 0, done.stderr
    assert _git(folder, "log", "-1", "--format=%s") == COMMIT
    assert _git(folder, "status", "--porcelain") == "", "커밋 뒤 트리가 더럽다 (D-0379)"
    assert "## D-0002." in (folder / "docs" / "DECISIONS.md").read_text(encoding="utf-8")


def test_뒤처리가_낸_것이_커밋에_담긴다(tmp_path: Path) -> None:
    """**D-0379가 샌 자리다.** `EXPECTED`에 더하고 담지 않으면 커밋이 낡는다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    bin_dir = _make(folder, 'echo "새 제출본" > site/proposal.docx')

    done = _run(folder, _patch(folder, after="proposal"), bin_dir)

    assert done.returncode == 0, done.stderr
    assert _git(folder, "status", "--porcelain") == "", done.stdout
    carried = _git(folder, "show", "--name-only", "--format=", "HEAD").split()
    assert "site/proposal.docx" in carried, f"뒤처리 산출물이 커밋에 없다: {carried}"


def test_뒤처리가_아무것도_안_바꿔도_간다(tmp_path: Path) -> None:
    """**D-0387이 막힌 자리다.** 생성기를 안 건드리면 자물쇠는 한 바이트도 안 바뀐다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    bin_dir = _make(folder, 'echo "가짜 make $*"')

    done = _run(folder, _patch(folder, after="proposal"), bin_dir)

    assert done.returncode == 0, done.stderr + done.stdout
    assert _git(folder, "log", "-1", "--format=%s") == COMMIT


def test_뒤처리가_터지면_커밋을_안_한다(tmp_path: Path) -> None:
    """**붙기만 하고 안 담긴 트리 위에서 다음 명령이 돌면 안 된다** (D-0375)."""
    folder = tmp_path / "repo"
    _fixture(folder)
    bin_dir = _make(folder, "exit 3")

    done = _run(folder, _patch(folder, after="proposal"), bin_dir)

    assert done.returncode != 0
    assert _git(folder, "log", "-1", "--format=%s") == "D-0001. 첫 기록", "터졌는데 커밋했다"


def test_섞인_작업이_있으면_붙이기_전에_막는다(tmp_path: Path) -> None:
    """**심은 결함** (D-0069). 더러운 트리 위에 붙이면 무엇이 패치인지 안 갈린다.

    선언 ↔ 실제 대조(D-0376)보다 **앞에서** 막는다 — 거기까지 가면 이미 붙어 있다.
    """
    folder = tmp_path / "repo"
    _fixture(folder)
    (folder / "남의작업.py").write_text("x = 1\n", encoding="utf-8")

    done = _run(folder, _patch(folder))

    assert done.returncode != 0
    assert "커밋되지 않은 변경" in done.stderr, done.stderr
    assert _git(folder, "log", "-1", "--format=%s") == "D-0001. 첫 기록"
    assert "## D-0002." not in (folder / "docs" / "DECISIONS.md").read_text(encoding="utf-8")


def test_선행이_대장에_없으면_안_붙인다(tmp_path: Path) -> None:
    """**D-0287.** 순서를 건너뛰면 뒤의 패치가 조용히 어긋난다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    patch = _patch(folder)
    patch.write_text(
        patch.read_text(encoding="utf-8").replace("hathor-needs: D-0001", "hathor-needs: D-0999"),
        encoding="utf-8",
    )

    done = _run(folder, patch)

    assert done.returncode != 0
    assert "D-0999" in done.stderr, done.stderr
    assert _git(folder, "status", "--porcelain") == "", "막았는데 트리를 건드렸다"


def test_기준_트리가_달라도_경로가_맞으면_붙는다(tmp_path: Path) -> None:
    """**D-0376.** 패치 밖의 파일 하나가 전부를 막으면 안 된다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    done = _run(folder, _patch(folder, base="0" * 40))

    assert done.returncode == 0, done.stderr
    # **경고는 stderr로 나간다** — 사람이 보라는 것이지 멈추라는 것이 아니다.
    assert "기준 트리가 다르다" in done.stderr, done.stderr
    assert _git(folder, "log", "-1", "--format=%s") == COMMIT


def test_두_번_붙여도_커밋은_하나다(tmp_path: Path) -> None:
    """**멱등성은 git이 진다** (스크립트 머리말). 두 번째는 *«이미 붙어 있다»*다."""
    folder = tmp_path / "repo"
    _fixture(folder)
    patch = _patch(folder)

    first = _run(folder, patch)
    second = _run(folder, patch)

    assert first.returncode == 0, first.stderr
    assert len(_git(folder, "log", "--format=%s").splitlines()) == 2, "두 번째가 또 커밋했다"
    assert second.returncode == 0 or "이미" in second.stdout + second.stderr, second.stderr
