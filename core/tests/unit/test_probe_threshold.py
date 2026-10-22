"""문턱의 오경보율·검출율을 재는 자 (D-0460).

**실측은 그의 기기에서만 된다** — 한 판이 어휘 셋을 생성하고 쌍 400에서 11분이다
(D-0015와는 다른 까닭이다: 비밀이 아니라 비용이다). 여기서 보는 것은 **세는 법**과
**막는 자리**다.

### 왜 이 자가 생겼나

D-0327이 `t>=2`를 고르며 *«음성 4% · 양성 100%»*를 쟀는데 **그 코퍼스를 짓는 코드가
커밋되지 않았다.** PLAN §3.1에 *«갚는 법: 도구 없음»*이 섰고, 그것이 O-81을 막았다.
"""

from __future__ import annotations

import argparse
import math
from typing import Any, cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_threshold")


def _sweep(gains: tuple[float, ...], *, passed: int = 0, errors: float = 0.004) -> Any:
    return TOOL.Sweep(
        name="시험",
        gains=gains,
        errors=(errors,) * len(gains),
        passed=passed,
        mass=0.7237,
        seconds=0.0,
    )


def test_평균의_t는_판_사이_흔들림으로_잰다() -> None:
    """**판별 `t`가 아니다** (D-0460).

    쌍이 겹치면 보고된 판별 오차를 못 믿는다 (O-81). 판 사이 흔들림은 판마다
    코퍼스와 쌍을 새로 뽑으므로 **겹침에 안 부푼다.**
    """
    one = _sweep((0.010, 0.012, 0.008, 0.010))

    assert one.mean == pytest.approx(0.010)
    assert one.spread == pytest.approx(0.0016329, abs=1e-6)
    assert one.mean_t > 10.0, "0에서 멀리 떨어진 평균인데 t가 작다"


def test_0_근처면_평균의_t가_작다() -> None:
    """**양성 대조** (D-0259). 위 시험만 있으면 «t가 늘 크다»도 통과한다."""
    one = _sweep((0.0012, -0.0004, 0.0021, -0.0011))

    assert abs(one.mean_t) < 2.0


def test_읽는_법이_문턱에서_갈린다() -> None:
    """**사전 등록이다** (D-0058). 수를 보고 정하지 않도록 코드에 박혀 있다."""
    biased = _sweep((0.010, 0.012, 0.008, 0.010))
    centred = _sweep((0.0012, -0.0004, 0.0021, -0.0011))

    assert "0이 아니다" in TOOL.verdict(biased)
    assert "쌍 수를 못 올린다" in TOOL.verdict(biased)
    assert "안 갈린다" in TOOL.verdict(centred)


def test_못_갈랐다를_0이라_안_한다() -> None:
    """**GR-0.5.** 「0과 안 갈린다」와 「0이다」는 다른 말이다."""
    centred = _sweep((0.0012, -0.0004, 0.0021, -0.0011))

    reading = TOOL.verdict(centred)

    assert "「0이다」가 아니라" in reading
    assert "못 갈랐다" in reading


def test_한_판이면_흔들림을_안_잰다() -> None:
    """쌍이 하나일 때 오차를 0이라 안 하는 것과 같은 규율 (GR-0.5)."""
    one = _sweep((0.01,))

    assert one.spread == 0.0
    assert math.isnan(one.mean_t), "흔들림을 못 쟀는데 수가 났다"
    assert "못 쟀다" in TOOL.verdict(one), "못 잰 것이 「0과 안 갈린다」로 읽히면 봐주는 쪽이다"


def test_판이_하나면_막는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**반쯤 쓴 판정이 가장 나쁘다.** 수는 나오는데 뜻이 없다 (D-0230)."""
    monkeypatch.setattr("sys.argv", ["probe_threshold.py", "--trials", "1"])

    assert TOOL.main() == 1
    assert "둘 이상" in capsys.readouterr().err


def test_비용을_먼저_찍는다() -> None:
    """**무거우면 끈다** (D-0129). 끄게 하려면 얼마나 무거운지 보여야 한다."""
    both = cast(
        "str",
        TOOL.cost(argparse.Namespace(songs=1000, pairs=400, trials=6, only="both", trial_seed=0)),
    )
    one = cast(
        "str",
        TOOL.cost(
            argparse.Namespace(songs=1000, pairs=400, trials=6, only="negative", trial_seed=0)
        ),
    )

    assert "덮는 곡" in both
    assert "11분" in both, "견줄 기준이 없으면 사람이 비용을 못 읽는다"
    assert "대조 2개" in both
    assert "대조 1개" in one, "`--only`가 비용에 안 비치면 사람이 두 배로 읽는다"


def test_마른_실행은_안_돈다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--dry-run`이 **생성을 한 벌도 안 돌린다.** 돌면 이 깃발이 거짓이다."""
    monkeypatch.setattr(TOOL, "sweep", _Exploding().sweep)
    monkeypatch.setattr("sys.argv", ["probe_threshold.py", "--dry-run"])

    assert TOOL.main() == 0
    assert "덮는 곡" in capsys.readouterr().out


def test_양성이_안_서면_음성을_안_읽는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**자가 안 도는데 수를 읽으면 안 된다** (D-0259 · D-0230).

    음성만 보면 **아무것도 통과 안 시키는 문턱이 가장 좋아 보인다** — D-0327이
    `t>=3`을 기각한 까닭이 양성 38%를 놓친다였다.
    """
    made = iter((_sweep((0.0, 0.0), passed=0), _sweep((0.0, 0.0), passed=0)))
    monkeypatch.setattr(TOOL, "sweep", lambda *_a, **_k: next(made))
    monkeypatch.setattr("sys.argv", ["probe_threshold.py", "--trials", "2"])

    assert TOOL.main() == 1
    assert "양성이 한 판도 안 통과" in capsys.readouterr().err


def test_판마다_코퍼스를_새로_뽑는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**같은 코퍼스에 쌍만 다시 뽑으면** 그 코퍼스의 치우침이 전 판에 공통으로

    남아 판 사이 흔들림이 그것을 못 본다. 묻는 것은 *«이 대조 **방식**이 0을
    내는가»*다 (D-0460).
    """
    seeds: list[int] = []
    drawn: list[tuple[int, ...]] = []
    built: Any = TOOL.build
    ran: Any = TOOL.EvaluateHarmonyOutput

    def spy(count: int, **kwargs: Any) -> Any:
        seeds.append(int(kwargs["seed"]))
        return built(count, **kwargs)

    def watch(condition: Any) -> Any:
        drawn.append(tuple(condition.seeds[:2]))
        return ran(condition)

    monkeypatch.setattr(TOOL, "build", spy)
    monkeypatch.setattr(TOOL, "EvaluateHarmonyOutput", watch)
    args = argparse.Namespace(
        songs=8, pairs=3, trials=3, mass=0.7237, corpus_seed=1000, sigma=0.9, trial_seed=0
    )

    TOOL.sweep("시험", sigma=0.0, args=args)

    assert seeds == [1000, 1001, 1002], f"판마다 코퍼스 시드가 안 바뀐다: {seeds}"
    # **생성 시드가 판마다 밀리는지가 이 시험의 반쪽이다** (D-0461). 처음엔 코퍼스만
    # 보고 있었고, 그 사이 `seed`가 생성기에 안 닿아 **전 판이 같은 진행을 봤다.**
    assert len(set(drawn)) == 3, f"판마다 생성 시드가 같다: {sorted(set(drawn))}"


class _Exploding:
    """**불리면 터진다** — 안 불려야 맞는 자리다."""

    def sweep(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("마른 실행인데 생성을 돌렸다")
