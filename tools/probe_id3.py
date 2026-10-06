"""ID3 프레임 전수 히스토그램. **`--emit`이 실측 정본의 `counts`를 다시 쓴다** (D-0366).

예전엔 사람이 읽는 글만 찍었고 **사람이 그 수를 `MASTER.md`로 옮겨 적었다.** 옮겨 적은
수는 낡는다 (GR-0.7). 지금은 이 도구가 `docs/measured.toml`의 `[id3.counts]`를 직접
쓰고, `tools/measured.py`가 거기서 표를 찍어 낸다.

    cd core && uv run python ../tools/probe_id3.py          # 사람이 읽는 전수
    cd core && uv run python ../tools/probe_id3.py --emit    # 정본의 counts를 갈아 넣는다
    make measure                                              # 둘 다 + 거울 (D-0374)

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
from mutagen.mp3 import MP3  # noqa: E402

from hathor.shared.config.paths import library_root, load_dotenv  # noqa: E402

DATE_FRAMES = ("TDRC", "TDRL", "TDOR", "TYER", "TDAT", "TORY")


ID3_RULER = "2026-10-04"
"""`[id3.counts]`를 낸 자의 이름 (D-0374). 프레임 보유 여부는 첫 판부터 같다."""

ID3_EMITS = (
    "TIT2", "TPE1", "TALB", "USLT", "APIC", "POPM", "TSSE", "TSOA", "TSOP", "TSOT",
    "TDRC", "TDRL", "TYER", "TDAT", "TSRC", "SYLT", "TRCK", "TPE2", "TCON", "TPOS",
)  # fmt: skip
"""`[id3.counts]`에 넣는 프레임. **히스토그램은 이보다 많이 세고 정본은 이만큼만 든다.**"""

CORPUS_RULER = "2026-10-06"
"""`[corpus.counts]`를 낸 자의 이름 (D-0374).

**2026-10-06에 바뀌었다** — `filename_convention`이 「하이픈이 있나」에서 「태그의
아티스트로 시작하나」가 됐다. 전자는 전수가 1004/1004라 **아무것도 안 재는 자**였다
(D-0230). 그래서 이 블록은 **다시 재야 한다.**
"""

CORPUS_EMITS = (
    "seconds", "bytes", "44.1kHz", "48kHz", "mp3",
    "read_failures", "nfd_names", "filename_convention",
)  # fmt: skip
"""`[corpus.counts]`에 넣는 수 (D-0371).

**D-0366이 이 블록도 상류 없이 뒀다.** 여덟 개가 「백분율에서 거꾸로 푼 수」로 서
있었고 `artist`만 남은 줄 알았다 — 세 블록 중 **둘**이었다. 파일을 한 번만 걷도록
여기서 같이 센다.
"""


def artist_of(tags: object) -> str:
    """`TPE1`의 글자. 없으면 빈 문자열."""
    frame = getattr(tags, "get", lambda _k: None)("TPE1")
    return str(frame).strip() if frame is not None else ""


def named(stem: str, tags: object) -> bool:
    """파일명이 `<TPE1>-…` 꼴인가 (D-0374).

    **이름 안의 하이픈과 안 싸운다.** 첫 하이픈에서 자르면 `G-DRAGON`이 `G`가 되고
    `probe_artist`가 그것을 **불일치 16곡**으로 찍었다 — 거짓 경보다 (GR-0.8).
    """
    artist = artist_of(tags)
    return bool(artist) and stem.startswith(f"{artist}-")


def main() -> int:
    parser = argparse.ArgumentParser(description="ID3 프레임 · 코퍼스 전수 (D-0366 · D-0371)")
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
    corpus: Counter[str] = Counter()
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
        # **코퍼스 수도 같은 걸음에서 센다** (D-0371). 1004개를 두 번 걷지 않는다.
        corpus["mp3"] += 1
        corpus["bytes"] += path.stat().st_size
        # **못 읽은 파일은 길이·샘플레이트를 안 더한다.** 0으로 더하면 합이 조용히
        # 줄고 그 줄어듦을 아무도 못 본다 (GR-0.5). 실패는 아래 ID3 열기와 **같은
        # 이름 집합**에 넣는다 — 한 파일이 둘 다 실패해도 하나로 센다.
        try:
            info = MP3(path).info  # type: ignore[no-untyped-call]
        except Exception as exc:  # mutagen이 내는 예외가 한 종류가 아니다
            failures.append((name, f"MP3.info {type(exc).__name__}: {exc}"))
        else:
            if info is None:
                failures.append((name, "MP3.info가 없다"))
            else:
                corpus["seconds"] += round(info.length)
                rate = {44100: "44.1kHz", 48000: "48kHz"}.get(info.sample_rate)
                if rate:
                    corpus[rate] += 1
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

        # **파일명 규칙은 태그로 본다** (D-0374). 「하이픈이 있나」는 `G-DRAGON-무제.mp3`도
        # 통과시키고 **전수가 1004/1004가 된다** — 늘 100%인 자는 아무것도 안 재는 자다
        # (D-0230). 태그의 아티스트로 시작하는지 보면 이름 안의 하이픈과 안 싸운다.
        if named(path.stem, tags):
            corpus["filename_convention"] += 1

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
        corpus["read_failures"] = len({name for name, _why in failures})
        corpus["nfd_names"] = nfd_names
        changed = measured.emit("id3", {name: count for name, count in frame_counter.items()})
        changed += measured.emit("corpus", {name: count for name, count in corpus.items()})
        for line in changed or ["바뀐 수가 없다"]:
            print(f"  {line}")
        print(f"정본 {measured.CANON.relative_to(measured.ROOT)} · 곡 {total}")
        print("  `python3 tools/measured.py --fix`로 거울을 맞춘다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
