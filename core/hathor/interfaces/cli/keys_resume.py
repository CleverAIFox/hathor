"""`ingest keys`의 이어받기와 잠금 (D-0277).

**`main.py`에 있었다.** `_run_ingest_keys` 352줄을 떼어내려 하니 이 넷이 함께 따라왔다 —
조건 묶음 · 깨진 줄 허용치 · 배치 잠금 · 이어받을 파일 고르기. 넷이 한 덩어리로 «같은
조건의 산출물에 이어 쓴다»(D-0075 · D-0077)를 이룬다.

**이름의 밑줄을 뗐다.** 모듈이 갈리면 `_keys_settings`는 남의 사적 이름을 부르는 것이 된다.

**잠금은 여기 없다** (D-0278). `BatchLock`이 이 자리에 있었는데 **파일 잠금은 인프라다** —
`infrastructure/batch_lock.py` 하나로 합쳤다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from hathor.domain.services.stem_sets import STEM_SETS

if TYPE_CHECKING:
    import argparse


def keys_settings(args: argparse.Namespace) -> dict[str, object]:
    """행에 적히는 조건 묶음. 이어받기 판정과 기록이 같은 값을 쓴다.

    **이것이 «이어받기가 같다고 볼 조건»이다** (D-0075). 하나라도 다르면 새 파일을 연다 —
    조건이 섞인 산출물은 무엇을 잰 것인지 알 수 없고, 그것이 D-0073에서 조건을 행에 적게
    만든 이유다. `limit`은 뺀다 — `--limit 200`으로 돌리다 전량으로 늘리는 것은 같은
    조건의 연장이다. **이 단락은 함수 위에 떠 있었고 파이썬이 버렸다** (D-0274).
    """
    return {
        # **`chroma`가 아니라 `chroma_mode`다.** 행에는 이미 `chroma`가 12차원
        # 벡터로 들어 있어 이름이 겹치면 조용히 덮이고, 그러면 이어받기가 영영
        # 안 걸린다. 실제로 그렇게 썼다가 잡았다.
        "chroma_mode": args.chroma,
        "profile": args.profile,
        "gamma": args.gamma,
        "harmonic": args.harmonic,
        "aggregate": args.aggregate,
        "separated": bool(args.separate),
        "halves": bool(args.halves),
        # **어떤 스템 조합을 뽑았는지가 조건이다** (D-0100). 예전에는 `separated`만
        # 있어서, `STEM_SETS`에 조합을 하나 더해도 "이미 전부 처리했다"로 건너뛰었다.
        # 실제로 D-0099가 `bass`를 더한 뒤 그 일이 났다 — **새 스템이 없는 파일에
        # 이어붙으려 했고, 없는 것을 찾다가 0곡이 됐다.**
        "stem_sets": sorted(STEM_SETS) if args.separate else [],
        # **시계열 창 길이도 조건이다** (D-0100). 다른 창으로 뽑은 산출물에
        # 이어붙으면 창 길이가 섞이고, 섞인 시계열은 무엇을 잰 것인지 알 수 없다.
        "series_seconds": args.series,
    }


BROKEN_LINE_TOLERANCE = 0.02
"""이어받을 때 견디는 깨진 줄 비율 (D-0077).

끊기면 **마지막 한 줄**이 잘려 있을 수 있고 그것은 정상이다. 그보다 많이 깨졌다면
동시 실행으로 줄이 섞였다는 뜻이며, **조용히 건너뛰면 49곡이 5곡으로 보인다.**
실제로 그렇게 됐고 그때는 파일이 이미 못 쓰게 된 뒤였다.
"""


def resume_target(out_root: Path, settings: dict[str, object]) -> tuple[Path, set[str], int]:
    """이어받을 파일과 이미 처리한 `source_key`를 낸다 (D-0075).

    **켜야 하는 옵션으로 두지 않는다.** `--resume`을 붙여야 이어받게 하면 붙이는 것을
    잊고, 잊으면 한 시간 반이 다시 사라진다. 조건이 같은 최근 파일이 있으면 그냥 잇고,
    조건이 하나라도 다르면 새 파일을 연다.

    깨진 줄은 건너뛴다. 중간에 끊기면 마지막 줄이 잘려 있을 수 있다.
    """
    import json
    from datetime import UTC, datetime

    # **후보가 열 개면 열 줄이 나온다** (D-0106). 가장 조건이 적게 다른 하나만 찍는다 —
    # 그것이 "무엇을 바꾸면 이어받는가"에 가장 가까운 답이다.
    skipped: list[tuple[str, list[str]]] = []
    if out_root.is_dir():
        for path in sorted(out_root.glob("keys-*.keys.jsonl"), reverse=True):
            done: set[str] = set()
            matched = False
            broken = 0
            total = 0
            try:
                with path.open(encoding="utf-8") as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        total += 1
                        try:
                            row = json.loads(line)
                        except ValueError:
                            broken += 1
                            continue  # 잘린 마지막 줄이면 정상, 많으면 손상이다
                        if not matched:
                            differing = [
                                key for key, value in settings.items() if row.get(key) != value
                            ]
                            if differing:
                                # **조용히 새 파일을 열지 않는다** (D-0100). 이어받기가
                                # 안 걸린 것을 모르면 한 시간 반을 다시 쓴다.
                                skipped.append((path.name, differing))
                                break
                            matched = True
                        source = row.get("source_key")
                        if source:
                            done.add(str(source))
            except OSError:
                continue
            if matched:
                return path, done, broken

    if skipped:
        name, differing = min(skipped, key=lambda entry: len(entry[1]))
        extra = f" (다른 후보 {len(skipped) - 1}개)" if len(skipped) > 1 else ""
        print(
            f"이어받지 않는다: {name} · 조건이 다르다 ({', '.join(differing)}){extra}",
            file=sys.stderr,
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return out_root / f"keys-{stamp}.keys.jsonl", set(), 0
