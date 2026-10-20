"""버리는 칸의 몫 전수 — 정본의 상류 (D-0449).

**실측은 그의 기기에서만 된다** (D-0015). 여기서 보는 것은 **세는 법**과 **막는
자리**다 — 산출물이 없을 때 정본을 안 건드리는지, 천분율로 옳게 접는지.

### 왜 이 상류가 생겼나

`MASTER`가 `other` 0.4357 · `mix` 0.4670을 *실측*이라 **손으로** 들고 있었는데, 그
수를 내는 산출물이 살아남은 여섯 중 **하나도 없었다.** 손으로 적은 수는 자료가
사라져도 안 운다 (GR-0.7 · D-0087).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_restriction")
CANON = tool_module("measured")


def test_천분율로_접는다() -> None:
    """정본은 **정수만** 든다 (D-0366). 거울이 `37.7%`로 찍는다."""
    assert TOOL._permille(0.3766) == 377
    assert TOOL._permille(0.4326) == 433
    assert TOOL._permille(0.0) == 0


def test_반올림이지_버림이_아니다() -> None:
    """**양성 대조.** 버림이면 0.4326이 432가 되고 거울이 0.1%p 틀린다."""
    assert TOOL._permille(0.4329) == 433
    assert TOOL._permille(0.4324) == 432


def test_정본이_그_출구를_든다() -> None:
    """`measured.SOURCES`가 이 도구를 가리키고 `EMITS`의 키가 정본과 같다 (D-0371).

    **양방향이다** — 아무도 안 세는 수도, 세고 버리는 수도 걸린다.
    """
    tool, const, ruler = cast("dict[str, tuple[str, str, str]]", CANON.SOURCES)["restriction"]

    assert (tool, const, ruler) == ("probe_restriction", "EMITS", "RULER")
    counts = cast("dict[str, dict[str, object]]", CANON.canon())["restriction"]["counts"]
    assert set(cast("dict[str, int]", counts)) == set(cast("tuple[str, ...]", TOOL.EMITS))


def test_자에_쌍_수와_시드가_적혀_있다() -> None:
    """**둘 다 자다** (D-0374). 쌍을 바꾸면 오차가, 시드를 바꾸면 본 쌍이 달라진다."""
    ruler = cast("str", TOOL.RULER)

    assert f"쌍 {TOOL.PAIRS}" in ruler
    assert f"시드 {TOOL.SEED}" in ruler


def test_산출물이_없으면_정본을_안_건드린다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 쟀으면 1을 낸다** (GR-0.5). 반쯤 쓴 정본이 가장 나쁘다."""
    monkeypatch.setattr(TOOL, "resolve_priors", lambda *_: None)
    monkeypatch.setattr(TOOL, "measured", _Exploding())
    monkeypatch.setattr("sys.argv", ["probe_restriction.py", "--emit"])

    assert TOOL.main() == 1
    assert "못 쟀다" in capsys.readouterr().err


def test_사전이_하나면_안_잰다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """곡 하나로는 쌍이 없다. **빈손보다 한 곡이 더 위험하다** — 수가 나온다."""
    monkeypatch.setattr(TOOL, "resolve_priors", lambda *_: tmp_path / "심은.keys.jsonl")
    monkeypatch.setattr(TOOL, "load_degree_priors", lambda *_: {"곡.flac": (1.0,) * 12})
    monkeypatch.setattr(TOOL, "measured", _Exploding())
    monkeypatch.setattr("sys.argv", ["probe_restriction.py", "--emit"])

    assert TOOL.main() == 1
    assert "사전이 1개다" in capsys.readouterr().err


class _Exploding:
    """`measured`를 대신한다. **불리면 터진다** — 안 불려야 맞는 자리다."""

    def emit(self, *_: object) -> list[str]:
        raise AssertionError("못 쟀는데 정본을 썼다")


# ------------------------------------------------- 시드 (D-0450)


def test_시드를_새로_안_짓는다() -> None:
    """**정본에서 든다** (D-0043 · D-0424).

    D-0449의 이 탐침이 `DEFAULT_SEED`가 있는데 `7`을 새로 적었다. 정본에 CLI와 다른
    수가 들어갔고, **그 둘의 차이가 판정을 뒤집는 크기**였다 — `other` 대비가
    -0.0005에서 +0.0245로, `t`가 -0.05에서 +2.88로 간다.
    """
    from hathor.application.evaluate_harmony_output import DEFAULT_PAIR_COUNT, DEFAULT_SEED

    assert TOOL.SEED == DEFAULT_SEED
    assert TOOL.PAIRS == DEFAULT_PAIR_COUNT


def test_시드가_한_곳에만_적혀_있다() -> None:
    """**여덟 곳에 손으로 박혀 있었다** (D-0450). CLI 다섯 · 응용 둘 · 정본 하나.

    한 곳만 고치는 날이 오면 **같은 자료가 다른 판정을 낸다.**
    """
    from hathor.application.evaluate_harmony_output import DEFAULT_SEED

    app = Path(__file__).resolve().parents[2] / "hathor"
    written = [
        f"{path.relative_to(app).as_posix()}:{number}"
        for path in sorted(app.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if str(DEFAULT_SEED) in line
    ]

    assert len(written) == 1, f"시드를 손으로 적은 자리: {' · '.join(written)}"
    assert written[0].startswith("application/evaluate_harmony_output.py")


def test_쌍_수도_한_곳에만_적혀_있다() -> None:
    """**시드와 같은 병이 쌍 수에도 있었다** (D-0453).

    `roots.DEFAULT_OUTPUT_PAIRS`와 `evaluate_harmony_output.DEFAULT_PAIR_COUNT`가
    각각 100을 들었다. 올릴 때 한 곳만 고치면 **화면과 기본값이 갈린다** (D-0043).
    """
    from hathor.application.evaluate_harmony_output import DEFAULT_PAIR_COUNT
    from hathor.interfaces.cli.roots import DEFAULT_OUTPUT_PAIRS

    assert DEFAULT_OUTPUT_PAIRS is DEFAULT_PAIR_COUNT

    app = Path(__file__).resolve().parents[2] / "hathor"
    written = [
        f"{path.relative_to(app).as_posix()}:{number}"
        for path in sorted(app.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if f"= {DEFAULT_PAIR_COUNT}" in line and "PAIR" in line.upper()
    ]

    assert len(written) == 1, f"쌍 수를 손으로 적은 자리: {' · '.join(written)}"


def test_쌍_수가_검정력으로_정해졌다() -> None:
    """**100은 24판 중 8판만 통과한다** (D-0452 실측).

    기준은 D-0327이 문턱을 고를 때 쓴 «양성을 놓치지 않는다»다 — 효과를 보고 올린
    것이 아니라 **서 있던 기준을 다른 손잡이에 댄 것이다** (D-0058).
    """
    from hathor.application.evaluate_harmony_output import DEFAULT_PAIR_COUNT

    assert DEFAULT_PAIR_COUNT == 400
