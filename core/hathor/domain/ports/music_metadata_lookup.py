"""외부 음악 메타데이터 조회 포트. 구현은 infrastructure가 담당한다 (DIP).

D-0019에 따라 조회는 2단계다. 아티스트를 먼저 확정해 정규명을 얻고,
그 정규명으로 곡을 조회한다. 태그 표기로 곡을 직접 찾으면 한글 표기
아티스트가 통째로 누락된다(실측 39.0% 대 78.5%).
"""

from __future__ import annotations

from typing import Protocol

from hathor.domain.entities.parsed_artist import ArtistCandidate
from hathor.domain.entities.resolved_identity import ResolvedArtist, ResolvedRecording


class ArtistLookup(Protocol):
    """1단계. 파서가 분해한 후보로 아티스트를 조회한다.

    후보는 normalized_key로 중복 제거된 상태여야 한다. 실측상 1004곡의
    고유 후보는 249개이며, 중복 제거 없이 조회하면 요청이 4배가 된다.

    조회 실패는 예외가 아니라 UNRESOLVED 상태로 반환한다. 미등재는
    정상적인 결과이지 오류가 아니다.
    """

    def resolve_artist(self, candidate: ArtistCandidate) -> ResolvedArtist: ...


class RecordingLookup(Protocol):
    """2단계. 확정된 아티스트 정규명으로 곡을 조회한다.

    artist_name에는 ResolvedArtist.canonical_name을 넘긴다. 단
    is_usable_for_lookup이 거짓이면 태그 표기를 그대로 넘겨야 한다.

    title은 부가 표기를 제거한 값이어야 한다. 괄호 깊이를 세어 중첩을
    처리하되 버전 표기는 보존한다. 버전은 레코딩을 구분하는 단서다.

    duration_ms는 후보 선별에 쓴다. 유명한 곡일수록 MB에 스튜디오·라이브·
    리마스터가 모두 등재돼 점수만으로는 갈리지 않는다. 실측상 AMBIGUOUS가
    38.4%였고 대부분이 이 유형이다.
    """

    def resolve_recording(
        self, source_key: str, title: str, artist_name: str, duration_ms: int
    ) -> ResolvedRecording: ...
