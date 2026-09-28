#!/usr/bin/env python3
"""산출물 대장과 실물을 대조한다 (D-0266).

### 왜 생겼나

사용자가 `make ship`의 한 줄을 보고 물었다 — *"교두보에 1090개 이거 맞나? 1004개가
아니라?"* **저장소가 그 질문에 답할 수 없었다.**

- `sync_artifacts status`는 양쪽의 **차집합**을 찍는다. 양쪽이 똑같이 틀리면 초록이다.
- `sync_artifacts verify`는 양쪽을 **서로** 비교한다. 같은 근거다.
- `var_fsck`는 *"판정하지 않는다"*가 규약이다 (D-0203).

**선언이 없으면 «맞나»는 물을 수 없는 질문이다.** 있는 것을 세는 것과 있어야 할 것과
대조하는 것은 다르다.

### 파이어레인에서 가져온다 — 이번에는 데이터 쪽을

이 저장소는 파이어레인의 **문서** 규율을 열 군데 넘게 가져왔다(`doc_fsck` ·
`deadcheck` · `encoding_check` · `check_doc_style` · `tidy` · 대장 생성). 그런데
**데이터 규율은 한 줄도 안 가져왔다** — `regenerable` · 산출물 대장 · `feeds` ·
`consumers`가 전부 0건이었다.

D-0173이 *"「파이어레인처럼」이라고 적은 것은 전부 되받은 말이었고 본 적이 없었다"*고
적은 그 일이 **데이터 쪽에서 되풀이됐다.**

### 판정 넷 (파이어레인 `scan_data.py`)

    대장에 있음 + 실물 있음  →  정상
    대장에 있음 + 실물 없음  →  결손
    대장에 없음 + 실물 있음  →  격리 대상
    선언이 모자람            →  대장 결함

### 두 모드로 갈라 둔다

`--check`는 **대장 자신만** 본다 — 칸이 다 있는가, 만드는 코드가 실재하는가,
재생성 불가인 계열이 교두보 의무를 지는가. 디스크를 안 읽으므로 CI에서 돈다.

`--audit`은 **실물과 대조한다.** `var/`가 있는 기기에서만 뜻이 있고 `make hygiene`이
부른다. **`var/`가 없으면 0건이 아니라 «못 쟀다»라고 말한다** — 파이어레인 `lakecheck`의
규율이다 (*"프로브가 잴 수 없으면 0건이 아니라 빨간불이다"*).

    python3 tools/check_artifacts.py --check
    python3 tools/check_artifacts.py --audit
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "artifacts.toml"
SUBTREE = Path("var") / "ingest"
"""대장이 덮는 자리. `sync_artifacts.SUBTREE`와 같은 값이며 **거기가 정본이다.**"""

REQUIRED = ("what", "made", "regen", "reads", "store", "state")
"""계열마다 있어야 하는 칸. **`reads`가 빠지면 남길 이유를 안 적은 것이다** (R4)."""

UNMADE = "미생성"
"""아직 한 번도 안 만들었다. **실물이 없는 것이 정상이다.**"""

UNDER_STUDY = "조사중"
"""정체가 덜 풀렸다 (D-0269). **모른다고 세는 것이 추론을 하나 더 얹는 것보다 낫다.**

작성자가 이 대장에서 네 판 연속 정체를 추론하고 네 번 다 틀렸다 (D-0266 ~ D-0269).
그래서 «모른다»에 자리를 준다 — 대신 **천장이 있다.** «재현 불명»에 D-0250이 한 것과
같은 모양이다.

`why`에 **무엇을 확인했고 무엇이 남았는지**를 적는 것이 필수다. 그것이 없으면
«조사중»은 그냥 «안 봤다»의 다른 이름이다."""

TRANSIENT = "임시"
"""**돌 때 생기고 남아도 되는 것 — 산출물이 아니다** (D-0278).

`flock` 잠금 파일이 그렇다. 커널이 fd 수명에 묶어 관리하므로 **파일을 지우지 않는다.**
한 번도 안 돌린 기기에는 없고, 한 번 돌린 기기에는 남는다 — 있음도 미생성도 폐기도 조사중도
그것을 말하지 못한다.

**지워서 없애는 길은 막았다.** `release()`에서 unlink하면 «등재할 것이 없다»가 되지만 그것은
R3가 금지하는 자리이고 **사실상 격리와 이름만 다르다.** 사용자의 판정이다 — *"unlink하면
그게 사실상 쿼런틴하고 이름만 다르지 같은 역할 아니냐."*

`store`가 거짓으로 강제된다. 잠금을 교두보에 복사해 오면 **없는 배치의 잠금**이 된다."""

STATES = ("있음", UNMADE, "폐기", UNDER_STUDY, TRANSIENT)
"""계열의 상태 (D-0266). 파이어레인 `lakecheck` L1 — *"reserved인데 파일이 있나 ·
active인데 0건인가"* — 와 같은 자리다.

| 값 | 실물이 없으면 | 실물이 있으면 |
|---|---|---|
| `있음` | **결손이다** | 정상 |
| `미생성` | 정상 — 아직 안 만들었다 | **선언이 낡았다** |
| `폐기` | 정상 — 지워도 되는 것이었다 | 정상. 판정의 근거로 남긴다 |
| `임시` | 정상 — 아직 안 돌렸다 | 정상 — 돌렸고 남았다 |

`미생성`을 빼면 `taste`(취향 라벨 0건 · D-0028)가 영원히 결손으로 뜬다. **정상을 빨갛게
찍는 검사는 꺼진다** (D-0126 · D-0129에서 되풀이 확인한 것이다)."""

RETIRED = "폐기"
"""`regen`이 이것이면 **만드는 도구를 일부러 없앴다.** 파일은 판정의 근거로 남는다.

D-0216이 `tools/probe_listenbrainz.py`를 지우면서 그 산출물 세 줄은 남겼다. 그 세 줄이
D-0216의 «자료» 칸이 가리키는 실물이다 (D-0265) — 지우면 판정의 근거가 사라진다."""

CANNOT = "불가"
"""`regen`이 이 값이면 다시 만들 수 없다 — 그때 `why`가 필수이고 `store`가 강제된다.

**R2다.** `var/`는 전부 `.gitignore`에 있다. 다시 만들 수 있어서 제외하는 것이며,
**못 만드는 것을 제외하면 그 파일은 사실상 소실된다.**"""

STAMP = re.compile(r"\d{8}T\d{6}Z")
"""실행 스탬프. 계열 이름의 `*`가 이것을 가린다 — `sync_artifacts.STAMP`와 같은 값이다."""

UNKNOWN = "불명"
"""`regen`이 이것이면 어떻게 만들었는지 모른다. `state = "조사중"`과 짝이다."""

UNDER_STUDY_CEILING = 1
"""`조사중`의 천장 (D-0269). **지금 1이다** — `keys-*.keys.jsonl.mix-other`.

무엇을 확인했는지는 그 계열의 `why`에 있다. **늘리려면 결정 기록이 필요하다** (D-0118) —
모르는 것을 여기 쌓는 길이 열려 있으면 이 칸이 두 번째 쓰레기통이 된다.

`해당 없음`이 첫 번째였다 (D-0265에서 18건을 되돌렸다)."""

TRANSIENT_CEILING = 1
"""`임시`의 천장 (D-0278). **지금 1이다** — `.ingest-keys.lock`.

면제는 세어야 면제다. 늘리려면 결정 기록이 필요하다 (D-0118) — 「산출물이 아니다」가 두
번째 쓰레기통이 되는 길을 막는다. `조사중`에 천장을 둔 것과 같은 자리다."""

QUARANTINE_CEILING = 0
"""대장에 없는 계열의 천장 (D-0266). **0이다** — R3가 «없는 산출물»이라 부르는 것이다.

늘리려면 결정 기록이 필요하다 (D-0118). 새 계열을 내면서 대장을 안 쓰는 길을 막는다."""


def load() -> dict[str, dict[str, object]]:
    """대장. **`tomllib`은 표준 라이브러리다** — 맨 `python3`으로 돈다 (D-0256)."""
    with LEDGER.open("rb") as handle:
        return dict(tomllib.load(handle).get("series", {}))


def check_ledger(entries: dict[str, dict[str, object]]) -> list[str]:
    """대장 자신이 규약을 지키는가. **디스크를 안 읽는다.**"""
    problems: list[str] = []
    if not entries:
        return ["대장이 비었다. `artifacts.toml`에 계열이 하나도 없다"]
    transient = sum(1 for entry in entries.values() if entry.get("state") == TRANSIENT)
    if transient > TRANSIENT_CEILING:
        problems.append(
            f"`{TRANSIENT}`가 {transient}개로 천장 {TRANSIENT_CEILING}개를 넘는다. "
            "**면제는 세어야 면제다** — 결정 기록이 필요하다 (D-0118)"
        )
    for name, entry in sorted(entries.items()):
        if any(isinstance(value, str) and value.startswith(TODO) for value in entry.values()):
            problems.append(f"{name}에 `{TODO}`가 남았다. **붙여 넣고 잊을 수 없다** (D-0268)")
        for field in REQUIRED:
            if field not in entry:
                problems.append(f"{name}에 `{field}` 칸이 없다")
        made = entry.get("made")
        if isinstance(made, str) and not (ROOT / made).exists():
            problems.append(f"{name}의 `made`가 없는 파일을 가리킨다: {made}")
        reads = entry.get("reads")
        if isinstance(reads, list) and not reads:
            problems.append(f"{name}의 `reads`가 비었다. 못 채우면 «미투입 — 언제 쓸지»를 적는다")
        state = entry.get("state")
        if state is not None and state not in STATES:
            problems.append(f"{name}의 `state`가 규약 밖이다: {state!r} (쓸 수 있는 것: {STATES})")
        if state == UNDER_STUDY:
            if entry.get("regen") != UNKNOWN:
                problems.append(f'{name}은 조사중인데 `regen`이 "{UNKNOWN}"이 아니다')
            if not entry.get("why"):
                problems.append(f"{name}은 조사중인데 `why`가 없다. **무엇을 확인했는지를 적는다**")
            elif "남은 것" not in str(entry["why"]):
                problems.append(f"{name}의 `why`에 «남은 것»이 없다. 다음 손이 어디를 볼지 적는다")
        if entry.get("regen") == RETIRED and not entry.get("why"):
            problems.append(f"{name}은 폐기인데 `why`가 없다. **왜 지웠는지가 그 파일의 뜻이다**")
        if state == TRANSIENT:
            if entry.get("store") is not False:
                problems.append(
                    f"{name}은 임시인데 `store`가 거짓이 아니다. "
                    "잠금을 교두보에 복사하면 **없는 배치의 잠금**이 된다"
                )
            if not entry.get("why"):
                problems.append(f"{name}은 임시인데 `why`가 없다. **왜 산출물이 아닌지를 적는다**")
        if entry.get("regen") == CANNOT:
            if not entry.get("why"):
                problems.append(f"{name}은 재생성 불가인데 `why`가 없다")
            if entry.get("store") is not True:
                problems.append(
                    f"{name}은 재생성 불가인데 `store`가 참이 아니다. "
                    "`var/`는 전부 ignore되므로 그대로면 소실된다 (R2)"
                )
    return problems


TODO = "TODO"
"""등재 자리를 찍어 줄 때 심는 표식. **`--check`가 거부한다** (D-0268).

붙여 넣고 잊는 길을 막는다 — 그 길이 열려 있으면 대장은 이름만 있는 목록이 된다."""


def measure(base: Path, name: str) -> str:
    """정체를 가릴 재료 — **파일 수 · 크기 · 가장 최근 시각** (D-0268).

    이름만으로는 «옛 이름 체계의 잔재»와 «어제 만든 것»을 못 가른다. 사람이 그것을
    가르려고 매번 `du`·`ls -lt`를 치게 만들면 **대장을 안 쓰는 쪽이 싸진다.**

    작성자가 세 판 연속으로 정체를 **추론**했고 세 번 다 틀렸다. 추론을 못 하게 하려면
    추론할 필요가 없게 만들어야 한다.
    """
    target = base / name
    paths = [item for item in target.rglob("*") if item.is_file()] if target.is_dir() else [target]
    alive = [item for item in paths if item.exists()]
    if not alive:
        return "빈 것"
    total = sum(item.stat().st_size for item in alive)
    newest = max(item.stat().st_mtime for item in alive)
    when = datetime.fromtimestamp(newest, tz=UTC).strftime("%Y-%m-%d")
    unit = total / 1024**2
    size = f"{unit:.1f}MB" if unit < 1024 else f"{unit / 1024:.1f}GB"
    return f"파일 {len(alive)}개 · {size} · 최근 {when}"


def skeleton(name: str, detail: str) -> str:
    """등재할 자리를 찍어 준다 (D-0268)."""
    return "\n".join(
        (
            f'[series."{name}"]',
            f'what = "{TODO} — 무엇인가. {detail}"',
            f'made = "{TODO} — 만드는 코드 경로. 없으면 폐기인지 본다"',
            f'regen = "{TODO} — 다시 만드는 명령. 못 만들면 «불가» 또는 «폐기»"',
            f'reads = ["{TODO} — 누가 읽나. 없으면 «미투입 — 언제 쓸지»"]',
            "store = true",
            'state = "있음"',
            "",
        )
    )


def folded(base: Path) -> dict[str, str]:
    """`접힌 이름 → 실물 이름 하나` (D-0269).

    **접힌 이름은 경로가 아니다.** `keys-*.keys.jsonl.mix-other`의 `*`는 리터럴이고
    그런 파일은 없다. 첫 판은 접힌 이름을 그대로 `measure()`에 넘겨 **스탬프가 있는
    계열마다 «못 쟀다»를 찍었다** — 스탬프 없는 계열만 우연히 통했다.

    재려면 실물 이름이 필요하므로 접기와 함께 보기 하나를 든다.
    """
    return {STAMP.sub("*", path.name): path.name for path in base.iterdir()}


def resolved(found: dict[str, str], declared: set[str]) -> dict[str, str]:
    """실물 이름을 **선언된 이름에 붙인다** (D-0292).

    `folded()`는 `*`를 **실행 스탬프**로만 푼다. 그런데 대장의 `*`가 늘 스탬프인 것은
    아니다 — `keys-*.onsets`의 `*`는 **홉 값**(`0.01s`)이고 `--hop`으로 갈린다.

    그래서 `keys-0.01s.onsets`가 어디에도 안 붙어 **결손과 격리로 두 번 세어졌다.**
    같은 것 하나가 «없다»와 «모르는 것이다»로 동시에 찍혔고, 사람은 그것을 배치가
    실패한 것으로 읽는다 — 1004곡이 다 들어온 뒤였다.

    **둘 이상에 맞으면 안 붙인다.** 골라 주면 그 선택이 조용하고, 조용한 선택은
    다음 사람이 못 본다 — 격리로 남겨 사람이 판정한다.
    """
    matched: dict[str, str] = {}
    globs = [name for name in declared if "*" in name]
    for name, real in found.items():
        if name in declared:
            matched[name] = real
            continue
        hits = [one for one in globs if fnmatch(name, one)]
        matched[hits[0] if len(hits) == 1 else name] = real
    return matched


def store_side() -> Path | None:
    """교두보의 `var/ingest`. **경로 파서를 새로 쓰지 않는다** (D-0199).

    `.env`를 읽는 파서가 둘이 되면 갈린다 — 그것이 D-0199가 고친 결함이다. 정본은
    `sync_artifacts.store_root()` 하나이고 여기서는 불러 쓴다."""
    sys.path.insert(0, str(ROOT / "tools"))
    import sync_artifacts

    root = sync_artifacts.store_root()
    if root is None:
        return None
    side = root / SUBTREE
    return side if side.is_dir() else None


class Verdict(NamedTuple):
    """판정 넷을 **따로** 든다 (D-0268).

    첫 판은 «선언이 낡았다»를 격리 목록에 섞었다. 그러면 `--suggest`가 **이미 선언된
    계열의 등재 자리를 또 찍어** 키가 겹친다. 문구가 다르면 자리도 달라야 한다.
    """

    missing: list[str]
    """결손 — 대장에 있는데 어디에도 없다."""
    orphan: list[str]
    """격리 대상 — 대장에 없는 계열. **등재할 것이다.**"""
    stale: list[str]
    """선언이 낡았다 — `미생성`이라 적혀 있는데 실물이 있다. **고칠 것은 선언이다.**"""
    normal: int
    examples: dict[str, str]
    """`접힌 이름 → 실물 이름 하나`. **재려면 실물 이름이 필요하다** (D-0269)."""


def audit(entries: dict[str, dict[str, object]], base: Path, store: Path | None = None) -> Verdict:
    """**세기만 한다 — 아무것도 옮기거나 지우지 않는다.**

    **양쪽을 본다** (D-0266). 로컬은 부분 사본이어도 된다 — `make artifacts-pull`의 기본이
    `keys,eval`뿐이다 (`ship.DEFAULT_ONLY`). 한쪽만 보면 **정상을 결손으로 찍고**, 그런
    검사는 꺼진다. 어디에도 없을 때만 결손이다.

    `state`가 `미생성`·`폐기`·`조사중`·`임시`인 계열은 실물이 없어도 결손이 아니다.
    """
    found = dict(folded(base))
    if store is not None:
        found = {**folded(store), **found}
    declared = set(entries)
    found = resolved(found, declared)
    seen = set(found)
    return Verdict(
        missing=sorted(
            name
            for name in declared - seen
            if entries[name].get("state") not in (UNMADE, RETIRED, UNDER_STUDY, TRANSIENT)
        ),
        orphan=sorted(seen - declared),
        stale=sorted(name for name in declared & seen if entries[name].get("state") == UNMADE),
        normal=len(declared & seen),
        examples=found,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="산출물 대장 대조 (D-0266)")
    parser.add_argument("--check", action="store_true", help="대장 자신만 본다. CI에서 돈다")
    parser.add_argument("--audit", action="store_true", help="실물과 대조한다. `var/`가 필요하다")
    parser.add_argument(
        "--suggest", action="store_true", help="미등재 계열의 등재 자리를 찍는다 (붙여 넣을 것)"
    )
    parser.add_argument("--root", type=Path, default=ROOT / SUBTREE, help="대조할 산출물 루트")
    args = parser.parse_args()

    entries = load()
    problems = check_ledger(entries)
    if problems:
        print(f"산출물 대장에 결함이 {len(problems)}건 있다.", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 1

    if not args.audit:
        cannot = [name for name, entry in entries.items() if entry.get("regen") == CANNOT]
        print(f"산출물 대장 검사 통과 · 계열 {len(entries)}개 · 재생성 불가 {len(cannot)}개")
        return 0

    store = store_side()
    if not args.root.is_dir() and store is None:
        # **못 쟀으면 못 쟀다고 말한다** — 0건으로 넘기지 않는다 (GR-0.5).
        print(f"{args.root}도 교두보도 없다. 산출물이 있는 기기에서 돌린다.", file=sys.stderr)
        print("  교두보에서 가져오려면: make artifacts-pull", file=sys.stderr)
        return 1

    seen = audit(entries, args.root, store)
    where = f"{args.root}" + (f" + 교두보 {store}" if store else " (교두보 안 붙었다)")
    print(
        f"{where}\n  정상 {seen.normal} · 결손 {len(seen.missing)} · "
        f"격리 대상 {len(seen.orphan)} · 낡은 선언 {len(seen.stale)}"
    )
    for name in seen.missing:
        print(f"  결손    {name}  — 어디에도 없다. {entries[name]['regen']}")
    sides = [side for side in (args.root, store) if side is not None and side.is_dir()]

    def detail_of(name: str) -> str:
        real = seen.examples.get(name, name)
        return next((measure(side, real) for side in sides if (side / real).exists()), "못 쟀다")

    for name in seen.orphan:
        print(f"  격리    {name}\n            {detail_of(name)}", file=sys.stderr)
    for name in seen.stale:
        print(
            f"  낡음    {name}  — 선언은 «{UNMADE}»인데 실물이 있다. **선언을 고친다**\n"
            f"            {detail_of(name)}",
            file=sys.stderr,
        )
    if seen.orphan and args.suggest:
        print("\n  ── 아래를 `artifacts.toml`에 붙이고 TODO를 채운다 ──\n")
        for name in seen.orphan:
            print(skeleton(name, detail_of(name)))
    if len(seen.orphan) > QUARANTINE_CEILING or seen.stale:
        if seen.orphan:
            print(
                f"\n대장에 없는 계열이 {len(seen.orphan)}개로 천장 "
                f"{QUARANTINE_CEILING}개를 넘는다.",
                file=sys.stderr,
            )
            print(
                "  **등록되지 않은 산출물은 없는 산출물이다** — 대장에 쓴다 (R3).", file=sys.stderr
            )
            print(
                "  등재 자리를 찍으려면: python3 tools/check_artifacts.py --audit --suggest",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
