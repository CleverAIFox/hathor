#!/usr/bin/env python3
"""주 1회 arXiv를 훑어 `PLAN` §4 「읽을 후보」에 붙인다 (D-0424).

    python3 tools/watch_papers.py              후보를 화면에
    python3 tools/watch_papers.py --write      PLAN에 붙인다
    python3 tools/watch_papers.py --days 14

**`seshat`의 `tools/watch_papers.py`를 옮겼다** (seshat DECISIONS §126). 그쪽에서 이미
돌고 있는 물건이고, 바꾼 것은 **주제 정규식과 붙이는 자리**뿐이다. 규율 넷은 그대로다.

### 요약하지 않는다

제목 · 초록 첫 문장 · **왜 걸렸는지**만 적고 「읽을 후보」에 넣는다. `MASTER` §3
「읽은 논문」 표의 *«무엇을 했나 · 가져올 것»*은 **읽어야 쓸 수 있다** — 안 읽고 쓰면
그것이 D-0423이 가른 선을 지우는 짓이다.

### 못 재면 0건이 아니라 빨간불이다

출처가 응답을 못 주면 **0으로 세지 않고 죽는다.** 조용한 0건은 *«새 논문이 없다»*로
읽힌다 — GR-0.5가 금한 바로 그것이고, `doctor`와 같은 규율이다.

### 표준 라이브러리만 쓴다

예약 작업이 의존성 하나 때문에 조용히 멈추는 자리를 안 만든다. Atom을 손으로 읽는다.

### main을 안 민다

워크플로가 가지와 PR만 낸다. **봇이 main을 움직이면 보내 둔 패치의 기준 나무가
갈리고**, 받는 쪽은 까닭 모를 *«기준 트리가 다르다»*를 본다 (D-0376).

### 무엇을 내보내나 — 망 접점이다

**질의는 분야와 날짜뿐이다.** 라이브러리도 곡 이름도 취향도 안 나간다 (D-0015).
`check_egress`의 허용 목록에 적혀 있고, 그 목록은 **늘리지 않는 것이 목표다.**

### Hugging Face는 안 본다

seshat은 번역 모델 목록도 훑는다. 음악 쪽은 파이프라인 태그 분류가 번역만큼 고르지
않아 **무엇이 걸리는지 못 믿는다.** 반쯤 맞는 그물은 잡음만 늘린다 — 안 건다 (GR-0.8).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import pathlib
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "PLAN.md"
HEADING = "## 4. 읽을 후보"
UA = "hathor-watch-papers (https://github.com/CleverAIFox/hathor)"

TOPICS: dict[str, re.Pattern[str]] = {
    "취향": re.compile(
        r"\bpreference\b|\bpersonaliz|\btaste\b|\buser profile|\blistening history\b", re.I
    ),
    "조건부 생성": re.compile(
        r"\btext-to-music\b|\bmusic generation\b|\bcontrollable\b|\bconditioning\b"
        r"|\bretrieval-?augmented\b",
        re.I,
    ),
    "표현": re.compile(
        r"\bself-supervised\b|\brepresentation learning\b|\bprobing\b|\bfoundation model\b", re.I
    ),
    "평가": re.compile(
        r"\bfr[eé]chet audio\b|\bFAD\b|\blistening test\b|\bsubjective evaluation\b", re.I
    ),
    "상징": re.compile(r"\bsymbolic music\b|\bMIDI\b|\bchord\b|\bkey estimation\b", re.I),
}
"""무엇을 찾는가 — 열린 질문이 정한다. 제목 + 초록에서 하나라도 걸려야 후보다."""

MUSIC = re.compile(r"\bmusic\b|\bsong\b|\baudio\b|\bmelod|\bharmon|\bMIR\b", re.I)
"""**음악 이야기여야 한다.** 위 낱말은 음악 밖에서 훨씬 자주 나온다 — `probing`도
`preference`도 음악과 무관한 논문이 매일 쏟아진다."""

ARXIV = "http://export.arxiv.org/api/query"
CATEGORIES = ("cs.SD", "eess.AS", "cs.IR", "cs.MM")
"""훑을 분야. 음악은 `cs.SD`·`eess.AS`에 살고 개인화·추천은 `cs.IR`에 산다."""

SEEN = re.compile(r"ar[Xx]iv[ :/]+(?:abs/)?(\d{4}\.\d{4,5})")
"""이미 적힌 논문 — `arXiv 2508.14909` · `arxiv.org/abs/2508.14909`."""


@dataclasses.dataclass(frozen=True, slots=True)
class Candidate:
    """후보 한 편. **요약이 아니다** — 들고 있는 것이 이것뿐인 것이 규율이다."""

    name: str
    title: str
    line: str
    topics: tuple[str, ...]
    when: str
    link: str


WAIT = (429, 503)
"""**기다리면 되는 것** — «너무 자주 불렀다»와 «지금 바쁘다»다.

둘 다 *«없다»*가 아니라 *«나중에»*다. 그래서 바로 안 죽는다. 나머지(404 · 500)는
기다려도 안 바뀌니 **그 자리에서 죽는다** — 15분 타임아웃을 태우지 않는다.
"""

BACKOFF = (5, 20, 60)
"""몇 초씩 쉬나. 합이 85초이고 작업의 `timeout-minutes: 15` 안에 넉넉히 든다."""

NAP_CEILING = 120
"""`Retry-After`가 아무리 커도 여기까지다. **서버가 시킨 수에 작업을 통째로 맡기지 않는다.**"""


def _nap(exc: urllib.error.HTTPError, floor: int) -> int:
    """얼마나 쉬나. **서버가 적어 주면 그쪽이 맞다** — 우리 수는 바닥일 뿐이다."""
    said = (exc.headers.get("Retry-After", "") if exc.headers else "").strip()
    return min(max(int(said), floor), NAP_CEILING) if said.isdigit() else floor


def _died(url: str, exc: Exception) -> str:
    code = getattr(exc, "code", 0)
    often = (
        "    **너무 자주 불렀다.** 손으로 다시 돌린 횟수도 같은 통에 들어간다 —\n"
        "    주 1회가 기본이고 그 사이에 거듭 부르면 월요일 치가 막힌다\n"
        if code in WAIT
        else ""
    )
    return (
        f"{urllib.parse.urlsplit(url).netloc}을 못 물었다 — {type(exc).__name__}: {exc}\n"
        "    **0건이 아니다.** 못 잰 것을 «새 것이 없다»로 적지 않는다 (GR-0.5)\n"
        f"{often}"
        f"    그물을 본다 : curl -sI {url}\n"
        "    잠깐 넘어진 것이면 다시 부른다 — 이 도구는 주 1회 도는 것이다"
    )


def fetch(url: str, timeout: int = 30) -> bytes:
    """**못 물면 죽는다.** 빈 손을 «새 것이 없다»로 적지 않는다.

    **단, 기다리라는 답은 못 문 것이 아니다** (D-0428). arXiv이 429를 줬고 봇이 그
    자리에서 죽었다 — 한 시간에 손으로 세 번 부른 탓이다. 쉬었다 다시 묻고, 그래도
    안 되면 그때 죽는다. **쉬는 횟수는 `BACKOFF`가 든다** — 영원히 안 돈다.
    """
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    naps = list(BACKOFF)
    while True:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body: bytes = response.read()
            return body
        except urllib.error.HTTPError as exc:
            if exc.code not in WAIT or not naps:
                raise SystemExit(_died(url, exc)) from exc
            nap = _nap(exc, naps.pop(0))
            left = f"{len(naps)}번 남았다"
            print(f"  {exc.code} — {nap}초 쉬고 다시 부른다 ({left})", file=sys.stderr)
            time.sleep(nap)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SystemExit(_died(url, exc)) from exc


def topics_of(text: str) -> tuple[str, ...]:
    """걸린 주제들. **음악 이야기가 아니면 빈 값이다.**"""
    if not MUSIC.search(text):
        return ()
    return tuple(name for name, pattern in TOPICS.items() if pattern.search(text))


def _tag(entry: str, name: str) -> str:
    found = re.search(rf"<{name}[^>]*>(.*?)</{name}>", entry, re.S)
    return re.sub(r"\s+", " ", found.group(1)).strip() if found else ""


def arxiv(days: int, cap: int = 300) -> list[Candidate]:
    """최근 `days`일의 신규 중 주제에 걸린 것. **Atom을 손으로 읽는다.**"""
    today = dt.date.today()
    since = today - dt.timedelta(days=days)
    where = " OR ".join(f"cat:{one}" for one in CATEGORIES)
    query = f"({where}) AND submittedDate:[{since:%Y%m%d}0000 TO {today:%Y%m%d}2359]"
    url = (
        f"{ARXIV}?search_query={urllib.parse.quote(query)}"
        f"&start=0&max_results={cap}&sortBy=submittedDate&sortOrder=descending"
    )
    body = fetch(url).decode("utf-8", "replace")
    entries = re.findall(r"<entry>(.*?)</entry>", body, re.S)
    if not entries:
        raise SystemExit(
            "arXiv이 항목을 하나도 안 줬다 — 질의나 Atom 모양이 바뀌었다 (**0건이 아니다**)\n"
            f"    {url}\n    받은 길이 {len(body)}\n"
            f'    눈으로 본다 : curl -s "{url}" | head -40'
        )
    found: list[Candidate] = []
    for entry in entries:
        link = _tag(entry, "id")
        title, summary = _tag(entry, "title"), _tag(entry, "summary")
        got = topics_of(f"{title} {summary}")
        if not got:
            continue
        found.append(
            Candidate(
                name=re.sub(r"^.*abs/|v\d+$", "", link),
                title=title,
                line=summary.split(". ")[0][:220],
                topics=got,
                when=_tag(entry, "published")[:10],
                link=link,
            )
        )
    return found


WIDTH = 96
"""접는 자리. **문서 줄이 100자를 넘으면 `check_decisions`가 막는다** (D-0426).

세샤트 양식을 그대로 옮겼더니 한 줄이 200~380자였고 **봇이 연 PR이 우리 관문을
못 지났다.** 남의 양식을 옮길 때는 **받는 쪽 규칙을 같이 본다.**
"""


def lines(found: list[Candidate]) -> list[str]:
    """후보 하나에 여러 줄. **요약이 아니라 후보다.**

    **강조를 안 쓴다.** 후보가 수십이면 `**`도 수십이고, `check_doc_style`이 한 절의
    강조를 16으로 막는다 — 봇이 쓴 줄이 절을 터뜨리면 사람이 쓴 줄까지 막힌다.
    """
    out: list[str] = []
    for one in found:
        out.append(f"- {one.when} · {' · '.join(one.topics)} · {one.link}")
        out += textwrap.wrap(
            f"{one.title} — {one.line}",
            width=WIDTH,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    return out


def write(text: str, fresh: list[str], today: str) -> str:
    """「읽을 후보」 바로 아래에 붙인다. **`MASTER`의 표는 안 건드린다.**"""
    if HEADING not in text:
        raise SystemExit(
            f"{PLAN.name}에 «{HEADING}»가 없다 — 붙일 자리를 못 찾았다\n"
            "    그 제목 줄을 되살린다 : git log -p -- docs/PLAN.md | head -40"
        )
    block = "\n".join([f"\n### 훑은 날 {today}", *fresh])
    at = text.index(HEADING) + len(HEADING)
    return text[:at] + "\n" + block + "\n" + text[at:].lstrip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="논문 후보 훑기 (D-0424)")
    parser.add_argument(
        "--days", type=int, default=8, help="주 1회 예약이 한 번 밀려도 안 새게 8이 기본이다"
    )
    parser.add_argument("--write", action="store_true", help="PLAN에 붙인다")
    args = parser.parse_args(argv)

    text = PLAN.read_text(encoding="utf-8")
    already = set(SEEN.findall(text))
    found = [one for one in arxiv(args.days) if one.name not in already and one.link not in text]
    if not found:
        print(f"  {args.days}일 안에 걸린 것이 없다 — arXiv은 답했다")
        return 0

    fresh = lines(found)
    print("\n".join("  " + one for one in fresh))
    if args.write:
        today = f"{dt.date.today():%Y-%m-%d}"
        PLAN.write_text(write(text, fresh, today), encoding="utf-8")
        print(f"\n  {PLAN.relative_to(ROOT)}의 «{HEADING}»에 {len(fresh)}줄 붙였다")
    return 0


if __name__ == "__main__":
    # **위반(1)과 도구 고장(2)을 다른 코드로 끝낸다.** 같은 코드면 도구가 깨진 것을
    # 검사가 실패한 것으로 읽는다.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback

        traceback.print_exc()
        print("    ✗ 도구가 깨졌다 — 위 역추적이 자리를 든다", file=sys.stderr)
        sys.exit(2)
