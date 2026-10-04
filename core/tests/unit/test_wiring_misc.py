"""**부품은 재고 배선은 안 쟀다** — 나머지 관문 (D-0359).

`check_compose` 셋 · `check_retired` 셋 · `mlflow_sync` 셋 · `prefect_flow` 셋 ·
`check_file_size` 둘 · `check_forbidden` 둘 · `check_requirements` 둘 ·
`check_under_load` 둘 · `encoding_check` 둘 · `gpu_smoke` 둘 · `mutate_gate` 둘.

`gpu_smoke`는 **이 기기에 CUDA가 없다** — `torch`를 심어서 입구를 돌린다. 못 재는 것을
안 쟀다고 적는 것보다, **재는 길을 만드는 것이 낫다** (GR-0.5).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import tool_module

COMPOSE = tool_module("check_compose")
RETIRED = tool_module("check_retired")
MLFLOW = tool_module("mlflow_sync")
PREFECT = tool_module("prefect_flow")
SIZE = tool_module("check_file_size")
FORBIDDEN = tool_module("check_forbidden")
REQS = tool_module("check_requirements")
LOAD = tool_module("check_under_load")
ENCODING = tool_module("encoding_check")
GPU = tool_module("gpu_smoke")
MUTATE = tool_module("mutate_gate")

PLANTED = "심은 문제"


def _spoke(capsys: pytest.CaptureFixture[str]) -> str:
    spoke = capsys.readouterr()
    return spoke.out + spoke.err


# ------------------------------------------------------------------ check_compose


def test_합계가_화면에_오른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`services()` · `totals()` 두 자리.

    **상한의 합이 기기 램을 넘는 것을 막는 검사다** (D-0262).
    """
    monkeypatch.setattr(COMPOSE, "services", lambda _: {"심은서비스": 2048})
    monkeypatch.setattr(COMPOSE, "totals", lambda _: {"심은묶음": 2048})
    monkeypatch.setattr(COMPOSE, "verdict", lambda *_: [])
    monkeypatch.setattr("sys.argv", ["check_compose.py", "--check"])

    assert COMPOSE.main() == 0
    spoke = _spoke(capsys)
    assert "서비스 1개" in spoke, "services()가 끊겼다"
    assert "심은묶음 2.00GB" in spoke, "totals()가 끊겼다"


def test_compose_판정이_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(COMPOSE, "services", lambda _: {})
    monkeypatch.setattr(COMPOSE, "totals", lambda _: {})
    monkeypatch.setattr(COMPOSE, "verdict", lambda *_: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_compose.py", "--check"])

    assert COMPOSE.main() == 1
    assert PLANTED in _spoke(capsys)


# ------------------------------------------------------------------ check_retired


def test_지운_말_검사가_파일마다_돈다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`targets()` · `check_retired_words()` 두 자리 — `check()` 안쪽."""
    one_doc = tmp_path / "문서.md"
    one_doc.write_text("아무 말\n", encoding="utf-8")
    monkeypatch.setattr(RETIRED, "ROOT", tmp_path)
    monkeypatch.setattr(RETIRED, "targets", lambda: [one_doc])
    monkeypatch.setattr(RETIRED, "check_retired_words", lambda *_: [PLANTED])

    assert RETIRED.check() == [PLANTED]


def test_통과줄이_훑은_문서_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()`의 `targets()` 자리. **수가 화면에 없으면 0인 것도 모른다** (D-0230)."""
    monkeypatch.setattr(RETIRED, "check", list)
    monkeypatch.setattr(RETIRED, "targets", lambda: [Path("가"), Path("나")])
    monkeypatch.setattr("sys.argv", ["check_retired.py", "--check"])

    assert RETIRED.main() == 0
    assert "문서 2개" in _spoke(capsys)


# ------------------------------------------------------------------ mlflow_sync


def test_원격_추적_서버는_받지_않는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`is_local()` 자리 — **음원도 지표도 기기를 안 떠난다** (D-0015 · D-0224)."""
    monkeypatch.setattr(MLFLOW, "is_local", lambda _: False)
    monkeypatch.setattr(MLFLOW, "load", list)
    monkeypatch.setattr("sys.argv", ["mlflow_sync.py", "--uri", "http://남의서버:5000"])

    assert MLFLOW.main() == 1
    assert "로컬만" in _spoke(capsys)


def test_리포트를_읽어_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`load()` 자리. 끊으면 **「리포트가 없다」를 늘 찍는다** — 있어도 없다고 한다."""
    monkeypatch.setattr(MLFLOW, "is_local", lambda _: True)
    monkeypatch.setattr(
        MLFLOW,
        "load",
        lambda _: [SimpleNamespace(name="심은리포트", metrics={"a": 1}, params={})],
    )
    monkeypatch.setattr("sys.argv", ["mlflow_sync.py", "--dry-run"])

    assert MLFLOW.main() == 0
    spoke = _spoke(capsys)
    assert "심은리포트" in spoke and "리포트 1개" in spoke


def test_옮긴_수와_건너뛴_수가_나온다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`sync()` 자리. **옮기지 않고 「옮겼다」를 찍던 모양을 막는다.**"""
    monkeypatch.setattr(MLFLOW, "is_local", lambda _: True)
    monkeypatch.setattr(MLFLOW, "load", lambda _: [SimpleNamespace(name="심은리포트")])
    monkeypatch.setattr(MLFLOW, "sync", lambda *_: (3, 4))
    monkeypatch.setattr("sys.argv", ["mlflow_sync.py"])

    assert MLFLOW.main() == 0
    assert "옮김 3 · 이미 있음 4" in _spoke(capsys)


# ------------------------------------------------------------------ prefect_flow


def test_plan이_명령을_찍는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`commands()` 자리. **흐름을 돌리기 전에 무엇이 돌지 눈으로 본다.**"""
    monkeypatch.setattr(PREFECT, "commands", lambda *_: [("심은단계", ["심은", "명령"])])
    monkeypatch.setattr("sys.argv", ["prefect_flow.py", "--plan"])

    assert PREFECT.main() == 0
    spoke = _spoke(capsys)
    assert "심은단계" in spoke and "심은 명령" in spoke


def test_원격_prefect는_받지_않는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(PREFECT, "api_is_local", lambda _: False)
    monkeypatch.setattr(PREFECT, "build", lambda *_: pytest.fail("원격인데 흐름을 세웠다"))
    monkeypatch.setattr("sys.argv", ["prefect_flow.py", "--mlflow", "http://127.0.0.1:5000"])

    assert PREFECT.main() == 1
    assert "로컬만" in _spoke(capsys)


def test_로컬이면_흐름을_세워_돌린다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`api_is_local()` · `build()` 두 자리. **세우지 않고 「끝」을 찍지 않는다.**"""
    monkeypatch.setattr(PREFECT, "api_is_local", lambda _: True)
    monkeypatch.setattr(PREFECT, "build", lambda *_: lambda: (8, 9))
    monkeypatch.setattr("sys.argv", ["prefect_flow.py", "--mlflow", "http://127.0.0.1:5000"])

    assert PREFECT.main() == 0
    assert "옮김 8 · 이미 있음 9" in _spoke(capsys)


# ------------------------------------------------------------------ check_file_size


def test_길이_update가_성장_허락을_넘긴다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**예외값을 올리는 것은 래칫을 뒤로 돌리는 일이다** (D-0117).

    허락이 안 닿으면 조용히 돈다.
    """
    seen: list[bool] = []

    def noted(grow: bool) -> int:
        seen.append(grow)
        return 3

    monkeypatch.setattr(SIZE, "update", noted)

    monkeypatch.setattr("sys.argv", ["check_file_size.py", "--update"])
    assert SIZE.main() == 3
    monkeypatch.setattr("sys.argv", ["check_file_size.py", "--update", "--allow-growth"])
    assert SIZE.main() == 3

    assert seen == [False, True]


def test_실측을_재서_검사에_넘긴다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`measure()` 자리. 끊으면 **파일을 한 개도 안 재고** 통과한다 (D-0230)."""
    seen: list[object] = []
    monkeypatch.setattr(SIZE, "measure", lambda: {"심은파일": 999})

    def noted(got: object) -> list[str]:
        seen.append(got)
        return []

    monkeypatch.setattr(SIZE, "check", noted)
    monkeypatch.setattr("sys.argv", ["check_file_size.py"])

    assert SIZE.main() == 0
    assert seen == [{"심은파일": 999}]


# ------------------------------------------------------------------ check_forbidden


def test_금지가_배선돼_있다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(FORBIDDEN, "survey", lambda: [PLANTED])
    monkeypatch.setattr("sys.argv", ["check_forbidden.py", "--check"])

    assert FORBIDDEN.main() == 1
    spoke = _spoke(capsys)
    assert PLANTED in spoke and FORBIDDEN.ALLOW in spoke


def test_금지_통과줄이_본_파일_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tracked()` 자리. **0개를 보고도 「통과」가 떠 있었다** (D-0230)."""
    monkeypatch.setattr(FORBIDDEN, "survey", list)
    monkeypatch.setattr(FORBIDDEN, "tracked", lambda: ["가", "나", "다"])
    monkeypatch.setattr("sys.argv", ["check_forbidden.py", "--check"])

    assert FORBIDDEN.main() == 0
    assert "파일 3개" in _spoke(capsys)


# ------------------------------------------------------------------ check_requirements


def test_요구사항_통과줄이_행과_그룹을_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`rows()` · `declared_groups()` 두 자리."""
    monkeypatch.setattr(REQS, "rows", lambda: [SimpleNamespace(rank="1", state="열림", phase="A")])
    monkeypatch.setattr(REQS, "declared_groups", lambda: {"심은그룹", "둘째"})
    monkeypatch.setattr(REQS, "check", lambda *_: [])
    monkeypatch.setattr("sys.argv", ["check_requirements.py", "--check"])

    assert REQS.main() == 0
    assert "1행 · 그룹 2개" in _spoke(capsys)


# ------------------------------------------------------------------ check_under_load


def test_부하_검사가_관문을_읽어_돌린다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`gates()` · `sweep()` 두 자리. **sweep을 끊으면 한 판도 안 돌고 통과한다** (D-0355)."""
    planted_gates = [f"tools/심은{number}.py" for number in range(LOAD.FLOOR + 1)]
    monkeypatch.setattr(LOAD, "gates", lambda: planted_gates)
    monkeypatch.setattr(LOAD, "sweep", lambda _: [("tools/심은0.py", PLANTED)])
    monkeypatch.setattr("sys.argv", ["check_under_load.py", "--check"])

    assert LOAD.main() == 1
    spoke = _spoke(capsys)
    assert PLANTED in spoke and "한가할 때는 안 보인다" in spoke


def test_부하_list가_관문_수를_말한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(LOAD, "gates", lambda: ["tools/심은.py"])
    monkeypatch.setattr(LOAD, "sweep", lambda _: pytest.fail("목록만 보자는데 돌렸다"))
    monkeypatch.setattr("sys.argv", ["check_under_load.py", "--list"])

    assert LOAD.main() == 0
    assert "관문 1개" in _spoke(capsys)


# ------------------------------------------------------------------ encoding_check


@pytest.fixture
def encoding_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    """**바닥을 실물로 채운다.** 훑은 수가 바닥 밑이면 그 앞에서 막힌다 (D-0356)."""
    monkeypatch.setattr(
        ENCODING, "tracked", lambda: [f"stub{number}" for number in range(ENCODING.FLOOR_TRACKED)]
    )
    monkeypatch.setattr(ENCODING, "looked_at", lambda _: True)


def test_글자_검사가_훑어서_판정한다(
    encoding_seen: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`scan()` 자리. **끊었는데 아무 시험도 안 울었다** — 수가 화면에만 있었다 (D-0356)."""
    monkeypatch.setattr(ENCODING, "scan", lambda: [("심은파일", ["CRLF"])])
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--check"])

    assert ENCODING.main() == 1
    assert "심은파일" in _spoke(capsys)


def test_fix가_고친_바이트를_쓴다(
    encoding_seen: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`repaired()` 자리. 끊으면 **「고쳤다」만 찍고 파일은 그대로다.**"""
    target = tmp_path / "깨진.txt"
    target.write_bytes(b"\xef\xbb\xbf\xea\xb0\x80\r\n")
    left: list[list[tuple[str, list[str]]]] = [[("깨진.txt", ["BOM"])], []]
    monkeypatch.setattr(ENCODING, "ROOT", tmp_path)
    monkeypatch.setattr(ENCODING, "scan", lambda: left.pop(0))
    monkeypatch.setattr(ENCODING, "repaired", lambda raw, suffix: b"\xea\xb0\x80\n")
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--fix"])

    assert ENCODING.main() == 0
    assert target.read_bytes() == b"\xea\xb0\x80\n", "고친 바이트를 안 썼다"
    assert "1개를 고쳤다" in _spoke(capsys)


def test_고친_뒤_다시_훑는다(
    encoding_seen: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--fix` 뒤의 `scan()` 자리.

    **고칠 수 없는 것이 남는다** — 비 UTF-8은 손으로 봐야 한다. 두 번째 훑기를 끊으면
    `--fix`가 **남은 것을 삼키고 0을 낸다.**
    """
    target = tmp_path / "깨진.txt"
    target.write_bytes(b"\xef\xbb\xbf\xea\xb0\x80\r\n")
    left: list[list[tuple[str, list[str]]]] = [
        [("깨진.txt", ["BOM"]), ("이진.bin", ["비 UTF-8"])],
        [("이진.bin", ["비 UTF-8"])],
    ]
    monkeypatch.setattr(ENCODING, "ROOT", tmp_path)
    monkeypatch.setattr(ENCODING, "scan", lambda: left.pop(0))
    monkeypatch.setattr(ENCODING, "repaired", lambda raw, suffix: b"\xea\xb0\x80\n")
    monkeypatch.setattr("sys.argv", ["encoding_check.py", "--fix"])

    assert ENCODING.main() == 1, "못 고친 것이 남았는데 통과했다"
    spoke = _spoke(capsys)
    assert "1개를 고쳤다" in spoke and "이진.bin" in spoke


# ------------------------------------------------------------------ gpu_smoke


@pytest.fixture
def planted_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    """**이 기기에 CUDA가 없다.** 입구를 재려면 `torch`를 심는 수밖에 없다."""

    class FakeTensor:
        def __matmul__(self, other: object) -> FakeTensor:
            return self

    stub = SimpleNamespace(
        __version__="2.0.0+심음",
        version=SimpleNamespace(cuda="12.1"),
        float16="float16",
        randn=lambda *_, **__: FakeTensor(),
        isfinite=lambda _: SimpleNamespace(all=lambda: SimpleNamespace(item=lambda: True)),
        cuda=SimpleNamespace(
            is_available=lambda: True,
            is_bf16_supported=lambda: True,
            get_device_properties=lambda _: SimpleNamespace(
                name="심은기기", total_memory=24 * 2**30, major=8, minor=9
            ),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", stub)


def test_필요_vram과_판정이_둘_다_배선돼_있다(
    planted_torch: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`required_vram()` · `verdict()` 두 자리.

    **조건은 `PLAN §1`에 적혀 있고 이 도구가 그것을 읽는다** — 손으로 적으면 어긋난다
    (D-0223). 판정이 끊기면 **미달인 기기에 「조건을 넘는다」를 찍는다.**
    """
    monkeypatch.setattr(GPU, "required_vram", lambda: 99)
    monkeypatch.setattr(GPU, "verdict", lambda *_: [PLANTED])

    assert GPU.main() == 0
    spoke = _spoke(capsys)
    assert "VRAM 99GB" in spoke, "required_vram()이 끊겼다"
    assert PLANTED in spoke, "verdict()가 끊겼다"


# ------------------------------------------------------------------ mutate_gate


def test_WIRING이_배선_모드로_간다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`cut_wiring()` 자리. **이 도구가 배선을 재는 도구다** — 제 배선이 먼저다."""
    monkeypatch.setenv("WIRING", "1")
    monkeypatch.setattr(MUTATE, "cut_wiring", lambda: 5)

    assert MUTATE.main() == 5


def test_관문_도구_목록을_거친다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`gate_tools()` 자리. 끊으면 **도구 0개를 망가뜨리고 초록을 찍는다** (D-0230).

    `WIRING`을 반드시 지운다 — `make mutate WIRING=1`이 자식에게 그 환경을 물려준다.
    """
    monkeypatch.delenv("WIRING", raising=False)
    monkeypatch.setattr(MUTATE, "gate_tools", lambda: ["있을리없는도구"])

    with pytest.raises((FileNotFoundError, OSError)):
        MUTATE.main()

    assert "관문 도구 1개" in _spoke(capsys), "목록을 안 거쳤다"
