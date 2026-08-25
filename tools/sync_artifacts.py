#!/usr/bin/env python3
"""산출물 교두보 동기화 (D-0118).

### 왜 필요한가

`var/`는 `.gitignore`에 있고 **기기 간에 옮길 방법이 없었다.** 리전에서 1시간 40분
걸려 뽑은 스템 크로마가 광인사에 없고, `doctor`는 "리전에서 다시 뽑아라"만 알렸다.
**이미 있는 것을 다시 만들라고 시키고 있었다.**

크기 문제가 아니다. 스템 오디오는 저장하지 않고 크로마만 저장하므로(D-0074)
산출물 전체가 수십 MB다. **옮기는 규약만 없었다.**

### 덮어쓰지 않는다

교두보는 **추가 전용**이다. 목적지에 같은 이름이 있으면 건너뛴다.

산출물 이름에 스탬프가 박혀 있어(`keys-<스탬프>.keys.jsonl`) 서로 다른 실행이
같은 이름을 낼 수 없고, 시계열은 곡별 npz라 같은 이름이면 같은 내용이다.
**그래서 양방향이 안전하다** — 어느 쪽이 최신인지 사람이 판단할 일이 없다.
정말 갈아치우려면 손으로 지운다. 조용히 덮는 것보다 낫다.

### 반쯤 복사된 파일을 남기지 않는다

`.part`로 받아 다 받은 뒤 이름을 바꾼다. 중간에 SSD가 빠지면 `.part`가 남고
다음 실행이 다시 받는다. **덮어쓰지 않는 규칙 때문에 반쪽짜리가 한 번 생기면
영원히 건너뛴다** — 그 자리를 이 방식이 막는다.

    python3 tools/sync_artifacts.py status
    python3 tools/sync_artifacts.py push --dry-run
    python3 tools/sync_artifacts.py pull
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE_ENV = "HATHOR_ARTIFACT_STORE"
SUBTREE = Path("var") / "ingest"
"""옮기는 것은 `var/ingest`뿐이다.

`var/out`의 MIDI는 시드만 있으면 그 자리에서 다시 만들어지므로 옮길 이유가 없다.
"""

PART = ".part"


def dotenv() -> dict[str, str]:
    """`.env`를 읽는다. **셸에 이미 있는 값은 덮지 않는다** (D-0066)."""
    found: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        found[key.strip()] = value.strip().strip("\"'")
    return found


def store_root() -> Path | None:
    value = os.environ.get(STORE_ENV) or dotenv().get(STORE_ENV)
    return Path(value).expanduser() if value else None


def walk(base: Path) -> dict[str, int]:
    """`상대경로 → 바이트`. **경로 구분자는 항상 `/`다** (D-0009)."""
    if not base.is_dir():
        return {}
    return {
        path.relative_to(base).as_posix(): path.stat().st_size
        for path in sorted(base.rglob("*"))
        if path.is_file() and not path.name.endswith(PART)
    }


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}GB"


def copy_one(source: Path, target: Path) -> None:
    """`.part`로 받고 다 받으면 이름을 바꾼다. **원자적으로 끝난다.**"""
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + PART)
    shutil.copy2(source, staging)
    staging.replace(target)


def transfer(source_base: Path, target_base: Path, label: str, dry_run: bool) -> int:
    have = walk(source_base)
    if not have:
        print(f"{source_base}에 옮길 것이 없다", file=sys.stderr)
        return 1
    already = walk(target_base)

    todo = sorted(set(have) - set(already))
    skipped = sorted(set(have) & set(already))
    volume = sum(have[name] for name in todo)

    print(f"{label}: {source_base}  ->  {target_base}")
    print(f"  보낼 것 {len(todo)}개 ({human(volume)}) · 이미 있음 {len(skipped)}개")
    for name in todo[:8]:
        print(f"    + {name}  {human(have[name])}")
    if len(todo) > 8:
        print(f"    + ... {len(todo) - 8}개 더")

    if dry_run:
        print("  --dry-run이라 아무것도 쓰지 않았다")
        return 0
    if not todo:
        print("  전부 있다. 아무것도 하지 않았다 (멱등)")
        return 0

    for name in todo:
        copy_one(source_base / name, target_base / name)
    print(f"  완료. {len(todo)}개 ({human(volume)})")
    return 0


def status(local: Path, remote: Path | None) -> int:
    here = walk(local)
    print(f"저장소  {local}")
    print(f"  {len(here)}개 · {human(sum(here.values()))}")
    if remote is None:
        print(f"\n{STORE_ENV}가 없다. `.env`에 한 줄 적는다:")
        print(f"  {STORE_ENV}=/mnt/e/hathor-artifacts   # SSD 마운트 지점")
        return 1
    there = walk(remote)
    print(f"\n교두보  {remote}")
    if not remote.is_dir():
        print("  !! 없다. SSD가 안 붙었거나 경로가 틀렸다")
        return 1
    print(f"  {len(there)}개 · {human(sum(there.values()))}")
    print(f"\n  교두보에만 {len(set(there) - set(here))}개 · 여기에만 {len(set(here) - set(there))}개")
    if set(there) - set(here):
        print("  가져오려면: make artifacts-pull")
    if set(here) - set(there):
        print("  보내려면:   make artifacts-push")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="산출물 교두보 동기화 (D-0118)")
    parser.add_argument("action", choices=("push", "pull", "status"))
    parser.add_argument("--store", type=Path, default=None, help=f"교두보 경로. 없으면 {STORE_ENV}")
    parser.add_argument("--dry-run", action="store_true", help="쓰지 않고 무엇이 갈지만 본다")
    args = parser.parse_args()

    local = ROOT / SUBTREE
    remote_root = args.store if args.store else store_root()

    if args.action == "status":
        return status(local, remote_root / SUBTREE if remote_root else None)

    if remote_root is None:
        print(f"{STORE_ENV}가 없다. `.env`에 적거나 --store로 준다.", file=sys.stderr)
        print(f"  {STORE_ENV}=/mnt/e/hathor-artifacts", file=sys.stderr)
        return 2
    remote = remote_root / SUBTREE

    if args.action == "push":
        return transfer(local, remote, "보냄", args.dry_run)
    if not remote.is_dir():
        print(f"교두보에 산출물이 없다: {remote}", file=sys.stderr)
        print("  SSD가 붙어 있는지, 리전에서 push했는지 본다.", file=sys.stderr)
        return 1
    return transfer(remote, local, "가져옴", args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
