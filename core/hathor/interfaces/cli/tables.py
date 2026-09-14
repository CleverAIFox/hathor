"""CLI 표 그리기. **머리글과 값을 같은 열 명세 하나에서 그린다** (D-0092 · D-0127).

`main.py`에서 내려왔다. `eval` 계열 다섯 명령이 쓰는데 진입점 파일에 있어,
그 파일을 쪼개려 할 때마다 **모두가 의존하는 조각이 가운데 박혀 있었다** (D-0127).

조성 파싱도 여기 있다. **둘 다 명령에 딸린 것이 아니라 명령들이 공유하는 조각이다.**
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.key_estimation import KEY_MARGIN_FLOOR

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hathor.domain.value_objects.key import Key


def parse_key(text: str) -> Key:
    """`"C major"` 같은 문자열을 조성으로 바꾼다."""
    from hathor.domain.value_objects.key import PITCH_CLASSES, Key, Mode

    parts = text.strip().rsplit(" ", 1)
    if len(parts) != 2 or parts[0] not in PITCH_CLASSES:
        raise SystemExit(f'--key는 "C major" 형식이어야 한다: {text}')
    try:
        mode = Mode(parts[1].lower())
    except ValueError:
        raise SystemExit(f"--key의 선법은 major 또는 minor여야 한다: {parts[1]}") from None
    return Key(tonic=parts[0], mode=mode)


def render_table(columns: Sequence[tuple[str, str]], rows: Sequence[Sequence[object]]) -> list[str]:
    """머리글과 값을 **같은 열 명세 하나에서** 그린다 (D-0092).

    `columns`는 `(이름, 형식)` 목록이다. 형식은 `>10.4f` 같은 형식 명세이며 폭을
    포함한다. 머리글은 같은 폭으로 정렬한다.

    **머리글 문자열과 행 문자열을 따로 쓰다가 한쪽만 고쳐 이름표와 값이 어긋났다.**
    실제로 `eval chromatic-origin`이 그 상태로 실측을 한 번 냈다 — 값은 옳았고
    이름표가 두 칸 밀려 있었다. **여기서는 갈릴 수 없다.**
    """
    for name, _ in columns:
        # **공백이 들어가면 표를 다시 읽을 수 없다.** 검사도 사람도 못 읽는다.
        if any(ch.isspace() for ch in name):
            raise ValueError(f"열 이름에 공백을 넣지 않는다: {name!r}")
    widths: list[int] = []
    for _, spec in columns:
        digits = "".join(ch for ch in spec.split(".")[0] if ch.isdigit())
        widths.append(int(digits) if digits else 10)
    aligns = [spec[0] if spec[:1] in "<>^" else ">" for _, spec in columns]
    header = "".join(
        f"{name:{align}{width}}"
        for (name, _), align, width in zip(columns, aligns, widths, strict=True)
    )
    lines = [header, "-" * len(header.encode("utf-8"))]
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"열 수가 머리글과 다르다: {len(row)} vs {len(columns)}")
        lines.append(
            "".join(f"{value:{spec}}" for value, (_, spec) in zip(row, columns, strict=True))
        )
    return lines


def ambiguity_report(
    *,
    modes: Sequence[str],
    ambiguous: np.ndarray,
    relative: Sequence[bool],
    floor: float,
    tunings: Sequence[float],
) -> list[str]:
    """조성 애매함 보고의 뒷부분 (O-22 · O-54 · D-0185).

    `--eda`가 크로마 상한을 **장조 0.6626 · 단조 0.3409**로 봤다. 조성 라벨이
    나온 바로 그 자료가 반토막이므로, **애매함이 단조에 몰려 있는지**가 그 원인을
    가른다.

    **바닥은 하나다.** `random_baseline`은 무작위 크로마 2000개이며 곡과 짝이 없고
    어느 선법인지도 안 낸다 — 선법별로 가를 수 없으므로 둘 다 같은 값과 견준다.
    **전체 바닥을 부분집합에 갖다 대는 것과는 다르다** (D-0182에서 그렇게 틀렸다).

    **`main.py`에 안 넣는다.** 래칫이 2902줄에서 막았고 그 파일은 이미 빚이다 —
    *"되돌리거나 쪼갠다"*를 따랐다 (D-0185).
    """
    kinds = np.asarray(modes)
    flags = np.asarray(ambiguous, dtype=bool)
    near = np.asarray(relative, dtype=bool)
    total, held_all = len(kinds), int(flags.sum())
    lines = [
        f"\n애매({KEY_MARGIN_FLOOR} 미만)  코퍼스 {held_all / total:.1%}  무작위 {floor:.1%}",
        f"2등이 나란한조 — 전체 대비          {float(near.mean()):.1%}",
    ]
    # **애매함의 원인은 애매한 곡 안에서 재야 한다** (D-0057). 전체 대비로 재면
    # 확신도 높은 곡의 2등까지 섞여 희석된다 — 분모가 틀린 지표였다.
    if held_all:
        share = float(near[flags].mean())
        lines.append(
            f"2등이 나란한조 — 애매한 곡 안에서   {share:.1%}"
            f"  ({int(near[flags].sum())}/{held_all})"
        )
    lines.append(f"\n선법마다 (O-54) · 무작위 바닥은 {floor:.1%} 하나다")
    for name in ("major", "minor"):
        picked = kinds == name
        count = int(picked.sum())
        if not count:
            continue
        inside = near[picked & flags]
        held = f"{float(inside.mean()):>6.1%}" if inside.size else "     -"
        lines.append(
            f"  {name:<8}{count:>5}곡  애매 {float(flags[picked].mean()):>6.1%}"
            f"  나란한조 {float(near[picked].mean()):>6.1%}  애매 안에서 {held}"
        )
    lines.append("  **무작위 바닥에 붙으면 그 선법에서는 격차가 판별을 못 한다**")

    # **`if tunings`로 거르지 않는다.** 0.0이 거짓이라 정확히 0센트인 곡이 통째로
    # 빠진다 — D-0057에서 분모 오류를 적어놓고 같은 세션에 또 냈다.
    if len(tunings):
        cents = np.asarray(tunings, dtype=float)
        off = int((np.abs(cents) > 10).sum())
        lines.append(
            f"\n조율 편차  중앙값 {float(np.median(cents)):+.1f}센트 · "
            f"|편차|>10센트 {off}곡 ({off / len(cents):.1%})"
        )

    lines += [
        "\n--- 읽는 법 ---",
        "상관·격차가 무작위와 비슷하면 그 지표는 판별력이 없다. 절대값에 속지 않는다.",
        "2등이 나란한조인 비율이 높으면 애매함은 K-S의 원리적 한계다 (고칠 수 없다).",
        "낮으면 크로마 추출이나 프로파일 쪽 문제이므로 고칠 여지가 있다.",
        "**맞다는 증명은 아니다. 틀렸다는 신호를 잡는 장치다 (O-22).**",
    ]
    return lines
