"""제목 부가 표기 제거 테스트 (D-0019, O-3).

케이스는 전부 실측 1004곡에서 나온 실제 제목이다.
"""

import pytest

from hathor.domain.services.title_annotation import strip_annotations


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("서울의 잠 못 이루는 밤 (Feat. 이수현)", "서울의 잠 못 이루는 밤"),
        ("니가 참 좋아 (Prod. by 박근태)", "니가 참 좋아"),
        ("사랑이 잘 (With 오혁)", "사랑이 잘"),
        ("잠시만 안녕 (Original)", "잠시만 안녕"),
    ],
)
def test_참여자_제작_표기를_뗀다(raw, expected):
    assert strip_annotations(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("잠 못드는 밤 (Feat. 펀치(Punch))", "잠 못드는 밤"),
        ("나비와 고양이 (Feat. 백현 (BAEKHYUN))", "나비와 고양이"),
        ("서커스 (Feat. 임유경(달래음악단), $howgun)", "서커스"),
    ],
)
def test_중첩_괄호에서_닫는_괄호가_남지_않는다(raw, expected):
    # 정규식 [^)）]* 방식은 여기서 ')'를 남긴다
    assert strip_annotations(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["아파 (Slow)", "무제(無題) (Untitled, 2014)", "뱅뱅뱅 (BANG BANG BANG)"],
)
def test_곡명_일부인_괄호는_보존한다(raw):
    assert strip_annotations(raw) == raw


def test_버전_표기는_보존한다():
    # 리마스터·라이브·한국어판이 MB에 별도 레코딩으로 등재돼 있다
    assert strip_annotations("Voice Mail (Korean Ver.)") == "Voice Mail (Korean Ver.)"


def test_빈_제목():
    assert strip_annotations("   ") == ""
