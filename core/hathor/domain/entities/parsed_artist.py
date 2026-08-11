"""아티스트 표기 파싱 결과 엔티티 (D-0014)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class ParseConfidence(IntEnum):
    """파싱 신뢰도. 값이 낮을수록 불확실하다."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2


class AmbiguityReason(StrEnum):
    """신뢰도를 떨어뜨린 사유. 유닛 #3 조회 전략의 입력이다."""

    COMMA_SEPARATED = "comma_separated"
    AMPERSAND_ONLY = "ampersand_only"
    SHORT_TOKEN = "short_token"
    AFFILIATION_SUSPECTED = "affiliation_suspected"
    NESTED_BRACKET = "nested_bracket"
    MULTIPLE_BRACKETS = "multiple_brackets"
    COMMA_INSIDE_BRACKET = "comma_inside_bracket"
    UNBALANCED_BRACKET = "unbalanced_bracket"
    EMPTY_SOURCE = "empty_source"


_BRACKET_SPAN = re.compile(r"[(（][^)）]*[)）]")
_WHITESPACE = re.compile(r"\s+")


def build_normalized_key(value: str) -> str:
    """괄호 구간 제거 + 공백 제거 + 소문자 (D-0014)."""
    stripped = _BRACKET_SPAN.sub("", value)
    return _WHITESPACE.sub("", stripped).lower()


@dataclass(frozen=True, slots=True)
class ArtistCandidate:
    """단일 아티스트 표기 후보. 정규명 확정은 유닛 #3 책임이다."""

    name: str
    aliases: tuple[str, ...] = ()

    @property
    def normalized_key(self) -> str:
        return build_normalized_key(self.name)


@dataclass(frozen=True, slots=True)
class ParsedArtist:
    """아티스트 태그 한 건의 파싱 결과."""

    raw: str
    primary: ArtistCandidate
    collaborators: tuple[ArtistCandidate, ...]
    confidence: ParseConfidence
    ambiguity_reasons: tuple[AmbiguityReason, ...]

    @property
    def normalized_key(self) -> str:
        return build_normalized_key(self.raw)

    @property
    def candidates(self) -> tuple[ArtistCandidate, ...]:
        return (self.primary, *self.collaborators)
