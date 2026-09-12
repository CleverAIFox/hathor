"""CLI 표 그리기. **머리글과 값을 같은 열 명세 하나에서 그린다** (D-0092 · D-0127).

`main.py`에서 내려왔다. `eval` 계열 다섯 명령이 쓰는데 진입점 파일에 있어,
그 파일을 쪼개려 할 때마다 **모두가 의존하는 조각이 가운데 박혀 있었다** (D-0127).

조성 파싱도 여기 있다. **둘 다 명령에 딸린 것이 아니라 명령들이 공유하는 조각이다.**
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
