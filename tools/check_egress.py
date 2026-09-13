#!/usr/bin/env python3
"""오디오가 기기를 떠날 수 있는 자리가 몇 개인가 (D-0015 · D-0134).

### 왜 필요한가

D-0015가 **오디오 비이동**을 불변 조건으로 두면서 이렇게 적었다.

    강제 수단은 정책 문구가 아니라 스키마다. 서버 수신 스키마에 오디오 필드를
    정의하지 않으면 전송 자체가 타입 수준에서 불가능해진다.

**그 스키마가 없다.** `interfaces/rest/`는 0줄이고 서버가 아직 없다. D-0132가
`강제자`를 전수로 채우면서 이 결정이 **설계 판단이며 고정할 동작이 없다**로
나왔다 — 프로젝트에서 어기면 가장 나쁜 규약인데 아무것도 지키지 않고 있었다.

### 서버가 없어도 강제할 수 있다

스키마를 못 만드는 이유는 서버가 없기 때문인데, **나갈 구멍을 세는 것은 지금 된다.**
실측하니 망을 타는 파일이 **하나**다 — `musicbrainz_lookup.py`이며 아티스트·제목
문자열로 질의한다.

**구멍이 하나일 때 그것을 못 박아 두면, 두 번째 구멍은 이 검사를 지나야 생긴다.**
서버가 생기는 날 이 목록에 한 줄이 늘고 그 줄이 리뷰 대상이 된다.

### 무엇을 보는가

`core/hathor`의 모든 파일에서 **망 라이브러리 임포트**를 찾는다. 허용 목록 밖이면
실패한다. 허용 목록은 **사유와 무엇을 보내는지**를 함께 적는다.

`import-linter`의 `송신부는 오디오를 모른다` 계약이 나머지 절반이다 — 이 검사는
**구멍의 개수**를, 계약은 **그 구멍이 오디오에 닿는지**를 본다.

### 무엇을 안 보는가

**파일을 여는 것은 안 본다.** 로컬 분석은 당연히 음원을 읽는다. 막으려는 것은
**기기 밖으로 나가는 것**이다.

**서브프로세스는 안 본다.** `ffmpeg`가 망을 탈 수 있지만 인자를 정적으로 판정할 수
없다. **오탐이 많은 검사는 꺼진다** (D-0126 · D-0129).

    python3 tools/check_egress.py            # 검사한다
    python3 tools/check_egress.py --list     # 허용된 접점을 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "core" / "hathor"

NETWORK = ("urllib", "requests", "httpx", "socket", "aiohttp", "http.client", "ftplib", "smtplib")
"""망 라이브러리. **`urllib.parse`만 쓰는 것도 잡는다** — 파서만 쓰는지 요청도 보내는지
가르려면 호출을 따라가야 하고, 접점 파일이 하나뿐인 지금은 **넓게 잡는 쪽이 싸다.**"""

ALLOWED = {
    "infrastructure/musicbrainz_lookup.py": (
        "MusicBrainz 조회 (D-0006). **아티스트·제목 문자열만 보낸다.** "
        "응답은 MBID와 재생시간이며 오디오는 어느 방향으로도 흐르지 않는다"
    ),
}
"""망을 타도 되는 자리. **사유와 보내는 것을 함께 적는다.**

**늘리지 않는 것이 목표다.** 한 줄이 늘면 오디오가 나갈 수 있는 자리가 하나 는다.
서버를 붙이는 날 여기에 줄이 생기고, 그때 D-0015의 스키마가 함께 와야 한다."""

IMPORT = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.M)


def check() -> list[str]:
    """허용 목록 밖의 망 접점. **첫 문제에서 멈추지 않는다.**"""
    problems: list[str] = []
    for path in sorted(TREE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        name = path.relative_to(TREE).as_posix()
        found = sorted(
            {
                module
                for module in IMPORT.findall(path.read_text(encoding="utf-8"))
                if module.split(".")[0] in NETWORK or module in NETWORK
            }
        )
        if found and name not in ALLOWED:
            joined = " · ".join(found)
            problems.append(
                f"core/hathor/{name}: 망 라이브러리 {joined}를 쓴다. "
                "허용 목록에 사유와 보내는 것을 적거나 쓰지 않는다 (D-0015)"
            )
    for name in sorted(ALLOWED):
        if not (TREE / name).exists():
            problems.append(f"허용 목록의 {name}이 없다. 지웠으면 목록에서도 뺀다")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="망 송신 접점 검사 (D-0134)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="허용된 접점을 찍는다")
    args = parser.parse_args()

    if args.list:
        for name, reason in sorted(ALLOWED.items()):
            print(f"  core/hathor/{name}\n      {reason}")
        return 0

    problems = check()
    if problems:
        print(f"허용되지 않은 망 접점이 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"망 접점 검사 통과 · 허용 {len(ALLOWED)}곳")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
