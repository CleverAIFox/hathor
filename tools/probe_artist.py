"""일회성 조사: 아티스트 표기 패턴. 프로덕션 코드 아님."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

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
    "괄호": r"[(（]",
    "대괄호": r"\[",
}


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
    paren = re.compile(r"[(（]([^)）]*)[)）]")
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


def main() -> int:
    root = Path("var/ingest")
    latest = latest_jsonl(root)
    if latest is None:
        print(f"산출물이 없다: {root}")
        return 1

    print(f"입력: {latest}")
    print()
    records = load_records(latest)
    analyze(records)
    cross_check_filenames(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
