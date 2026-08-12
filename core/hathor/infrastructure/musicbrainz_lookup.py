"""MusicBrainz 조회. ArtistLookup / RecordingLookup 포트의 구현이다.

D-0019 실측: 아티스트 RESOLVED 84.3%, 곡 RESOLVED 78.5%.
조회는 2단계다. 태그 표기로 곡을 직접 찾으면 39.0%까지 떨어진다.

MB는 초당 1요청 제한이며 식별 가능한 User-Agent를 요구한다.
위반 시 503으로 차단된다. 형식은 괄호 안 양쪽에 공백이 필요하다.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from hathor.domain.entities.parsed_artist import ArtistCandidate
from hathor.domain.entities.resolved_identity import (
    ResolutionState,
    ResolvedArtist,
    ResolvedRecording,
)
from hathor.domain.services.lookup_verdict import (
    DurationCandidate,
    LookupVerdict,
    judge_scores,
    narrow_by_duration,
)

MB_BASE = "https://musicbrainz.org/ws/2"
MIN_INTERVAL_SECONDS = 1.1
# 유명한 곡은 상위 5건이 전부 재발매판이라 원곡이 밀린다.
# 실측: Adele - Hello의 정답이 limit 5에는 없고 25에는 있었다.
RECORDING_SEARCH_LIMIT = 25
MAX_ATTEMPTS = 4
REQUEST_TIMEOUT_SECONDS = 30


class MusicBrainzUnavailableError(Exception):
    """재시도를 소진하고도 응답을 얻지 못했다."""


class MusicBrainzClient:
    """레이트 리밋과 재시도를 책임지는 얇은 HTTP 계층.

    실측상 503이 산발적으로 발생한다. 첫 재시도에서 대부분 회복되므로
    선형 백오프로 충분하다. 소진 시 예외를 던지며, 조회 결과가 없는
    것과 통신 실패는 구분해야 한다.
    """

    def __init__(self, user_agent: str, interval: float = MIN_INTERVAL_SECONDS) -> None:
        self._user_agent = user_agent
        self._interval = interval
        self._last_call = 0.0

    def search(self, entity: str, query: str, limit: int = 2) -> list[dict[str, Any]]:
        params = {"query": query, "fmt": "json", "limit": str(limit)}
        url = f"{MB_BASE}/{entity}?{urllib.parse.urlencode(params)}"
        payload = self._fetch(url)
        hits = payload.get(f"{entity}s", [])
        return list(hits) if isinstance(hits, list) else []

    def _fetch(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_for_slot()
            try:
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    decoded: Any = json.loads(response.read().decode("utf-8"))
                    return dict(decoded) if isinstance(decoded, dict) else {}
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                if attempt == MAX_ATTEMPTS:
                    raise MusicBrainzUnavailableError(url) from None
                time.sleep(self._interval * attempt * 2)
        raise MusicBrainzUnavailableError(url)

    def _wait_for_slot(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_call = time.monotonic()


def verdict_of(hits: list[dict[str, Any]]) -> LookupVerdict:
    """MB 응답에서 점수를 꺼내 도메인 판정에 넘긴다.

    판정 규칙 자체는 도메인에 있다. 여기는 응답 형식을 벗기는 일만 한다.
    """
    if not hits:
        return LookupVerdict(ResolutionState.UNRESOLVED, 0, 0)
    top = _score_of(hits[0])
    runner_up = _score_of(hits[1]) if len(hits) > 1 else 0
    return judge_scores(top, runner_up)


def _score_of(hit: dict[str, Any]) -> int:
    raw = hit.get("score", 0)
    return int(raw) if isinstance(raw, int | str) else 0


def _length_of(hit: dict[str, Any]) -> int | None:
    """MB 레코딩 길이. 비어 있는 경우가 실제로 있다."""
    raw = hit.get("length")
    return int(raw) if isinstance(raw, int | str) and str(raw).isdigit() else None


def _text_of(hit: dict[str, Any], key: str) -> str | None:
    value = hit.get(key)
    return str(value) if isinstance(value, str) and value else None


class MusicBrainzLookup:
    """ArtistLookup·RecordingLookup 포트의 구현.

    1단계 결과를 normalized_key로 캐시한다. 실측상 1004곡의 고유 후보는
    249개이므로 캐시 없이는 요청이 4배가 된다.
    """

    def __init__(self, client: MusicBrainzClient) -> None:
        self._client = client
        self._artists: dict[str, ResolvedArtist] = {}

    def resolve_artist(self, candidate: ArtistCandidate) -> ResolvedArtist:
        key = candidate.normalized_key
        cached = self._artists.get(key)
        if cached is not None:
            return cached
        hits = self._client.search("artist", candidate.name)
        verdict = verdict_of(hits)
        head = hits[0] if hits else {}
        resolved = ResolvedArtist(
            query_key=key,
            state=verdict.state,
            canonical_name=_text_of(head, "name"),
            mbid=_text_of(head, "id"),
            top_score=verdict.top_score,
            runner_up_score=verdict.runner_up_score,
        )
        self._artists[key] = resolved
        return resolved

    def resolve_recording(
        self, source_key: str, title: str, artist_name: str, duration_ms: int
    ) -> ResolvedRecording:
        query = f'recording:"{title}" AND artist:"{artist_name}"'
        hits = self._client.search("recording", query, limit=RECORDING_SEARCH_LIMIT)
        state = verdict_of(hits).state
        head = hits[0] if hits else {}
        if state is ResolutionState.AMBIGUOUS and duration_ms > 0:
            picked = narrow_by_duration(
                [DurationCandidate(i, _length_of(h)) for i, h in enumerate(hits)], duration_ms
            )
            if picked is not None:
                state = ResolutionState.RESOLVED
                head = hits[picked.index]
        return ResolvedRecording(
            source_key=source_key,
            state=state,
            recording_mbid=_text_of(head, "id") if state is ResolutionState.RESOLVED else None,
            canonical_title=_text_of(head, "title"),
            isrc=None,
        )
