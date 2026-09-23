#!/usr/bin/env python3
"""저장소 글자와 개행이 한 규격인가 (D-0230).

### 왜 필요한가

여기는 **윈도와 WSL을 오간다.** 패치는 윈도 다운로드 폴더에서 오고(D-0070), 편집은 WSL에서
하며, 일부 파일은 윈도가 직접 읽는다. 그 경계에서 새는 것이 넷이다 — BOM · CRLF · 비 UTF-8 ·
끝 개행 없음. **`.gitattributes`는 커밋 시점에만 개입한다.** 이미 들어온 것과 작업 트리의 것은
못 잡으므로 검사가 따로 선다. fire-lane이 같은 검사를 `verify.sh`에 달고 있다.

| 무엇 | 왜 문제인가 |
|---|---|
| BOM | 첫 줄이 `\\ufeff…`가 되어 첫 열 이름 · 첫 명령이 깨진다 |
| CRLF | diff가 통째로 바뀌고 셸 스크립트가 `\\r` 때문에 안 돈다 |
| 비 UTF-8 | 한글 문서가 열리지 않는다 — 이 저장소는 문서가 한글이다 |
| 끝 개행 없음 | 다음 출력이 붙고 `cat`이 줄을 잃는다 |

### 무엇을 안 보나

**`git`이 추적하지 않는 것**(산출물 · `.venv` · 캐시)과 **바이너리**(docx · png · npz)는 안 본다.
윈도가 직접 읽는 확장자(`.bat` · `.cmd` · `.ps1`)는 CRLF를 그대로 둔다 — 고치면 그쪽이 깨진다.

    python3 tools/encoding_check.py          # 검사한다
    python3 tools/encoding_check.py --fix    # BOM · CRLF · 끝 개행만 고친다
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOM = b"\xef\xbb\xbf"
CRLF_KEEP = {".bat", ".cmd", ".ps1"}
"""윈도가 직접 읽는다. CRLF가 규격이다."""

BINARY = {
    ".docx", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".npz", ".npy",
    ".zip", ".gz", ".ico", ".woff", ".woff2", ".mp3", ".flac", ".wav",
}  # fmt: skip
"""바이트가 정본인 것. 개행을 손대면 파일이 죽는다."""


def tracked(root: Path = ROOT) -> list[Path]:
    """`git`이 아는 파일만. 산출물과 캐시는 애초에 대상이 아니다."""
    done = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        return []
    return [root / name for name in done.stdout.split("\0") if name]


def looked_at(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() not in BINARY


def faults(data: bytes, suffix: str) -> list[str]:
    """이 바이트열의 위반. **빈 파일은 위반이 없다** — 끝 개행을 물을 줄이 없다."""
    if not data:
        return []
    found: list[str] = []
    if data.startswith(BOM):
        found.append("BOM")
    if b"\r\n" in data and suffix.lower() not in CRLF_KEEP:
        found.append("CRLF")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        found.append("비 UTF-8")
    if not data.endswith(b"\n"):
        found.append("끝 개행 없음")
    return found


def repaired(data: bytes, suffix: str) -> bytes:
    """고칠 수 있는 셋만 고친다.

    **비 UTF-8은 안 고친다** — 어느 인코딩인지 짐작하면 글자가 깨진다.
    """
    fixed = data.removeprefix(BOM)
    if suffix.lower() not in CRLF_KEEP:
        fixed = fixed.replace(b"\r\n", b"\n")
    if fixed and not fixed.endswith(b"\n"):
        fixed += b"\n"
    return fixed


def scan(root: Path = ROOT) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    for path in tracked(root):
        if not looked_at(path):
            continue
        bad = faults(path.read_bytes(), path.suffix)
        if bad:
            found.append((path.relative_to(root).as_posix(), bad))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="글자 · 개행 검사 (D-0230)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--fix", action="store_true", help="BOM · CRLF · 끝 개행을 고친다")
    args = parser.parse_args()

    problems = scan()
    if args.fix:
        fixed = 0
        for name, bad in problems:
            if bad == ["비 UTF-8"]:
                continue
            path = ROOT / name
            path.write_bytes(repaired(path.read_bytes(), path.suffix))
            fixed += 1
        print(f"{fixed}개를 고쳤다. 비 UTF-8은 손으로 본다")
        problems = scan()
    if problems:
        print(f"글자 · 개행 규격을 어긴 파일 {len(problems)}개.", file=sys.stderr)
        for name, bad in problems:
            print(f"  - {name}: {' · '.join(bad)}", file=sys.stderr)
        print("고치려면 `python3 tools/encoding_check.py --fix`", file=sys.stderr)
        return 1
    print(f"글자 · 개행 검사 통과 · 추적 텍스트 {sum(1 for p in tracked() if looked_at(p))}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
