"""정규 신원 확정 유스케이스 테스트 (D-0019).

네트워크를 타지 않는다. 조회기는 가짜를 주입한다.
"""

from datetime import UTC, datetime

from hathor.application.resolve_identities import ResolveIdentities
from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.parsed_artist import ArtistCandidate
from hathor.domain.entities.resolved_identity import (
    ResolutionState,
    ResolvedArtist,
    ResolvedRecording,
)
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags


def make_track(artist: str | None, title: str | None) -> ScannedTrack:
    return ScannedTrack(
        source_key="a.mp3",
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            duration_ms=1000, bitrate_bps=320000, sample_rate_hz=44100, channels=2, codec="mp3"
        ),
        tags=TrackTags(
            title=title,
            artist=artist,
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        ),
        raw_frame_names=(),
    )


class FakeArtists:
    def __init__(self, resolved: ResolvedArtist) -> None:
        self._resolved = resolved
        self.seen: list[str] = []

    def resolve_artist(self, candidate: ArtistCandidate) -> ResolvedArtist:
        self.seen.append(candidate.name)
        return self._resolved


class FakeRecordings:
    def __init__(self, state: ResolutionState) -> None:
        self._state = state
        self.seen: list[tuple[str, str]] = []

    def resolve_recording(
        self, source_key: str, title: str, artist_name: str, duration_ms: int
    ) -> ResolvedRecording:
        self.seen.append((artist_name, title))
        return ResolvedRecording(
            source_key=source_key,
            state=self._state,
            recording_mbid="mbid-1" if self._state is ResolutionState.RESOLVED else None,
        )


def test_resolved_아티스트는_정규명으로_조회한다():
    artists = FakeArtists(ResolvedArtist("아이유", ResolutionState.RESOLVED, canonical_name="IU"))
    recordings = FakeRecordings(ResolutionState.RESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    records = list(use_case.run([make_track("아이유(IU)", "좋은 날")]))

    assert artists.seen == ["아이유"]
    assert recordings.seen == [("IU", "좋은 날")]
    assert records[0].recording.identity == "mbid-1"


def test_ambiguous_아티스트는_태그_표기를_그대로_쓴다():
    # 확정되지 않은 정규명으로 치환하면 오답이 곡 조회로 전파된다
    artists = FakeArtists(
        ResolvedArtist("효린", ResolutionState.AMBIGUOUS, canonical_name="Hyolyn")
    )
    recordings = FakeRecordings(ResolutionState.RESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    list(use_case.run([make_track("효린", "안녕")]))

    assert recordings.seen == [("효린", "안녕")]


def test_제목_부가_표기를_떼고_조회한다():
    artists = FakeArtists(ResolvedArtist("10cm", ResolutionState.RESOLVED, canonical_name="10cm"))
    recordings = FakeRecordings(ResolutionState.RESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    list(use_case.run([make_track("10CM", "서울의 잠 못 이루는 밤 (Feat. 이수현)")]))

    assert recordings.seen == [("10cm", "서울의 잠 못 이루는 밤")]


def test_unresolved면_폴백_키가_식별자가_된다():
    artists = FakeArtists(ResolvedArtist("전혜성", ResolutionState.UNRESOLVED))
    recordings = FakeRecordings(ResolutionState.UNRESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    records = list(use_case.run([make_track("전혜성", "할말을 잃어서")]))

    assert records[0].recording.identity == "전혜성"


def test_제목이_비면_조회하지_않는다():
    artists = FakeArtists(ResolvedArtist("x", ResolutionState.RESOLVED, canonical_name="X"))
    recordings = FakeRecordings(ResolutionState.RESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    records = list(use_case.run([make_track("아이유", None)]))

    assert recordings.seen == []
    assert records[0].recording.state is ResolutionState.UNRESOLVED


def test_요약이_상태별로_누적된다():
    artists = FakeArtists(ResolvedArtist("a", ResolutionState.RESOLVED, canonical_name="A"))
    recordings = FakeRecordings(ResolutionState.RESOLVED)
    use_case = ResolveIdentities(artists, recordings)  # type: ignore[arg-type]

    list(use_case.run([make_track("a", "t1"), make_track("a", "t2")]))

    assert use_case.summary.total == 2
    assert use_case.summary.ratio_of(ResolutionState.RESOLVED) == 1.0
