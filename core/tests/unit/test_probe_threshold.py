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
import re
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


def test_상한이_문턱_아래면_승인한다() -> None:
    """**승인 쪽 가지가 PLAN에만 있었다** (D-0464).

    *«95% 상한이 +0.001 아래면 쌍 1600이 승인된다»*가 문서에만 있어 읽는 사람이
    **반올림된 화면 수를 곱해야** 했다. 문턱이 넷째 자리인데 화면이 넷째 자리까지라
    실제로 그렇게 읽다가 +0.000988로 **승인 쪽으로 잘못 읽었다** — 전체 자릿수는
    +0.001030이었다 (GR-0.7).
    """
    tight = _sweep((0.0002, -0.0008, 0.0012, -0.0004, 0.0008, 0.0002))

    assert abs(tight.mean_t) < 2.0, "동결 쪽이 켜지면 승인 가지를 안 밟는다"
    assert tight.ceiling < TOOL.CEILING_FLOOR
    assert "승인된다" in TOOL.verdict(tight)


def test_치우침이_확정이면_상한이_낮아도_동결이다() -> None:
    """**두 가지가 같이 켜진다** (D-0464). 엄한 쪽을 든다.

    참 치우침이 0만 아니면 판을 늘릴수록 상한은 점추정으로 내려가 **승인**을 켜고
    `t`는 `√판`으로 자라 **동결**을 켠다. 참이 정확히 0일 때만 양립하는 규칙이라
    순서를 박아야 하고, *«작지만 확실히 0이 아니다»*는 **동결**로 읽는다.
    """
    small_but_certain = _sweep((0.00040, 0.00041, 0.00039, 0.00040, 0.00041, 0.00039))

    assert small_but_certain.ceiling < TOOL.CEILING_FLOOR, "상한은 승인 쪽을 켠다"
    assert abs(small_but_certain.mean_t) >= 2.0, "t는 동결 쪽을 켠다"
    assert "쌍 수를 못 올린다" in TOOL.verdict(small_but_certain), "둘이 겹치는데 승인했다"


def test_상한을_여섯_자리로_찍는다(capsys: pytest.CaptureFixture[str]) -> None:
    """**판정 문턱이 넷째 자리다** (D-0464). 넷째 자리까지 찍으면 읽는 사람이 못 가른다."""
    TOOL.report(_sweep((0.0002, -0.0008, 0.0012, -0.0004, 0.0008, 0.0002)))

    printed = capsys.readouterr().out
    assert re.search(r"95% 상한 [+-]0\.\d{6}", printed), f"자릿수가 모자란다: {printed}"
    assert re.search(r"평균 이득 [+-]0\.\d{6}", printed), (
        f"평균도 넷째 자리로는 못 읽는다: {printed}"
    )


def test_못_쟀으면_상한도_nan이다() -> None:
    """`mean_t`와 **같은 관례다** (D-0461). 0을 내면 봐주는 쪽으로 열린다."""
    one = _sweep((0.01,))

    assert math.isnan(one.ceiling)
    assert "못 쟀다" in TOOL.verdict(one)


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
        songs=8,
        pairs=3,
        trials=3,
        mass=0.7237,
        corpus_seed=1000,
        sigma=0.9,
        trial_seed=0,
        hold_corpus=False,
    )

    TOOL.sweep("시험", sigma=0.0, args=args)

    assert seeds == [1000, 1001, 1002], f"판마다 코퍼스 시드가 안 바뀐다: {seeds}"
    # **생성 시드가 판마다 밀리는지가 이 시험의 반쪽이다** (D-0461). 처음엔 코퍼스만
    # 보고 있었고, 그 사이 `seed`가 생성기에 안 닿아 **전 판이 같은 진행을 봤다.**
    assert len(set(drawn)) == 3, f"판마다 생성 시드가 같다: {sorted(set(drawn))}"


def test_잘린_로그에서_요약을_되살린다(tmp_path: Any) -> None:
    """**판 120개짜리가 104개에서 잘렸다** (D-0464). 요약은 끝에만 찍힌다.

    손으로 합치면 GR-0.7이라 도구가 되읽는다. **요약 줄의 「평균 이득」을 판으로
    세면 안 된다** — 한 번 그 함정에 빠져 93판을 94판으로 셌다.
    """
    log = tmp_path / "잘린.log"
    log.write_text(
        "코퍼스 1000곡 · 쌍 800 · 판 120\n"
        "  음성 판   0 · 이득 +0.001000 ±0.002000 · t +0.50 · 실패\n"
        "  음성 판   1 · 이득 +0.003000 ±0.002000 · t +1.50 · 실패\n"
        "  음성 판   2 · 이득 +0.005000 ±0.002000 · t +2.50 · 통과\n"
        "음성: 통과 **1/3** · 평균 이득 +0.003000 ±0.001155(판 사이) · 평균의 t +2.60\n",
        encoding="utf-8",
    )

    revived = TOOL.summarize(log)

    assert len(revived.gains) == 3, "요약 줄을 판으로 셌다"
    assert revived.passed == 1
    assert revived.mean == pytest.approx(0.003)
    assert math.isnan(revived.mass), "로그에 없는 질량을 수처럼 채웠다 (GR-0.5)"
    assert "3판" in revived.name, "몇 판에서 잘렸는지가 이름에 있어야 읽는 사람이 안다"


def test_판_줄이_모자라면_요약을_거부한다(tmp_path: Any) -> None:
    """**양성 대조** (D-0259). 위 시험만 있으면 «빈 로그도 요약»이 통과한다."""
    log = tmp_path / "빈.log"
    log.write_text("코퍼스 1000곡 · 쌍 800 · 판 120\n", encoding="utf-8")

    with pytest.raises(ValueError, match="판 줄이 둘 미만"):
        TOOL.summarize(log)


def test_찍은_줄을_되읽으면_같은_수가_나온다(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """**왕복이다** (D-0464). 찍는 쪽과 되읽는 쪽이 **같은 꼴**이어야 한다.

    따로 걸면 서식이 바뀌어도 시험이 조용히 헛돈다 — 손으로 쓴 로그는 **내가
    기억하는 꼴**을 검사하지 도구가 내는 꼴을 검사하지 않는다 (D-0043).

    그리고 자릿수가 여기서 걸린다: 넷째 자리로 찍으면 되읽은 평균이 안 맞는다.
    """
    args = argparse.Namespace(
        songs=8,
        pairs=3,
        trials=3,
        mass=0.7237,
        corpus_seed=1000,
        sigma=0.9,
        trial_seed=0,
        hold_corpus=False,
    )

    live = TOOL.sweep("음성", sigma=0.0, args=args)
    log = tmp_path / "찍힌.log"
    log.write_text(capsys.readouterr().out, encoding="utf-8")
    revived = TOOL.summarize(log)

    # **비트까지 같을 수는 없다** — 찍는 순간 여섯째 자리에서 반올림된다. 걸 것은
    # *«얼마나 틀리나»*이고, 그것이 **판정 눈금보다 훨씬 작아야** 되살린 요약을 쓴다.
    half = 5e-7
    assert revived.passed == live.passed
    assert len(revived.gains) == len(live.gains)
    for got, want in zip(revived.gains, live.gains, strict=True):
        assert got == pytest.approx(want, abs=half), "되읽은 이득이 반올림 폭을 넘는다"
    # 판정이 걸리는 자리는 `CEILING_FLOOR`(0.001)와 평균의 오차(1e-4 자리)다.
    assert abs(revived.mean - live.mean) < TOOL.CEILING_FLOOR / 1000


def test_코퍼스를_붙들면_쌍만_움직인다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**정직성이 무엇을 재는지가 모드에 달렸다** (D-0464).

    기본 모드의 판 사이 흔들림에는 **코퍼스 사이 흔들림**이 섞여 있어, 짝이 완벽히
    독립이어도 보고오차와의 비가 쌍 수와 함께 오른다. 코퍼스와 생성 시드를 붙들면
    그 섞임이 사라지고 **쌍 표집만** 남는다 — 그래야 「쌍 겹침이 정보를 깎나」를 묻는다.
    """
    seeds: list[int] = []
    offsets: list[int] = []
    pairs_seen: list[tuple[int, ...]] = []
    built: Any = TOOL.build
    ran: Any = TOOL.EvaluateHarmonyOutput

    def spy(count: int, **kwargs: Any) -> Any:
        seeds.append(int(kwargs["seed"]))
        return built(count, **kwargs)

    def watch(condition: Any) -> Any:
        offsets.append(condition.seed_offset)
        evaluator = ran(condition)
        pairs_seen.append(evaluator.pair_indices(8))
        return evaluator

    monkeypatch.setattr(TOOL, "build", spy)
    monkeypatch.setattr(TOOL, "EvaluateHarmonyOutput", watch)
    args = argparse.Namespace(
        songs=8,
        pairs=3,
        trials=3,
        mass=0.7237,
        corpus_seed=1000,
        sigma=0.9,
        trial_seed=0,
        hold_corpus=True,
    )

    TOOL.sweep("시험", sigma=0.0, args=args)

    assert set(seeds) == {1000}, f"코퍼스를 붙들라 했는데 시드가 움직인다: {seeds}"
    assert set(offsets) == {0}, f"생성 시드가 움직이면 쌍 표집만 보는 것이 아니다: {offsets}"
    assert len(set(pairs_seen)) == 3, "쌍은 판마다 달라야 한다 — 안 그러면 흔들림이 0이다"


class _Exploding:
    """**불리면 터진다** — 안 불려야 맞는 자리다."""

    def sweep(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("마른 실행인데 생성을 돌렸다")
