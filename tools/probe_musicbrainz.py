"""일회성 조사: MusicBrainz 조회 성공률 (D-0017). 프로덕션 코드 아님.

MB는 초당 1요청 제한이며 식별 가능한 User-Agent를 요구한다.
위반 시 503으로 차단된다.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from hathor.domain.services.artist_name_parser import parse_artist_field  # noqa: E402

BASE = "https://musicbrainz.org/ws/2"
AGENT = "Hathor/0.1 ( https://github.com/CleverAIFox/hathor )"
INTERVAL = 1.1


def query(entity: str, params: dict[str, str]) -> dict[str, object]:
    """MB 검색 API 호출. 실패 시 빈 결과를 돌려준다."""
    url = f"{BASE}/{entity}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            wait = INTERVAL * (attempt + 1) * 2
            print(f"  재시도 {attempt + 1}/3 ({exc}) {wait:.1f}s", file=sys.stderr)
            time.sleep(wait)
    return {}


def load_rows() -> list[dict[str, object]]:
    """최신 스캔 산출물을 읽는다."""
    latest = sorted(Path("var/ingest").glob("*.jsonl"))[-1]
    return [json.loads(line) for line in latest.read_text(encoding="utf-8").splitlines()]


_ANNOTATION = re.compile(
    r"[(（]\s*(feat|ft|with|prod|inst|duet|vocal|remix|album version|original)\b[^)）]*[)）]",
    re.IGNORECASE,
)


def strip_annotations(title: str) -> str:
    """제목의 부가 표기를 뗀다.

    실측상 아티스트 필드에는 feat.가 0건이지만 제목 필드로 옮겨가 있다.
    "(Feat. 이수현)" "(Prod. by 박근태)" "(With 오혁)"이 붙으면 MB 매칭이 실패한다.
    """
    return _ANNOTATION.sub("", title).strip()


def judge(hits: list[dict[str, object]]) -> tuple[str, int, int]:
    """1·2순위 점수 격차로 판정한다. score 단독으로는 오답을 못 거른다."""
    if not hits:
        return "UNRESOLVED", 0, 0
    top = int(hits[0].get("score", 0))
    second = int(hits[1].get("score", 0)) if len(hits) > 1 else 0
    if top < 90:
        return "UNRESOLVED", top, second
    if top - second < 10:
        return "AMBIGUOUS", top, second
    return "RESOLVED", top, second


def probe_artists(rows: list[dict[str, object]]) -> dict[str, tuple[str, str]]:
    """파서가 분해한 후보 단위로 조회한다. 원문 조회로는 primary를 못 잡는다."""
    names: dict[str, str] = {}
    for row in rows:
        raw = row["tags"]["artist"]  # type: ignore[index]
        if not raw:
            continue
        for cand in parse_artist_field(str(raw)).candidates:
            if cand.normalized_key:
                names.setdefault(cand.normalized_key, cand.name)

    print(f"[아티스트] 후보 {len(names)}개, 예상 {len(names) * INTERVAL / 60:.1f}분")
    out: dict[str, tuple[str, str]] = {}
    for index, (key, name) in enumerate(sorted(names.items()), 1):
        result = query("artist", {"query": name, "fmt": "json", "limit": "2"})
        hits = result.get("artists") or []
        verdict, top, second = judge(hits)  # type: ignore[arg-type]
        matched = str(hits[0].get("name", "")) if hits else ""
        out[key] = (verdict, matched)
        print(f"  {index:>3}/{len(names)} {verdict:<10} {top:>3}/{second:<3} {name} -> {matched}")
        time.sleep(INTERVAL)
    return out


def probe_recordings(
    rows: list[dict[str, object]], resolved: dict[str, tuple[str, str]]
) -> dict[str, int]:
    """곡 제목 + 아티스트 원문으로 Recording MBID를 조회한다."""
    print(f"[곡 조회] {len(rows)}건, 예상 {len(rows) * INTERVAL / 60:.1f}분")
    tally = {"resolved": 0, "unresolved": 0, "skipped": 0}
    for index, row in enumerate(rows, 1):
        tags = row["tags"]
        # 곡 조회도 원문이 아니라 파서 분해 결과를 써야 한다.
        # 원문을 그대로 던지면 "아이유(IU)"가 통째로 검색돼 전량 실패한다.
        title = str(tags["title"] or "").strip()  # type: ignore[index]
        raw_artist = str(tags["artist"] or "").strip()  # type: ignore[index]
        parsed = parse_artist_field(raw_artist) if raw_artist else None
        artist = parsed.primary.name if parsed else ""
        # 2단계 조회: 1단계에서 확정한 MB 정규명을 쓴다.
        # 태그 표기 '아이유'로는 실패하고 정규명 'IU'로는 성공한다 (O-1).
        if parsed:
            hit = resolved.get(parsed.primary.normalized_key)
            if hit and hit[0] == "RESOLVED" and hit[1]:
                artist = hit[1]
        title = strip_annotations(title)
        if not title or not artist:
            tally["skipped"] += 1
            continue
        result = query(
            "recording",
            {"query": f'recording:"{title}" AND artist:"{artist}"', "fmt": "json", "limit": "3"},
        )
        hits = result.get("recordings") or []
        top = hits[0] if hits else None
        score = int(top.get("score", 0)) if isinstance(top, dict) else 0
        ok = score >= 90
        tally["resolved" if ok else "unresolved"] += 1
        print(f"  {index:>4}/{len(rows)} {'O' if ok else 'X'} score={score:>3} {artist} - {title}")
        time.sleep(INTERVAL)
    return tally


def main() -> int:
    rows = load_rows()
    found = probe_artists(rows)

    tally: dict[str, int] = {}
    for verdict, _ in found.values():
        tally[verdict] = tally.get(verdict, 0) + 1
    total = len(found)
    print(f"\n[아티스트 결과] 후보 {total}개")
    for verdict in ("RESOLVED", "AMBIGUOUS", "UNRESOLVED"):
        count = tally.get(verdict, 0)
        print(f"  {verdict:<11} {count:>3} ({count / total * 100:5.1f}%)")

    if "--recordings" in sys.argv:
        result = probe_recordings(rows, found)
        print(f"\n[곡 결과] {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
