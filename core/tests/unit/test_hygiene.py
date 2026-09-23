"""환경 · 봇 · 찌꺼기 (D-0225) · 명령 (D-0226) · 죽은 검사와 글자 (D-0230)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import deadcheck  # noqa: E402
import encoding_check  # noqa: E402
import gh_ops  # noqa: E402
import tidy  # noqa: E402

# ------------------------------------------------------------------ 환경은 한 명령


SYNC_ALLOWED = (
    "Makefile",
    ".github/workflows/",
    "docs/DECISIONS.md",
    "core/tests/",
    "core/uv.lock",
)
"""`uv sync --…`를 적어도 되는 자리. Makefile이 정본이고, CI는 새 러너에 필요한 것만 깔며,
결정 기록은 과거다."""


def test_환경을_맞추는_명령은_make_sync_하나다() -> None:
    """**D-0225의 강제자.** 안내 셋이 서로를 지웠다.

    README에 `--group docs` · `--group mlops` 안내가 따로 있었고 uv는 정확 동기화라 **하나를
    치면 나머지가 지워졌다.** D-0222가 GPU 묶음으로 한 번 겪었고 D-0224의 안내로 docs 묶음이
    또 지워졌다. 숫자가 두 곳에 있으면 결함이다 (D-0223) — 명령도 같다.
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    offenders = []
    for name in tracked:
        if name.startswith(SYNC_ALLOWED) or not (ROOT / name).is_file():
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"uv sync --", text):
            offenders.append(name)
    assert offenders == []
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "uv sync --all-extras --all-groups" in makefile


# ------------------------------------------------------------------ 봇 갱신


def _updates() -> list[str]:
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    return re.split(r"\n  - package-ecosystem:", text)[1:]


def test_봇은_한_달에_한_번_생태계마다_PR_하나다() -> None:
    """주 1회 · 묶음 없이 두면 봇 PR과 브랜치가 쌓이고 아무도 안 읽는다 (fire-lane §212-3)."""
    blocks = _updates()
    assert len(blocks) == 2
    for block in blocks:
        assert 'interval: "monthly"' in block
        assert 'patterns: ["*"]' in block
        assert "open-pull-requests-limit:" in block


def test_봇이_보는_폴더에_매니페스트가_있다() -> None:
    """폴더를 옮기고 설정을 안 고치면 봇이 매달 오류만 낸다."""
    for block in _updates():
        directory = re.search(r'directory: "([^"]+)"', block)
        assert directory is not None
        base = ROOT / directory.group(1).strip("/")
        if '"uv"' in block:
            assert (base / "pyproject.toml").is_file() and (base / "uv.lock").is_file()
        else:
            assert (base / ".github" / "workflows").is_dir()


def test_워크플로_린트가_러너_라벨을_안다() -> None:
    """등록 도구 · 흐름 · actionlint 설정의 라벨이 한 벌이다."""
    config = (ROOT / ".github" / "actionlint.yaml").read_text(encoding="utf-8")
    script = (ROOT / "tools" / "register_runner.sh").read_text(encoding="utf-8")
    labels = re.search(r"RUNNER_LABELS:-([\w,]+)", script)
    assert labels is not None
    assert set(labels.group(1).split(",")) == set(re.findall(r"^\s+- (\S+)$", config, re.M))


# ------------------------------------------------------------------ 찌꺼기


def test_지금_선_브랜치는_안_지운다() -> None:
    rows = ["main [gone]", "feat [gone]", "keep [ahead 1]", "plain "]
    assert tidy.gone_branches(rows, current="main") == ["feat"]


def test_봇_추적_참조만_고른다() -> None:
    rows = ["origin/main", "origin/dependabot/uv/core/python-1", "origin/HEAD", "fork/dependabot/x"]
    assert tidy.bot_refs(rows) == ["origin/dependabot/uv/core/python-1", "fork/dependabot/x"]


def test_적용된_패치는_제목이_로그에_있는_것이다(tmp_path: Path) -> None:
    (tmp_path / "D0300.patch").write_text("# hathor-commit: D0300: 무엇\ndiff\n", encoding="utf-8")
    (tmp_path / "D0301.patch").write_text("# hathor-commit: D0301: 아직\n", encoding="utf-8")
    (tmp_path / "other.patch").write_text("diff --git a b\n", encoding="utf-8")
    (tmp_path / "applied").mkdir()
    (tmp_path / "applied" / "D0299.patch").write_text("# hathor-commit: 옛것\n", encoding="utf-8")
    subjects = {"D0300: 무엇", "옛것"}
    assert [p.name for p in tidy.applied_patches(tmp_path, subjects)] == ["D0300.patch"]
    assert tidy.patch_subject(tmp_path / "other.patch") is None


def test_보고는_셋까지만_이름을_찍는다() -> None:
    found = [tidy.Finding("봇 브랜치 추적 참조", tuple(f"r{i}" for i in range(5)), ())]
    assert tidy.report(found) == ["봇 브랜치 추적 참조 5: r0 · r1 · r2 외 2"]


# ------------------------------------------------------------------ 웹 화면 대신 명령 (D-0226)


def test_웹_화면_안내는_명령으로_바꾼다() -> None:
    """**D-0226의 강제자.** 버튼 안내는 PLAN에 손 항목으로 쌓이고 누를 자리를 잊는다."""
    places = ["README.md", "docs/PLAN.md", "docs/MASTER.md", ".github/workflows/gpu-smoke.yml"]
    places += [f"tools/{name}" for name in ("register_runner.sh", "gh_ops.py", "tidy.py")]
    for name in places:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "Settings →" not in text and "Run workflow" not in text, name


def test_봇_실행_중_실패만_고른다() -> None:
    runs = [
        {"workflowName": "Dependabot Updates", "conclusion": "failure", "databaseId": 1},
        {"workflowName": "Dependabot Updates", "conclusion": "success", "databaseId": 2},
        {"workflowName": "Copilot", "conclusion": "failure", "databaseId": 3},
    ]
    assert [run["databaseId"] for run in gh_ops.failed(runs)] == [1]


def test_gh가_없으면_까는_법을_말한다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh_ops.shutil, "which", lambda name: None)
    reason = gh_ops.ready()
    assert reason is not None and "gh auth login" in reason


def test_core에서_쳐도_뿌리_목표가_돈다() -> None:
    forward = (ROOT / "core" / "Makefile").read_text(encoding="utf-8")
    assert "-C .." in forward
    assert "\ncheck:" not in forward, "목표를 core에 두 벌 두지 않는다"


# ------------------------------------------------------------------ 러너 · 잠금 (D-0227)


def test_스모크는_라벨을_다_가진_켜진_러너가_있어야_건다() -> None:
    """**D-0227의 강제자 하나.** 손으로 등록한 러너에 `gpu`가 없어 실행이 대기열에서 멈췄다."""
    wanted = gh_ops.wanted_labels()
    assert wanted == {"self-hosted", "linux", "gpu"}

    def runner(name: str, status: str, *labels: str) -> dict[str, object]:
        return {"name": name, "status": status, "labels": [{"name": x} for x in labels]}

    runners = [
        runner("bare", "online", "self-hosted", "Linux", "X64"),
        runner("off", "offline", "self-hosted", "Linux", "gpu"),
        runner("ok", "online", "self-hosted", "Linux", "X64", "gpu", "1660ti"),
    ]
    assert gh_ops.usable(runners, wanted) == ["ok"]


def test_잠금은_도는_곳만_푼다() -> None:
    """**D-0227의 강제자.** macOS 칸의 demucs 제약이 봇 갱신을 통째로 죽였다.

    도는 곳은 WSL · CI · 데브 컨테이너 — 전부 리눅스 x86_64다. 안 도는 칸을 풀면 거기 제약이
    우리 갱신을 막는다.
    """
    project = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    assert (
        "environments = [\"sys_platform == 'linux' and platform_machine == 'x86_64'\"]" in project
    )
    lock = (ROOT / "core" / "uv.lock").read_text(encoding="utf-8")
    head = lock.split("[[package]]", 1)[0]
    assert "darwin" not in head and "win32" not in head


def test_러너_등록은_다시_쳐도_된다() -> None:
    """이미 등록된 기기에서 `config.sh`를 다시 부르면 죽는다 — 사용자 기기에서 그랬다."""
    script = (ROOT / "tools" / "register_runner.sh").read_text(encoding="utf-8")
    assert "if [ -f .runner ]" in script
    assert "actions/runners/$id/labels" in script


def test_다른_저장소의_러너는_안_건드린다() -> None:
    """**D-0228의 강제자.** 기본 폴더에 seshat 러너가 있었고 첫 판이 그 서비스를 올렸다.

    개인 계정의 러너는 저장소 하나에 묶인다 — 폴더를 저장소마다 나누고, 남의 폴더면 멈춘다.
    """
    script = (ROOT / "tools" / "register_runner.sh").read_text(encoding="utf-8")
    assert 'dir="${RUNNER_DIR:-$HOME/actions-runner-${slug#*/}}"' in script
    assert '"$(field gitHubUrl)" != "$url"' in script


# ------------------------------------------------------------------ 죽은 검사 · 글자 (D-0230)


def test_프로브는_심은_결함에_운다() -> None:
    """**D-0230의 강제자.** 실제 트리의 0건은 «깨끗하다»이지 «프로브가 산다»가 아니다.

    fire-lane은 이 둘을 섞어 «결함이 많을수록 확실히 통과하는» 관문을 돌렸다. 생사는 합성
    트리에서 묻고, 저장소의 수는 래칫이 본다.
    """
    assert deadcheck.positive_control() == []


def test_죽은_검사_래칫은_양방향이다() -> None:
    top = {"무검증 시험": 0, "건너뛴 시험": 2}
    assert deadcheck.verdict({"무검증 시험": 0, "건너뛴 시험": 2}, top) == []
    assert len(deadcheck.verdict({"무검증 시험": 1, "건너뛴 시험": 2}, top)) == 1
    assert len(deadcheck.verdict({"무검증 시험": 0, "건너뛴 시험": 1}, top)) == 1


def test_면제는_선언으로만_된다() -> None:
    """선언 없는 면제는 없다 (D-0219와 같은 규율)."""
    lines = ["def test_x():", "    pass  # deadcheck: ok 사유", "def test_y():", "    pass"]
    assert deadcheck.exempt(lines, 1, 2)
    assert not deadcheck.exempt(lines, 3, 4)
    assert deadcheck.exempt(lines, 2, 2), "한 줄짜리도 그 줄의 선언을 받는다"


def test_글자_규격을_어긴_바이트를_전부_센다() -> None:
    assert encoding_check.faults(b"\xef\xbb\xbfhi\n", ".md") == ["BOM"]
    assert encoding_check.faults(b"hi\r\nthere\n", ".py") == ["CRLF"]
    assert encoding_check.faults(b"hi\r\n", ".bat") == []
    assert encoding_check.faults(b"\xc7\xd1\n", ".md") == ["비 UTF-8"]
    assert encoding_check.faults(b"hi", ".md") == ["끝 개행 없음"]
    assert encoding_check.faults(b"", ".md") == []
    assert encoding_check.faults("한글\n".encode(), ".md") == []


def test_고치면_규격에_맞고_다시_고쳐도_같다() -> None:
    raw = b"\xef\xbb\xbf\xed\x95\x9c\r\n\xea\xb8\x80"
    fixed = encoding_check.repaired(raw, ".md")
    assert encoding_check.faults(fixed, ".md") == []
    assert encoding_check.repaired(fixed, ".md") == fixed
