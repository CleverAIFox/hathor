#!/usr/bin/env python3
"""관문의 **시야**를 못으로 박는다 — 그물을 정의하는 상수가 조용히 줄면 막는다 (D-0349).

### 왜 필요한가

`check_issue_mentions.SKIP_TREES`가 **`("",)`였다.** `name.startswith("")`는 늘
참이므로 `DOCUMENTS` 전부가 떨어져 나갔고, **문서 축을 한 줄도 안 보는 채로 348판
동안 초록을 찍었다.** 화면에는 「닫힘 42 · 열림 30」이 찍혔다 — 그 수는 **표의 수**이지
**읽은 파일 수**가 아니다. 아무도 못 알아챘다.

D-0230이 이미 적었다 — ***그물이 비면 「전부 맞다」가 거짓으로 참이 된다.*** 그 문장을
적어 두고 **세는 것을 안 만들었다** (D-0126의 그 죄다).

### 카나리아와 못은 막는 것이 다르다

| | 무엇을 잡나 | 언제 |
|---|---|---|
| 카나리아 (`deadcheck.positive_control`) | 시야는 그대로인데 **잡는 능력**을 잃었다 | 다음 판 |
| **시야 못 (여기)** | **시야 자체**가 조용히 줄었다 | **바꾸는 판** |

`SKIP_TREES` 사고는 **뒤쪽**이었다. 검사는 멀쩡히 돌았고 볼 것이 없었다. 카나리아를
아무리 심어도 **대상 목록이 비어 있으면 카나리아도 안 읽힌다.** 그래서 둘 다 필요하다.

### 규율은 `deadcheck.CEILING`과 같다 (D-0117 · D-0223)

**정본은 이 파일 하나다.** 손으로 안 고치고 `--update`로 조인다 — 조이는 판마다
결정 기록에 한 줄이 남는 것이 이 마찰의 값이다.

### 방향은 이름에서 읽는다

**모으는 상수와 빼는 상수는 반대로 움직인다.** `DOCUMENTS`가 줄면 그물이 줄고,
`SKIP_FILES`가 늘면 그물이 줄어든다. 그래서 `SKIP`·`ALLOW`·`IGNORE`·`EXCLUDE`로
시작하는 이름은 **천장**이고 나머지는 **바닥**이다. **손으로 적은 방향표는 안 둔다** —
두 곳이 어긋난다 (D-0043).

| | 늘면 | 줄면 |
|---|---|---|
| 바닥 (`DOCUMENTS` · `TREES` · `NETWORK` …) | 통과 | **막는다** |
| 천장 (`SKIP_*` · `ALLOW*` …) | **막는다** | 통과 |

**방향과 무관하게 막는 둘**: 빈 문자열이 들었거나(`("",)`가 정확히 그것이다),
못 박힌 이름이 **사라졌다**.

    python3 tools/check_sight.py --check     # 검사한다
    python3 tools/check_sight.py --list      # 실측을 찍는다
    python3 tools/check_sight.py --update    # 조이는 쪽으로만 쓴다
    python3 tools/check_sight.py --update --loosen   # 느슨하게. **결정 기록이 필요하다**
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve()

REGISTRY = "check_sight.PINNED"
"""못 장부 자신의 이름. **장부는 세는 대상이 아니다** — `measure()`의 주석을 본다."""

WIDENS = ("SKIP", "ALLOW", "IGNORE", "EXCLUDE")
"""**늘면 그물이 줄어드는** 이름의 머리. 이쪽만 천장이고 나머지는 바닥이다."""

PINNED = {
    "build_proposal.TBL_PR_ORDER": 17,
    "check_args.FLOOR": 4,
    "check_args.OWN_ENV_ALLOWED": 2,
    "check_args.SKIP_FLAGS": 1,
    "check_artifacts.REQUIRED": 6,
    "check_artifacts.TRANSIENT_ALLOWED": 1,
    "check_artifacts.UNDER_STUDY_ALLOWED": 1,
    "check_compose.CEILING": 3,
    "check_decisions.REQUIRED_SECTIONS": 2,
    "check_doc_style.AXES": 3,
    "check_doc_style.DOCUMENTS": 4,
    "check_doc_style.NO_TOOL": 2,
    "check_doc_style.OUTSIDE_TENSE": 3,
    "check_doc_style.POLITE": 2,
    "check_doc_style.SECTION": 3,
    "check_egress.ALLOWED": 4,
    "check_egress.NETWORK": 10,
    "check_egress.TREES": 2,
    "check_file_size.LIMITS": 2,
    "check_file_size.TREES": 2,
    "check_forbidden.TREES": 2,
    "check_issue_mentions.DOCUMENTS": 4,
    "check_issue_mentions.FLOOR": 2,
    "check_issue_mentions.SKIP_FILES": 2,
    "check_issue_mentions.SKIP_NUMBERS": 1,
    "check_issue_mentions.SKIP_TREES": 1,
    "check_issue_mentions.TREES": 3,
    "check_model_licenses.COMMERCIAL": 3,
    "check_model_licenses.TREES": 1,
    "check_patch.HEADS": 3,
    "check_ratchets.KINDS": 6,
    "check_ratchets.NAILS": 4,
    "check_ratchets.OWNED_ELSEWHERE": 1,
    "check_ratchets.SOURCES": 2,
    "check_ratchets.VOCABULARY": 5,
    "check_requirements.DONE": 2,
    "check_requirements.MVP_EXEMPT": 9,
    "check_requirements.STATES": 9,
    "check_retired.LIVING": 3,
    "check_script.SCRIPTS": 1,
    "check_secrets.FORBIDDEN": 1,
    "check_secrets.PLACEHOLDER_PREFIXES": 6,
    "check_secrets.SKIP_FILES": 1,
    "check_secrets.SKIP_SUFFIXES": 2,
    "check_sight.WIDENS": 4,
    "deadcheck.BLIND": 2,
    "deadcheck.CEILING": 6,
    "deadcheck.CODE_TREES": 2,
    "deadcheck.NET_TREES": 7,
    "debts.SECURITY_SETUP": 2,
    "debts.WATCHED": 3,
    "doc_counts.GR_TREES": 5,
    "doc_counts.LEDGER": 2,
    "doc_fsck.LIVING": 3,
    "doc_fsck.SKIP_SUFFIXES": 6,
    "encoding_check.BINARY": 16,
    "encoding_check.CRLF_KEEP": 3,
    "measured.BLOCKS": 3,
    "measured.SOURCES": 3,
    "mlflow_sync.TELEMETRY_OFF": 4,
    "mutate_gate.ENTRIES": 2,
    "prefect_flow.CLI": 6,
    "probe_artist.EMITS": 6,
    "probe_artist.SEPARATORS": 13,
    "probe_id3.CORPUS_EMITS": 8,
    "probe_id3.DATE_FRAMES": 6,
    "probe_id3.ID3_EMITS": 20,
    "probe_stems.PITCH_STEMS": 2,
    "probe_stems.PREFIXES": 2,
    "proposal_source.GENERATORS": 6,
    "render_figures.FONTS": 4,
    "ship.LEFTOVERS": 2,
    "ship.OUTSIDE": 3,
    "ship.PASSING": 3,
    "ship.REGENERABLE": 1,
    "step0_check.AUDIO_EXTS": 10,
}
"""**시야 못. 정본은 여기 하나다** (D-0223). `--update`로만 조인다.

`check_sight.WIDENS`가 자기 자신에게도 못을 박는 것은 의도다 — **방향을 정하는 표가 비면 모든
천장이 바닥으로 뒤집힌다.** 자기를 안 보는 검사가 D-0257이 센 그것이다.
"""

BLOCK = re.compile(r"^PINNED = \{\n.*?^\}\n", re.MULTILINE | re.DOTALL)


def is_ceiling(name: str) -> bool:
    """**늘면 막는 자리인가.** 이름의 머리로 읽는다 — 방향표를 손으로 안 둔다."""
    return name.startswith(WIDENS)


def collections(path: Path) -> dict[str, tuple[str, ...]]:
    """한 모듈의 **문자열 묶음 상수**를 전부 낸다. 사전은 열쇠를 센다.

    AST로 읽는다 — **불러오지 않는다.** `import`는 부작용을 내고, 못이 검사
    대상을 실행하면 못이 검사 대상에 의존한다.
    """
    found: dict[str, tuple[str, ...]] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name) and t.id.isupper()]
        if not names:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            continue
        if isinstance(value, dict):
            items = tuple(str(key) for key in value)
        elif isinstance(value, (tuple, list, set, frozenset)):
            if not all(isinstance(item, str) for item in value):
                continue
            items = tuple(str(item) for item in value)
        else:
            continue
        for name in names:
            found[name] = items
    return found


def measure() -> dict[str, tuple[str, ...]]:
    """`tools/` 전부의 실측. 정렬해 낸다 — **순서가 판마다 달라지면 못 읽는다.**"""
    seen: dict[str, tuple[str, ...]] = {}
    for path in sorted(ROOT.joinpath("tools").glob("*.py")):
        for name, items in collections(path).items():
            key = f"{path.stem}.{name}"
            if key == REGISTRY:
                # **장부 자신은 안 센다.** 세면 못이 하나 박힐 때마다 장부 크기가
                # 바뀌고 **고정점이 없다** — 조여도 다음 판에 또 어긋난다.
                continue
            seen[key] = items
    return dict(sorted(seen.items()))


def verdict(seen: dict[str, tuple[str, ...]], pinned: dict[str, int]) -> list[str]:
    """어긴 자리를 **전부** 낸다. 첫 문제에서 멈추지 않는다."""
    problems: list[str] = []
    for key, items in seen.items():
        name = key.split(".", 1)[1]
        if "" in items:
            problems.append(
                f'{key}에 빈 문자열이 들었다. `startswith("")`는 늘 참이라 '
                f"그물이 통째로 빈다 — D-0349가 그 사고다"
            )
        floor = pinned.get(key)
        if floor is None:
            continue
        if is_ceiling(name) and len(items) > floor:
            problems.append(
                f"{key}가 {len(items)}개다. 못은 {floor}개였다 — **빼는 목록이 늘면 "
                f"그물이 줄어든다.** 늘린 것이 맞다면 `--update`로 조이고 결정 기록을 쓴다"
            )
        elif not is_ceiling(name) and len(items) < floor:
            problems.append(
                f"{key}가 {len(items)}개다. 못은 {floor}개였다 — **그물이 줄었다.** "
                f"상수가 비었는지 본다. 줄인 것이 맞다면 `--update`로 조이고 결정 기록을 쓴다"
            )
    for key in pinned:
        if key not in seen:
            problems.append(
                f"{key}가 사라졌다. 못은 {pinned[key]}개였다 — **상수를 지우면 "
                f"그 관문이 무엇을 보는지 아무도 모른다.** 지운 것이 맞다면 `--update`"
            )
    return problems


def rendered(seen: dict[str, tuple[str, ...]]) -> str:
    """`PINNED` 블록을 다시 적는다. **이 파일이 정본이라 이 파일에 적는다.**"""
    rows = "".join(f'    "{key}": {len(items)},\n' for key, items in seen.items())
    return f"PINNED = {{\n{rows}}}\n"


def loosening(seen: dict[str, tuple[str, ...]], pinned: dict[str, int]) -> list[str]:
    """`--update`가 **느슨해지는 쪽**으로 쓰려는 자리 (D-0349 — `fire-lane`에서 가져왔다).

    ### 자동 래칫의 함정

    저쪽 `tools/ratchet.py:87`이 `DIRECTIONS = ("down", "up", "down-map")`을 두고
    **반대 방향이면 쓰지 않고 빨간불을 낸다.** 사유가 `sizecheck.py` 머리말에 있다 —
    ***"느슨해진 래칫은 초록으로 위장한다."*** 저쪽은 커버리지 래칫이 14인데 실물이
    24%인 것을 **나흘간** 아무도 몰랐다.

    첫 판의 `--update`는 **실측을 그대로 적었다.** 그러면 상수를 비운 사람이
    `--update` 한 번으로 못을 같이 내릴 수 있고, **그것이 이 못이 막으려던 사고
    그 자체다.** `check_file_size`가 이미 같은 규율을 든다 — `--update`는 내리고
    올리려면 `GROW=1`과 결정 기록이 필요하다 (D-0118).

    | | 조이는 쪽 | 느슨해지는 쪽 |
    |---|---|---|
    | 바닥 | 수가 **늘었다** | 수가 **줄었다** |
    | 천장 | 수가 **줄었다** | 수가 **늘었다** |
    | 사라진 못 | — | **늘 느슨해지는 쪽이다** |
    """
    report: list[str] = []
    for key, floor in sorted(pinned.items()):
        name = key.split(".", 1)[1]
        items = seen.get(key)
        if items is None:
            report.append(f"{key}: 못 {floor} → **사라졌다**")
        elif is_ceiling(name) and len(items) > floor:
            report.append(f"{key}: 천장 {floor} → {len(items)} (늘었다)")
        elif not is_ceiling(name) and len(items) < floor:
            report.append(f"{key}: 바닥 {floor} → {len(items)} (줄었다)")
    return report


def update(allow_loosening: bool = False) -> int:
    text = HERE.read_text(encoding="utf-8")
    if not BLOCK.search(text):
        print("`PINNED` 블록을 못 찾았다. 정본이 사라졌다", file=sys.stderr)
        return 1
    seen = measure()
    slack = loosening(seen, PINNED)
    if slack and not allow_loosening:
        print(f"못이 느슨해지는 쪽이다. {len(slack)}곳이다 — 안 쓴다.", file=sys.stderr)
        for line in slack:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\n**느슨해진 래칫은 초록으로 위장한다** (`fire-lane`의 실측 — 나흘을 몰랐다).\n"
            "상수가 비었는지부터 본다. 줄인 것이 **맞다면** `--update --loosen`과 "
            "**결정 기록**이 필요하다 (D-0118의 `GROW=1`과 같은 규율).",
            file=sys.stderr,
        )
        return 1
    swapped = BLOCK.sub(lambda _: rendered(seen), text, count=1)
    if swapped == text:
        print(f"못은 이미 실측과 같다 · 상수 {len(seen)}개")
        return 0
    HERE.write_text(swapped, encoding="utf-8")
    verdict = "느슨하게 다시 박았다" if slack else "조였다"
    print(f"못을 {verdict} · 상수 {len(seen)}개. **결정 기록에 무엇을 왜 바꿨는지 쓴다**")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="관문의 시야에 못을 박는다 (D-0349)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="실측을 찍는다")
    parser.add_argument("--update", action="store_true", help="못을 실측으로 조인다")
    parser.add_argument(
        "--loosen",
        action="store_true",
        help="느슨해지는 쪽으로도 쓴다. **결정 기록이 필요하다** (D-0118의 `GROW=1`과 같다)",
    )
    args = parser.parse_args()

    if args.update:
        return update(allow_loosening=args.loosen)

    seen = measure()
    if args.list:
        for key, items in seen.items():
            mark = "천장" if is_ceiling(key.split(".", 1)[1]) else "바닥"
            print(f"  {len(items):3d}  {mark}  {key}")
        return 0

    if not seen:
        print("상수를 0개 읽었다. **못이 아무것도 안 본다** (D-0230)", file=sys.stderr)
        return 1

    problems = verdict(seen, PINNED)
    if problems:
        print(f"시야 못을 어긴 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    tools = len({key.split(".", 1)[0] for key in seen})
    print(f"시야 못 검사 통과 · 상수 {len(seen)}개 · 도구 {tools}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
