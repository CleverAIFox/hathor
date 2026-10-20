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
TREES = ("core/hathor", "tools")
"""훑을 나무. **`tools`도 본다** (D-0146).

D-0134는 `core/hathor`만 봤다. 전수로 훑으니 `tools/probe_musicbrainz.py`가 `urllib`을
쓰고 있었고 **검사 밖이었다.** 도구도 이 기기에서 돈다."""

NETWORK = (
    "urllib",
    "requests",
    "httpx",
    "socket",
    "aiohttp",
    "http.client",
    "ftplib",
    "smtplib",
    "mlflow",
    "prefect",
)
"""망 라이브러리. **`urllib.parse`만 쓰는 것도 잡는다** — 파서만 쓰는지 요청도 보내는지
가르려면 호출을 따라가야 하고, 접점이 손에 꼽는 지금은 **넓게 잡는 쪽이 싸다.**

**`mlflow` · `prefect`도 센다** (D-0224). 둘 다 서버에 HTTP로 붙는 클라이언트인데 이름에
`requests`가 안 보인다 — 여기 없으면 새 구멍이 검사를 그냥 지난다."""

ALLOWED = {
    "tools/probe_musicbrainz.py": (
        "MusicBrainz 조회 탐침 (D-0019). **아티스트·제목 문자열만 보낸다.** "
        "제품 경로가 아니라 조사용이며 오디오를 만지지 않는다"
    ),
    "core/hathor/infrastructure/musicbrainz_lookup.py": (
        "MusicBrainz 조회 (D-0006). **아티스트·제목 문자열만 보낸다.** "
        "응답은 MBID와 재생시간이며 오디오는 어느 방향으로도 흐르지 않는다"
    ),
    "tools/watch_papers.py": (
        "arXiv 신규 논문 훑기 (D-0424). **분야 이름과 날짜만 보낸다.** "
        "라이브러리도 곡 이름도 취향도 나가지 않으며 받기만 한다"
    ),
    "tools/mlflow_sync.py": (
        "평가 리포트 → MLflow (D-0224). **평가 숫자와 라벨만 보낸다.** "
        "로컬 주소가 아니면 거절하고 사용 통계를 끈다"
    ),
    "tools/prefect_flow.py": (
        "인제스트 흐름 → Prefect (D-0224). **단계 이름 · 상태 · 로그만 보낸다.** "
        "로컬 주소가 아니면 거절하고 사용 통계를 끈다"
    ),
}
"""망을 타도 되는 자리. **사유와 보내는 것을 함께 적는다.**

**늘리지 않는 것이 목표다.** 한 줄이 늘면 오디오가 나갈 수 있는 자리가 하나 는다.
어디로 가는지는 아래 `OUTWARD`가 가른다 — **이 글로 세지 않는다** (D-0446).
서버를 붙이는 날 여기에 줄이 생기고, 그때 D-0015의 스키마가 함께 와야 한다."""

OUTWARD = frozenset(
    {
        "tools/probe_musicbrainz.py",
        "core/hathor/infrastructure/musicbrainz_lookup.py",
        "tools/watch_papers.py",
    }
)
"""**기기 밖으로 나가는** 접점. 나머지는 로컬 주소만 받는다 (D-0224).

이 집합이 없던 동안 내역은 **글로만 있었다.** D-0424가 `watch_papers`를 `ALLOWED`에
넣고 **바로 위 문단은 안 고쳤다** — 그 문단도, `MASTER` 두 줄도, `README` 한 줄도
*«밖 둘 · 로컬 둘»*로 남았다. `README`는 **한 줄 안에서 「5곳 (밖 2 · 로컬 2)」**이었고
축은 `5`만 읽어 초록이었다 (D-0126: 안 걸면 안 돈다).

**내역을 데이터로 둔다.** 그래야 `doc_counts`가 밖과 로컬을 따로 세고, 글이 썩으면
운다. 줄을 더할 때 여기 넣을지 말지를 **반드시 한 번 고르게 되는 것**이 목적이다."""

IMPORT = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.M)


def found_files() -> list[Path]:
    """훑을 파일 전부."""
    picked: list[Path] = []
    for tree in TREES:
        base = ROOT / tree
        if base.is_dir():
            picked.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return picked


def check() -> list[str]:
    """허용 목록 밖의 망 접점. **첫 문제에서 멈추지 않는다.**"""
    problems: list[str] = []
    for path in sorted(found_files()):
        name = path.relative_to(ROOT).as_posix()
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
                f"{name}: 망 라이브러리 {joined}를 쓴다. "
                "허용 목록에 사유와 보내는 것을 적거나 쓰지 않는다 (D-0015)"
            )
    for name in sorted(ALLOWED):
        if not (ROOT / name).exists():
            problems.append(f"허용 목록의 {name}이 없다. 지웠으면 목록에서도 뺀다")
    return problems


def pairing_problems() -> list[str]:
    """`OUTWARD`가 `ALLOWED` 밖을 가리키는가 (D-0446).

    **`check()`에 안 넣는다.** 저쪽은 *나무를 훑어* 안 적힌 접점을 찾는 일이고 시험이
    `ALLOWED`를 비워 두고 부른다 — 거기 끼우면 **심은 나무마다 이 경고가 세 줄씩**
    따라 나와 진짜 발견을 덮는다. 이것은 나무가 아니라 **두 상수 사이의 약속**이다.

    어긋나면 밖과 로컬의 합이 총합과 안 맞고, 그 둘을 세는 축이 조용히 틀린 수를 낸다.
    """
    return [
        f"`OUTWARD`의 {name}이 허용 목록에 없다. 둘이 어긋났다 (D-0446)"
        for name in sorted(OUTWARD - set(ALLOWED))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="망 송신 접점 검사 (D-0134)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="허용된 접점을 찍는다")
    args = parser.parse_args()

    if args.list:
        for name, reason in sorted(ALLOWED.items()):
            print(f"  {name}\n      {reason}")
        return 0

    problems = pairing_problems() + check()
    if problems:
        print(f"허용되지 않은 망 접점이 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    # **내역을 같이 찍는다** (D-0446). 총합만 올리면 밖이 둘인지 셋인지 화면으로 못
    # 가르고, 그 틈에서 문서 네 자리가 *«밖 둘»*로 썩었다.
    print(
        f"망 접점 검사 통과 · 허용 {len(ALLOWED)}곳 · "
        f"밖 {len(OUTWARD)}곳 · 로컬 {len(ALLOWED) - len(OUTWARD)}곳"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
