"""칸 배치가 음성 대조에 바닥을 만드나 (O-83 · D-0462).

**실측은 비싸다** — 진행 수백만 개다. 여기서 보는 것은 **세는 법**과 **막는 자리**다.

### 왜 이 자가 생겼나

D-0460이 *«자가 없으면 다시 못 잰다»*로 연 판인데, 그 판을 쓰면서 **나도 커밋 안 한
스크립트로 쟀다.** D-0462가 그것을 적고 **바로 갚았다** — 적어 두고 넘어가면
다음에 또 짓는다.
"""

from __future__ import annotations

import argparse
import math
from typing import Any, cast

import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_layout")


def _run(gains: tuple[float, ...], errors: tuple[float, ...]) -> Any:
    return TOOL.Run(mass=0.7237, gains=gains, errors=errors, realised=0.7199)


def test_오차는_둘_중_큰_쪽이다() -> None:
    """**판이 셋이면 판 사이 오차가 운으로 작아진다** (D-0461 · D-0462).

    D-0461이 못 하나를 한 시드로 박아 운으로 통과하던 자리에서 배운 것과 같다.
    짝지은 오차가 더 크면 그쪽을 든다.
    """
    lucky = _run((0.0010, 0.0011, 0.0009), (0.0030, 0.0030, 0.0030))

    across = 0.0001 / 3**0.5
    assert lucky.error > across * 5, "판 사이가 운으로 작은데 그것을 그대로 썼다"
    assert lucky.error == pytest.approx(0.0030 / 3**0.5, rel=1e-6)


def test_판_사이가_더_크면_그쪽을_든다() -> None:
    """**양성 대조** (D-0259). 위 시험만 있으면 «늘 짝지은 오차»도 통과한다."""
    wobbly = _run((0.010, -0.008, 0.004), (0.0005, 0.0005, 0.0005))

    assert wobbly.error > 0.004, "판이 널뛰는데 짝지은 오차를 들었다"


def test_상한은_아래로_묶는_수다() -> None:
    """**실측된 바닥이 아니다** (GR-0.5). 「이보다는 작다」가 이 수의 전부다."""
    one = _run((0.0002, 0.0002, 0.0002), (0.0009, 0.0009, 0.0009))

    assert one.ceiling > one.mean
    assert one.ceiling == pytest.approx(one.mean + 1.96 * one.error, rel=1e-9)


def test_한_판이면_못_잰다() -> None:
    """쌍이 하나일 때 오차를 0이라 안 하는 것과 같은 규율 (GR-0.5)."""
    one = _run((0.001,), (0.0,))

    assert one.error == 0.0
    assert math.isnan(one.t), "오차를 못 쟀는데 수가 났다"


def test_판이_하나면_막는다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**반쯤 쓴 판정이 가장 나쁘다** — 수는 나오는데 뜻이 없다 (D-0230)."""
    monkeypatch.setattr("sys.argv", ["probe_layout.py", "--trials", "1"])

    assert TOOL.main() == 1
    assert "둘 이상" in capsys.readouterr().err


def test_비용을_먼저_찍는다() -> None:
    """**무거우면 끈다** (D-0129). 끄게 하려면 얼마나 무거운지 보여야 한다."""
    text = cast(
        "str",
        TOOL.cost(argparse.Namespace(songs=1000, pairs=4000, trials=3)),
    )

    assert "덮는 곡" in text
    assert "진행" in text
    # **시험이 박힌 실측을 지키고 있었다** (D-0470). 「3.5배」는 한 판의 수였고
    # 쌍·시드·선 수가 바뀌면 움직이는데 글자는 안 움직였다. 비용 줄의 요점은
    # **`run()`을 왜 안 쓰는가**이지 그 배수가 아니다.
    assert "`paired` 하나만" in text, "`run()`을 왜 안 쓰는지가 비용 줄의 요점이다"
    assert "3.5배" not in text, "실측을 글자로 다시 박았다 (GR-0.7)"


def test_마른_실행은_안_돈다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--dry-run`이 **생성을 한 벌도 안 돌린다.**"""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("마른 실행인데 생성을 돌렸다")

    monkeypatch.setattr(TOOL, "sweep", explode)
    monkeypatch.setattr("sys.argv", ["probe_layout.py", "--dry-run"])

    assert TOOL.main() == 0
    printed = capsys.readouterr().out
    assert "덮는 곡" in printed
    # **두 배치를 화면에 적는다** — 질문이 「자리가 다르다」이므로 그 자리를 안 보이면
    # 읽는 사람이 무엇을 재는지 모른다 (D-0191).
    assert "bIII" in printed and "x-b2" in printed


def test_두_배치가_같은_무게_묶음을_다른_자리에_둔다() -> None:
    """**이것이 질문의 전부다** (O-83).

    `mixture`와 `control`은 둘 다 아홉 칸이고 **온음계 여섯을 공유한다.** 다른 것은
    나머지 셋이 **정렬된 풀의 어디에 앉느냐**이고, `rng.choices`가 누적 무게 위에서
    역변환 추출을 하므로 그 자리가 **두 곡의 뽑기가 얼마나 묶이는지**를 바꾼다.
    """
    from hathor.domain.value_objects.key import Mode
    from hathor.engines.compose.harmony_generator import Vocabulary, vocabulary_degrees

    mixture = vocabulary_degrees(Mode.MAJOR, Vocabulary("mixture"))
    control = vocabulary_degrees(Mode.MAJOR, Vocabulary("control"))
    base = set(vocabulary_degrees(Mode.MAJOR, Vocabulary("base")))

    assert len(mixture) == len(control), "칸 수가 다르면 거리가 공짜로 오른다 (D-0094)"
    assert base < set(mixture) and base < set(control), "둘 다 온음계를 품어야 견줄 수 있다"

    odd_mixture = tuple(i for i, name in enumerate(mixture) if name not in base)
    odd_control = tuple(i for i, name in enumerate(control) if name not in base)

    assert odd_mixture != odd_control, "자리가 같으면 이 판의 질문이 없다"
    assert odd_mixture == (2, 6, 8)
    assert odd_control == (1, 5, 8)


def test_밀지_않은_대조가_배수를_1로_만든다() -> None:
    """**음성 대조의 음성 대조다** (D-0259).

    밀지 않으면 아홉 무게가 교환가능해 두 배치가 같은 법칙이고, **거기서도 차이가
    나오면 기전이 배치가 아니다.**
    """
    from control_corpus import mass_factor

    assert mass_factor(TOOL.FLAT_MASS) == pytest.approx(1.0)
    assert mass_factor(TOOL.REAL_DIATONIC_MASS) > 2.0


def test_판_0에서_코퍼스와_쌍이_다른_흐름이다() -> None:
    """**numpy가 끝의 0을 버린다** (D-0470).

    `default_rng([seed, 0])`은 `default_rng(seed)`와 **같은 흐름**이다. 코퍼스를
    `seed`로 짓고 쌍을 `[seed, trial]`로 뽑고 있었으므로 **판 0에서 둘이 한
    난수열을 나눠 썼다** — 어느 코퍼스가 지어졌나와 어느 쌍이 뽑혔나가 묶인다.

    흐름마다 태그를 다는 것으로 끊었고, **태그가 0이면 같은 병이 돌아온다.**
    """
    import numpy as np

    assert TOOL.STREAM_PAIRS != 0, "태그가 0이면 끝에서 접혀 흐름이 다시 겹친다"

    corpus = np.random.default_rng(80000)
    pairs = np.random.default_rng([80000, TOOL.STREAM_PAIRS, 0])

    assert corpus.random() != pairs.random(), "판 0에서 두 흐름이 아직 같다"
    # **옛 꼴이 실제로 겹쳤다는 것도 건다** — 안 그러면 이 시험이 무엇을 막는지 모른다.
    assert np.random.default_rng(80000).random() == np.random.default_rng([80000, 0]).random()
