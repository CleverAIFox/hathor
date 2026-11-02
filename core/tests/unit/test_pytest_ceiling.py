"""pytest 상한과 그것을 풀 날 (D-0475). 위생 시험이 길이 상한을 넘어 따로 뒀다."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _workers_for_marked_group(tmp_path: Path) -> list[str]:
    """표식을 **직접 적은** 합성 나무를 `--dist loadgroup`으로 돌려 시험이 간 워커를 낸다.

    훅을 안 거친다 — 여기서 묻는 것은 저장소 배선이 아니라 «상류가 `loadgroup`을 아직
    깨뜨리고 있는가»다. 배선은 `test_gate_isolation.py`가 따로 본다.
    """
    seen = tmp_path / "seen"
    for name in ("a", "b", "c"):
        (tmp_path / f"test_{name}.py").write_text(
            "import os, pytest\n\n"
            "@pytest.mark.xdist_group('gpu')\n"
            f"def test_{name}():\n"
            f"    open({str(seen)!r}, 'a').write(os.environ['PYTEST_XDIST_WORKER'] + ' ')\n",
            encoding="utf-8",
        )
    for index in range(40):  # 채우는 시험 — 워커보다 적으면 어차피 몰려 통과한다
        (tmp_path / f"test_fill{index}.py").write_text(
            f"def test_fill{index}() -> None:\n    assert True\n", encoding="utf-8"
        )
    subprocess.run(
        (
            *(sys.executable, "-m", "pytest", str(tmp_path), "-q", "--no-cov", "-n", "6"),
            *("--dist", "loadgroup", "-p", "no:cacheprovider", "--rootdir", str(tmp_path)),
        ),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return seen.read_text(encoding="utf-8").split() if seen.exists() else []


def test_pytest_상한을_풀_때가_되면_운다(tmp_path: Path) -> None:
    """**상한만 적어 두면 2년 뒤에도 그대로 남는다** (GR-0.7, D-0475).

    `pyproject.toml`이 pytest를 9.2 미만으로 묶은 것은 9.2가 xdist의 `loadgroup`을 깼기
    때문이다. 적은 이유는 낡지만 재는 것은 안 낡는다 — 설치된 pytest가 9.2 이상일 때
    **실제로 무리가 한 워커로 묶이면** 이유가 사라진 것이니 상한을 풀라고 운다.

    9.2 미만이면 잴 것이 없다(상한 안이다). 여기서 재는 것은 «풀어도 되는가»다.
    """
    from importlib.metadata import version

    installed = tuple(int(part) for part in version("pytest").split(".")[:2])
    if installed < (9, 2):
        return
    workers = _workers_for_marked_group(tmp_path)
    assert len(workers) == 3, f"셋이 다 안 돌았다: {workers}"
    assert len(set(workers)) > 1, (
        f"pytest {version('pytest')}에서 loadgroup이 다시 묶는다 ({workers}) — "
        "core/pyproject.toml의 `pytest>=8.3,<9.2` 상한을 풀 때가 됐다 (D-0475)"
    )
