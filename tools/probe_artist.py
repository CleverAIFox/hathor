"""아티스트 표기 전수. **`--emit`이 실측 정본의 `counts`를 다시 쓴다** (D-0371).

D-0366이 `docs/measured.toml`을 정본으로 내리며 세 블록을 넣었고, 상류 도구를 붙인 것은
`corpus`·`id3` 둘뿐이었다. **`[artist.counts]` 여섯 개는 그날부터 「백분율에서 거꾸로
푼 수」로 서 있었다** — 아무도 다시 센 적이 없다. 그 빚을 여기서 갚는다.

    cd core && uv run python ../tools/probe_artist.py          # 사람이 읽는 전수
    cd core && uv run python ../tools/probe_artist.py --emit   # 정본의 counts를 갈아 넣는다

### 입력이 다르다

`probe_id3`는 **원본 음원**을 읽고 이쪽은 **스캔 산출물**(`var/ingest/scan-*.jsonl`)을
읽는다. 그래서 먼저 한 번 스캔해야 한다 — 없으면 **막고 그 명령을 찍는다** (D-0367).

**기기에서만 돈다.** 산출물에 곡별 태그가 들어 있고 `var/`는 기기를 안 떠난다
(D-0015 · D-0134). 정본으로 나가는 것은 **수 여섯 개뿐**이다.

### 세는 법을 글로 적는다

`counts`가 바뀌면 *"자가 바뀐 것"*인지 *"음원이 바뀐 것"*인지 알아야 한다. 그래서
`--emit`이 **각 수의 정의를 같이 찍는다** — 수만 찍으면 다음 사람이 그것을 못 가른다
(GR-0.5 · D-0269).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INGEST = ROOT / "var" / "ingest"

SEPARATORS = {
    "쉼표": r",",
    "앰퍼샌드": r"&",
    "feat": r"(?i)\bfeat\.?\b",
    "featuring": r"(?i)\bfeaturing\b",
    "with": r"(?i)\bwith\b",
    "X 대문자": r"(?<=\s)X(?=\s)",
    "x 소문자": r"(?<=\s)x(?=\s)",
    "슬래시": r"/",
    "가운뎃점": r"·",
    "and 영문": r"(?i)\band\b",
    "와과": r"(와|과)\s",
    "괄호": r"[(（]",  # noqa: RUF001 — 전각 괄호는 한국 음원 태그에 실제로 쓰인다
    "대괄호": r"\[",
}


COUNTED: dict[str, tuple[str, str]] = {
    "bracket": (r"[(（\[]", "괄호 또는 대괄호를 품은 곡"),  # noqa: RUF001 — 전각 괄호는 한국 음원 태그에 실제로 쓰인다
    "comma": (r",", "쉼표를 품은 곡"),
    "ampersand": (r"&", "앰퍼샌드를 품은 곡"),
    "separator_words": (
        r"(?i)\b(?:feat\.?|featuring|with|and)\b|/|·",
        "`feat.` `with` `and` `/` `·` 중 하나를 품은 곡",
    ),
}
"""정본의 `[artist.counts]` 키 → (정규식, 사람이 읽는 정의).

**정의를 코드 옆에 둔다** — 수가 바뀐 날 *"자가 바뀌었나 음원이 바뀌었나"*를
가르는 것은 이 문장이다 (D-0371). `unique`·`plain`은 정규식 하나로 안 되므로
`tally()`가 따로 센다.
"""

ALL_SEPARATORS = "(?i)(" + ")|(".join(p.replace("(?i)", "") for p in SEPARATORS.values()) + ")"
"""**어느 구분자도 없는 곡**을 가리기 위한 합집합. `analyze()`가 쓰던 식 그대로다 (D-0043)."""


EMITS = ("unique", "plain", "bracket", "comma", "ampersand", "separator_words")
"""이 도구가 정본에 넣는 키. **`measured`가 양방향으로 맞댄다** (D-0371).

여기 없는 키가 `[artist.counts]`에 있으면 **아무도 안 세는 수**이고, 여기 있는데
정본에 없으면 **센 수를 버리는 것**이다. 둘 다 조용히 생긴다 (D-0363 · D-0230).
"""


def tally(artists: list[str]) -> dict[str, int]:
    """정본에 넣을 수 여섯 개. **문자열은 하나도 안 나간다** (D-0015)."""
    found = {
        key: sum(1 for one in artists if re.search(pattern, one))
        for key, (pattern, _why) in COUNTED.items()
    }
    found["unique"] = len(set(artists))
    found["plain"] = sum(1 for one in artists if not re.search(ALL_SEPARATORS, one))
    return found


def load_records(path: Path) -> list[dict[str, object]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                records.append(json.loads(line))
    return records


def latest_jsonl(root: Path) -> Path | None:
    candidates = sorted(
        p for p in root.glob("scan-*.jsonl") if not p.name.endswith(".failures.jsonl")
    )
    return candidates[-1] if candidates else None


def analyze(records: list[dict[str, object]]) -> None:
    artists = [str(r["tags"]["artist"]) for r in records]  # type: ignore[index]
    total = len(artists)

    print(f"총 {total}곡")
    print(f"고유 아티스트 문자열: {len(set(artists))}")
    print()

    print("=== 구분자 출현 빈도 ===")
    hits: Counter[str] = Counter()
    for name, pattern in SEPARATORS.items():
        count = sum(1 for a in artists if re.search(pattern, a))
        if count:
            hits[name] = count
    for name, count in hits.most_common():
        print(f"  {name:12s} {count:5d}곡  ({count / total * 100:5.1f}%)")

    print()
    print("=== 구분자 없는 단일 아티스트 ===")
    combined = "(?i)(" + ")|(".join(p.replace("(?i)", "") for p in SEPARATORS.values()) + ")"
    singles = [a for a in artists if not re.search(combined, a)]
    print(f"  {len(singles)}곡 ({len(singles) / total * 100:.1f}%)")

    print()
    print("=== 괄호 내용 표본 (최대 25) ===")
    paren = re.compile(r"[(（]([^)）]*)[)）]")  # noqa: RUF001 — 전각 괄호는 한국 음원 태그에 실제로 쓰인다
    contents: Counter[str] = Counter()
    for artist in artists:
        for match in paren.findall(artist):
            contents[match.strip()] += 1
    for content, count in contents.most_common(25):
        print(f"  {count:3d}회  {content!r}")


def cross_check_filenames(records: list[dict[str, object]]) -> None:
    """파일명 `아티스트-제목.mp3`와 TPE1 태그를 대조한다(D-0006)."""
    print()
    print("=== 파일명 대 태그 교차검증 ===")
    mismatched: list[tuple[str, str]] = []
    no_hyphen = 0

    for record in records:
        source_key = str(record["source_key"])
        stem = source_key.rsplit(".", 1)[0]
        if "-" not in stem:
            no_hyphen += 1
            continue
        from_name = stem.split("-", 1)[0].strip()
        from_tag = str(record["tags"]["artist"]).strip()  # type: ignore[index]
        if from_name != from_tag:
            mismatched.append((from_name, from_tag))

    total = len(records)
    print(f"  하이픈 없는 파일명: {no_hyphen}곡")
    print(f"  불일치: {len(mismatched)}곡 ({len(mismatched) / total * 100:.1f}%)")
    print()
    print("  불일치 표본 (최대 20):")
    for from_name, from_tag in mismatched[:20]:
        print(f"    파일명={from_name!r}  태그={from_tag!r}")


def scripts(value: str) -> set[str]:
    """표기 체계 집합. 숫자는 이름의 일부라 신호에서 뺀다."""
    kinds: set[str] = set()
    for char in value:
        if not char.isalnum() or char.isdigit():
            continue
        name = unicodedata.name(char, "")
        if name.startswith("HANGUL"):
            kinds.add("KO")
        elif name.startswith("LATIN"):
            kinds.add("LA")
        else:
            kinds.add("ETC")
    return kinds


def check_bracket_script(records: list[dict[str, object]]) -> None:
    """괄호 안팎의 표기 체계 대조 (D-0016).

    별칭 병기는 같은 이름의 다른 표기라 체계가 갈리고,
    소속 병기는 다른 이름이라 같은 체계로 쓰인다.
    """
    print()
    print("[괄호 표기 체계 대조]")
    pattern = re.compile(r"^([^(（]+)[(（]([^)）]+)[)）]\s*$")  # noqa: RUF001 — 전각 괄호는 한국 음원 태그에 실제로 쓰인다
    seen = {str(r["tags"]["artist"]).strip() for r in records}  # type: ignore[index]
    for raw in sorted(seen):
        matched = pattern.match(raw)
        if matched is None:
            continue
        outer, inner = matched.group(1), matched.group(2)
        verdict = "소속 의심" if scripts(outer) & scripts(inner) else "별칭"
        print(f"  {verdict}\t{raw}")


def main() -> int:
    parser = argparse.ArgumentParser(description="아티스트 표기 전수 (D-0371)")
    parser.add_argument("--emit", action="store_true", help="실측 정본의 counts를 다시 쓴다")
    args = parser.parse_args()

    # **cwd에 기대지 않는다** (D-0367). `core/`에서 `uv run`으로 부르므로 상대 경로는
    # 거기를 가리키고, 그러면 *«산출물이 없다»*만 찍히고 **왜 없는지는 안 적힌다.**
    latest = latest_jsonl(INGEST)
    if latest is None:
        print(
            f"스캔 산출물이 없다: {INGEST.as_posix()}/scan-*.jsonl\n"
            "  먼저 한 번 스캔한다 — `cd core && uv run python -m hathor.cli ingest scan`\n"
            "  라이브러리 경로는 `.env`의 `HATHOR_LIBRARY_ROOT`가 진다 (D-0066)",
            file=sys.stderr,
        )
        return 2

    print(f"입력: {latest.as_posix()}")
    print()
    records = load_records(latest)
    analyze(records)
    cross_check_filenames(records)
    check_bracket_script(records)

    if args.emit:
        import measured

        artists = [str(r["tags"]["artist"]) for r in records]  # type: ignore[index]
        counts = tally(artists)
        print()
        print("=== 정본에 넣는 수와 그 정의 ===")
        print(f"  {'unique':18s} {counts['unique']:5d}  고유 아티스트 문자열의 개수")
        print(f"  {'plain':18s} {counts['plain']:5d}  어느 구분자도 없는 곡")
        for key, (_pattern, why) in COUNTED.items():
            print(f"  {key:18s} {counts[key]:5d}  {why}")
        print()
        changed = measured.emit("artist", counts)
        for line in changed or ["바뀐 수가 없다"]:
            print(f"  {line}")
        print(f"정본 {measured.CANON.relative_to(measured.ROOT)} · 곡 {len(records)}")
        print("  `python3 tools/measured.py --fix`로 거울을 맞춘다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
