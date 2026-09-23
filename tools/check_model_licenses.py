#!/usr/bin/env python3
"""코드가 부르는 모델 가중치가 **상업 제품에 갈 수 있는가** (D-0217).

### 왜 필요한가

목표가 남들이 쓰는 제품이 됐다 (D-0215). 엔진 후보의 라이선스를 보다가 **이미 쓰고
있는 것**을 봤다 — `m-a-p/MERT-v1-95M`이 **CC-BY-NC-4.0**이다. 검색 M1 20.4배
(D-0027)와 화성 `layer03`(D-0181)이 전부 그 위에 서 있고 **백칠십 건의 결정 동안
아무도 라이선스를 안 봤다.**

### 망 접점과 같은 모양이다

`check_egress`가 *"구멍이 하나일 때 못 박아 두면 두 번째 구멍은 이 검사를 지나야
생긴다"*로 접점을 센다. 여기서는 **가중치를 센다.** 표에 없는 모델을 부르면 빨개지고,
표에 올리려면 **라이선스와 상업 가부를 적어야 한다.**

### 비상업을 막지는 않는다

지금은 연구 단계이고 MERT를 빼면 D-0027부터 다시 재야 한다. **막는 대신 센다** —
상업 불가가 몇 개인지 매번 찍고, 검사 코드가 그 집합을 이름으로 못 박는다. 하나가
늘면 리뷰에 걸린다.

### `unknown`을 둔다

`htdemucs`는 코드가 MIT인데 **가중치의 라이선스가 따로 안 적혀 있다.** 코드 라이선스를
가중치에 넘겨 *"된다"*고 적으면 그것이 추측이다 (GR-0.5). 모르는 것은 모른다고 둔다.

    python3 tools/check_model_licenses.py            # 검사한다
    python3 tools/check_model_licenses.py --list     # 표를 찍는다
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TREES = ("core/hathor",)
"""**제품 코드만 본다.** 도구와 검사는 제품에 안 실린다."""

MODEL = re.compile(r"""^\s*DEFAULT_MODEL\s*=\s*["']([^"']+)["']""", re.M)
"""모델을 부르는 자리. **이 저장소는 전부 `DEFAULT_MODEL` 한 이름으로 적는다** — 셋 다
그렇다. 다른 이름으로 적으면 이 검사가 못 보므로 규약이 된다."""

COMMERCIAL = ("yes", "no", "unknown")

LICENSES: dict[str, tuple[str, str, str]] = {
    "m-a-p/MERT-v1-95M": (
        "CC-BY-NC-4.0",
        "no",
        "검색(D-0027) · 화성 layer03(D-0181)의 기반. **제품 경로에 못 간다** (O-68)",
    ),
    "laion/larger_clap_music": (
        "Apache-2.0",
        "yes",
        "MERT 대체 후보 — 같은 하네스로 나란히 잰다 (O-68 · D-0231)",
    ),
    "BAAI/bge-m3": ("MIT", "yes", "가사 임베딩 (D-0048)"),
    "htdemucs": (
        "코드 MIT · 가중치 미명시",
        "unknown",
        "스템 분리 (D-0018). **가중치 라이선스가 따로 안 적혀 있다**",
    ),
}
"""모델 → (라이선스, 상업 가부, 사유). **HF 모델 카드에서 읽은 값이다** (2026-09-22)."""


def found_models() -> dict[str, str]:
    """`모델 이름 → 처음 나온 파일`."""
    found: dict[str, str] = {}
    for tree in TREES:
        base = ROOT / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for name in MODEL.findall(path.read_text(encoding="utf-8")):
                found.setdefault(name, path.relative_to(ROOT).as_posix())
    return found


def check() -> list[str]:
    problems: list[str] = []
    found = found_models()
    for name, where in sorted(found.items()):
        if name not in LICENSES:
            problems.append(
                f"{where}: {name}의 라이선스가 표에 없다. 모델 카드를 읽고 적는다 (D-0217)"
            )
    for name, (_, commercial, _) in sorted(LICENSES.items()):
        if commercial not in COMMERCIAL:
            problems.append(f"{name}: 상업 가부는 {COMMERCIAL} 중 하나다 — {commercial!r}")
        if name not in found:
            problems.append(f"표의 {name}을 코드가 안 부른다. 지웠으면 표에서도 뺀다")
    return problems


def blocked() -> list[str]:
    """상업 제품에 못 가는 모델. **`unknown`은 여기 안 넣는다** — 막힌 것이 아니라 모른다."""
    return sorted(name for name, (_, flag, _) in LICENSES.items() if flag == "no")


def main() -> int:
    parser = argparse.ArgumentParser(description="모델 가중치 라이선스 검사 (D-0217)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="표를 찍는다")
    args = parser.parse_args()

    if args.list:
        for name, (license_name, flag, reason) in sorted(LICENSES.items()):
            print(f"  {name}  [{flag}]  {license_name}\n      {reason}")
        return 0

    problems = check()
    if problems:
        print(f"모델 라이선스 규약에 문제가 {len(problems)}건 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    unknown = sum(1 for _, flag, _ in LICENSES.values() if flag == "unknown")
    print(
        f"모델 라이선스 검사 통과 · 모델 {len(LICENSES)}개"
        f" · 상업 불가 {len(blocked())} · 미확인 {unknown}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
