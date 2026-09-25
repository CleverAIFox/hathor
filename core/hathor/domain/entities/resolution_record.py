"""곡 1건의 신원 확정 결과 (O-56 · D-0236).

`JsonlResolutionStore`가 담는다. 저장소가 담는 것은 도메인의 것이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.entities.resolved_identity import ResolvedRecording


@dataclass(frozen=True, slots=True)
class ResolutionRecord:
    """곡 1건의 확정 결과와 조회에 쓴 질의."""

    recording: ResolvedRecording
    queried_artist: str
    queried_title: str
