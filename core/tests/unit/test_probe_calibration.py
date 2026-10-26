"""보고된 오차가 제 변동을 담는가 — 그 자의 단위 검사 (D-0451).

**실측은 그의 기기에서만 된다** (D-0015). 여기서 보는 것은 **세는 법**이다 —
흔들림과 오차의 비를 옳게 내는지, 자료가 없을 때 멈추는지.

### 왜 이 자가 생겼나

같은 자료·같은 쌍 수인데 **시드 하나로 판정이 뒤집혔다** (D-0450). 보고된 오차가
0.0085인데 두 판이 0.025 떨어졌다 — **오차가 제 변동을 담는지 아무도 안 쟀다.**
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_calibration")


def test_정직한_오차는_비가_1이다() -> None:
    """**비가 이 자의 전부다.** 흔들림을 오차로 나눈다 — 1이면 오차가 정직하다."""
    gaps = [0.00, 0.01, -0.01, 0.02, -0.02]
    spread = statistics.stdev(gaps)
    errors = [spread] * len(gaps)

    found = TOOL.report_on("심은 것", gaps, errors, 0)

    assert found["honesty"] == 1000


def test_오차가_절반이면_비가_2다() -> None:
    """**양성 대조** (D-0259). 과소평가를 심었는데 1000이 나오면 이 자가 눈이 멀었다."""
    gaps = [0.00, 0.01, -0.01, 0.02, -0.02]
    errors = [statistics.stdev(gaps) / 2] * len(gaps)

    assert TOOL.report_on("심은 것", gaps, errors, 0)["honesty"] == 2000


def test_뒤집힘은_적은_쪽을_센다() -> None:
    """**24판 중 20판 통과면 뒤집힘이 4다** — 다수결이 아니라 **갈린 정도**를 센다.

    전부 통과하거나 전부 실패하면 0이다. 그것이 «안 갈린다»의 뜻이다.
    """
    gaps = [0.01] * 24
    errors = [0.001] * 24

    assert TOOL.report_on("심은 것", gaps, errors, 24)["flips"] == 0
    assert TOOL.report_on("심은 것", gaps, errors, 0)["flips"] == 0
    assert TOOL.report_on("심은 것", gaps, errors, 20)["flips"] == 4
    assert TOOL.report_on("심은 것", gaps, errors, 12)["flips"] == 12


def test_시드_수를_값으로_못질한다() -> None:
    """**D-0327이 오경보율에 쓴 수다** (D-0058). 잘 나오는 값을 찾아 돌린 것이 아니다.

    **이름을 바꿨다** (D-0470). 「새로 안 골랐다」는 이 단언이 재는 성질이 아니다 —
    리터럴을 두 번 적었을 뿐이고, 고르고 나서 여기 수도 같이 고치면 **아무 일도
    안 일어난다.** 이것은 **값 못질**이다: 바꾸려면 결정 기록을 같이 쓰게 만드는
    턱이지, 안 골랐다는 증거가 아니다.

    그 수가 실제로 몇 판을 돌게 하는지는 아래에서 **기본값 경로로** 건다.
    """
    assert TOOL.SEEDS == 24

    # **상수가 배선에 꽂혀 있는가**는 재어진다 (D-0126). 안 꽂혀 있으면 이 못은
    # 아무 데도 안 박힌 채 문서 노릇만 한다.
    source = Path(str(TOOL.__file__)).read_text(encoding="utf-8")
    assert '"--seeds", type=int, default=SEEDS' in source, "상수가 기본값에 안 꽂혀 있다"


def test_넉_배로_늘리면_오차가_반이다() -> None:
    """쌍이 넉 배면 **오차가 반**이어야 한다. 안 그러면 쌍이 겹친 것이다.

    **그 성질을 아무도 안 쟀다** (D-0470). 시험은 `WIDE == 4`만 걸었고 도구는
    두 오차를 따로 찍기만 했다 — **적어 둔 주장과 도는 코드 사이가 비어 있었다**
    (D-0126: 안 걸면 안 돈다).
    """
    assert TOOL.WIDE == 4, "값 못질 — 바꾸려면 기록을 같이 쓴다"

    # 보고된 오차가 `1/sqrt(n)`을 정확히 따른 꼴. **도구가 그 비를 내는가**를 본다.
    got, want = TOOL.shrink({"error": 40}, {"error": 20}, 4)
    assert want == pytest.approx(2.0)
    assert got == pytest.approx(2.0)

    # **덜 줄면 덜 줄었다고 나와야 한다** — 봐주는 쪽으로 접히면 안 본 것과 같다.
    half, _ = TOOL.shrink({"error": 40}, {"error": 32}, 4)
    assert half < want

    # **못 쟀으면 nan이다** (GR-0.5 · N6과 같은 관례).
    import math

    assert math.isnan(TOOL.shrink({"error": 40}, {"error": 0}, 4)[0])


def test_산출물이_없으면_멈춘다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**못 쟀으면 1을 낸다** (GR-0.5). 반쯤 잰 비가 가장 나쁘다."""
    monkeypatch.setattr(TOOL, "resolve_priors", lambda *_: None)
    monkeypatch.setattr("sys.argv", ["probe_calibration.py", "--seeds", "2"])

    assert TOOL.main() == 1
    assert "정본을 안 건드린다" in capsys.readouterr().err


def test_쌍_수를_정본에서_든다() -> None:
    """`DEFAULT_PAIR_COUNT`를 든다. **새로 지으면 D-0450이 다시 난다.**"""
    from hathor.application.evaluate_harmony_output import DEFAULT_PAIR_COUNT

    assert TOOL.DEFAULT_PAIR_COUNT == DEFAULT_PAIR_COUNT
