"""아티스트 표기 파서 (D-0014).

정규화하지 않는다. 후보와 신뢰도만 제시하고 정규명 확정은
유닛 #3 MusicBrainz 조회가 책임진다.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from hathor.domain.entities.parsed_artist import (
    AmbiguityReason,
    ArtistCandidate,
    ParseConfidence,
    ParsedArtist,
)

_OPEN_BRACKETS = "(（"
_CLOSE_BRACKETS = ")）"
_SEPARATORS = ",，"
_AMPERSANDS = "&＆"
_MIN_TOKEN_LENGTH = 2


class _Script(StrEnum):
    """표기 체계. 별칭 병기와 소속 병기를 가르는 신호다."""

    HANGUL = "KO"
    LATIN = "LA"
    DIGIT = "NUM"
    OTHER = "ETC"


def _script_kinds(value: str) -> frozenset[_Script]:
    """문자열에 등장하는 표기 체계 집합."""
    kinds: set[_Script] = set()
    for char in value:
        if not char.isalnum():
            continue
        name = unicodedata.name(char, "")
        if name.startswith("HANGUL"):
            kinds.add(_Script.HANGUL)
        elif name.startswith("LATIN"):
            kinds.add(_Script.LATIN)
        elif char.isdigit():
            kinds.add(_Script.DIGIT)
        else:
            kinds.add(_Script.OTHER)
    return frozenset(kinds)


def _shares_script(left: str, right: str) -> bool:
    """숫자를 뺀 표기 체계가 겹치는지. 겹치면 소속 병기를 의심한다."""
    lhs = _script_kinds(left) - {_Script.DIGIT}
    rhs = _script_kinds(right) - {_Script.DIGIT}
    if not lhs or not rhs:
        return True
    return bool(lhs & rhs)


def _split_top_level(raw: str) -> tuple[list[str], set[AmbiguityReason]]:
    """괄호 깊이 0인 구분자에서만 분리한다."""
    reasons: set[AmbiguityReason] = set()
    tokens: list[str] = []
    buffer: list[str] = []
    depth = 0
    for char in raw:
        if char in _OPEN_BRACKETS:
            depth += 1
            if depth > 1:
                reasons.add(AmbiguityReason.NESTED_BRACKET)
        elif char in _CLOSE_BRACKETS:
            if depth == 0:
                reasons.add(AmbiguityReason.UNBALANCED_BRACKET)
            depth = max(depth - 1, 0)
        elif depth == 0 and char in _SEPARATORS:
            tokens.append("".join(buffer))
            buffer = []
            continue
        elif depth > 0 and char in _SEPARATORS:
            reasons.add(AmbiguityReason.COMMA_INSIDE_BRACKET)
        buffer.append(char)
    if depth > 0:
        reasons.add(AmbiguityReason.UNBALANCED_BRACKET)
    tokens.append("".join(buffer))
    return [token.strip() for token in tokens if token.strip()], reasons


def _extract_brackets(token: str) -> tuple[str, list[str], set[AmbiguityReason]]:
    """토큰에서 최상위 괄호 구간을 떼어 별칭 후보로 넘긴다."""
    reasons: set[AmbiguityReason] = set()
    outer: list[str] = []
    inner: list[str] = []
    spans: list[str] = []
    depth = 0
    for char in token:
        if char in _OPEN_BRACKETS:
            depth += 1
            if depth > 1:
                inner.append(char)
            continue
        if char in _CLOSE_BRACKETS and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append("".join(inner).strip())
                inner = []
            else:
                inner.append(char)
            continue
        if depth > 0:
            inner.append(char)
        else:
            outer.append(char)
    if inner:
        spans.append("".join(inner).strip())
    if len(spans) > 1:
        reasons.add(AmbiguityReason.MULTIPLE_BRACKETS)
    return "".join(outer).strip(), [s for s in spans if s], reasons


def _grade_token(name: str, aliases: list[str]) -> tuple[ParseConfidence, set[AmbiguityReason]]:
    """토큰 하나의 신뢰도. 하락 사유가 하나라도 있으면 LOW로 내린다."""
    reasons: set[AmbiguityReason] = set()
    if len(name.replace(" ", "")) < _MIN_TOKEN_LENGTH:
        reasons.add(AmbiguityReason.SHORT_TOKEN)
    if any(char in _AMPERSANDS for char in name):
        reasons.add(AmbiguityReason.AMPERSAND_ONLY)
    if any(_shares_script(name, alias) for alias in aliases):
        reasons.add(AmbiguityReason.AFFILIATION_SUSPECTED)
    if reasons:
        return ParseConfidence.LOW, reasons
    return ParseConfidence.HIGH, reasons


def parse_artist_field(raw: str) -> ParsedArtist:
    """아티스트 태그 한 건을 후보와 신뢰도로 분해한다 (D-0014)."""
    source = raw.strip()
    if not source:
        return ParsedArtist(
            raw=raw,
            primary=ArtistCandidate(name=""),
            collaborators=(),
            confidence=ParseConfidence.LOW,
            ambiguity_reasons=(AmbiguityReason.EMPTY_SOURCE,),
        )

    tokens, reasons = _split_top_level(source)
    if not tokens:
        tokens = [source]

    candidates: list[ArtistCandidate] = []
    grades: list[ParseConfidence] = []
    for token in tokens:
        name, aliases, bracket_reasons = _extract_brackets(token)
        reasons |= bracket_reasons
        if not name:
            name, aliases = token, []
        grade, token_reasons = _grade_token(name, aliases)
        reasons |= token_reasons
        grades.append(grade)
        candidates.append(
            ArtistCandidate(name=name, aliases=tuple(aliases)),
        )

    confidence = min(grades)
    if len(candidates) > 1:
        reasons.add(AmbiguityReason.COMMA_SEPARATED)
        confidence = min(confidence, ParseConfidence.MEDIUM)

    return ParsedArtist(
        raw=raw,
        primary=candidates[0],
        collaborators=tuple(candidates[1:]),
        confidence=confidence,
        ambiguity_reasons=tuple(sorted(reasons)),
    )
