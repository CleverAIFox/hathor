"""가짜 모듈을 심는 시험은 혼자 돌아도 통과하는가 (D-0276).

### 왜 이것이 필요했나

D-0275를 내보낸 뒤 사용자 기기에서 **하나가 빨갛게 났다.**

    AttributeError: module 'torch' has no attribute 'Tensor'

`test_clap_feature_extractor`가 `sys.modules["torch"]`에 가짜를 심는다. 제품 코드는 그
가짜를 잘 쓰는데, `to_clap_waveform`이 **함수 안에서** `from scipy.signal import
resample_poly`를 한다. 그 임포트가 가짜가 심긴 동안 일어나면 `scipy`의
`array_api_compat`이 `is_torch_array`에서 `getattr(torch, "Tensor")`를 하다 죽는다.

**가짜 모듈은 제품 코드만 속이는 것이 아니라 그 프로세스 전체를 속인다.**

### 왜 지금까지 초록이었나

같은 파일의 첫 시험이 `scipy`를 먼저 들여서 **우연히** 살아 있었다. `-n auto`가 시험을
워커에 나누므로 **어느 워커에 무엇이 가느냐**에 따라 갈린다 — 시험 수가 바뀌면 배치가
바뀌고, D-0274·D-0275가 시험을 더하자 배치가 움직여 터졌다.

실측: 가짜를 쓰는 시험 다섯 중 **넷이 혼자 돌면 죽었다.** 파일 단위로 돌리면 다섯 다
통과한다 — **파일 격리로는 안 잡힌다.**

### 무엇을 보는가

가짜를 심는 시험을 **하나씩 제 프로세스에서** 돌린다. 6건에 7초다.

고친 뒤 **1553건 전부를 하나씩 돌려 봤다 — 0건이다.** 이 부류 말고 순서에 기대는 시험은
없다. 전수는 9분이라 관문에 못 넣고, 가짜 모듈이 심긴 자리만 매번 본다.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[2]
TESTS = CORE / "tests"
PLANT = "setitem(sys.modules"
"""가짜 모듈을 심는 자리의 표식. 이 파일은 세는 대상에서 빠진다 (D-0261의 `SELF`)."""

SELF = Path(__file__).name

ISOLATED = 6
"""혼자 돌려야 하는 시험의 수. **세는 값이 있어야 «전부»가 뜻을 갖는다** (D-0230).

그물이 비면 이 관문은 아무것도 안 돌리고도 초록이다. 늘리려면 결정 기록이 필요하다
(D-0118) — 가짜 모듈이 하나 더 생겼다는 뜻이고, 그것은 판단할 일이다."""


def _planters(tree: ast.Module) -> set[str]:
    """`sys.modules`에 가짜를 심는 함수 이름. 도우미일 수도 시험일 수도 있다."""
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and PLANT in ast.unparse(node)
    }


def planting_tests() -> list[str]:
    """가짜 모듈이 심긴 채로 도는 시험의 노드 아이디.

    **한 걸음만 따라간다** — 시험이 직접 심거나, 심는 도우미를 부르거나. 지금 저장소는
    그 두 꼴뿐이고, 더 깊어지면 이 그물이 비어 `ISOLATED`가 막는다.
    """
    found: list[str] = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path.name == SELF:
            continue
        source = path.read_text(encoding="utf-8")
        if PLANT not in source:
            continue
        tree = ast.parse(source)
        planters = _planters(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            body = ast.unparse(node)
            if PLANT in body or any(f"{name}(" in body for name in planters):
                found.append(f"{path.relative_to(CORE).as_posix()}::{node.name}")
    return found


INHERITED = ("COV_CORE_", "COVERAGE_", "PYTEST_")
"""자식이 물려받으면 안 되는 환경변수의 머리 (D-0282).

부모가 `--cov`로 돌면 `pytest-cov`가 `.pth` 훅을 심어 **모든 파이썬 자식이 측정을 시작한다.**
그 자식이 또 `pytest`면 부모의 측정 자리에 자기 자료를 쓴다 — 여섯 자식이 그렇게 한다.

**자식은 이 관문이 묻는 것만 대답해야 한다** — «혼자 돌면 통과하는가»다. 부모의 측정을
물려받으면 그 답에 부모가 섞인다."""


def _clean_env() -> dict[str, str]:
    """부모의 측정·캐시 설정을 뺀 환경."""
    return {name: value for name, value in os.environ.items() if not name.startswith(INHERITED)}


def test_그물이_비지_않았다() -> None:
    """**세는 그물이 비면 «전부 통과»가 거짓으로 참이 된다** (D-0230)."""
    found = planting_tests()
    assert len(found) == ISOLATED, f"가짜를 심는 시험이 {len(found)}개다: {found}"


def test_가짜_모듈을_심는_시험은_혼자_돌아도_통과한다() -> None:
    """**D-0276의 강제자.** 배치 운이 아니라 규약으로 통과해야 한다.

    `--no-cov`로 자식이 커버리지 바닥에 안 걸리게 한다 — 한 시험만 도니 그 바닥은 뜻이 없다.
    이 저장소에는 순서를 섞는 플러그인이 없으므로(`pytest-randomly` 미설치) 수집 순서는
    고정이고, **갈리는 것은 `-n auto`가 시험을 워커에 나누는 경계뿐이다.**
    """
    broken: list[str] = []
    for node_id in planting_tests():
        done = subprocess.run(
            (sys.executable, "-m", "pytest", node_id, "-q", "--no-cov", "-p", "no:cacheprovider"),
            cwd=CORE,
            env=_clean_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            broken.append(f"{node_id}\n{done.stdout[-1200:]}")

    assert not broken, "혼자 돌면 죽는 시험이 있다:\n" + "\n".join(broken)


# --------------------------------- 장비를 같이 쓰는 시험은 한 워커로 (D-0290)

GPU_BOUND = 5
"""GPU를 실제로 잡는 시험의 수. **세는 값이 있어야 «전부»가 뜻을 갖는다** (D-0230).

mert 3 · demucs 2다. `test_clap_feature_extractor`는 **가짜 모듈을 심으므로 카드를 안
잡는다** — 그 여섯은 D-0276이 드는 자리이고 여기가 아니다. 섞으면 이 수가 거짓이 된다."""


def _collected(*paths: str) -> dict[str, int]:
    """`-m xdist_group`으로 실제 수집해서 무리에 든 시험을 파일별로 센다.

    **표식이 붙었는지 소스로 안 본다.** 훅이 붙이는 것이라 소스에는 한 글자도 없다 —
    D-0283에서 글자 자리를 보는 시험이 틀린 그 자리다.

    `addopts`가 이미 `-q`라 수집 출력은 `파일: 수` 꼴이다. 노드 아이디를 세려고 `-v`를
    얹으면 **이 시험이 저장소 설정에 기대게 된다.**
    """
    done = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-cov",
            "-p",
            "no:cacheprovider",
            "-m",
            "xdist_group",
            *paths,
        ),
        cwd=CORE,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    found: dict[str, int] = {}
    for line in done.stdout.splitlines():
        name, _, count = line.rpartition(": ")
        if name.endswith(".py") and count.strip().isdigit():
            found[name] = int(count)
    return found


def test_GPU를_잡는_시험만_무리에_든다() -> None:
    """**목록을 손으로 안 든다** (D-0290). 이미 선언된 건너뜀 사유를 읽는다.

    손목록은 낡고, 새 GPU 시험이 조용히 밖에 남는다 — 그 시험은 다시 경합에 노출되고
    **왜 가끔 터지는지 아무도 모른다.**
    """
    found = _collected("tests/unit")
    total = sum(found.values())
    assert total == GPU_BOUND, f"무리에 든 시험이 {total}개다: {found}"


def test_가짜를_심는_시험은_무리에_안_든다() -> None:
    """**가짜 모듈은 카드를 안 잡는다.** 섞으면 `GPU_BOUND`가 거짓이 된다."""
    assert _collected("tests/unit/test_clap_feature_extractor.py") == {}


def test_무리로_묶으면_한_워커로_간다(tmp_path: Path) -> None:
    """**강제자다** — `--dist loadgroup`이 실제로 모으는가 (양성 대조).

    설정만 바꾸고 동작을 안 보면, 다음 판에 `-n auto`만 남아도 조용히 흩어진다.
    """
    tests = tmp_path / "t"
    tests.mkdir()
    for name in ("a", "b"):
        (tests / f"test_{name}.py").write_text(
            "import os, pytest\n"
            "@pytest.mark.xdist_group('gpu')\n"
            f"def test_{name}():\n"
            f"    (os.environ['PYTEST_XDIST_WORKER'] + ' {name}\\n') and None\n"
            f"    open({str(tmp_path / 'seen')!r}, 'a').write(os.environ['PYTEST_XDIST_WORKER'])\n",
            encoding="utf-8",
        )
    subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            str(tests),
            "-q",
            "--no-cov",
            "-n",
            "4",
            "--dist",
            "loadgroup",
            "-p",
            "no:cacheprovider",
        ),
        cwd=CORE,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    seen = (tmp_path / "seen").read_text(encoding="utf-8")
    assert len(set(seen.replace("gw", " gw").split())) == 1, f"흩어졌다: {seen}"
