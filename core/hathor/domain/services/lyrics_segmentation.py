"""가사를 구간으로 나눈다. 순수 함수다.

곡 하나를 벡터 하나로 만들면 M0(자기일관성)를 잴 수 없다. 오디오 경로가
10초 청크로 나눠 홀·짝이 서로를 찾는지 보는 것과 같은 구조가 필요하므로
가사도 구간으로 나눈다.

**빈 줄을 우선한다.** USLT 가사는 절·후렴 사이에 빈 줄이 있는 경우가 많고,
그 경계는 사람이 넣은 것이라 임의 분할보다 낫다. 빈 줄이 없으면 줄 수로 자른다.
"""

from __future__ import annotations

import re
import unicodedata

MIN_SEGMENT_CHARS = 8
"""이보다 짧은 구간은 버린다. `(간주)` 같은 표기가 구간 하나를 차지하면 안 된다."""

FALLBACK_LINES = 4
"""빈 줄이 없을 때 몇 줄씩 묶을지. 한국어 가사 한 절이 대략 이 정도다."""

MIN_SEGMENTS = 2
"""M0는 홀·짝으로 나누므로 최소 두 구간이 필요하다."""

BLANK_LINE = re.compile(r"\n\s*\n")
BRACKETED = re.compile(r"^[\[\(<].*[\]\)>]$")


def normalize_lyrics(raw: str) -> str:
    """NFC 정규화와 줄바꿈 통일. 내용은 손대지 않는다."""
    text = unicodedata.normalize("NFC", raw)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_segments(raw: str | None) -> list[str]:
    """가사를 구간 목록으로 나눈다. 나눌 수 없으면 빈 목록이다.

    대괄호·괄호만으로 이루어진 줄(`[Verse 1]`, `(간주)`)은 버린다. 구조 표기이지
    가사가 아니며, 그대로 두면 서로 다른 곡이 그 표기 때문에 비슷해진다.
    """
    if not raw or not raw.strip():
        return []

    text = normalize_lyrics(raw)
    blocks = [block for block in BLANK_LINE.split(text) if block.strip()]
    if len(blocks) < MIN_SEGMENTS:
        blocks = _group_lines(text)

    segments = [cleaned for block in blocks if (cleaned := _clean(block))]
    return segments if len(segments) >= MIN_SEGMENTS else []


def _group_lines(text: str) -> list[str]:
    lines = [line for line in text.split("\n") if line.strip()]
    return [
        "\n".join(lines[start : start + FALLBACK_LINES])
        for start in range(0, len(lines), FALLBACK_LINES)
    ]


def _clean(block: str) -> str:
    lines = [
        line.strip()
        for line in block.split("\n")
        if line.strip() and not BRACKETED.match(line.strip())
    ]
    joined = " ".join(lines).strip()
    return joined if len(joined) >= MIN_SEGMENT_CHARS else ""
