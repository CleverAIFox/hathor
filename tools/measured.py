#!/usr/bin/env python3
"""**실측 집계의 정본은 한 곳이다** (D-0366 · D-0043).

### 상류는 있었고 사람이 옮겨 적었다

기획서의 실측 표 — 개발 코퍼스 · ID3 프레임 · 아티스트 표기 — 는 `MASTER.md`에 **손으로
타이핑돼 있었다.** 세는 도구는 있었다: `probe_id3.py`가 1004곡을 전수로 세고 사람이
읽는 글을 찍었고, **그 수를 사람이 MASTER로 옮겼다.** 옮겨 적은 수는 낡는다 (GR-0.7) —
<!-- doc_fsck: ok 그때의 값을 인용한다 -->
D-0361이 기획서 캡션의 «계약 5종»에서 같은 꼴을 잡았다.

### 두 벌을 만들지 않는다

정본은 `docs/measured.toml` **하나**다. MASTER에 있는 표는 그것을 찍어 낸 **거울**이고
표식 사이에 산다 — `decision-ledger`가 이미 그 꼴이다 (D-0223). 수를 두 곳에 적으면
어긋난다 (D-0043).

    python3 tools/measured.py --check   # 정본 ↔ MASTER 블록
    python3 tools/measured.py --fix     # 블록을 다시 쓴다

**`--fix`는 관문이 안 부른다** (D-0288과 같은 규율) — 관문이 문서를 고치면 사람이
무엇이 바뀌었는지 모른다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "docs" / "measured.toml"
MASTER = ROOT / "docs" / "MASTER.md"

BLOCKS = {
    "corpus": ("개발 코퍼스 실측", ("항목", "값")),
    "id3": ("ID3 프레임 실측", ("프레임", "보유율", "용도")),
    "artist": ("아티스트 표기 실측", ("항목", "값")),
}
"""표식 이름 → (제목에 들어갈 말, 머리 칸). **세 표가 1004곡 전수에서 나온다.**"""

FLOOR_ROWS = 20
"""세 블록의 행 합계 **바닥** (D-0230). 실측 26행 — 정본이 비면 빈 표가 조용히 들어간다."""


SOURCES = {
    "corpus": ("probe_id3", "CORPUS_EMITS"),
    "id3": ("probe_id3", "ID3_EMITS"),
    "artist": ("probe_artist", "EMITS"),
}
"""블록 → (그 수를 세는 도구, 그 도구가 내는 키를 든 상수) (D-0371).

**D-0366은 블록 셋을 내리고 상류를 하나만 붙였다.** `id3`만 `--emit`이 있었고
`corpus`·`artist` **열넷**은 「백분율에서 거꾸로 푼 수」로 섰다. 기록은 `artist`만
남았다고 적었다 — **세어 보지 않고 적은 수다** (GR-0.5).

여기 적힌 상수를 **글자로 읽는다.** 도구를 임포트하면 `mutagen`이 딸려 와 `make check`에
못 넣는다 (D-0256과 같은 자리).
"""

DECLARED = re.compile(r"(?ms)^(\w+)\s*=\s*\(\s*(.*?)\)")
NAME = re.compile(r'"([^"]+)"')


def emitted(tool: str, const: str) -> set[str]:
    """그 도구가 **낸다고 선언한** 키. 없으면 비어 있고, 그것이 곧 문제가 된다."""
    text = (ROOT / "tools" / f"{tool}.py").read_text(encoding="utf-8")
    for found in DECLARED.finditer(text):
        if found.group(1) == const:
            return set(NAME.findall(found.group(2)))
    return set()


def check_upstream(data: dict[str, dict[str, object]]) -> list[str]:
    """**정본의 수마다 그것을 세는 도구가 있나** — 양방향 (D-0371 · D-0363).

    한쪽만 보면 **아무도 안 세는 수**가 조용히 눌러앉고, 반대쪽만 보면 **센 수를
    버리는 것**이 안 보인다. 둘 다 사람 눈에만 보이는 종류다.
    """
    problems: list[str] = []
    for name, (tool, const) in SOURCES.items():
        counts = data.get(name, {}).get("counts")
        if not isinstance(counts, dict):
            problems.append(f"정본에 `[{name}.counts]`가 없다")
            continue
        declared = emitted(tool, const)
        if not declared:
            problems.append(f"`{tool}.{const}`을 못 읽었다 — 상류 선언이 사라졌다 (D-0230)")
            continue
        orphan = sorted(set(counts) - declared)
        dropped = sorted(declared - set(counts))
        if orphan:
            problems.append(
                f"`[{name}.counts]`의 {orphan}을 **아무도 안 센다** — "
                f"`{tool}`이 내거나 정본에서 뺀다 (D-0371)"
            )
        if dropped:
            problems.append(
                f"`{tool}`이 내는 {dropped}이 `[{name}.counts]`에 없다 — "
                "**센 수를 버린다.** `display`와 함께 더한다 (D-0366)"
            )
    return problems


def begin(name: str) -> str:
    return f"<!-- measured:{name}:begin -->"


def end(name: str) -> str:
    return f"<!-- measured:{name}:end -->"


def canon() -> dict[str, dict[str, object]]:
    """정본. **`tomllib`은 표준 라이브러리다** — 맨 `python3`으로 돈다 (D-0256)."""
    with CANON.open("rb") as handle:
        return dict(tomllib.load(handle))


def pct(part: int, whole: int) -> str:
    """백분율 표기. **정수면 소수점을 안 붙인다** — `100%`이지 `100.0%`가 아니다."""
    if not whole:
        raise LookupError("전수가 0이다 — 나눌 수 없다")
    value = part / whole * 100
    return f"{value:.0f}%" if abs(value - round(value)) < 0.05 else f"{value:.1f}%"


def human(size: int) -> str:
    """바이트를 **센 수와 읽는 수 둘 다** 낸다 — 둘 중 하나만 적으면 대조가 안 된다."""
    return f"{size:,} 바이트 ({size / 2**30:.2f} GiB)"


def cell(kind: str, row: dict[str, object], counts: dict[str, int], tracks: int) -> str:
    """표시 한 칸. **백분율은 여기서 계산한다** — 정본에 적지 않는다 (D-0366)."""
    name = row.get("of")
    prefix, suffix = str(row.get("prefix", "")), str(row.get("suffix", ""))
    if kind == "share-pair":
        if not isinstance(name, list):
            raise LookupError(f"`share-pair`의 `of`가 묶음이 아니다: {name!r}")
        missing = [one for one in map(str, name) if one not in counts]
        if missing:
            raise LookupError(f"`counts`에 없는 센 수를 부른다: {missing}")
        return " / ".join(
            f"{one} {pct(counts[one], tracks)} ({counts[one]}곡)" for one in map(str, name)
        )
    if str(name) not in counts:
        raise LookupError(f"`display`가 센 수 `{name}`을 부르는데 `counts`에 없다")
    got = counts[str(name)]
    if kind == "count":
        return f"{got:,}"
    if kind == "hours":
        return f"{got / 3600:.2f}시간"
    if kind == "bytes":
        return human(got)
    if kind == "share":
        return f"{prefix}{pct(got, tracks)}{suffix}"
    if kind == "share-tracks":
        return f"{pct(got, tracks)} ({got}곡)"
    if kind == "cases":
        return f"**{got}건**" if row.get("bold") else f"{got}건"
    if kind == "nfc":
        return f"NFC {pct(tracks - got, tracks)} (NFD {got}건)"
    raise LookupError(f"모르는 표시 부류다: {kind}")


def rows_of(section: dict[str, object]) -> list[list[str]]:
    """**센 수와 표시를 합쳐** 표의 행을 만든다. 정본에 완성된 행은 없다.

    `frames`를 든 행은 ID3 쪽이다 — 프레임 여럿을 한 줄로 묶고, 묶음 안에서 수가
    갈리면 `join`으로 나란히 적는다.
    """
    counts = section.get("counts")
    display = section.get("display")
    if not isinstance(counts, dict) or not isinstance(display, list):
        raise LookupError("`counts` · `display`가 없다 — 정본의 모양이 바뀌었다")
    tracks = int(str(section["tracks"]))
    rows: list[list[str]] = []
    for row in display:
        label = str(row["label"])
        if "frames" in row:
            frames = [str(one) for one in row["frames"]]
            shares = [pct(counts[one], tracks) for one in frames]
            same = len(set(shares)) == 1
            joiner = str(row.get("join", "/"))
            text = shares[0] if same else joiner.join(one.rstrip("%") for one in shares) + "%"
            rows.append([label, f"**{text}**" if row.get("bold") else text, str(row["use"])])
            continue
        rows.append([label, cell(str(row["kind"]), row, counts, tracks)])
    return rows


def table(name: str, section: dict[str, object]) -> str:
    """한 블록의 본문. **표식은 빼고** 표만 낸다."""
    _, head = BLOCKS[name]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in rows_of(section):
        if len(row) != len(head):
            raise LookupError(f"{name}의 행이 {len(row)}칸인데 머리는 {len(head)}칸이다")
        lines.append("| " + " | ".join(row) + " |")
    # **언제 잰 수인지 표와 함께 둔다** (D-0373 · D-0269). 전에는 정본의 `stamp`를
    # 아무도 안 쓰고 아무도 안 봤다 — 주석에 「마지막 실측」표를 **손으로** 적었다.
    stamp, tracks = section.get("stamp"), section.get("tracks")
    if not isinstance(stamp, str) or not isinstance(tracks, int):
        raise LookupError(f"{name}에 `stamp`나 `tracks`가 없다 — 언제 잰 수인지 모른다")
    lines += ["", f"<small>{tracks}곡 전수 · {stamp} 실측</small>"]
    return "\n".join(lines)


def built() -> dict[str, str]:
    """표식 이름 → 들어가야 하는 본문."""
    data = canon()
    return {name: table(name, data[name]) for name in BLOCKS if name in data}


def present(text: str, name: str) -> str | None:
    """MASTER에 들어 있는 본문. 표식이 없으면 `None`."""
    found = re.search(re.escape(begin(name)) + r"\n(.*?)\n" + re.escape(end(name)), text, re.DOTALL)
    return found.group(1) if found else None


def check() -> list[str]:
    """정본과 거울이 같은가. **첫 문제에서 멈추지 않는다.**"""
    text = MASTER.read_text(encoding="utf-8")
    data = canon()
    problems: list[str] = []
    total = 0
    for name, (title, _) in BLOCKS.items():
        if name not in data:
            problems.append(f"정본에 `[{name}]`이 없다 — 《{title}》의 수가 사라졌다")
            continue
        try:
            # **깨진 정본은 읽을 수 있는 문제로 낸다.** 터지면 `make check`의 다른
            # 판정까지 가려진다 (GR-0.8).
            total += len(rows_of(data[name]))
            want = table(name, data[name])
        except (LookupError, TypeError, ValueError) as error:
            problems.append(f"《{title}》 정본이 깨졌다: {error}")
            continue
        have = present(text, name)
        if have is None:
            problems.append(
                f"`MASTER`에 «{begin(name)}» 표식이 없다 — 《{title}》 표가 거울이 아니다"
            )
        elif have.strip() != want.strip():
            problems.append(
                f"《{title}》가 정본과 어긋난다. `python3 tools/measured.py --fix` (D-0366)"
            )
    if total < FLOOR_ROWS:
        problems.append(f"정본의 행이 {total}개다(바닥 {FLOOR_ROWS}). **그물이 비었다** (D-0230)")
    return problems + check_upstream(data)


def fix() -> list[str]:
    """거울을 정본으로 다시 쓴다. 고친 블록 이름을 낸다."""
    text = MASTER.read_text(encoding="utf-8")
    changed: list[str] = []
    for name, want in built().items():
        have = present(text, name)
        if have is None or have.strip() == want.strip():
            continue

        # **`re.sub`의 치환 문자열을 안 쓴다** — 표에 `\1` 같은 글자가 들어오면
        # 역참조로 읽힌다. 함수로 주면 본문이 글자 그대로 간다.
        def put(_: re.Match[str], want: str = want, name: str = name) -> str:
            return f"{begin(name)}\n\n{want}\n\n{end(name)}"

        text = re.sub(
            re.escape(begin(name)) + r"\n.*?\n" + re.escape(end(name)),
            put,
            text,
            flags=re.DOTALL,
        )
        changed.append(name)
    if changed:
        MASTER.write_text(text, encoding="utf-8")
    return changed


COUNT_LINE = re.compile(r'(?m)^([A-Za-z_][\w.]*|"[^"]+")( = )(\d+)$')
"""`counts` 표의 한 줄. **값만 간다** — 주석도 순서도 그대로 둔다 (D-0288과 같은 규율)."""


STAMP_LINE = re.compile(r'(?m)^(stamp = ")(\d{4}-\d{2}-\d{2})(")')


def restamp(text: str, section: str, today: str | None = None) -> str:
    """그 블록의 `stamp`를 **오늘로** 바꿔 돌려준다 (D-0373).

    **`--emit`이 수를 쓰면서 날짜를 안 썼다.** 그래서 `[artist]`가 2025-09-19로
    남아 있었고, 「마지막 실측」을 **주석에 손으로** 적게 됐다 — 이 정본이 막으려던
    바로 그 꼴이다 (GR-0.7). 날짜도 도구가 쓴다.
    """
    when = today or dt.date.today().isoformat()
    head = f"[{section}]"
    if head not in text:
        raise LookupError(f"정본에 `{head}`가 없다")
    start = text.index(head) + len(head)
    stop = text.find("\n[", start)
    block = text[start : stop if stop != -1 else len(text)]
    fixed = STAMP_LINE.sub(lambda m: f"{m.group(1)}{when}{m.group(3)}", block, count=1)
    if fixed == block and STAMP_LINE.search(block) is None:
        raise LookupError(f"`{head}`에 `stamp`가 없다 — 언제 잰 수인지 적을 자리가 없다")
    return text[:start] + fixed + text[start + len(block) :]


def emit(section: str, counts: dict[str, int]) -> list[str]:
    """정본의 `[<section>.counts]`를 **센 수로 갈아 넣는다** (D-0366). 바뀐 키를 낸다.

    **표를 다시 쓰지 않는다.** `display`는 사람이 정한 것이고 센 수만 바뀐다 — 그래서
    상류 도구가 편집을 덮을 수 없다.

    **없는 키는 안 더한다.** 더하려면 `display`도 같이 가야 하므로 사람이 한다 —
    조용히 자라는 정본은 아무도 안 읽는 정본이 된다.
    """
    text = CANON.read_text(encoding="utf-8")
    text = restamp(text, section)
    head = f"[{section}.counts]"
    if head not in text:
        raise LookupError(f"정본에 `{head}`가 없다")
    start = text.index(head) + len(head)
    stop = text.find("\n[", start)
    block = text[start : stop if stop != -1 else len(text)]
    changed: list[str] = []

    def swap(found: re.Match[str]) -> str:
        key = found.group(1).strip('"')
        if key not in counts or counts[key] == int(found.group(3)):
            return found.group(0)
        changed.append(f"{key} {found.group(3)} → {counts[key]}")
        return f"{found.group(1)}{found.group(2)}{counts[key]}"

    fixed = COUNT_LINE.sub(swap, block)
    # **수가 안 바뀌어도 쓴다** — 날짜는 바뀌었다. 「다시 쟀다」는 사실이 수의
    # 변화와 같지 않다 (D-0373). 그래야 *«바뀐 수가 없다»*도 기록에 남는다.
    CANON.write_text(text[:start] + fixed + text[start + len(block) :], encoding="utf-8")
    missing = sorted(set(counts) - {m.group(1).strip('"') for m in COUNT_LINE.finditer(block)})
    if missing:
        changed.append(f"**정본에 없는 키 {len(missing)}개는 안 더했다**: {missing}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="실측 집계 정본 ↔ MASTER 거울 (D-0366)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--fix", action="store_true", help="MASTER의 블록을 다시 쓴다")
    parser.add_argument("--list", action="store_true", help="정본을 찍는다")
    args = parser.parse_args()

    try:
        data = canon()
    except (OSError, tomllib.TOMLDecodeError, LookupError) as error:
        print(f"실측 정본을 못 읽었다: {error}", file=sys.stderr)
        return 2

    if args.list:
        for name, (title, _) in BLOCKS.items():
            got = len(rows_of(data[name])) if name in data else 0
            print(f"  {name:8} {got:3}행  {title}")
        return 0

    if args.fix:
        changed = fix()
        for name in changed:
            print(f"docs/MASTER.md «{name}» 블록을 다시 썼다")
        print(f"블록 {len(BLOCKS)}개 · 고친 자리 {len(changed)}곳")
        return 0

    problems = check()
    if problems:
        print(f"실측 정본과 어긋난 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    rows = sum(len(rows_of(data[name])) for name in BLOCKS if name in data)
    print(f"실측 정본 검사 통과 · 블록 {len(BLOCKS)}개 · {rows}행 · 곡 {data['id3']['tracks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
