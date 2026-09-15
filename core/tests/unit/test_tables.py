"""명령들이 공유하는 표 조각 (D-0127 · D-0185 · D-0191)."""

from __future__ import annotations

import numpy as np

from hathor.interfaces.cli.tables import _display_width, ambiguity_report, render_table


def _report(modes, ambiguous, relative, floor=0.30, tunings=()):
    return "\n".join(
        ambiguity_report(
            modes=modes,
            ambiguous=np.asarray(ambiguous, dtype=bool),
            relative=relative,
            floor=floor,
            tunings=tunings,
        )
    )


def test_선법마다_따로_낸다():
    """**장단이 갈리는 것이 O-54의 전부다** (D-0185)."""
    text = _report(["major"] * 4 + ["minor"] * 4, [0, 0, 0, 1, 1, 1, 1, 0], [False] * 8)
    assert "major" in text and "minor" in text
    assert "25.0%" in text and "75.0%" in text


def test_바닥은_하나다():
    """`random_baseline`은 무작위 크로마이며 **선법을 안 낸다** (D-0185).

    전체 바닥을 부분집합에 갖다 대는 것과 다르다 — D-0182에서 그렇게 틀렸다.
    """
    text = _report(["major", "minor"], [1, 0], [False, False], floor=0.321)
    assert text.count("32.1%") >= 2


def test_애매한_곡_안에서_잰다():
    """**분모가 애매한 곡이다** (D-0057). 전체 대비로 재면 희석된다."""
    text = _report(
        ["major"] * 4,
        [1, 1, 0, 0],
        [True, False, True, True],
        floor=0.3,
    )
    # 나란한조 3/4 = 75.0% · 애매 안에서는 1/2 = 50.0%
    assert "75.0%" in text and "50.0%" in text


def test_조율이_0센트여도_센다():
    """**`if tunings`로 거르지 않는다.** 0.0이 거짓이라 통째로 빠진다 (D-0057)."""
    text = _report(["major"], [0], [False], tunings=[0.0, 0.0])
    assert "조율 편차" in text


def test_조율이_없으면_안_적는다():
    assert "조율 편차" not in _report(["major"], [0], [False])


def test_읽는_법이_끝에_붙는다():
    """**맞다는 증명이 아니라 틀렸다는 신호를 잡는 장치다** (O-22(닫힘 D-0201))."""
    assert _report(["major"], [0], [False]).rstrip().endswith("(O-22(닫힘 D-0201)).**")


def test_한글_머리글이_값과_어긋나지_않는다():
    """**한글은 터미널에서 두 칸이다** (D-0200).

    `len()`으로 채우면 `강도`(2글자·4칸)가 폭 6을 4칸만 먹은 것으로 계산돼
    머리글이 값 위로 밀려 붙는다. D-0092가 *"머리글과 값은 갈릴 수 없다"*고
    적고 **같은 명세에서 그리게 했는데 표시폭이 달라 여전히 어긋났다.**
    """
    lines = render_table((("강도", ">8.1f"), ("선법", ">9")), [(0.0, "major")])

    assert _display_width(lines[0]) == 17
    assert _display_width(lines[2]) == 17
    assert len(lines[1]) == 17


def test_구분선이_표와_같은_길이다():
    """`len(header.encode("utf-8"))`은 한글을 **세 배**로 셌다."""
    lines = render_table((("무작위바닥", ">13.1%"), ("나란한조", ">11.1%")), [(0.35, 0.2)])

    assert len(lines[1]) == _display_width(lines[0])


def test_부호와_소수점이_있는_형식도_읽는다():
    """`>+10.4f` 같은 명세를 정렬·폭·나머지로 가른다."""
    lines = render_table((("차이", ">+10.4f"),), [(-0.5,)])

    assert lines[2].strip() == "-0.5000"
    assert len(lines[2]) == 10
