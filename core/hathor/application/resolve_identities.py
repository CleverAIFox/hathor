"""정규 신원 확정 유스케이스. 파싱 결과를 외부 조회로 확정한다 (D-0019).

조회는 2단계다. 아티스트를 먼저 확정해 정규명을 얻고 그 정규명으로
곡을 조회한다. 1단계 결과 캐시는 구현체의 책임이므로 여기서는
곡을 순차 처리하며 매번 1단계를 호출한다.

파일을 쓰지 않는다. 산출물 기록은 호출자의 책임이다.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from hathor.application.resolution_summary import ResolutionSummary
from hathor.domain.entities.resolved_identity import ResolutionState, ResolvedRecording
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.ports.music_metadata_lookup import ArtistLookup, RecordingLookup
from hathor.domain.services.artist_name_parser import parse_artist_field
from hathor.domain.services.title_annotation import strip_annotations


@dataclass(frozen=True, slots=True)
class ResolutionRecord:
    """곡 1건의 확정 결과와 조회에 쓴 질의."""

    recording: ResolvedRecording
    queried_artist: str
    queried_title: str


class ResolveIdentities:
    """스캔 결과를 순회하며 정규 신원을 확정한다.

    결과를 리스트로 모으지 않고 스트리밍한다. 1004곡에 곡당 1.1초이므로
    전체 소요가 20분 안팎이며 중단·재개가 전제다 (D-0015).

    조회 실패는 예외로 올리지 않는다. MB 미등재는 정상적인 결과이며
    UNRESOLVED 상태로 폴백 식별자를 쓴다 (D-0017).
    """

    def __init__(self, artists: ArtistLookup, recordings: RecordingLookup) -> None:
        self._artists = artists
        self._recordings = recordings
        self.summary = ResolutionSummary()

    def run(self, tracks: Iterable[ScannedTrack]) -> Iterator[ResolutionRecord]:
        for track in tracks:
            record = self._resolve_one(track)
            self.summary.observe(record.recording.state)
            yield record

    def _resolve_one(self, track: ScannedTrack) -> ResolutionRecord:
        raw_artist = (track.tags.artist or "").strip()
        raw_title = (track.tags.title or "").strip()
        parsed = parse_artist_field(raw_artist)
        title = strip_annotations(raw_title)

        artist_name = parsed.primary.name
        fallback = parsed.primary.normalized_key
        if raw_artist:
            resolved = self._artists.resolve_artist(parsed.primary)
            if resolved.is_usable_for_lookup and resolved.canonical_name:
                artist_name = resolved.canonical_name

        if not title or not artist_name:
            return ResolutionRecord(
                recording=ResolvedRecording(
                    source_key=track.source_key,
                    state=ResolutionState.UNRESOLVED,
                    fallback_key=fallback or None,
                ),
                queried_artist=artist_name,
                queried_title=title,
            )

        recording = self._recordings.resolve_recording(
            track.source_key, title, artist_name, track.stream.duration_ms
        )
        return ResolutionRecord(
            recording=self._with_fallback(recording, fallback),
            queried_artist=artist_name,
            queried_title=title,
        )

    @staticmethod
    def _with_fallback(recording: ResolvedRecording, fallback: str) -> ResolvedRecording:
        """확정되지 않은 결과에 폴백 식별자를 채운다.

        구현체는 폴백을 모른다. 파서가 만든 normalized_key는 도메인 지식이고
        조회처에 따라 달라지지 않는다 (D-0014).
        """
        if recording.state is ResolutionState.RESOLVED or not fallback:
            return recording
        return ResolvedRecording(
            source_key=recording.source_key,
            state=recording.state,
            recording_mbid=recording.recording_mbid,
            canonical_title=recording.canonical_title,
            artist_mbids=recording.artist_mbids,
            isrc=recording.isrc,
            fallback_key=fallback,
        )
