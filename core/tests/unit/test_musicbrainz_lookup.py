"""MusicBrainz 조회 구현 테스트 (D-0019).

네트워크를 타지 않는다. 클라이언트는 가짜를 주입한다.
"""

from typing import Any

from hathor.domain.entities.parsed_artist import ArtistCandidate
from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.infrastructure.musicbrainz_lookup import (
    MusicBrainzLookup,
    judge_hits,
)


class FakeClient:
    """search 호출을 기록하고 미리 정한 결과를 돌려준다."""

    def __init__(self, hits: list[dict[str, Any]]) -> None:
        self._hits = hits
        self.calls: list[tuple[str, str]] = []

    def search(self, entity: str, query: str, limit: int = 2) -> list[dict[str, Any]]:
        self.calls.append((entity, query))
        return self._hits


def test_결과가_없으면_unresolved():
    assert judge_hits([])[0] is ResolutionState.UNRESOLVED


def test_격차가_크면_resolved():
    hits = [{"score": 100}, {"score": 71}]
    assert judge_hits(hits)[0] is ResolutionState.RESOLVED


def test_격차가_좁으면_ambiguous():
    # 실측: Dan + Shay 100 vs Justin Bieber 99
    hits = [{"score": 100}, {"score": 99}]
    assert judge_hits(hits)[0] is ResolutionState.AMBIGUOUS


def test_점수가_낮으면_unresolved():
    assert judge_hits([{"score": 62}])[0] is ResolutionState.UNRESOLVED


def test_아티스트_조회는_normalized_key로_캐시한다():
    client = FakeClient([{"score": 100, "name": "IU", "id": "mbid-iu"}])
    lookup = MusicBrainzLookup(client)  # type: ignore[arg-type]

    first = lookup.resolve_artist(ArtistCandidate("아이유"))
    second = lookup.resolve_artist(ArtistCandidate("아이유"))

    assert first.canonical_name == "IU"
    assert second is first
    assert len(client.calls) == 1


def test_괄호_표기가_달라도_같은_캐시를_쓴다():
    # 소유 (SOYOU)와 소유(SOYOU)는 normalized_key가 같다 (D-0014)
    client = FakeClient([{"score": 100, "name": "SOYOU", "id": "mbid-soyou"}])
    lookup = MusicBrainzLookup(client)  # type: ignore[arg-type]

    lookup.resolve_artist(ArtistCandidate("소유", ("SOYOU",)))
    lookup.resolve_artist(ArtistCandidate("소 유", ("SOYOU",)))

    assert len(client.calls) == 1


def test_ambiguous면_recording_mbid를_채우지_않는다():
    # 확정되지 않은 매칭에 MBID를 넣으면 상태 구분이 무의미해진다
    client = FakeClient([{"score": 100, "title": "좋은 날", "id": "x"}, {"score": 99}])
    lookup = MusicBrainzLookup(client)  # type: ignore[arg-type]

    result = lookup.resolve_recording("a.mp3", "좋은 날", "IU")

    assert result.state is ResolutionState.AMBIGUOUS
    assert result.recording_mbid is None
    assert result.identity == "a.mp3"


def test_resolved면_mbid가_정규_식별자가_된다():
    client = FakeClient([{"score": 100, "title": "좋은 날", "id": "mbid-1"}])
    lookup = MusicBrainzLookup(client)  # type: ignore[arg-type]

    result = lookup.resolve_recording("a.mp3", "좋은 날", "IU")

    assert result.recording_mbid == "mbid-1"
    assert result.identity == "mbid-1"
