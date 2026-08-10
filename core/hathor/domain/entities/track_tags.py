"""트랙 태그 원문. 인제스트는 값을 해석하지 않고 그대로 보존한다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackTags:
    """ID3 태그에서 읽은 원문 값.

    D-0010 실측: 1004곡 전수 조사 결과 유효 프레임은 4종뿐이다.
    TIT2 / TPE1 / TALB / USLT 각 100%.
    발매일 프레임과 TSRC는 전량 부재하므로 태그에서 읽지 않는다.

    아티스트 문자열은 피처링이 혼재한 원문 그대로다
    (예: "10CM, BIG Naughty (서동현)"). 분해는 유닛 #2가 담당한다.
    """

    title: str | None
    artist: str | None
    album: str | None
    lyrics_text: str | None

    has_album_art: bool
    has_synced_lyrics: bool

    # 유닛 #3(AcoustID/MusicBrainz 조회)이 채운다. 인제스트 시점에는 항상 None.
    release_date_raw: str | None = None
    isrc: str | None = None

    @property
    def is_identifiable(self) -> bool:
        """지문 조회 없이 곡을 식별할 최소 정보를 갖췄는지."""
        return bool(self.title and self.artist)
