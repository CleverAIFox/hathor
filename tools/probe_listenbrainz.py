#!/usr/bin/env python3
"""대중성 라벨을 **공개 데이터로** 붙일 수 있나 — 커버리지만 잰다 (O-66 · D-0215).

    cd core
    RESOLVE=/mnt/f/projects/hathor/var/ingest/resolve-20260812T133829Z.resolve.jsonl
    uv run python ../tools/probe_listenbrainz.py --resolve "$RESOLVE"

**판정하지 않는다.** 모델도 안 만든다. 묻는 것은 하나다 — *"우리 곡의 몇 %에 청취자
수가 붙는가, 그리고 같은 가수 안에서 비교할 만큼 모이는가."* 안 붙으면 이 설계는
데이터에서 막히고, 그것을 가장 싸게 아는 길이 이것이다.

### 왜 ListenBrainz인가

| 출처 | 판정 |
|---|---|
| 써클차트 | 사이트가 **AI/ML 학습·TDM 무단 사용을 금지**한다. 제휴 없이 못 쓴다 |
| 유튜브 조회수 | 버전이 갈리고 세대마다 플랫폼이 다르다 (D-0215) |
| **ListenBrainz** | 청취 기록이 **CC0**이고 MBID마다 **청취 수·고유 청취자 수**를 준다 |

**MBID는 이미 있다.** `ingest resolve`가 레코딩 MBID를 뽑아 뒀다 (D-0019).

### 무엇을 보내나

**레코딩 MBID 문자열만** 보낸다. 오디오·태그·파일 이름은 안 보낸다 (D-0015).

### 알려진 치우침

ListenBrainz 사용자층은 **서구·기술 친화 쪽으로 기울어 있을 것이다** (확인 안 됨).
K-pop 커버리지가 낮으면 그것이 이 탐침의 답이다 — 치우침을 보정하는 것은 그 뒤 일이다.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.listenbrainz.org/1/popularity/recording"
AGENT = "hathor-probe/0.1 ( https://github.com/CleverAIFox/hathor )"
BATCH = 25
"""한 번에 보낼 MBID 수. 서버 상한은 문서에 상수로만 적혀 있어 **작게 잡는다.**"""

CACHE = ROOT / "var" / "ingest" / "popularity-listenbrainz.jsonl"
"""**타임스탬프를 안 붙인다** (O-62). 다시 돌리면 덮는다."""

MIN_PER_ARTIST = 3
"""같은 가수 안 비교에 필요한 최소 곡 수. **셋 미만이면 순위라고 부를 것이 없다.**"""


def resolved(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("recording_mbid"):
                rows.append(
                    {
                        "source_key": str(row["source_key"]),
                        "mbid": str(row["recording_mbid"]),
                        "artist": str(row.get("queried_artist") or ""),
                    }
                )
    return rows


def post(mbids: list[str]) -> list[dict[str, object]]:
    body = json.dumps({"recording_mbids": mbids}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"User-Agent": AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset = response.headers.get("X-RateLimit-Reset-In")
                if remaining == "0" and reset:
                    time.sleep(float(reset) + 1)
                found = json.loads(response.read())
                return found if isinstance(found, list) else []
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(float(error.headers.get("X-RateLimit-Reset-In") or 10) + 1)
                continue
            raise
        except urllib.error.URLError:
            time.sleep(2**attempt)
    raise RuntimeError("ListenBrainz가 응답하지 않는다")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resolve", type=Path, required=True, help="*.resolve.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = resolved(args.resolve)[: args.limit]
    total = sum(1 for line in args.resolve.open(encoding="utf-8") if line.strip())
    if not rows:
        print(f"레코딩 MBID가 있는 곡이 없다: {args.resolve}", file=sys.stderr)
        return 1

    counts: dict[str, dict[str, object]] = {}
    for start in range(0, len(rows), BATCH):
        chunk = [row["mbid"] for row in rows[start : start + BATCH]]
        for item in post(chunk):
            counts[str(item.get("recording_mbid"))] = item
        print(f"  {min(start + BATCH, len(rows))}/{len(rows)}", file=sys.stderr, flush=True)
        time.sleep(0.5)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("w", encoding="utf-8") as stream:
        for row in rows:
            item = counts.get(row["mbid"], {})
            stream.write(
                json.dumps(
                    {
                        **row,
                        "listens": item.get("total_listen_count"),
                        "listeners": item.get("total_user_count"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    listeners = {
        row["mbid"]: counts[row["mbid"]].get("total_user_count")
        for row in rows
        if row["mbid"] in counts
    }
    covered = [row for row in rows if isinstance(listeners.get(row["mbid"]), int)]
    values = sorted(int(listeners[row["mbid"]]) for row in covered)  # type: ignore[arg-type]

    by_artist: dict[str, int] = defaultdict(int)
    for row in covered:
        by_artist[row["artist"]] += 1
    comparable = {artist: n for artist, n in by_artist.items() if n >= MIN_PER_ARTIST}

    print(f"\n곡 {total} · 레코딩 MBID {len(rows)} ({len(rows) / total:.1%})")
    print(f"청취자 수가 붙은 곡 {len(covered)} (전체의 {len(covered) / total:.1%})")
    if len(values) > 1:
        quartiles = statistics.quantiles(values, n=4)
        print(
            f"고유 청취자  최소 {values[0]} · 25% {quartiles[0]:.0f} · 중앙 {quartiles[1]:.0f}"
            f" · 75% {quartiles[2]:.0f} · 최대 {values[-1]}"
        )
        print(f"청취자 1명뿐인 곡 {sum(1 for v in values if v <= 1)}")
    print(
        f"\n같은 가수 안 비교 가능 (붙은 곡 {MIN_PER_ARTIST}곡 이상) · 가수 {len(comparable)}명"
        f" · 곡 {sum(comparable.values())}"
    )
    for artist, n in sorted(comparable.items(), key=lambda item: -item[1])[:10]:
        print(f"  {n:>3}  {artist[:40]}")
    print(f"\n저장: {CACHE}")
    print(
        "\n--- 읽는 법 ---\n"
        "붙은 곡이 적거나 청취자가 한 자릿수에 몰리면 **이 출처로는 라벨이 안 선다.**\n"
        "같은 가수 안 비교 가능 곡이 수백을 못 넘으면 곡의 몫을 가를 표본이 없다.\n"
        "**둘 다 통과해야 다음(대중성 등급 설계)으로 간다.**"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
