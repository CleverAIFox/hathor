"""ID3 프레임 전수 히스토그램. **`--emit`이 실측 정본의 `counts`를 다시 쓴다** (D-0366).

예전엔 사람이 읽는 글만 찍었고 **사람이 그 수를 `MASTER.md`로 옮겨 적었다.** 옮겨 적은
수는 낡는다 (GR-0.7). 지금은 이 도구가 `docs/measured.toml`의 `[id3.counts]`를 직접
쓰고, `tools/measured.py`가 거기서 표를 찍어 낸다.

    cd core && uv run python ../tools/probe_id3.py          # 사람이 읽는 전수
    cd core && uv run python ../tools/probe_id3.py --emit    # 정본의 counts를 갈아 넣는다

**맨 `python3`로는 안 돈다** — `mutagen`이 프로젝트 묶음에 있다. 작성자가 독스트링에
맨 `python3`를 적었고 **사용자가 그 줄을 그대로 쳐서 터졌다** (D-0367). 이제
`check_args`가 그 갈림을 막는다.

**경로는 `.env`가 진다.** `HATHOR_LIBRARY_ROOT` 한 줄이고 셸에 치지 않는다 (D-0066) —
없으면 **막는다.** 예전엔 `/mnt/d/노래/노래`를 코드에 박아 두고 조용히 그것을 봤고,
드라이브 글자가 바뀌자 *«경로 없음»*만 찍혔다.

**기기에서만 돈다** — 1004곡 원본이 필요하고 오디오는 기기를 떠나지 않는다 (D-0015).
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from mutagen.id3 import ID3, ID3NoHeaderError  # noqa: E402

from hathor.shared.config.paths import library_root, load_dotenv  # noqa: E402

DATE_FRAMES = ("TDRC", "TDRL", "TDOR", "TYER", "TDAT", "TORY")


def main() -> int:
    parser = argparse.ArgumentParser(description="ID3 프레임 전수 (D-0366)")
    parser.add_argument("--emit", action="store_true", help="실측 정본의 counts를 다시 쓴다")
    args = parser.parse_args()
    # **정본 해결기를 쓴다** (D-0367 · D-0066). 제 손으로 환경변수를 읽으면 `.env`가
    # 안 읽히고, 기본값을 박으면 **드라이브가 바뀌어도 조용히 그것을 본다.**
    load_dotenv()
    root = library_root()
    if root is None:
        print(
            "`HATHOR_LIBRARY_ROOT`가 없다. `.env`에 한 줄 적는다 (`make setup`) — "
            "셸에 치지 않는다 (D-0066)",
            file=sys.stderr,
        )
        return 2
    if not root.is_dir():
        print(f"라이브러리가 없다: {root} — 드라이브가 안 붙었거나 경로가 틀렸다", file=sys.stderr)
        return 2

    files = sorted(p for p in root.rglob("*.mp3") if p.is_file())
    frame_counter: Counter[str] = Counter()
    date_counter: Counter[str] = Counter()
    nfd_names = 0
    has_isrc = 0
    has_uslt = 0
    has_sylt = 0
    has_any_date = 0
    failures: list[tuple[str, str]] = []

    for path in files:
        name = path.name
        if unicodedata.normalize("NFC", name) != name:
            nfd_names += 1
        try:
            # mutagen의 `ID3`는 상류에서 주석이 없다. 우리가 고칠 수 없으므로
            # **여기 한 줄에만 선언하고 넘긴다** (D-0219 · D-0263).
            tags = ID3(path)  # type: ignore[no-untyped-call]
        except ID3NoHeaderError:
            frame_counter["<NO_ID3_HEADER>"] += 1
            continue
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            continue

        keys = set(tags.keys())  # type: ignore[no-untyped-call]
        prefixes = {k.split(":")[0] for k in keys}
        for prefix in prefixes:
            frame_counter[prefix] += 1
        if "TSRC" in prefixes:
            has_isrc += 1
        if "USLT" in prefixes:
            has_uslt += 1
        if "SYLT" in prefixes:
            has_sylt += 1
        found = [f for f in DATE_FRAMES if f in prefixes]
        if found:
            has_any_date += 1
            date_counter["+".join(found)] += 1

    total = len(files)
    print(f"총 파일: {total}")
    print(f"읽기 실패: {len(failures)}")
    print(f"파일명 NFD(비정규화): {nfd_names}")
    print()
    print("=== 핵심 지표 ===")
    for label, count in (
        ("발매일 프레임 보유", has_any_date),
        ("ISRC(TSRC)", has_isrc),
        ("가사 USLT", has_uslt),
        ("동기가사 SYLT", has_sylt),
    ):
        pct = (count / total * 100) if total else 0.0
        print(f"{label:22s} {count:5d} / {total}  ({pct:5.1f}%)")
    print()
    print("=== 발매일 프레임 조합 ===")
    for combo, count in date_counter.most_common():
        print(f"  {combo:28s} {count:5d}")
    print()
    print("=== 전체 프레임 히스토그램 ===")
    for frame, count in frame_counter.most_common():
        pct = (count / total * 100) if total else 0.0
        print(f"  {frame:12s} {count:5d}  ({pct:5.1f}%)")
    if failures:
        print()
        print("=== 실패 샘플(최대 10) ===")
        for name, detail in failures[:10]:
            print(f"  {name}: {detail}")

    if args.emit:
        # **`sys.path`를 손대지 않는다** — 같은 `tools/`에 있으므로 그냥 들어온다.
        import measured

        print()
        changed = measured.emit("id3", {name: count for name, count in frame_counter.items()})
        for line in changed or ["바뀐 수가 없다"]:
            print(f"  {line}")
        print(f"정본 {measured.CANON.relative_to(measured.ROOT)} · 곡 {total}")
        print("  `python3 tools/measured.py --fix`로 거울을 맞춘다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
