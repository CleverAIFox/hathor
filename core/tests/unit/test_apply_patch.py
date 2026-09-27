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
