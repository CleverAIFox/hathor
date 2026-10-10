#!/usr/bin/env python3
"""**기획서 화면은 생성물이다** — 손으로 쓴 사본을 만들지 않는다 (D-0368).

### 사본을 대조로 지키는 것보다 사본을 만들지 않는 것이 싸다

fire-lane의 `render_workflow.py`가 적어 둔 문장이다. 그쪽은 `docs/workflow.html`을
손으로 썼다가 **규약 정본이 둘이 됐고, 같은 날 한 절만 낡은 채로 머지를 통과해 작업
하나가 소리 없이 사라졌다.**

hathor의 `site/proposal.html`은 **PDF를 끼워 보여 주는 34줄**이었다 (D-0229). 사본은
아니었지만 **화면이 정본을 안 읽었다** — 표·그림·절이 무엇이든 PDF 한 장이었다.

### 와꾸는 렌더러가 들고 **칸은 색인표가 정한다**

`MASTER`의 「□ 기획서 화면 색인」이 *절 → 칸*을 선언한다. **서식으로 가르지 않는다** —
fire-lane이 그렇게 했다가 *«서식이 곧 스키마인데 아무도 그렇게 선언한 적이 없었다»*로
되돌렸다. 누가 표를 목록으로 바꾸면 그 절이 조용히 다른 칸으로 옮겨간다. 서식은
**그리는 방법**에만 쓴다.

### 제출본은 칸을 안 쓴다

심사 서식의 순서를 지켜야 하므로 docx는 `MASTER` 순서 그대로다 (`build_proposal`).
**칸을 나누는 것은 화면 쪽만이다.**

### 도킹이 양방향이다

| 방향 | 무엇을 보나 |
|---|---|
| `index()` | 구간 안의 2단 절이 **색인에 다 있나** — 없으면 렌더가 죽는다 |
| `audit()` | 색인이 든 절이 **화면에 다 담겼나** |
| `--check` | 생성물이 **재생성 결과와 바이트로 같나** |

한 방향만 보면 목록을 두 벌 유지해야 한다.

### JS를 쓰지 않는다

탭은 CSS 라디오다. fire-lane이 적은 까닭 그대로다 — **이 페이지의 스크립트를 보는
검사가 없으므로 스크립트가 들어가면 검사 밖에서 자란다.**

    python3 tools/render_proposal.py --check    # 재생성 대조 · 정본 ↔ docx ↔ html
    python3 tools/render_proposal.py            # site/proposal.html 을 다시 쓴다

**맨 `python3`로 돈다** — 표준 라이브러리만 쓴다 (D-0256 · D-0367).
"""

from __future__ import annotations

import argparse
import html as _html
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import measured  # noqa: E402
from proposal_body import FIGURES, place_figures  # noqa: E402
from proposal_source import (  # noqa: E402
    FINGERPRINT,
    GENERATORS,
    RENDERERS,
    SourceError,
    fingerprint,
    recorded_renderers,
    source,
    stale,
)

OUT = ROOT / "site" / "proposal.html"
DOCX = ROOT / "docs" / "proposal.docx"
INDEX_BEGIN = "<!-- proposal-index:begin -->"
INDEX_END = "<!-- proposal-index:end -->"
TITLE = "HATHOR — 개인 취향 기반 AI 음악 창작 시스템"
FIGURE_DIR = "figures"

FLOOR_SLOTS = 5
"""색인이 들어야 하는 칸의 **바닥** (D-0230). 실측 6칸 — 표가 비면 빈 화면이 조용히 나간다."""


def index() -> dict[str, str]:
    """`절 제목 → 칸`. **색인에 없는 구간 내 2단 절이 있으면 죽는다.**

    fire-lane의 `index()`와 같은 자리다 — 그쪽은 절 번호(`§12-5`)를 키로 쓰고 여기는
    **제목 글자**를 쓴다. hathor의 절은 번호가 고르지 않다(`□`로 시작하는 것이 있다).
    """
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    if INDEX_BEGIN not in master or INDEX_END not in master:
        raise SourceError("MASTER에 「□ 기획서 화면 색인」 표식이 없다 — 화면의 칸이 사라졌다")
    block = master.split(INDEX_BEGIN)[1].split(INDEX_END)[0]
    slots: dict[str, str] = {}
    seen: list[str] = []
    for row in block.splitlines():
        cells = [one.strip() for one in row.strip().strip("|").split("|")]
        if len(cells) != 2 or set(cells[0]) <= set("-: ") or cells[0] == "칸":
            continue
        name = re.sub(r"`[^`]*`\s*", "", cells[0]).strip()
        seen.append(name)
        for heading in cells[1].split(" · "):
            slots[heading.strip()] = name
    if len(seen) < FLOOR_SLOTS:
        raise SourceError(f"색인에서 칸을 {len(seen)}개 읽었다(바닥 {FLOOR_SLOTS}) — 표가 비었다")
    missing = [one for one in headings() if one not in slots]
    if missing:
        raise SourceError(
            f"색인에 없는 절이 {len(missing)}개다: {missing} — "
            "「□ 기획서 화면 색인」에 한 줄 더하거나 그 절을 구간 밖으로 옮긴다 (D-0368)"
        )
    return slots


def pictured(path: Path, caption: str) -> list[str]:
    """화면에 박을 그림 한 줄. **PNG를 안 연다** (D-0370).

    제출본은 쪽 폭을 적느라 파일을 열어야 하는데, `--check`은 pandoc도 그림도 없는
    CI에서 돌고 **`var/`는 git이 안 나른다** (D-0369). 폭은 CSS가 맡는다.
    """
    return ["", f"![{caption}]({path.as_posix()})", ""]


def plan() -> dict[str, Path]:
    """그림 이름 → 화면에서 가리킬 자리. **제출본과 같은 목록을 쓴다** (D-0043)."""
    return {name: Path(FIGURE_DIR) / f"{name}.png" for _, name, _, _ in FIGURES}


def lines() -> list[str]:
    """기획서 구간의 줄. **그림이 박힌 뒤다** (D-0370) · 울타리 안은 제목으로 안 읽는다.

    D-0368은 정본을 **그대로** 읽었다. 정본에는 그림이 없고 `place_figures()`가 박는데
    **제출본 쪽만 그것을 불렀다** — 화면에 28장이 전부 빠졌고, 배포는 아무도 안 가리키는
    PNG 28장을 올리고 있었다. `inline()`은 멀쩡했고 **먹이가 안 왔다.**
    """
    return place_figures(source(), plan(), image=pictured).split("\n")


def headings() -> list[str]:
    """구간 안의 1~2단 제목 — `Part` 묶음은 뺀다 (칸이 그것을 대신한다)."""
    found, fence = [], False
    for line in lines():
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if line.startswith("## "):
            found.append(line[3:].strip())
    return found


def classify(slots: dict[str, str]) -> dict[str, list[tuple[str, str, str]]]:
    """`(제목, 형태, 조각)`을 **칸별로** 모은다. 형태는 그리는 방법일 뿐이다."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    head = next(iter(slots), "")
    slot = slots.get(head, next(iter(slots.values()), ""))
    fence = False
    buffer: list[str] = []
    kind: str | None = None

    def flush() -> None:
        nonlocal buffer, kind
        if buffer and kind:
            out.setdefault(slot, []).append((head, kind, "\n".join(buffer)))
        buffer, kind = [], None

    for line in lines():
        if line.startswith("```"):
            fence = not fence
            flush()
            if fence:
                kind = "pic"
            continue
        if fence:
            kind = kind or "pic"
            buffer.append(line)
            continue
        if line.startswith("## "):
            flush()
            head = line[3:].strip()
            slot = slots.get(head, slot)
            continue
        if line.startswith(("### ", "#### ")):
            flush()
            buffer.append(line)
            kind = "head"
            flush()
            continue
        if line.startswith("# "):
            flush()
            continue
        if line.startswith("|"):
            if kind != "tbl":
                flush()
                kind = "tbl"
            buffer.append(line)
            continue
        if line.startswith("![") or (line.startswith("    ") and line.strip()):
            if kind != "pic":
                flush()
                kind = "pic"
            buffer.append(line.removeprefix("    "))
            continue
        if not line.strip():
            flush()
            continue
        if kind not in (None, "why"):
            flush()
        kind = "why"
        buffer.append(line)
    flush()
    return out


def inline(text: str) -> str:
    """굵게 · 코드 · 그림만 푼다. **나머지는 글자 그대로** — 임의 HTML을 안 만든다."""
    found = re.match(r"!\[(.*?)\]\((?:[^)]*/)?([\w.-]+\.png)\)", text.strip())
    if found:
        caption, name = _html.escape(found.group(1)), found.group(2)
        return (
            f'<figure><img src="{FIGURE_DIR}/{name}" alt="{caption}" loading="lazy">'
            f"<figcaption>{caption}</figcaption></figure>"
        )
    out = _html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def as_table(chunk: str) -> str:
    rows = [one for one in chunk.split("\n") if one.startswith("|")]
    body = []
    for number, row in enumerate(rows):
        cells = [one.strip() for one in row.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        tag = "th" if number == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{inline(one)}</{tag}>" for one in cells) + "</tr>")
    return "<table>" + "".join(body) + "</table>"


def as_pic(chunk: str) -> str:
    """그림 조각. **PNG 한 줄은 `<figure>`, 나머지는 `<pre>`다.**"""
    if chunk.strip().startswith("!["):
        return "".join(inline(one) for one in chunk.split("\n") if one.strip())
    return f"<pre>{_html.escape(chunk)}</pre>"


def as_prose(chunk: str) -> str:
    return "<p>" + "<br>".join(inline(one) for one in chunk.split("\n")) + "</p>"


def as_head(chunk: str) -> str:
    level = 4 if chunk.startswith("#### ") else 3
    return f"<h{level}>{inline(chunk.lstrip('# '))}</h{level}>"


DRAW = {"tbl": as_table, "pic": as_pic, "why": as_prose, "head": as_head}


def audit(groups: dict[str, list[tuple[str, str, str]]], slots: dict[str, str]) -> None:
    """**색인이 든 절이 화면에 다 담겼나.** 어긋나면 죽는다 (fire-lane `audit()`)."""
    picked = {head for chunks in groups.values() for head, _, _ in chunks}
    lost = sorted(set(slots) - picked)
    if lost:
        raise SourceError(
            f"색인이 든 절 {len(lost)}개가 화면에 안 담겼다: {lost} — "
            "그 절의 내용이 표도 그림도 산문도 아닌 형태라 분류에서 빠졌다"
        )


FRAME_HEADS = 1
"""와꾸가 제 몫으로 더하는 제목 수 — 「목차」 하나. 칸 이름은 색인이 센다 (D-0372)."""

ROW = re.compile(r"^\|[\s:|-]+\|$")
HEAD = re.compile(r"<h([234])[^>]*>(.*?)</h\1>", re.S)


def bare(text: str) -> str:
    """태그를 걷어낸 글자. 제목을 정본과 맞대려면 같은 꼴이어야 한다."""
    return re.sub(r"<[^>]+>", "", _html.unescape(text)).strip()


def canon_parts() -> tuple[list[str], int]:
    """정본이 든 `(제목, 표 수)`. **울타리 안은 제목이 아니다.**"""
    heads, tables, fence = [], 0, False
    for line in lines():
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        found = re.match(r"^#{2,4} (.+)$", line)
        if found:
            heads.append(found.group(1).strip())
        elif ROW.match(line.strip()):
            tables += 1
    return heads, tables


def carried(made: str, slots: dict[str, str]) -> list[str]:
    """**정본이 든 것을 생성물이 다 담았나** (D-0372).

    바이트 대조는 「손으로 안 바뀌었나」만 본다. 생성기가 **처음부터** 빠뜨리면 커밋된
    것과 재생성 결과가 **같이 틀려서** 영원히 조용하다 — D-0370에서 그림 28장이 통째로
    빠진 채 관문 넷이 전부 초록이었다. 그래서 **수가 아니라 정본과 맞댄다.**
    """
    heads, tables = canon_parts()
    problems: list[str] = []

    seen = [bare(text) for _level, text in HEAD.findall(made)]
    lost = [one for one in heads if one not in seen]
    if lost:
        problems.append(f"정본의 제목 {len(lost)}개가 화면에 없다: {lost[:5]}")
    want = len(dict.fromkeys(slots.values())) + FRAME_HEADS
    extra = [one for one in seen if one not in heads]
    if len(extra) != want:
        problems.append(
            f"화면에만 있는 제목이 {len(extra)}개다(와꾸의 몫 {want}): {extra[:8]} — "
            "와꾸가 제목을 더 만들거나 정본의 제목이 다른 글자로 나왔다"
        )

    drawn = made.count("<figure>")
    if drawn != len(FIGURES):
        problems.append(f"화면의 그림이 {drawn}장이다(정본의 자리 {len(FIGURES)}). (D-0370)")
    shown = made.count("<table>")
    if shown != tables:
        problems.append(f"화면의 표가 {shown}개다(정본 {tables}). 분류에서 빠진 덩이가 있다")
    return problems


def build() -> str:
    """화면 한 장. **정본에서만 나온다.**"""
    slots = index()
    groups = classify(slots)
    audit(groups, slots)
    order = list(dict.fromkeys(slots.values()))
    tabs, panes = [], []
    for number, slot in enumerate(order):
        chosen = " checked" if number == 0 else ""
        tabs.append(f'<input type="radio" name="slot" id="s{number}"{chosen}>')
        tabs.append(f'<label for="s{number}">{_html.escape(slot)}</label>')
        body = []
        last = None
        for head, kind, chunk in groups.get(slot, []):
            if head != last:
                body.append(f'<h2 id="{_html.escape(head)}">{inline(head)}</h2>')
                last = head
            body.append(DRAW[kind](chunk))
        panes.append(f'<section class="pane">{"".join(body)}</section>')
    toc = []
    for slot in order:
        heads = list(dict.fromkeys(head for head, _, _ in groups.get(slot, [])))
        toc.append(f"<h3>{_html.escape(slot)}</h3><ul>")
        toc += [f'<li><a href="#{_html.escape(one)}">{inline(one)}</a></li>' for one in heads]
        toc.append("</ul>")
    # **표식을 하나씩 바꾼다.** `str.format`은 CSS의 `{`를 자리로 읽는다 — 중괄호를
    # 두 번씩 적어 피하는 길도 있지만 그러면 **스타일시트가 사람이 읽을 수 없게 된다.**
    filled = TEMPLATE
    for name, value in (
        ("title", _html.escape(TITLE)),
        ("stamp", fingerprint()),
        ("slots", str(len(order))),
        ("tabs", "\n".join(tabs)),
        ("toc", "\n".join(toc)),
        ("panes", "\n".join(panes)),
        ("script", SCRIPT),
    ):
        marker = "{" + name + "}"
        if marker not in filled:
            raise SourceError(f"템플릿에 `{marker}` 자리가 없다 — 와꾸가 바뀌었다")
        filled = filled.replace(marker, value)
    return filled


TEMPLATE = (ROOT / "site" / "proposal.template.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "site" / "proposal.js").read_text(encoding="utf-8")
"""페이지에 박는 스크립트. **두 벌이 되지 않게 파일 하나에만 있다** (D-0368).

`node --check`가 이 파일을 본다 — fire-lane이 JS를 뺀 까닭(*«스크립트를 보는 검사가
없으므로 검사 밖에서 자란다»*)을 그 관문이 없앤다. 사용자의 판단이다 — *«JS를 써야
해. 기획서는 훨씬 고도화 문서니까. 근데 뭐 억지로 쓸 필요는 없고.»* 그래서 **CSS로
되는 것은 CSS가 한다** — 탭은 라디오고, JS는 찾기와 현재 절 추적 둘만 맡는다.
"""


def short(path: Path) -> str:
    """화면에 적을 경로. **뿌리 밖이면 이름만** — `relative_to`가 거기서 터진다."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def docx_text(path: Path) -> str:
    """제출본의 글자. **엔티티를 푼다** (D-0372).

    안 풀면 `&`가 `&amp;`로 남는다. 「(Accuracy & Safety)」 같은 제목이 **없는 것으로
    보이고**, `truths()`도 그 글자로 맞대 왔다 — 대조 다섯에 `&`가 없어서 조용했을
    뿐이다. 완전성 자를 붙이자 그 자리에서 드러났다.
    """
    with zipfile.ZipFile(path) as archive:
        body = archive.read("word/document.xml").decode("utf-8")
    return _html.unescape(re.sub(r"<[^>]+>", "", body))


def stamped_docx(path: Path) -> str | None:
    with zipfile.ZipFile(path) as archive:
        if "docProps/core.xml" not in archive.namelist():
            return None
        core = archive.read("docProps/core.xml").decode("utf-8")
    found = re.search(re.escape(FINGERPRINT) + r"\s*([0-9a-f]{64})", core)
    return found.group(1) if found else None


def truths() -> list[tuple[str, str]]:
    """생성물에 있어야 할 문자열. **`docx_check`에서 흡수했다** (D-0220 → D-0368)."""
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    licenses = (ROOT / "tools" / "check_model_licenses.py").read_text(encoding="utf-8")
    corpus = int(str(measured.canon()["id3"]["tracks"]))
    m1 = _one(
        r"M1 앨범 검색 P@10 \| \*\*실측 [\d.]+ \(무작위 [\d.]+ 대비 ([\d.]+)배", master, "§10"
    )
    vram = _one(r"재개 조건: NVIDIA · VRAM (\d+)GB 이상", plan, "PLAN §1")
    blocked = re.findall(r'"([\w./-]+)": \(\s*"([^"]+)",\s*"no"', licenses)
    if not blocked:
        raise SourceError("check_model_licenses.py에서 상업 불가 모델을 못 읽었다")
    found = [
        (f"{corpus}곡", "measured.toml — 개발 코퍼스"),
        (f"{m1}배", "MASTER §10 — M1 앨범 검색"),
        (f"VRAM {vram}GB", "PLAN §1 — 엔진 재개 조건"),
    ]
    for name, license_name in blocked:
        found.append((name.split("/")[-1].split("-")[0], f"상업 불가 {name}"))
        found.append((license_name, f"{name}의 라이선스"))
    return found


def _one(pattern: str, text: str, where: str) -> str:
    found = re.search(pattern, text)
    if not found:
        raise SourceError(f"{where}에서 `{pattern}`을 못 읽었다")
    return found.group(1)


def check() -> list[str]:
    """생성물 둘이 정본과 맞나. **화면은 재생성해서 바이트로 본다.**"""
    problems: list[str] = []
    want = fingerprint()
    made = build()
    if not OUT.is_file():
        problems.append(f"{short(OUT)}가 없다 — 생성물을 커밋한다 (D-0368)")
    elif OUT.read_text(encoding="utf-8") != made:
        problems.append(
            f"{short(OUT)}가 정본과 다르다. `python3 tools/render_proposal.py`로 "
            "다시 낸다 — 손으로 고쳤다면 그 수정을 `MASTER`로 옮긴다 (D-0368)"
        )
    if not DOCX.is_file():
        return [*problems, "docs/proposal.docx가 없다"]
    written = stamped_docx(DOCX)
    if written is None:
        problems.append("docs/proposal.docx에 지문이 없다 — 빌드가 안 찍었다")
    elif written != want:
        problems.append("docs/proposal.docx의 지문이 정본과 다르다 — 다시 빌드하지 않았다")
    text = docx_text(DOCX)
    # **표지는 「언제 명령을 쳤나」가 아니라 「어느 판인가」를 적는다** (D-0376).
    # 예전 라벨은 `dt.date.today()`라 아무것도 안 고치고 다시 빌드해도 움직였고,
    # 그 움직임이 docx 바이트를 흔들어 **기준 트리 대조를 거짓으로 빨갛게** 했다.
    if f"정본 {want[:12]}" not in text:
        problems.append(
            f"제출본 표지에 «정본 {want[:12]}»가 없다 — 날짜 라벨로 돌아갔거나 "
            "다시 빌드하지 않았다 (D-0376)"
        )
    screen = re.sub(r"<[^>]+>", " ", made)
    for value, where in truths():
        for name, body in (("제출본", text), ("화면", screen)):
            if value not in body:
                problems.append(f"{name}에 «{value}»가 없다 ({where})")
    problems += carried(made, index())
    heads, tables = canon_parts()
    lost = [one for one in heads if one not in text]
    if lost:
        problems.append(f"정본의 제목 {len(lost)}개가 제출본에 없다: {lost[:5]} (D-0372)")
    with zipfile.ZipFile(DOCX) as archive:
        inside = archive.read("word/document.xml").decode("utf-8").count("<w:tbl>")
    if inside != tables:
        problems.append(f"제출본의 표가 {inside}개다(정본 {tables}). 빌드가 빠뜨렸다 (D-0372)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 화면 생성물 (D-0368)")
    parser.add_argument("--check", action="store_true", help="재생성 대조 · 정본 ↔ 생성물")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="자물쇠가 낡으면 **막는다**. 배포 잡이 쓴다 (D-0376)",
    )
    args = parser.parse_args()

    try:
        if args.check:
            problems = check()
            # **자물쇠는 따로 센다** (D-0376). 정본은 맞는데 생성기가 앞서 간 경우가
            # 있고, 그것으로 **커밋을 막으면** `make apply`가 제가 만든 커밋에 걸려
            # 멈춘다 (D-0374에서 겪었다). 그래서 **배포만** 막는다.
            rotten = stale()
            if args.deploy:
                problems += rotten
        else:
            made = build()
    except (SourceError, LookupError, KeyError, zipfile.BadZipFile) as error:
        print(f"기획서 화면 도구가 죽었다: {error}", file=sys.stderr)
        return 2

    if args.check:
        if problems:
            print(f"기획서가 {len(problems)}곳 어긋난다.", file=sys.stderr)
            for text in problems:
                print(f"  - {text}", file=sys.stderr)
            return 1
        if rotten:
            # **통과했지만 초록이 아니다.** 사람이 읽는 자리에 적고 배포에서 막힌다.
            print(
                f"기획서는 정본과 맞다. 그러나 **배포는 막힌다** — {len(rotten)}곳:",
                file=sys.stderr,
            )
            for text in rotten:
                print(f"  - {text}", file=sys.stderr)
            print("  → `make proposal`로 제출본을 다시 낸다 (D-0376)", file=sys.stderr)
        heads, tables = canon_parts()
        drew = recorded_renderers()
        lock = (
            f"자물쇠 **낡았다** {len(rotten)}곳"
            if rotten
            else f"자물쇠 {len(GENERATORS)}개 · "
            + " ".join(f"{name} {drew.get(name, '안 적혔다')}" for name in RENDERERS)
        )
        print(
            f"기획서 검사 통과 · 정본 대조 {len(truths())}건 · "
            f"칸 {len(dict.fromkeys(index().values()))}개 · 생성물 2개 · "
            f"옮겨진 것 제목 {len(heads)} · 표 {tables} · 그림 {len(FIGURES)} · {lock}"
        )
        return 0

    OUT.write_text(made, encoding="utf-8")
    panes = made.count('class="pane"')
    print(f"→ {short(OUT)} · {len(made) // 1024}KB · 칸 {panes}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
