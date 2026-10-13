#!/usr/bin/env python3
"""**쓰는 배열마다 읽는 자리가 있나** (D-0395 · D-0350 · D-0126).

`ingest all`이 곡 하나를 묶음(`var/ingest/audio/<해시>.npz`)에 담을 때 배열 이름을
`<계열>/<소스>` 꼴로 짓는다 — `chroma/other` · `onset/drums` · `mert/bass/layer07`.
**이름은 코드가 짓고 문서가 인용한다.** 그 둘이 어긋나면 아무도 모른다.

### 어긋나 있었다

D-0392가 템포를 참조곡에서 뽑으면서 독스트링에 *«참조곡의 `onset/drums`에서 뽑는다»*
라고 적었고, **D-0394가 그 문장을 `README`로 옮겼다.** 실제로 읽는 것은 묶음이
아니라 **믹스 온셋 포락선 폴더**(`keys-*.onsets`)다. `onset/<스템>` 네 벌은
1004곡에 쓰여 있고 **제품에서 읽는 자리가 0곳이다** (D-0350과 같은 꼴).

말이 틀린 것보다 나쁜 것은 **그 틀린 말이 다음 판의 근거가 되는 것**이다. 실제로
그렇게 됐다 — 「`onset/drums`가 1004곡에 있으므로 막는 것이 없다」가 O-46(닫힘 D-0404)의 재개
조건이었다.

### 세 가지를 본다

| | 무엇 | 왜 |
|---|---|---|
| 쓰는 계열 | `ingest_all.py`의 `arrays[...]` 이름 | **정본은 쓰는 쪽이다** (D-0117) |
| 읽는 자리 | 제품 코드가 **독스트링 아닌 자리**에서 그 이름을 부르나 | 주석은 배선이 아니다 |
| 적힌 말 | 안 읽는 계열을 문서·독스트링이 부르나 | **그것이 이번에 틀린 자리다** |

**독스트링을 읽는 자리로 세지 않는다.** 내 시험이 내 주석에 걸리는 꼴을 세 판
연속 겪었다 (D-0385 · D-0388 · D-0393) — 여기서는 그 둘을 아예 가른다.

    python3 tools/check_bundle_keys.py --check
"""

from __future__ import annotations

import argparse
import ast
import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITER = "core/hathor/application/ingest_all.py"
"""배열 이름을 **짓는** 자리. 여기가 정본이고 나머지는 인용이다."""

SELF = "tools/check_bundle_keys.py"
"""이 파일. **제 선언에 제가 걸리면 안 된다** — 계열 이름을 여기 적고 있다."""

PRODUCT = ("core/hathor", "tools")
"""읽는 자리를 찾는 나무. **시험은 안 본다** — 시험만 읽는 배열은 산출물이 아니다."""

DOCS = ("README.md", "docs/MASTER.md", "docs/PLAN.md")
"""말을 찾는 문서. `DECISIONS.md`는 **과거이며 추가 전용**이라 안 본다 (D-0117)."""

STEMS = ("mixture", "other", "bass", "vocals", "drums")
"""묶음이 담는 소스 이름. `<계열>/<이 중 하나>`가 **인용의 꼴**이다."""

OK = "check_bundle_keys: ok"
"""**그 줄만 비키는 선언** (D-0219 · `doc_fsck`의 `ok` 표식과 같은 꼴).

안 읽는 계열을 **안 읽는다고 적는 줄**은 이 검사에 걸릴 수밖에 없다 — O-76의
질문 행과, D-0392의 틀린 말을 인용하는 자리가 그것이다. 비킬 줄에 이 말을 적고
**왜인지 함께 적는다.** 적지 않으면 안 비킨다."""

WRITTEN = re.compile(r"""arrays\[f?["']([a-z_]+)/""")
"""`arrays[f"chroma/{name}"]` · `arrays["silence/mixture"]` 둘 다 같은 꼴로 읽는다."""

FAMILY_FLOOR = 6
"""쓰는 계열 수의 **바닥** (D-0230). 실측 6계열 — 정규식이 깨지면 0계열이 되고,
0계열이면 *«읽는 자리 없는 계열 0개»*가 **통과로 읽힌다.**"""

BY_ARGUMENT = {
    "mert": "사람이 `eval retrieval --keys mert/<소스>/<층>`으로 이름을 준다 (D-0233)",
}
"""**읽기는 하는데 코드에 이름이 없는 계열** (D-0219). 사람이 인자로 이름을 주므로
문자열이 저장소에 없다 — 그래서 읽는 자리를 세는 자에게는 안 보인다.

차집합은 **선언으로만** 비운다. 여기 적는 것이 그 선언이다."""

UNREAD = {
    "onset": "쓰기만 하고 아무도 안 읽는다 — 믹스 포락선을 읽는다 (O-76 · D-0395)",
}
"""**쓰고 안 읽는 계열.** 여기 적힌 계열은 문서·독스트링도 부를 수 없다 —
안 읽는 것을 읽는다고 적은 것이 D-0395가 고친 결함이다.

**읽는 자리가 생기면 여기서 빼야 한다.** 안 빼면 이 검사가 운다 (양방향 · D-0371)."""


def _said(node: ast.expr | None) -> bool:
    """그 노드가 **글자 상수**인가."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _docstrings(tree: ast.Module) -> set[int]:
    """독스트링 노드의 `id`. **문자열 상수 중 이것만 말이고 나머지는 배선이다.**

    ### 상수 독스트링도 말이다 (D-0411)

    처음에는 **모듈·클래스·함수의 첫 줄**만 셌다. 그런데 이 저장소는 상수마다 그
    아래에 설명을 단다 — `KICK_BEATS = (0, 2)` 다음 줄의 글자가 그것이고, 파이썬
    문법으로는 **그냥 떠 있는 상수**다. 그래서 이 검사가 *«`onset/drums`를 읽는
    자리»*로 셌고, **설명 한 줄이 배선으로 읽혔다.**

    제 독스트링에 세 판 연속 걸린 그 꼴이 **네 번째로 났다** (D-0385 · D-0388 ·
    D-0393). 이번에는 비키는 선언을 더하지 않고 **눈을 고쳤다** — 대입 바로 뒤에
    오는 글자는 그 이름의 설명이다 (PEP 258).
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and _said(body[0].value):
            found.add(id(body[0].value))
        # **대입 바로 뒤의 글자는 그 이름의 설명이다** (PEP 258 · D-0411).
        for before, after in itertools.pairwise(body):
            if not isinstance(before, ast.Assign | ast.AnnAssign):
                continue
            if isinstance(after, ast.Expr) and _said(after.value):
                found.add(id(after.value))
    return found


def _python(root: Path) -> list[Path]:
    """제품 코드 전부. **순서를 고정한다** — 메시지가 기기마다 달라지면 못 대조한다."""
    found: list[Path] = []
    for folder in PRODUCT:
        found += sorted((root / folder).rglob("*.py"))
    return found


def written(root: Path) -> set[str]:
    """`ingest all`이 **짓는** 계열 이름."""
    text = (root / WRITER).read_text(encoding="utf-8")
    return set(WRITTEN.findall(text))


def _stem_pattern(families: set[str]) -> re.Pattern[str]:
    """`<계열>/<스템>` 꼴 하나. **계열마다 저장소를 다시 걷지 않는다** — 한 판에 다 센다."""
    names = "|".join(re.escape(one) for one in sorted(families))
    return re.compile(rf"({names})/(?:{'|'.join(STEMS)})")


def scan(root: Path, families: set[str]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """**한 번 걸으며 둘을 센다** — (읽는 자리, 말로 부르는 자리).

    계열마다 따로 걸으면 파일을 여섯 번 파싱한다. 215개 파일에 2분이 넘었고
    **관문에 2분을 더하면 사람이 검사를 끈다** (D-0129).
    """
    reading: dict[str, list[str]] = {family: [] for family in families}
    saying: dict[str, list[str]] = {family: [] for family in families}
    stem = _stem_pattern(families)
    for name in DOCS:
        for number, line in enumerate((root / name).read_text(encoding="utf-8").splitlines(), 1):
            if OK in line:
                continue
            for found in stem.finditer(line):
                saying[found.group(1)].append(f"{name}:{number}")
    for path in _python(root):
        relative = path.relative_to(root).as_posix()
        if relative in {WRITER, SELF}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        spoken = _docstrings(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in spoken:
                # **독스트링도 줄 단위로 본다.** 통째로 비키게 하면 한 줄 선언이
                # 그 밑의 모든 말을 덮는다.
                for offset, line in enumerate(node.value.splitlines()):
                    if OK in line:
                        continue
                    for found in stem.finditer(line):
                        saying[found.group(1)].append(f"{relative}:{node.lineno + offset}")
                continue
            for family in families:
                if f"{family}/" in node.value:
                    reading[family].append(f"{relative}:{node.lineno}")
    return reading, saying


def verdict(root: Path) -> list[str]:
    """문제 목록. **빈 목록이 통과다.**"""
    families = written(root)
    if len(families) < FAMILY_FLOOR:
        return [
            f"쓰는 계열이 {len(families)}개다(바닥 {FAMILY_FLOOR}). **그물이 비었다** — "
            f"`{WRITER}`의 `arrays[...]`를 못 읽었다 (D-0230)"
        ]
    reading, saying = scan(root, families)
    problems: list[str] = []
    declared = {**BY_ARGUMENT, **UNREAD}
    for family in sorted(families):
        seen = reading[family]
        if not seen and family not in declared:
            problems.append(
                f"`{family}/*`를 쓰고 **읽는 자리가 0곳이다** — 읽는 쪽을 달거나 "
                f"`UNREAD`에 적는다 (D-0350 · D-0219)"
            )
        if seen and family in declared:
            problems.append(
                f"`{family}/*`는 《{declared[family]}》로 선언돼 있는데 읽는 자리가 "
                f"{len(seen)}곳이다({seen[0]}) — **선언을 뺀다** (D-0371)"
            )
    for family in sorted(UNREAD):
        if family not in families:
            problems.append(f"`UNREAD`의 `{family}`을 쓰는 자리가 없다 — 선언이 낡았다")
            continue
        for where in saying[family]:
            problems.append(
                f"{where}가 `{family}/<스템>`을 부르는데 **아무도 안 읽는다** — "
                f"《{UNREAD[family]}》 (D-0395)"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="묶음 배열의 쓰는 쪽 ↔ 읽는 쪽 (D-0395)")
    parser.add_argument("--check", action="store_true")
    parser.parse_args()

    problems = verdict(ROOT)
    if problems:
        print(f"묶음 배열에 문제가 {len(problems)}건 있다.", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 1

    families = written(ROOT)
    reading, _ = scan(ROOT, families)
    shown = " · ".join(f"{family} {len(reading[family])}곳" for family in sorted(families))
    print(
        f"묶음 배열 검사 통과 · 계열 {len(families)}개 · {shown} · "
        f"선언 {len(BY_ARGUMENT)}+{len(UNREAD)}개"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
