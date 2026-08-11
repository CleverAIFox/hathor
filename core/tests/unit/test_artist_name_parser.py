"""아티스트 파서 실측 회귀 테스트 (D-0014).

케이스는 전부 실측 1004곡 / 고유 아티스트 247개에서 나온 실제 태그다.
"""

import pytest

from hathor.domain.entities.parsed_artist import (
    AmbiguityReason,
    ParseConfidence,
    build_normalized_key,
)
from hathor.domain.services.artist_name_parser import parse_artist_field


def test_구분자_없으면_단일_후보_high():
    result = parse_artist_field("볼빨간사춘기")
    assert result.primary.name == "볼빨간사춘기"
    assert result.collaborators == ()
    assert result.confidence is ParseConfidence.HIGH
    assert result.ambiguity_reasons == ()


@pytest.mark.parametrize(
    ("raw", "name", "alias"),
    [
        ("아이유(IU)", "아이유", "IU"),
        ("BIGBANG (빅뱅)", "BIGBANG", "빅뱅"),
        ("백예린(Yerin Baek)", "백예린", "Yerin Baek"),
        ("10CM", "10CM", None),
    ],
)
def test_표기체계가_다른_괄호는_별칭(raw, name, alias):
    result = parse_artist_field(raw)
    assert result.primary.name == name
    assert result.primary.aliases == (() if alias is None else (alias,))
    assert result.confidence is ParseConfidence.HIGH


@pytest.mark.parametrize(
    "raw",
    [
        "전우성(노을)",
        "순순희(지환)",
        "DAY6 (Even of Day)",
        "WSG워너비(4FIRE)",
    ],
)
def test_표기체계가_겹치는_괄호는_소속_의심(raw):
    result = parse_artist_field(raw)
    assert result.confidence is ParseConfidence.LOW
    assert AmbiguityReason.AFFILIATION_SUSPECTED in result.ambiguity_reasons


def test_쉼표_협업은_medium():
    result = parse_artist_field("임재범, 박정현")
    assert result.primary.name == "임재범"
    assert [c.name for c in result.collaborators] == ["박정현"]
    assert result.confidence is ParseConfidence.MEDIUM
    assert AmbiguityReason.COMMA_SEPARATED in result.ambiguity_reasons


def test_괄호는_쉼표로_쪼갠_토큰마다_따로_붙는다():
    result = parse_artist_field("소유 (SOYOU), 권순일(어반자카파)")
    assert result.primary.name == "소유"
    assert result.primary.aliases == ("SOYOU",)
    assert [c.name for c in result.collaborators] == ["권순일"]
    assert result.collaborators[0].aliases == ("어반자카파",)
    assert result.confidence is ParseConfidence.LOW


def test_괄호_안의_쉼표로는_쪼개지_않는다():
    result = parse_artist_field("이유 갓지(GOD G) 않은 이유(박명수, 아이유)")
    assert result.collaborators == ()
    assert AmbiguityReason.COMMA_INSIDE_BRACKET in result.ambiguity_reasons
    assert AmbiguityReason.MULTIPLE_BRACKETS in result.ambiguity_reasons


def test_중첩_괄호는_별칭에_보존된다():
    result = parse_artist_field("미연((여자)아이들)")
    assert result.primary.name == "미연"
    assert result.primary.aliases == ("(여자)아이들",)
    assert AmbiguityReason.NESTED_BRACKET in result.ambiguity_reasons


def test_앰퍼샌드는_쪼개지_않고_신뢰도만_낮춘다():
    result = parse_artist_field("Earth, Wind & Fire")
    assert [c.name for c in result.collaborators] == ["Wind & Fire"]
    assert result.confidence is ParseConfidence.LOW
    assert AmbiguityReason.JOINER_TOKEN in result.ambiguity_reasons


@pytest.mark.parametrize("raw", ["GD X TAEYANG", "Dan + Shay", "GD&TOP"])
def test_결합어_토큰은_low(raw):
    result = parse_artist_field(raw)
    assert result.collaborators == ()
    assert result.confidence is ParseConfidence.LOW
    assert AmbiguityReason.JOINER_TOKEN in result.ambiguity_reasons


@pytest.mark.parametrize("raw", ["MAX", "X-teen", "10CM"])
def test_이름_속_x는_결합어가_아니다(raw):
    assert parse_artist_field(raw).confidence is ParseConfidence.HIGH


def test_빈_문자열():
    result = parse_artist_field("   ")
    assert result.primary.name == ""
    assert result.confidence is ParseConfidence.LOW
    assert result.ambiguity_reasons == (AmbiguityReason.EMPTY_SOURCE,)


def test_normalized_key는_괄호와_공백을_지운다():
    assert build_normalized_key("BIGBANG (빅뱅)") == "bigbang"
    assert parse_artist_field("아이유(IU)").primary.normalized_key == "아이유"
