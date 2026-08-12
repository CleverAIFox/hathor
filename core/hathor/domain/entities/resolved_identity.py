"""외부 조회로 확정한 정규 신원 (D-0017 · D-0019).

파서(유닛 #2)가 제시한 후보를 MusicBrainz 조회로 확정한 결과다.
정규화 기준은 Recording MBID 확보이며 ISRC는 조회 보조 키로만 쓴다.
실측상 ISRC 태그 보유율이 0%이므로 판정 조건이 될 수 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResolutionState(StrEnum):
    """정규화 상태. 참거짓으로는 재조회 대상을 구분할 수 없다.

    UNRESOLVED와 PENDING을 나누는 이유는 재조회 판단 때문이다.
    미등재 곡은 다시 조회해도 결과가 같으므로 반복하면 낭비다.
    """

    PENDING = "pending"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ResolvedArtist:
    """1단계 아티스트 조회 결과.

    canonical_name은 MB 정규명이며 태그 표기와 다를 수 있다
    (아이유 -> IU, 엠씨더맥스 -> M.C the MAX).
    2단계 곡 조회는 태그 표기가 아니라 이 값을 써야 한다 (D-0019).

    AMBIGUOUS인 후보의 canonical_name은 신뢰할 수 없으므로
    2단계에서 치환에 사용하지 않는다. 오답이 곡 조회로 전파된다.
    """

    query_key: str
    state: ResolutionState
    canonical_name: str | None = None
    mbid: str | None = None
    top_score: int = 0
    runner_up_score: int = 0

    @property
    def is_usable_for_lookup(self) -> bool:
        """2단계 조회에서 정규명으로 치환해도 되는지."""
        return self.state is ResolutionState.RESOLVED and bool(self.canonical_name)


@dataclass(frozen=True, slots=True)
class ResolvedRecording:
    """2단계 곡 조회 결과. 정규 신원의 최종 형태다.

    D-0017에서 폐기한 Track을 대신한다. Track은 ISRC 존재로 정규화를
    판정했으나 ISRC는 이 조회의 산출물이지 입력이 아니었다.

    실측 성공률은 78.5%다 (D-0019). 나머지는 MB 미등재이거나 크레딧
    표기가 어긋나는 경우이며, 이때는 파서의 normalized_key를 폴백
    식별자로 쓴다. 폴백은 라이브러리 내부에서만 유효하다.
    """

    source_key: str
    state: ResolutionState
    recording_mbid: str | None = None
    canonical_title: str | None = None
    artist_mbids: tuple[str, ...] = ()
    isrc: str | None = None
    fallback_key: str | None = None

    @property
    def identity(self) -> str:
        """정규 식별자. 미확정이면 폴백 키를 쓴다."""
        if self.recording_mbid:
            return self.recording_mbid
        return self.fallback_key or self.source_key
