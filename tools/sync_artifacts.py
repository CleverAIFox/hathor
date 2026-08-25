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


ATTACHED = "붙어 있다"
EMPTY = "아직 비었다"
MISSING = "안 붙었다"


def can_write(store: Path) -> tuple[bool, str]:
    """**진짜로 써 본다** (D-0120).

    `os.access`는 DrvFs에서 참을 내고도 실제 쓰기가 막힐 수 있다. 6036개 목록을
    찍은 뒤 첫 파일에서 죽는 것보다 **한 바이트를 먼저 써 보는 것이 싸다.**

    실제로 옮길 때와 같은 순서(쓰기 → 이름 바꾸기)를 밟는다. 순서가 다르면
    통과하고도 본작업에서 죽는다.
    """
    probe_file = store / f".hathor-probe{PART}"
    try:
        probe_file.write_bytes(b"x")
        probe_file.replace(store / ".hathor-probe")
        (store / ".hathor-probe").unlink()
    except OSError as failure:
        return False, failure.strerror or str(failure)
    return True, ""


def probe(store: Path | None) -> tuple[str, str]:
    """교두보가 **어느 상태인지** 가른다 (D-0119).

    D-0118은 이 셋을 한 메시지로 뭉쳐 `!! 없다. SSD가 안 붙었거나 경로가 틀렸다`를
    냈다. **처음이라 비어 있을 때도 그렇게 말해서** 붙어 있는 SSD를 안 붙었다고
    읽게 만들었다. **가장 흔한 경우가 가장 무서운 문구를 받고 있었다.**
    """
    if store is None:
        return MISSING, f"{STORE_ENV} 미설정. `.env`에 한 줄 적는다"
    if not store.is_dir():
        return MISSING, f"{store} 가 없다. SSD가 안 붙었거나 경로가 틀렸다"
    writable, why = can_write(store)
    if not writable:
        return MISSING, f"{store} 에 쓸 수 없다 — {why}"
    if not (store / SUBTREE).is_dir():
        return EMPTY, f"{store}  (아직 비었다. 첫 push가 만든다)"
    return ATTACHED, str(store)


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
    """`.part`로 받고 다 받으면 이름을 바꾼다. **원자적으로 끝난다.**

    **`copy2`가 아니라 `copyfile`이다** (D-0120). `copy2`는 내용을 옮긴 뒤 권한과
    시각까지 옮기려고 `chmod`를 부르는데, **윈도우 드라이브 마운트(DrvFs)는
    그것을 못 한다** — `Operation not permitted`가 나고 내용은 이미 옮겨진 뒤다.

    권한도 시각도 쓰지 않는다. `walk`가 이름과 크기만 보고, 산출물 이름에는
    스탬프나 내용 해시가 박혀 있다. **옮길 이유가 없는 것을 옮기다 죽고 있었다.**
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + PART)
    shutil.copyfile(source, staging)
    staging.replace(target)


def keep(names: dict[str, int], only: list[str] | None) -> dict[str, int]:
    """접두어로 거른다. **없으면 전부다** (D-0119).

    실측에서 산출물이 1.7GB · 17192개였다 (D-0118은 "수십 MB"라 적었고 30배 틀렸다).
    그중 O-37이 읽는 것은 `keys-*` 74MB뿐이다. **DrvFs에서는 크기보다 개수가 아프다.**
    """
    if not only:
        return names
    return {name: size for name, size in names.items() if name.startswith(tuple(only))}


def transfer(
    source_base: Path,
    target_base: Path,
    label: str,
    dry_run: bool,
    only: list[str] | None = None,
) -> int:
    have = keep(walk(source_base), only)
    if not have:
        where = f"{source_base}에 옮길 것이 없다"
        print(f"{where} (--only {' '.join(only)})" if only else where, file=sys.stderr)
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

    done = 0
    for name in todo:
        try:
            copy_one(source_base / name, target_base / name)
        except OSError as failure:
            # **역추적을 뿜지 않는다** (D-0119). 이 저장소의 다른 도구는 전부
            # `실패: ` 한 줄이며, 스택 4겹은 무엇을 해야 하는지 알려주지 않는다.
            print(f"\n실패: {name} 에서 멈췄다 — {failure.strerror or failure}", file=sys.stderr)
            print(f"  {done}개는 옮겼다. 고치고 다시 돌리면 이어받는다.", file=sys.stderr)
            return 1
        done += 1
    print(f"  완료. {done}개 ({human(volume)})")
    return 0


def status(local: Path, store: Path | None) -> int:
    """양쪽에 무엇이 있는지. **비었다고 실패로 치지 않는다** (D-0119)."""
    here = walk(local)
    print(f"저장소  {local}")
    print(f"  {len(here)}개 · {human(sum(here.values()))}")

    state, note = probe(store)
    print(f"\n교두보  {note}")
    if state == MISSING:
        if store is None:
            print(f"  {STORE_ENV}=/mnt/f/hathor-artifacts   # 기기마다 드라이브가 다르다")
        return 1
    if state == EMPTY:
        print("  보내려면:   make artifacts-push")
        return 0

    assert store is not None
    there = walk(store / SUBTREE)
    print(f"  {len(there)}개 · {human(sum(there.values()))}")
    incoming, outgoing = set(there) - set(here), set(here) - set(there)
    print(f"\n  교두보에만 {len(incoming)}개 · 여기에만 {len(outgoing)}개")
    if incoming:
        print("  가져오려면: make artifacts-pull")
    if outgoing:
        print("  보내려면:   make artifacts-push")
    if not incoming and not outgoing:
        print("  양쪽이 같다.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="산출물 교두보 동기화 (D-0118 · D-0119)")
    parser.add_argument("action", choices=("push", "pull", "status"))
    parser.add_argument("--store", type=Path, default=None, help=f"교두보 경로. 없으면 {STORE_ENV}")
    parser.add_argument("--dry-run", action="store_true", help="쓰지 않고 무엇이 갈지만 본다")
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="접두어",
        help="이 접두어로 시작하는 것만. 여러 번 줄 수 있다 (예: --only keys)",
    )
    args = parser.parse_args()

    local = ROOT / SUBTREE
    store = args.store if args.store else store_root()

    if args.action == "status":
        return status(local, store)

    # **파일을 하나도 쓰기 전에 교두보를 본다** (D-0119). D-0118은 17192개 목록을
    # 다 찍은 뒤 첫 복사에서 죽었다.
    state, note = probe(store)
    if state == MISSING:
        print(f"실패: 교두보를 쓸 수 없다 — {note}", file=sys.stderr)
        return 2
    assert store is not None
    remote = store / SUBTREE

    if args.action == "push":
        return transfer(local, remote, "보냄", args.dry_run, args.only)
    if state == EMPTY:
        print(f"실패: 교두보가 비었다 — {store}", file=sys.stderr)
        print("  리전에서 make artifacts-push를 먼저 돌린다.", file=sys.stderr)
        return 1
    return transfer(remote, local, "가져옴", args.dry_run, args.only)


if __name__ == "__main__":
    raise SystemExit(main())
