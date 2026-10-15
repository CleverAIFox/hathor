"""환경 · 봇 · 찌꺼기 (D-0225) · 명령 (D-0226) · 죽은 검사와 글자 (D-0230)."""

from __future__ import annotations

import ast
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


def test_액션을_한_가지_꼴로_고정한다() -> None:
    """**꼴이 둘이면 그물이 한쪽을 못 본다** (D-0428 · D-0230).

    위 바닥 검사는 `@v<수>`를 찾는다. `papers.yml`을 세샤트에서 옮기며 그쪽의 SHA 핀을
    같이 들고 왔고, **그 파일만 정규식 밖에 섰다.** `checkout@v5`(저장소는 v7)에
    `setup-python`은 Node 20이었는데 **아홉 판 동안 아무 검사도 안 짖었다.**

    고르는 것은 **꼴 하나**다 (D-0043). 꼬리표로 박으면 Dependabot이 올려 주고 바닥
    검사가 본다 — SHA로 박으면 둘 다 못 한다.
    """
    sha = re.compile(r"uses: ([\w./-]+)@([0-9a-f]{40})")
    odd = [
        f"{path.name}: {found.group(1)}@{found.group(2)[:8]}…"
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        for found in sha.finditer(path.read_text(encoding="utf-8"))
    ]
    assert not odd, f"SHA로 박았다: {odd}. 이 저장소는 `@v<수>`로 고정한다 (D-0428)"


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


# ------------------------------------------------- 얕은 클론 (D-0382)

DEEP = re.compile(r"HEAD(?:~(\d+)|(\^+)(?!\{))")
"""저장소 이력을 거슬러 가는 꼴. `HEAD^{tree}`처럼 **껍질 벗기기는 아니다.**"""

SHALLOW_OK = "shallow: ok"
"""제 저장소를 따로 짓는 시험의 면제 선언. **까닭을 같이 적는다.**"""


def _ci_depth() -> int:
    """CI가 pytest를 도는 잡의 **받는 깊이**. 정본은 워크플로다 (D-0043)."""
    flow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    found = [int(one) for one in re.findall(r"fetch-depth:\s*(\d+)", flow) if one != "0"]
    assert found, "ci.yml에서 fetch-depth를 못 읽었다 — 깊이를 모르면 판정하지 않는다"
    return min(found)


def _spoken(tree: ast.Module) -> set[int]:
    """독스트링인 문자열. **산문은 안 센다** — 이 시험의 설명에도 `HEAD~3`이 적혀 있다."""
    return {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }


def test_시험이_얕은_클론보다_깊이_안_판다() -> None:
    """**같은 시험이 기기마다 다른 길을 돌면 판정이 둘이 된다** (D-0353 · D-0382).

    CI는 `fetch-depth: 2`로 받는다 — 내 기기에는 이력이 다 있고 거기엔 둘뿐이다.
    세 칸을 판 시험이 **내 기기에서만 초록**이었고 CI에서 셋이 빨갰다. 이 죄가
    **사흘에 세 번**이다: `dot`이 깔렸나 · `HEAD`가 뭘 건드렸나 · 이력이 얼마나 깊나.

    제 저장소를 따로 짓는 시험은 `# shallow: ok <사유>`로 면제한다 — 그 깊이는 제가
    만든 것이라 환경과 무관하다.
    """
    depth = _ci_depth()
    guilty = []
    for path in sorted((ROOT / "core" / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _spoken(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docs or SHALLOW_OK in node.value:
                continue
            for tilde, carets in DEEP.findall(node.value):
                back = int(tilde) if tilde else len(carets)
                if back >= depth:
                    guilty.append(f"{path.name}:{node.lineno} 이력 {back}칸 (CI는 {depth})")

    assert guilty == [], "제 저장소를 짓거나 `# shallow: ok <사유>`를 적는다 (D-0382)"


# ------------------------------------------------- 시험은 실물 저장소에 안 쓴다 (D-0386)


GIT_WRITES = frozenset(
    {
        "commit",
        "commit-tree",
        "hash-object",
        "write-tree",
        "update-index",
        "update-ref",
        "push",
        "tag",
        "am",
        "reset",
        "checkout",
        "merge",
        "rebase",
        "gc",
        "prune",
    }
)
"""**저장소를 바꾸는 git 동사.** 쓰기는 ident · 인덱스 · 이력 깊이를 묻고 그 셋이
기기마다 다르다 — 읽기(`show` · `rev-parse` · `status`)는 묻지 않는다."""

WRITE_FLOOR = 8
"""그물의 **바닥** (D-0230). 동사 목록이 비면 이 검사가 영원히 0을 낸다."""


def _root_runners(tree: ast.AST) -> set[str]:
    """`cwd=ROOT`로 무언가를 부르는 **함수의 이름**.

    이번 결함이 정확히 이 틈으로 들어왔다 (D-0386): `_git()`이 `cwd=ROOT`를 들고
    있었고 호출자는 `_git("commit-tree", …)`라고만 적었다. **호출만 보면 안 걸린다.**
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and any(
                keyword.arg == "cwd"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "ROOT"
                for keyword in call.keywords
            ):
                found.add(node.name)
    return found


def _words(nodes: list[ast.expr]) -> set[str]:
    """인자에 **글자 그대로 적힌** 문자열. 튜플·리스트 안까지 본다."""
    out: set[str] = set()
    for node in nodes:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                out.add(inner.value)
    return out


def _root_writes(path: Path) -> list[str]:
    """그 파일이 **실물 저장소에** 거는 쓰기 동사."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    runners = _root_runners(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        by_name = isinstance(node.func, ast.Name) and node.func.id in runners
        by_cwd = any(
            keyword.arg == "cwd"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "ROOT"
            for keyword in node.keywords
        )
        if not (by_name or by_cwd):
            continue
        found += sorted(_words(node.args) & GIT_WRITES)
    return found


def test_시험이_실물_저장소에_git을_안_쓴다() -> None:
    """**쓰기는 환경에 묻는다** (D-0386 · D-0353).

    같은 죄를 네 판 연속 지었다. 넷 다 **로컬은 초록이고 CI만 빨갰다**:

    | 판 | 물은 것 |
    |---|---|
    | D-0377 | `dot`이 깔려 있나 |
    | D-0378 | 같은 것을 다시 |
    | D-0382 | 이력이 얼마나 깊나 (`fetch-depth: 2`) |
    | D-0385 | **`commit-tree`** — ident · 인덱스 파일 |

    임시 저장소에 쓰는 것은 **정상이다** — 그 안에서 `git init`부터 하므로 환경이
    시험의 것이다. 여기서 막는 것은 **실물 저장소**에 거는 쓰기 하나뿐이다.
    """
    assert len(GIT_WRITES) >= WRITE_FLOOR, "동사 목록이 비면 영원히 0을 낸다 (D-0230)"

    dirty = {
        path.relative_to(ROOT).as_posix(): said
        for path in sorted((ROOT / "core" / "tests").rglob("*.py"))
        if (said := _root_writes(path))
    }

    assert dirty == {}, dirty


def test_그물이_헬퍼를_거친_쓰기도_문다(tmp_path: Path) -> None:
    """**심은 결함** (D-0069). 호출만 보던 그물은 이것을 놓친다 — 그게 D-0385였다."""
    page = tmp_path / "심은것.py"
    page.write_text(
        "ROOT = 1\n"
        "def _git(*args):\n"
        "    return subprocess.run(('git', *args), cwd=ROOT)\n"
        "def test_하나():\n"
        '    _git("commit-tree", "x")\n',
        encoding="utf-8",
    )

    assert _root_writes(page) == ["commit-tree"]


def test_그물이_임시_저장소_쓰기는_안_문다(tmp_path: Path) -> None:
    """**거짓 경보는 진짜 경보를 죽인다** (GR-0.8). 임시 저장소 쓰기는 정상이다."""
    page = tmp_path / "정상.py"
    page.write_text(
        "def test_하나(tmp_path):\n"
        '    subprocess.run(("git", "commit", "-m", "x"), cwd=tmp_path)\n',
        encoding="utf-8",
    )

    assert _root_writes(page) == []


# ------------------------------------- 시험이 실물 저장소를 안 고친다 (D-0398)
#
# **D-0386은 `git` 쓰기만 봤다.** 파일 쓰기는 그물 밖이었고 **정적으로는 안 보인다** —
# 쓰는 자가 시험이 아니라 **시험이 부른 도구**다. `test_mutate_gate`가 `ROOT`를 안 바꾼
# 채 `cut_wiring()`을 불러 실물 `tools/tidy.py`를 덮었고, 그가 **190줄이 비워진 트리**를
# 받았다. `make check`은 **전부 초록이었다.**

GUARD = _tool("tree_guard")


def test_나무_지킴이가_make_test에_걸려_있다() -> None:
    """**안 걸면 안 돈다** (D-0126). 지문만 뜨고 대조를 안 하면 장식이다."""
    recipe = (ROOT / "Makefile").read_text(encoding="utf-8")
    start = recipe.index("\ntest:")
    block = recipe[start : recipe.index("\n\n", start)]

    assert "tree_guard.py --snapshot" in block
    assert "tree_guard.py --check" in block
    assert block.index("--snapshot") < block.index("pytest"), "지문을 시험 뒤에 뜬다"
    assert block.index("pytest") < block.index("--check"), "대조를 시험 전에 한다"


def test_지켜보는_파일이_바닥을_넘는다() -> None:
    """**0개를 지켜보며 「아무것도 안 바뀌었다」를 내놓을 수 있다** (D-0230)."""
    assert len(GUARD.fingerprint()) >= GUARD.FLOOR


def test_바뀐_파일을_센다() -> None:
    """바뀐 것 · 생긴 것 · 사라진 것 셋 다 든다."""
    before = {"가": [1, 1], "나": [2, 2]}

    assert GUARD.changed(before, before) == []
    assert GUARD.changed(before, {**before, "가": [1, 9]}) == ["가"]
    assert GUARD.changed(before, {**before, "다": [3, 3]}) == ["다"]
    assert GUARD.changed(before, {"가": [1, 1]}) == ["나"]


def test_되돌려_놔도_걸린다() -> None:
    """**쓰기 자체가 결함이다.** 내용이 같아도 `mtime`이 다르면 누가 쓴 것이다.

    `test_mutate_gate`는 `finally`로 되돌리고 있었다 — 그래서 내용만 보면 **영원히
    안 걸린다.** 그 창에서 끊긴 것이 이번 사고다.
    """
    before = {"가": [10, 111]}

    assert GUARD.changed(before, {"가": [10, 222]}) == ["가"]


def test_시험_나무는_안_지켜본다() -> None:
    """**빨간 시험을 일부러 심고 지우는 자가 있다** (D-0359 · D-0219).

    그 차집합은 **선언으로만** 비운다 — `WATCHED`에 `core/tests`가 없는 것이 그 선언이다.
    """
    assert "core/tests" not in GUARD.WATCHED
    assert set(GUARD.WATCHED) == {"tools", "core/hathor"}


def test_저장소_안에_지문을_안_쓴다() -> None:
    """**새 파일이 `ship`의 위생에 센다.** 지문은 기기의 임시 자리에 둔다."""
    assert ROOT not in GUARD.where().parents
    assert GUARD.where().name.startswith("hathor-tree-")
