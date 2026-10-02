"""환경 · 봇 · 찌꺼기 (D-0225) · 명령 (D-0226) · 죽은 검사와 글자 (D-0230)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import tool_module as _tool

ROOT = Path(__file__).resolve().parents[3]

SHIP = _tool("ship")
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


def test_패치_검사가_이름_바꾸기를_읽는다(tmp_path: Path) -> None:
    """**D-0237의 강제자.** `git apply --numstat`은 **간 곳만** 찍는다.

    D-0236이 파일 다섯을 옮기자 트리에는 삭제 둘이 더 있었고, 검사가 «다른 작업이 섞였다»며
    막았다. 섞인 것은 없었다 — **검사가 이름 바꾸기를 못 읽은 것이다.**
    """
    patch = tmp_path / "rename.patch"
    patch.write_text(
        "diff --git a/old/thing.py b/new/thing.py\n"
        "similarity index 100%\n"
        "rename from old/thing.py\n"
        "rename to new/thing.py\n"
        "diff --git a/kept.py b/kept.py\n"
        "--- a/kept.py\n"
        "+++ b/kept.py\n",
        encoding="utf-8",
    )
    script = ROOT / "tools" / "apply_patch.sh"
    # 스크립트 전체를 돌리지 않고 **그 함수만** 떼어 부른다 — 붙이기는 여기서 할 일이 아니다.
    shell = f'source <(sed -n "/^declared_paths()/,/^}}/p" {script}); declared_paths "{patch}"'
    source = subprocess.run(["bash", "-c", shell], capture_output=True, text=True, check=True)
    assert source.stdout.split() == ["kept.py", "new/thing.py", "old/thing.py"], (
        "떠난 곳이 빠지면 커밋에 삭제가 안 들어가고 검사가 정상을 막는다"
    )


def test_시험_이름에_메모리_주소가_없다(request: pytest.FixtureRequest) -> None:
    """**D-0238의 강제자.** 이름이 실행마다 달라지면 병렬 실행이 죽는다.

    `_StoreAction` 객체를 `str()`로 이름에 넣어 `type=<function resolve_path at 0x7f...>`가
    박혀 있었다. 주소는 프로세스마다 다르므로 `pytest -n`이 **«워커마다 다른 시험을 모았다»**며
    수집 단계에서 죽었다. 이름이 안 고정되면 `--lf`도, 로그의 이름으로 다시 부르기도 안 된다.
    """
    unstable = [
        item.nodeid for item in request.session.items if re.search(r"at 0x[0-9a-f]+", item.nodeid)
    ]
    assert not unstable, f"시험 이름에 주소가 박혔다: {unstable[:3]}"


# ------------------------------- 지우는 것과 세는 것 (D-0279)


def test_지울_것과_셀_것이_갈려_있다() -> None:
    """**재생성 가능성이 «지워도 되는가»를 가른다** (D-0279 · `artifacts.toml` R2).

    PLAN §3에 «정리 정책이 `__pycache__`뿐이다»로 적혀 있었다. 세어 보니 `ship.py`는
    `.backup/`·`.o7-*/`·루트 `*.sh`를 **이미 세고 있었다** — 없던 것은 **부류를 가르는
    규칙**이었다. 세기만 하는 것이 옳은 자리인지 판단할 근거가 적혀 있지 않았다.
    """
    assert set(SHIP.REGENERABLE) & set(SHIP.COUNTED) == set(), "한 패턴이 두 부류에 있다"
    assert SHIP.REGENERABLE and SHIP.COUNTED, "부류가 비었다"


def test_make_clean이_선언과_같은_것을_지운다() -> None:
    """**선언과 명령이 어긋나면 그중 하나가 거짓말이다** (D-0219와 같은 규율).

    `make clean`이 지우는 것은 «자동으로 지운다»로 선언한 것과 같아야 하고, «세기만
    한다»는 거기 없어야 한다 — 있으면 사람이 넣은 것이 조용히 사라진다.
    """
    body = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = body.split("\nclean:", 1)[1].split("\nclean-all:", 1)[0]

    for pattern in SHIP.REGENERABLE:
        assert pattern in target, f"`make clean`이 {pattern}을 안 지운다"
    for pattern in SHIP.COUNTED:
        assert pattern not in target, f"`make clean`이 {pattern}을 지운다. 세기만 해야 한다"


def test_러너를_고정한다() -> None:
    """**`ubuntu-latest`는 날짜가 오면 저절로 바뀐다** (D-0330).

    2026-10-19부터 Ubuntu 26으로 옮겨 간다고 GitHub이 잡마다 경고를 찍었고, 그 경고를
    낸 잡 하나의 이름이 **`reproducibility`**였다 — 재현성을 보는 관문이 안 고정된 라벨
    위에 서 있었다.

    `uv.lock`을 리눅스 x86_64 하나로 좁혀 둔 저장소에서(D-0227) **러너만 떠다니면
    무엇이 재현된 것인지 알 수 없다.** 자체 호스팅 러너(`self-hosted`)는 라벨이
    기기를 가리키므로 해당이 없다.
    """
    floating: list[str] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "runs-on:" in line and "-latest" in line:
                floating.append(f"{path.name}:{number}")
    assert not floating, f"떠다니는 러너 라벨: {floating}. 판을 고정한다 (D-0330)"


def test_액션이_노드20에_머물러_있지_않다() -> None:
    """**Dependabot이 9월 22일에 올리라고 했고 PR이 닫혔다** (D-0330).

    `make bot-close`가 봇 PR을 **내용을 안 보고 전부 닫는다.** 그래서 아홉 날 뒤 Node 20
    폐기 경고가 떴다. 여기 적힌 판은 그 PR(#10)이 계산한 것이며 **내가 고른 수가 아니다.**

    `gitleaks-action`은 뺐다 — 주요 판을 올리면 비밀 검사 관문이 **닫히는 쪽으로** 깨질
    수 있고 여기서 돌려 볼 수가 없다. **못 재는 것을 고친 척하지 않는다** (GR-0.5).
    """
    least = {
        "actions/checkout": 5,
        "astral-sh/setup-uv": 7,
        "actions/configure-pages": 6,
        "actions/upload-pages-artifact": 5,
        "actions/deploy-pages": 5,
    }
    behind: list[str] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        body = path.read_text(encoding="utf-8")
        for action, floor in least.items():
            for found in re.finditer(rf"uses: {re.escape(action)}@v(\d+)", body):
                if int(found.group(1)) < floor:
                    behind.append(f"{path.name}: {action}@v{found.group(1)} < v{floor}")
    assert not behind, f"Node 20 판에 머물러 있다: {behind}"


def test_파이썬_하한을_상한과_같이_읽는다(tmp_path: Path) -> None:
    """**한 가지 꼴만 가정한 파서였다** (D-0341).

    앞을 `lstrip("><=~^ ")`하고 점으로 자르던 코드가 `">=3.12,<3.13"`에서
    `'12,<3'`을 `int`에 넘기고 **`make check`를 통째로 세웠다.** 상한을 박은 이유는
    `uv`가 3.13 · 3.14 · 3.15 칸까지 풀어 Dependabot이 다섯 번 죽어서다.
    """
    for spec, want in (
        (">=3.12", (3, 12)),
        (">=3.12,<3.13", (3, 12)),
        (">= 3.13 , <3.14", (3, 13)),
    ):
        folder = tmp_path / spec.replace(" ", "").replace(",", "_").replace("<", "lt")
        (folder / "core").mkdir(parents=True)
        (folder / "core" / "pyproject.toml").write_text(
            f'[project]\nname = "x"\nversion = "0"\nrequires-python = "{spec}"\n', encoding="utf-8"
        )
        assert deadcheck.python_floor(folder) == want, spec


def test_하한이_없으면_수를_지어내지_않는다(tmp_path: Path) -> None:
    """**없는 것을 0이라고 말하지 않는다** (GR-0.5). 하한이 없으면 판정을 못 한다."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\nrequires-python = "<3.13"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="하한이 없다"):
        deadcheck.python_floor(tmp_path)
