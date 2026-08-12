"""곡 제목의 부가 표기 제거 (D-0019, O-3).

D-0010은 아티스트 필드에 feat.가 0건이라 했으나 실제로는 제목 필드로
옮겨가 있다. 제거하지 않으면 MB 조회가 실패한다.

정규식으로는 안 된다. `(Feat. 펀치(Punch))`처럼 중첩되므로
`[^)）]*` 방식은 닫는 괄호를 남긴다. 괄호 깊이를 세야 한다.
"""

from __future__ import annotations

import re

_ANNOTATION_HEAD = re.compile(
    r"^\s*(feat|ft|with|prod|inst|duet|vocal|remix|album version|original|bonus track)\b",
    re.IGNORECASE,
)
_OPEN = "(（"
_CLOSE = ")）"


def strip_annotations(title: str) -> str:
    """참여자·제작 표기를 뗀다. 곡명 일부와 버전 표기는 보존한다.

    `아파 (Slow)` `무제(無題)`는 곡명의 일부이고 `(Korean Ver.)`는
    레코딩을 구분하는 단서이므로 남긴다. 버전을 지우면 리마스터·라이브가
    한 곡으로 뭉개진다.
    """
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in title:
        if char in _OPEN:
            depth += 1
            if depth == 1:
                buf = []
                continue
        if char in _CLOSE and depth > 0:
            depth -= 1
            if depth == 0:
                inner = "".join(buf)
                if not _ANNOTATION_HEAD.match(inner):
                    out.append(f"({inner})")
                continue
        (buf if depth > 0 else out).append(char)
    return "".join(out).strip()
