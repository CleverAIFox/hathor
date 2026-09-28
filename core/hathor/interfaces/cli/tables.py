"""CLI 표 그리기. **머리글과 값을 같은 열 명세 하나에서 그린다** (D-0092 · D-0127).

`main.py`에서 내려왔다. `eval` 계열 다섯 명령이 쓰는데 진입점 파일에 있어,
그 파일을 쪼개려 할 때마다 **모두가 의존하는 조각이 가운데 박혀 있었다** (D-0127).

조성 파싱도 여기 있다. **둘 다 명령에 딸린 것이 아니라 명령들이 공유하는 조각이다.**
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from hathor.application.key_distribution import OFF_CENTS, Ambiguity
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
    parsed = [_parse_spec(spec) for _, spec in columns]
    header = "".join(
        _pad(name, align, width)
        for (name, _), (align, width, _) in zip(columns, parsed, strict=True)
    )
    lines = [header, "-" * _display_width(header)]
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"열 수가 머리글과 다르다: {len(row)} vs {len(columns)}")
        lines.append(
            "".join(
                _pad(format(value, rest), align, width)
                for value, (align, width, rest) in zip(row, parsed, strict=True)
            )
        )
    return lines


SPEC = re.compile(r"^([<>^])?([+\- ])?(\d*)((?:\.\d+)?[a-zA-Z%]?)$")
"""`>+10.4f`를 정렬·폭·나머지로 가른다. 폭은 우리가 채우므로 형식에서 뺀다."""


def _display_width(text: str) -> int:
    """**터미널이 차지하는 칸 수다.** 한글은 한 글자가 두 칸이다 (D-0200).

    `len()`으로 채우면 `강도`(2글자·4칸)가 폭 6을 4칸만 먹은 것으로 계산돼
    **머리글이 값 위로 밀려 붙는다.** 구분선은 더 나빴다 — `len(...encode("utf-8"))`
    은 한글을 **세 배**로 세어 표보다 한참 길었다.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _parse_spec(spec: str) -> tuple[str, int, str]:
    found = SPEC.match(spec)
    if found is None:
        raise ValueError(f"읽을 수 없는 열 형식이다: {spec!r}")
    align, sign, digits, rest = found.groups()
    return align or ">", int(digits) if digits else 10, (sign or "") + (rest or "")


def _pad(text: str, align: str, width: int) -> str:
    gap = max(0, width - _display_width(text))
    if align == "<":
        return text + " " * gap
    if align == "^":
        return " " * (gap // 2) + text + " " * (gap - gap // 2)
    return " " * gap + text


def ambiguity_report(found: Ambiguity) -> list[str]:
    """조성 애매함 보고 (O-22(닫힘 D-0201) · O-54 · D-0185).

    `--eda`가 크로마 상한을 **장조 0.6626 · 단조 0.3409**로 봤다. 조성 라벨이 나온 바로 그
    자료가 반토막이므로, **애매함이 단조에 몰려 있는지**가 그 원인을 가른다.

    **수는 안 만든다** (D-0280). 여기 `numpy`로 마스크를 세고 있었고 표시 계층이 계산하는
    자리였다 — 분모를 틀린 자리가 둘(D-0057 · D-0182)이었고 그때는 **출력 문자열로만**
    확인할 수 있었다. 이제 `application/key_distribution`이 수를 내고 시험이 그것을 직접 본다.
    """
    lines = [
        f"\n애매({KEY_MARGIN_FLOOR} 미만)  코퍼스 {found.ambiguous_share:.1%}"
        f"  무작위 {found.floor:.1%}",
        f"2등이 나란한조 — 전체 대비          {found.relative_share:.1%}",
    ]
    if found.relative_in_ambiguous is not None:
        count, share = found.relative_in_ambiguous
        lines.append(
            f"2등이 나란한조 — 애매한 곡 안에서   {share:.1%}  ({count}/{found.ambiguous})"
        )
    lines.append(f"\n선법마다 (O-54) · 무작위 바닥은 {found.floor:.1%} 하나다")
    for mode in found.modes:
        inside = mode.relative_in_ambiguous
        held = f"{inside:>6.1%}" if inside is not None else "     -"
        lines.append(
            f"  {mode.name:<8}{mode.count:>5}곡  애매 {mode.ambiguous:>6.1%}"
            f"  나란한조 {mode.relative:>6.1%}  애매 안에서 {held}"
        )
    lines.append("  **무작위 바닥에 붙으면 그 선법에서는 격차가 판별을 못 한다**")

    if found.tuning is not None:
        tuning = found.tuning
        lines.append(
            f"\n조율 편차  중앙값 {tuning.median_cents:+.1f}센트 · "
            f"|편차|>{OFF_CENTS:g}센트 {tuning.off_count}곡 ({tuning.off_share:.1%})"
        )

    lines += [
        "\n--- 읽는 법 ---",
        "상관·격차가 무작위와 비슷하면 그 지표는 판별력이 없다. 절대값에 속지 않는다.",
        "2등이 나란한조인 비율이 높으면 애매함은 K-S의 원리적 한계다 (고칠 수 없다).",
        "낮으면 크로마 추출이나 프로파일 쪽 문제이므로 고칠 여지가 있다.",
        "**맞다는 증명은 아니다. 틀렸다는 신호를 잡는 장치다 (O-22(닫힘 D-0201)).**",
    ]
    return lines


REPLAY_HONOURS = ("--harmonic", "--profile")
"""`--replay`가 실제로 거는 손잡이 (D-0191)."""


REPLAY_DEFAULTS = (
    ("--gamma", "gamma", 0.0),
    ("--aggregate", "aggregate", "mean"),
    ("--window-seconds", "window_seconds", 10.0),
    ("--chroma", "chroma", "cq"),
    ("--tuning", "tuning", False),
    ("--separate", "separate", False),
    ("--halves", "halves", False),
    ("--series", "series", None),
)
"""`--replay`가 못 쓰는 손잡이와 그 기본값 (D-0191)."""


def replay_refusal(args: object) -> str:
    """`--replay`가 못 쓰는 손잡이를 쓴 경우의 한 줄. 없으면 빈 문자열이다.

    저장된 크로마에서 다시 재므로 `REPLAY_HONOURS` 둘만 걸린다. `--gamma`는 추출
    경로에만 배선돼 있었고 `--aggregate`는 창별 중앙값이라 **크로마가 이미 계산된
    뒤에는 원리적으로 못 쓴다.**

    **조용히 무시하면 *"효과가 없다"*로 읽힌다** — 실제로 그렇게 읽을 뻔했다.
    `--gamma 0.5`와 `--aggregate median`이 기본값과 **소수점까지 같은 표**를 냈다.
    D-0164가 두 번 당한 부류이며 거기서는 산출물이 섞였고 여기서는 손잡이가 죽었다.
    """
    used = [
        flag for flag, name, default in REPLAY_DEFAULTS if getattr(args, name, default) != default
    ]
    if not used:
        return ""
    return (
        f"--replay는 {' · '.join(used)}를 못 쓴다. "
        f"저장된 크로마에서 재판정하므로 {' · '.join(REPLAY_HONOURS)}만 걸린다."
    )
