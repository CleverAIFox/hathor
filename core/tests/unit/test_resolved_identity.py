"""정규 신원 엔티티 테스트 (D-0017 · D-0019)."""

from hathor.domain.entities.resolved_identity import (
    ResolutionState,
    ResolvedArtist,
    ResolvedRecording,
)


def test_resolved_아티스트만_정규명_치환에_쓴다():
    ok = ResolvedArtist("아이유", ResolutionState.RESOLVED, canonical_name="IU")
    assert ok.is_usable_for_lookup is True


def test_ambiguous는_정규명이_있어도_쓰지_않는다():
    # 오답이 곡 조회로 전파되는 것을 막는다 (효린 -> Hyolyn 4곡 전량 실패)
    bad = ResolvedArtist("이준", ResolutionState.AMBIGUOUS, canonical_name="이준")
    assert bad.is_usable_for_lookup is False


def test_정규명이_없으면_쓰지_않는다():
    empty = ResolvedArtist("전혜성", ResolutionState.UNRESOLVED)
    assert empty.is_usable_for_lookup is False


def test_mbid가_있으면_정규_식별자로_쓴다():
    rec = ResolvedRecording(
        "a.mp3", ResolutionState.RESOLVED, recording_mbid="mbid-1", fallback_key="아이유"
    )
    assert rec.identity == "mbid-1"


def test_mbid가_없으면_폴백_키를_쓴다():
    rec = ResolvedRecording("a.mp3", ResolutionState.UNRESOLVED, fallback_key="전혜성")
    assert rec.identity == "전혜성"


def test_폴백_키도_없으면_source_key를_쓴다():
    rec = ResolvedRecording("a.mp3", ResolutionState.PENDING)
    assert rec.identity == "a.mp3"
