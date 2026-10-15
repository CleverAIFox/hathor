"""논문 후보 훑기 (D-0424).

**망을 안 탄다.** `fetch`를 가짜로 바꿔 Atom 문자열을 먹인다 — 예약 작업의 검사가
바깥 서비스에 걸리면 그 검사는 서비스가 흔들릴 때마다 빨개진다 (GR-0.8).
"""

from __future__ import annotations

import contextlib
import email.message
import types
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import tool_module

if TYPE_CHECKING:  # pragma: no cover - 형만 쓴다
    from types import ModuleType

WATCH = tool_module("watch_papers")


def _entry(name: str, title: str, summary: str, when: str = "2026-10-13") -> str:
    return (
        f"<entry><id>http://arxiv.org/abs/{name}v1</id>"
        f"<title>{title}</title><summary>{summary}</summary>"
        f"<published>{when}T00:00:00Z</published></entry>"
    )


def _feed(*entries: str) -> bytes:
    return f"<feed>{''.join(entries)}</feed>".encode()


def _served(monkeypatch: pytest.MonkeyPatch, body: bytes) -> ModuleType:
    monkeypatch.setattr(WATCH, "fetch", lambda url, timeout=30: body)
    return WATCH


# ------------------------------------------------------------------ 무엇이 걸리나


def test_음악_이야기가_아니면_안_걸린다() -> None:
    """**`preference`도 `probing`도 음악 밖에서 매일 쏟아진다.**"""
    assert WATCH.topics_of("User preference elicitation for web search ranking") == ()


def test_음악_이야기면_주제가_걸린다() -> None:
    assert "취향" in WATCH.topics_of("Personalized music recommendation from listening history")


def test_주제가_없으면_음악이어도_안_걸린다() -> None:
    """**그물이 넓으면 사람이 읽기를 그만둔다.** 음악이기만 하면 매주 수백 편이다."""
    assert WATCH.topics_of("A dataset of folk song lyrics in audio form") == ()


def test_걸린_주제를_전부_적는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """어느 열린 질문에 닿는지가 **읽을지 말지를 정한다.**"""
    body = _feed(
        _entry("2610.00001", "Chord-aware music generation", "We present controllable MIDI chord.")
    )
    (one,) = _served(monkeypatch, body).arxiv(8)

    assert set(one.topics) == {"조건부 생성", "상징"}


# ------------------------------------------------------------------ 못 재면 빨간불


def test_못_물면_죽는다_0건이_아니다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**조용한 0건은 «새 논문이 없다»로 읽힌다** (GR-0.5)."""

    def 넘어진다(url: str, timeout: int = 30) -> bytes:
        raise TimeoutError

    monkeypatch.setattr(WATCH.urllib.request, "urlopen", 넘어진다)
    with pytest.raises(SystemExit, match="0건이 아니다"):
        WATCH.fetch("https://example.invalid/x")


def test_항목이_하나도_없으면_죽는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**질의나 Atom 모양이 바뀐 것**이지 새 논문이 없는 것이 아니다."""
    with pytest.raises(SystemExit, match="0건이 아니다"):
        _served(monkeypatch, b"<feed></feed>").arxiv(8)


# ------------------------------------------------------------------ 붙이는 자리


def test_읽을_후보_아래에_붙인다() -> None:
    text = "# 계획\n\n## 4. 읽을 후보\n\n설명 줄\n"
    out = WATCH.write(
        text, ["- **arXiv 2026-10-13** [가](http://arxiv.org/abs/2610.1)"], "2026-10-14"
    )

    assert "## 4. 읽을 후보\n\n### 훑은 날 2026-10-14\n- **arXiv" in out
    assert "설명 줄" in out, "본문을 지웠다"


def test_붙일_자리가_없으면_죽는다() -> None:
    """**제목이 사라졌는데 조용히 끝나면** 후보가 어디에도 안 남는다."""
    with pytest.raises(SystemExit, match="붙일 자리를 못 찾았다"):
        WATCH.write("# 계획\n", ["- 가"], "2026-10-14")


def test_요약하지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**초록 첫 문장까지다** — «무엇을 했나 · 가져올 것»은 읽은 사람이 쓴다 (D-0423)."""
    body = _feed(
        _entry(
            "2610.00002",
            "Music taste profiles",
            "First sentence about preference. Second sentence that must not appear.",
        )
    )
    (one,) = _served(monkeypatch, body).arxiv(8)

    assert one.line == "First sentence about preference"
    assert "Second sentence" not in WATCH.lines([one])[0]


def test_실제_PLAN에_자리가_있다() -> None:
    """**도구가 가리키는 제목이 정본에 실제로 있나** — 없으면 주 1회 예약이 죽는다."""
    plan = Path(WATCH.PLAN)

    assert plan.exists(), f"{plan}가 없다"
    assert WATCH.HEADING in plan.read_text(encoding="utf-8")


# ------------------------------- 봇이 쓴 줄이 우리 관문을 못 지났다 (D-0426)


def test_줄이_문서_상한을_안_넘는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**`check_decisions`가 문서 줄을 100자로 막는다** (D-0426).

    세샤트 양식을 그대로 옮겼더니 200~380자가 나왔고 **봇이 연 PR이 우리 관문을
    못 지났다.** 남의 양식을 옮길 때는 받는 쪽 규칙을 같이 본다.
    """
    body = _feed(
        _entry("2610.00009", "music " + "가" * 120, "preference " + "나" * 300 + ". 뒷문장.")
    )
    (one,) = _served(monkeypatch, body).arxiv(8)

    for row in WATCH.lines([one]):
        assert len(row) < 100, f"{len(row)}자다: {row[:40]}"


def test_강조를_안_쓴다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**한 절의 강조는 16까지다.** 후보가 수십이면 봇이 절을 터뜨린다 (`check_doc_style`)."""
    body = _feed(_entry("2610.00010", "Music taste", "Preference study of music."))
    (one,) = _served(monkeypatch, body).arxiv(8)

    assert all("**" not in row for row in WATCH.lines([one]))


def test_링크와_제목이_둘_다_남는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """접느라 **무엇을 읽을지 못 알아보면** 후보가 아니다."""
    body = _feed(_entry("2610.00011", "Chord generation", "Symbolic music MIDI study."))
    (one,) = _served(monkeypatch, body).arxiv(8)
    rows = "\n".join(WATCH.lines([one]))

    assert one.link in rows
    assert "Chord generation" in rows
    assert "상징" in rows, "걸린 주제가 사라졌다"


# ------------------------------- 기다리라는 답은 못 문 것이 아니다 (D-0428)

BODY = b"<feed><entry></entry></feed>"


def _headers(**fields: str) -> email.message.Message:
    said = email.message.Message()
    for name, value in fields.items():
        said[name.replace("_", "-")] = value
    return said


class _Flaky:
    """urlopen의 자리. **정해진 만큼 넘어지고 그 다음에 준다.**"""

    def __init__(self, *falls: int, said: email.message.Message | None = None) -> None:
        self.falls = list(falls)
        self.said = said if said is not None else email.message.Message()
        self.asked = 0

    def __call__(self, request: object, timeout: int = 30) -> object:
        del request, timeout
        self.asked += 1
        if self.falls:
            raise urllib.error.HTTPError("u", self.falls.pop(0), "", self.said, None)
        return contextlib.nullcontext(types.SimpleNamespace(read=lambda: BODY))


def _rested(monkeypatch: pytest.MonkeyPatch, door: _Flaky) -> list[int]:
    """**재우지 않는다.** 검사가 실제로 쉬면 관문이 분 단위로 느려진다."""
    naps: list[int] = []
    monkeypatch.setattr(WATCH.urllib.request, "urlopen", door)
    monkeypatch.setattr(WATCH.time, "sleep", naps.append)
    return naps


def test_429면_쉬고_다시_부른다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**봇이 429에서 그 자리에 죽었다** (D-0428).

    한 시간에 손으로 세 번 돌렸고 arXiv이 막았다. 429는 «없다»가 아니라 «나중에»다.
    """
    door = _Flaky(429, 429)
    naps = _rested(monkeypatch, door)

    assert WATCH.fetch("https://x.invalid/q") == BODY
    assert naps == [5, 20], "안 쉬었거나 수를 지어냈다"


def test_계속_429여도_영원히_안_돈다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**쉬는 횟수는 `BACKOFF`가 든다.** 안 그러면 작업이 15분을 태우고 죽는다."""
    door = _Flaky(*([429] * 9))
    naps = _rested(monkeypatch, door)

    with pytest.raises(SystemExit, match="너무 자주 불렀다"):
        WATCH.fetch("https://x.invalid/q")
    assert len(naps) == len(WATCH.BACKOFF)
    assert door.asked == len(WATCH.BACKOFF) + 1


def test_404는_안_기다린다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**기다려도 안 바뀌는 것을 기다리면** 빨간불이 85초 늦게 뜬다."""
    naps = _rested(monkeypatch, _Flaky(404))

    with pytest.raises(SystemExit, match="0건이 아니다"):
        WATCH.fetch("https://x.invalid/q")
    assert naps == [], "404를 기다렸다"


def test_Retry_After를_따른다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**서버가 적어 주면 그쪽이 맞다** — 우리 수는 바닥일 뿐이다 (GR-0.5)."""
    naps = _rested(monkeypatch, _Flaky(429, said=_headers(Retry_After="45")))

    assert WATCH.fetch("https://x.invalid/q") == BODY
    assert naps == [45], "서버가 적어 준 수를 안 썼다"


def test_Retry_After가_터무니없으면_천장에_막힌다() -> None:
    """**작업을 서버가 시킨 수에 통째로 맡기지 않는다.**"""
    huge = urllib.error.HTTPError("u", 429, "", _headers(Retry_After="86400"), None)

    assert WATCH._nap(huge, 5) == WATCH.NAP_CEILING
