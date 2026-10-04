#!/usr/bin/env python3
"""문서가 가리키는 것이 실물로 있는가 (D-0189).

    python3 tools/doc_fsck.py

### 왜 생겼나

강제자가 여덟인데 **전부 문서 ↔ 문서**였다. 색인이 기록과 맞는가, 표기가 규약과
맞는가, 레이아웃이 맞는가. **문서 ↔ 실물을 보는 것이 하나도 없었다.**

`fire-lane`의 `doc_fsck.py`가 같은 자리에서 생겼고 거기 적힌 말이 그대로 맞는다 —
*"읽으면 보이는데 아무도 안 읽었다."* 이 저장소에서도 같은 일이 났다.

| 실제로 난 일 | 언제 |
|---|---|
| `PLAN §1`이 없는 `tools/probe_keys.py`를 가리켰다 | D-0182 |
| 탐침이 `find_keys_store`에 엉뚱한 인자를 넘겼다 | D-0180 |
| 재현 절이 `cd core` 기준 상대 경로를 적어 빈손이 됐다 | D-0153이 검사를 만든 뒤에도 |
| `apply_patch.sh`가 이름이 바뀐 도구를 불러 `make apply`가 죽었다 | D-0189 이후 줄곧 |

### 무엇을 보나

| | 무엇 |
|---|---|
| 경로 | 문서가 적은 `tools/x.py` · `core/...`가 실재하는가 |
| 명령 | `재현` 절의 `python3 tools/x.py`가 실재하는가 |
| 도구 | `tools/*.py`가 문서 어디서든 불리는가 (죽은 도구) |
| 배선 | `Makefile`·훅·CI·셸이 부르는 스크립트가 실재하는가 (D-0196) |
| 빈 자리 | 비어 있는 패키지가 **언제 차는지**를 적었는가 |

### 무엇을 안 보나

**자연어 모순은 안 잡는다.** *"A 문서와 B 문서가 다른 말을 한다"*를 기계가 판정하려면
두 서술의 의미를 비교해야 하고 그것은 이 도구의 범위가 아니다. 여기서 보는 것은
**구조뿐이다** — 판단이 아니라 대조다.

**결정 기록 본문의 옛 경로는 안 잡는다.** 기록은 그때를 적는 문서이고 소급해서
고치지 않는다 (GR-0.2 · D-0081). 지금을 말하는 문서만 본다.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

from doc_counts import COUNTED, gate_tools

ROOT = Path(__file__).resolve().parents[1]

LIVING = ("README.md", "docs/MASTER.md", "docs/PLAN.md")
"""**지금을 말하는 문서만 본다.** `DECISIONS.md`는 과거라 옛 경로가 정상이다."""

PATH_LIKE = re.compile(r"`((?:tools|core|docs|web|infra|docker)/[\w./\-]+\.\w+)`")
"""백틱 안의 저장소 경로. **백틱 밖은 안 본다** — 산문의 예시와 구분이 안 된다."""

SKIP_SUFFIXES = (".mp3", ".mid", ".npz", ".jsonl", ".json", ".patch")
"""산출물은 `.park` 뒤에 있어 없는 것이 정상이다 (D-0075)."""

INVOCATION = re.compile(r"(?:python3?|bash|sh)\s+(?:\.\./)?((?:tools|core)/[\w./\-]+\.(?:py|sh))")
"""셸·`Makefile`이 실제로 부르는 스크립트. **`python3 tools/x.py` 꼴 한 줄이다.**"""

TOOL_PATH = re.compile(r"(?:tools|core)/[\w./\-]+\.(?:py|sh)")
"""파이썬 호출 인자에 통째로 적힌 도구 경로. 쪼개져 있어 `INVOCATION`이 못 본다."""


def living_documents() -> list[Path]:
    return [ROOT / name for name in LIVING if (ROOT / name).exists()]


FLOOR_RULES = 18
"""`MASTER`가 선언한 GR의 **바닥** (D-0364 · D-0230). 실측 22개 — 정규식이 망가지면
0을 읽고 「추적되지 않는 규칙 0개」가 거짓으로 참이 된다."""

UNENFORCED_CEILING = 16
"""**코드가 이름을 한 번도 안 드는 GR의 천장** (D-0364).

### 강제자 없는 규칙은 글로 후퇴한다

`DECISIONS`는 절마다 `강제자` 줄을 요구한다 — 361절 전부 있다. **`MASTER`에는 그
요구가 없고, 운영 규칙은 `MASTER`에 산다.** 세샤트/토트 세션이 그 틈에서 당했다:
`MASTER`가 *"옛 규칙은 둘 다 평서로 바꿨다"*라고 **과거형으로** 적고 있었는데 고친
적이 없었고, 단방향 톱니가 그 사이를 몇 주 동안 덮어 164줄이 틀린 채로 돌았다.

### 전부에 강제자를 달라는 뜻이 아니다

강제자가 없는 것이 **정상인 규칙도 있다** — GR-0.3(자율성 경계)·GR-0.4(반대 의무)는
사람의 태도고 기계가 볼 것이 아니다. 그래서 **0을 목표로 두지 않는다.**

막는 것은 **이 수가 자라는 것**이다. 규칙을 새로 적으면서 강제자를 안 달면 16이
되고 그 판에서 막힌다. **줄어도 운다** — 강제자를 달았으면 박아야 다음 판에 그
칸이 안 비어 있다 (D-0363이 이름 천장에서 배운 것과 같다).

실측 22개 중 **시험이 이름을 든 것 6개**다. 「이름을 든다」는 약한 자다 — GR-1.1(케이스)은
`ruff`의 `N` 규칙이 이름을 안 들고 강제한다(내가 오늘 `N806`에 걸렸다). 그래서 이 수는
**「강제자 없음」이 아니라 「추적되지 않음」**으로 읽는다.

**자를 한 번 틀렸다.** 처음엔 `tools/`의 독스트링까지 「이름을 든 것」으로 셌고, 그
덕에 이 독스트링을 쓰는 것만으로 15 → 12가 됐다 — **언급이 강제로 셈해졌다.**
"""

FLOOR_CODE = 40
"""축의 수를 적을 수 있는 코드의 **바닥** (D-0361 · D-0230). 실측 54개."""

COUNT_OK = "doc_fsck: ok"
"""축의 수를 **과거 값으로 인용한 줄**의 면제 선언. **사유와 함께 적는다** (D-0361).

`deadcheck`의 `deadcheck: ok`와 같은 규율이다 — **선언 없는 면제는 없다** (D-0219).
**그 줄이나 바로 윗줄**에 적는다.
<!-- doc_fsck: ok 선언 그 자체를 설명한다 -->
도구 독스트링은 *"D-0261이 여섯째 계약을 넣고 «계약 5종» 세 곳을 안 고쳤다"*처럼
**그때 틀렸던 수**를 적는다. 그것을 실물로 갈아 넣으면 문장이 뜻을 잃는다.
"""


def counting_code() -> list[Path]:
    """축의 수를 **적을 수 있는 코드** (D-0361).

    ### 축은 있었는데 시야에 코드가 없었다

    «관문 도구» 축은 D-0350부터 살아 있었다. 그런데 `check_counts`가 **살아 있는 문서
    <!-- doc_fsck: ok 잡은 값을 인용한다 -->
    셋만** 봤다 — `mutate_gate`의 독스트링이 *"관문 도구 47개"*라 적고 있었고 **실물은
    17(그 축의 셈)도 37(다른 셈)도 아니었다.** 338판이 통과했다.

    D-0349와 같은 자리다: **축은 멀쩡하고 시야가 좁았다.**

    **고치지는 않는다** — `--fix`는 문서만 간다. 코드의 수를 관문이 고치면 주석의
    뜻까지 바뀐다 (D-0288이 표기를 안 건드리는 것과 같은 까닭).
    """
    return sorted((ROOT / "tools").glob("*.py"))


def code_shortfall() -> list[str]:
    """시야가 바닥 밑으로 내려갔나 (D-0361 · D-0230).

    **판정은 입구에서 한다.** `counting_code()`가 직접 울면 임시 뿌리를 쓰는 시험이
    전부 터진다 — 거짓 경보다 (GR-0.8). `check_issue_mentions.shortfall()`과 같은 꼴.
    """
    seen = len(counting_code())
    if seen >= FLOOR_CODE:
        return []
    return [
        f"축을 적을 수 있는 코드를 {seen}개 읽었다(바닥 {FLOOR_CODE}). **그물이 비었다** "
        f"(D-0230) — 비면 이 검사는 D-0361 전으로 돌아간다"
    ]


def check_paths() -> list[str]:
    """문서가 적은 경로가 실재하는가."""
    problems: list[str] = []
    for path in living_documents():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in dict.fromkeys(PATH_LIKE.findall(line)):
                if found.endswith(SKIP_SUFFIXES):
                    continue
                if not (ROOT / found).exists():
                    problems.append(f"{name}:{number}: `{found}`가 없다")
    return problems


def check_commands() -> list[str]:
    """문서가 적은 `python3 tools/x.py`가 실재하는가."""
    runner = re.compile(r"python3?\s+(?:\.\./)?(tools/[\w./\-]+\.py)")
    problems: list[str] = []
    for path in living_documents():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in dict.fromkeys(runner.findall(line)):
                if not (ROOT / found).exists():
                    problems.append(f"{name}:{number}: 명령이 부르는 `{found}`가 없다")
    return problems


def check_orphan_tools() -> list[str]:
    """문서 어디서도 안 불리는 도구가 있는가.

    **`DECISIONS.md`까지 센다.** 도구는 과거 기록이 부르기만 해도 살아 있다 —
    *"왜 만들었나"*가 거기 있기 때문이다.
    """
    blob = "".join(
        path.read_text(encoding="utf-8")
        for path in [
            *living_documents(),
            ROOT / "docs" / "DECISIONS.md",
            ROOT / "Makefile",
        ]
        if path.exists()
    )
    problems: list[str] = []
    for tool in sorted((ROOT / "tools").glob("*.py")):
        if tool.name not in blob:
            problems.append(f"tools/{tool.name}: 문서 어디서도 안 불린다. 쓰이는가")
    return problems


def compose_services() -> list[str]:
    """`docker-compose.yml`의 서비스 이름. **정본은 그 파일이다** (D-0223)."""
    body = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    inside = body.split("\nservices:", 1)[-1].split("\nvolumes:", 1)[0]
    return re.findall(r"(?m)^  ([a-z][a-z0-9-]*):$", inside)


def service_count() -> int:
    """서비스 수. `check_compose`가 메모리로 세는 것과 같은 실물을 센다."""
    return len(compose_services())


GATE_TABLE = "### □ 검사 체계"
"""관문 목록이 사는 절. **표를 콕 집는다** — 살아 있는 문서 전체로 보면 README의
도구표가 대신 만족시켜 `MASTER`가 넷을 빠뜨린 채 통과한다 (D-0350)."""


def check_orphan_workflows() -> list[str]:
    """**실물 워크플로가 살아 있는 문서에 적혀 있나** (D-0349 — `fire-lane`에서 가져왔다).

    ### 거꾸로 보는 눈이 없었다

    `check_paths`와 `check_orphan_tools`는 *"문서가 가리키는 것이 실물로 있나"*와
    *"도구가 문서에 불리나"*를 본다. 그런데 **CI 표는 손으로 적은 목록**이라 워크플로가
    생겨도 아무도 안 적는다 — `codeql.yml`이 **스무 판 넘게** `MASTER`의 CI 표에 없었다.

    `fire-lane`의 `readmecheck`가 같은 자리다 — `web/` 실물과 README 표를 대조한다.
    **문서→실물만 보면 실물이 늘어난 것은 영원히 안 보인다.**

    도구와 달리 **과거 축은 안 센다** — 결정 기록이 한 번 불렀다고 CI 표에 있는 것이
    아니다. 지금 도는 것은 **지금 문서**가 적어야 한다.
    """
    blob = "".join(path.read_text(encoding="utf-8") for path in living_documents())
    lowered = blob.lower()
    problems = [
        f"docker-compose.yml의 `{name}` 서비스를 살아 있는 문서가 안 적는다. "
        f"`MASTER`의 컨테이너 표에 한 줄 더한다 (D-0349)"
        for name in compose_services()
        if name.replace("-", "") not in lowered.replace("-", "").replace(" ", "")
    ]
    if not compose_services():
        problems.append("docker-compose.yml에 서비스가 0개다. **그물이 비었다** (D-0230)")
    # **그 표에만 겨눈다** (D-0350). 살아 있는 문서 전체로 보면 README의 도구표가
    # 대신 만족시켜 **§11이 넷을 빠뜨린 채로 통과한다** — 그것이 첫 판이었다.
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    table = master.split(GATE_TABLE, 1)[-1].split("\n### ", 1)[0] if GATE_TABLE in master else ""
    if not table:
        problems.append(f"`MASTER`에 «{GATE_TABLE}» 절이 없다. **그물이 비었다** (D-0230)")
    problems.extend(
        f"tools/{name}.py가 `--check`를 받는데 **`MASTER` §11 「검사 체계」 표에 없다**. "
        f"한 줄 더한다 (D-0350)"
        for name in gate_tools()
        if table and f"tools/{name}.py" not in table
    )
    if not gate_tools():
        problems.append("`--check`를 받는 관문이 0개다. **그물이 비었다** (D-0230)")
    base = ROOT / ".github" / "workflows"
    if not base.is_dir():
        return [*problems, ".github/workflows가 없다. 실물이 사라졌다"]
    found = sorted(base.glob("*.yml"))
    if not found:
        return [*problems, ".github/workflows에 워크플로가 0개다. **그물이 비었다** (D-0230)"]
    return problems + [
        f"{path.relative_to(ROOT).as_posix()}: 살아 있는 문서가 이 워크플로를 안 적는다. "
        f"`MASTER`의 CI 표에 한 줄 더한다 (D-0349)"
        for path in found
        if path.stem not in blob
    ]


def wiring_files() -> list[Path]:
    """**배선이다** — 문서가 아니라 실제로 실행되는 자리."""
    found = [ROOT / "Makefile", *sorted((ROOT / "tools").glob("*.sh"))]
    for folder in (ROOT / ".githooks", ROOT / ".github" / "workflows"):
        if folder.is_dir():
            found += sorted(path for path in folder.iterdir() if path.is_file())
    return [path for path in found if path.exists()]


def check_wiring() -> list[str]:
    """배선이 부르는 스크립트가 실재하는가 (D-0196 · D-0199).

    **`check_orphan_tools`와 방향이 반대다.** 저쪽은 *"도구가 어디서 불리는가"*를
    묻고 여기는 *"부르는 이름이 실재하는가"*를 묻는다. 그래서 D-0189가 이름을
    `sync_decision_index.py` → `check_decisions.py`로 바꿨을 때 **둘 다 초록이었다** —
    새 이름은 문서가 부르고 있었고, 옛 이름은 아무도 안 봤다.

    그 옛 이름이 `apply_patch.sh`에 남아 `make apply`를 **커밋 직전에** 죽였다.
    붙이기는 이미 끝난 뒤였으므로 사람이 손으로 커밋을 이어 쳤고, 그 결과 커밋
    메시지와 내용이 어긋났다 — O-60(닫힘 D-0196)이 *"도구를 안 쓴 탓"*으로 적은
    것의 실제 원인이다.

    **셸과 파이썬을 다르게 읽는다.** 셸은 `python3 tools/x.py` 꼴 한 줄이고
    주석은 뺀다. 파이썬은 `_run("python3", "tools/x.py")`처럼 **인자가 쪼개져
    있어** 정규식이 못 본다 — `ast`로 호출 인자만 본다. 문서 문자열이 걸리지
    않는 것도 이 방식이라 공짜로 따라온다.
    """
    problems: list[str] = []
    for path in wiring_files():
        name = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for found in dict.fromkeys(INVOCATION.findall(line)):
                if not (ROOT / found).exists():
                    problems.append(f"{name}:{number}: 부르는 `{found}`가 없다")
    return problems + _check_python_calls()


def _check_python_calls() -> list[str]:
    """`tools/*.py`가 호출 인자로 적은 도구 경로가 실재하는가.

    `ship.py`가 `_run("python3", "tools/sync_artifacts.py", "status")`로 부른다.
    **개명하면 같은 자리에서 같은 모양으로 죽는다.**
    """
    problems: list[str] = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        name = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for argument in node.args:
                items = argument.elts if isinstance(argument, ast.List | ast.Tuple) else [argument]
                for item in items:
                    if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                        continue
                    if TOOL_PATH.fullmatch(item.value) and not (ROOT / item.value).exists():
                        problems.append(f"{name}:{item.lineno}: 부르는 `{item.value}`가 없다")
    return problems


def check_reserved_packages() -> list[str]:
    """비어 있는 패키지가 **언제 차는지**를 적었는가 (D-0190).

    빈 폴더 스물둘이 전부 0바이트 `__init__.py`였다. **비운 것이 아니라 열어 둔
    것인데 그 말이 어디에도 없었다** — 마스터에 `engines`가 1회, `artwork`·`score`는
    0회 나온다. 단계표(P1~P8)는 있는데 **어느 단계가 어느 폴더를 채우는지**가 없었다.

    `docstring`이 정본인 저장소에서 **빈 파일은 아무 말도 안 한다.** 적어 두면
    빈 자리가 약속이 되고, 안 적으면 그냥 잊힌 폴더다.

    **차 있는 패키지는 안 본다.** 형제 파일이 있으면 그 파일들이 설명한다.
    """
    base = ROOT / "core" / "hathor"
    if not base.is_dir():
        return []
    problems: list[str] = []
    for init in sorted(base.rglob("__init__.py")):
        if "__pycache__" in init.parts:
            continue
        # **자식이 차 있으면 뿌리는 비어도 된다.** `domain/`은 파일을 안 들고
        # `entities`·`services`를 드는 계층 뿌리이며, 그 폴더들이 설명한다.
        filled = [
            path
            for path in init.parent.rglob("*.py")
            if path.name != "__init__.py" and "__pycache__" not in path.parts
        ]
        if filled or init.stat().st_size:
            continue
        problems.append(f"{init.relative_to(ROOT).as_posix()}: 빈 패키지인데 언제 차는지 안 적혔다")
    return problems


ALBUM_LIFT = re.compile(r"M1(?!\d)[^\n]{0,30}?배")
"""`M1`의 배수를 인용한 자리 (D-0284).

`M1`은 «같은 앨범 찾기»이고 **그 과제가 곧 앨범 효과다** — 같은 앨범은 마스터링이 같아
쉽게 맞고 성능이 부푼다 (Mandel & Ellis, ISMIR 2005). 하네스는 그것을 알고 `M2`에서 같은
앨범을 후보에서 빼는데, **인용이 부푼 쪽을 골랐다.**

밖에 내보일 수는 `M2`다. `M1`을 들려면 **같은 줄에 `M2`나 «앨범»을 같이 적는다** — 읽는
사람이 그 수가 무엇 위의 수인지 알 수 있어야 한다."""


def check_album_lift() -> list[str]:
    """`M1` 배수를 앨범 효과 언급 없이 인용한 자리 (D-0284)."""
    problems: list[str] = []
    for path in living_documents():
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
            if ALBUM_LIFT.search(line) and "M2" not in line and "앨범" not in line:
                where = path.relative_to(ROOT).as_posix()
                problems.append(
                    f"{where}:{number}: `M1` 배수를 앨범 효과 없이 인용했다. "
                    "같은 줄에 `M2`나 «앨범»을 적는다 (D-0284)"
                )
    return problems


def unenforced_rules() -> list[str]:
    """`MASTER`가 선언한 GR 중 **코드가 이름을 한 번도 안 드는 것** (D-0364)."""
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    rules = sorted(set(re.findall(r"GR-\d+\.\d+", master)))
    # **시험이 강제자다** (D-0364). 처음엔 `tools/`까지 봤는데, 이 독스트링이 GR-0.3 ·
    # GR-0.4 · GR-1.1을 입에 올리자 **수가 15에서 12로 좋아졌다** — 강제한 것이 아니라
    # 언급한 것인데 자가 그것을 못 가렸다. `DECISIONS`의 `강제자` 줄이 시험 노드를
    # 가리키는 것과 같은 규율로 **시험만 본다.**
    seen = "".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "core" / "tests").rglob("*.py"))
    )
    return [one for one in rules if one not in seen]


def check_enforcers() -> list[str]:
    """추적되지 않는 규칙의 수가 못과 같은가 (D-0364). **양방향이다.**"""
    rules = sorted(
        set(re.findall(r"GR-\d+\.\d+", (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")))
    )
    if len(rules) < FLOOR_RULES:
        return [
            f"`MASTER`에서 GR을 {len(rules)}개 읽었다(바닥 {FLOOR_RULES}). "
            f"**그물이 비었다** (D-0230)"
        ]
    bare = unenforced_rules()
    if len(bare) > UNENFORCED_CEILING:
        return [
            f"시험이 이름을 안 드는 GR이 {len(bare)}개로 천장 {UNENFORCED_CEILING}개를 "
            f"넘는다: {' · '.join(bare)} — **규칙을 적으면서 강제자를 안 달았다** (D-0364)"
        ]
    if len(bare) < UNENFORCED_CEILING:
        return [
            f"시험이 이름을 안 드는 GR이 {len(bare)}개다(천장 {UNENFORCED_CEILING}). "
            f"**좋아졌으면 박는다** — `UNENFORCED_CEILING`을 {len(bare)}로 내린다 (D-0363)"
        ]
    return []


def check_counts() -> list[str]:
    """문서가 적은 수가 실물과 같은가 (D-0263).

    ### 읽는 자리가 0곳인 축은 죽은 축이다 (D-0350)

    `fire-lane`의 `docgen.apply_all`이 **축이 어느 블록에도 안 걸리면 실패**시킨다. 그
    규율을 안 가져왔더니 **「열린 질문」 축이 읽는 자리 0곳으로 있었다** — 세는 함수는
    멀쩡하고 **비교할 상대가 없어서 영원히 아무것도 못 잡는다.**

    **0건은 통과가 아니다** (D-0230). 축을 놓는 것과 그 축이 **무는** 것은 다르다.
    """
    problems: list[str] = []
    for name, pattern, count in COUNTED:
        real = count()
        read = sum(
            len(pattern.findall(path.read_text(encoding="utf-8"))) for path in living_documents()
        )
        if not read:
            problems.append(
                f"«{name}» 축을 읽는 자리가 **0곳이다** — 살아 있는 문서 중 하나가 그 수를 "
                f"들어야 한다. 안 들면 그 축은 영원히 아무것도 못 잡는다 (D-0350)"
            )
        # **문서만 보면 코드에 적힌 수는 영원히 안 걸린다** (D-0361). 고치는 쪽은
        # 문서만 가고, 코드는 **보기만 한다** — 면제는 `doc_fsck: ok` 선언으로만.
        for path in [*living_documents(), *counting_code()]:
            where = path.relative_to(ROOT).as_posix()
            body = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(body, 1):
                # **그 줄이나 바로 윗줄** — `deadcheck`와 같은 규율이다. 산문 한 줄에
                # 선언까지 붙이면 100자를 넘어 `ruff`가 막는다.
                if COUNT_OK in line or (number > 1 and COUNT_OK in body[number - 2]):
                    continue
                problems += [
                    f"{where}:{number} «{name}»을 {said}이라 적었는데 실물은 {real}이다. "
                    "`make docs-fix` (D-0263 · D-0288 · D-0361)"
                    for said in pattern.findall(line)
                    if int(said) != real
                ]
    return problems


def fix_counts() -> list[str]:
    """축의 수를 **실물로 갈아 넣는다** (D-0288). 고친 자리를 낸다.

    **관문은 이것을 안 부른다.** `--check`만 돈다 — 관문이 문서를 고치면 **사람이 무엇이
    바뀌었는지 모르고**, 그러면 잘못 센 축이 조용히 문서를 망친다 (`fire-lane`의 같은 판단).

    **표기는 안 건드린다.** 라벨도 «건»도 굵게도 그대로 두고 **숫자만** 간다 — 안 그러면
    다음 판에 정규식이 제 자리를 못 찾는다.

    **왜 쓰는 쪽이 필요한가.** 대장은 판마다 한 행씩 는다. 검사만 있으면 **사람이 매번 손으로
    맞추고**, 손으로 맞추는 것이 이 관문이 막으려던 바로 그것이다.
    """
    changed: list[str] = []
    for name, pattern, count in COUNTED:
        real = str(count())
        for path in living_documents():
            body = path.read_text(encoding="utf-8")
            lines = body.split("\n")
            for index, line in enumerate(lines):
                if not pattern.search(line):
                    continue

                def swap(found: re.Match[str], real: str = real) -> str:
                    """**숫자만 간다.** 라벨도 굵게도 그대로 둔다."""
                    return found.group(0).replace(found.group(1), real)

                fixed = pattern.sub(swap, line)
                if fixed != line:
                    lines[index] = fixed
                    changed.append(
                        f"{path.relative_to(ROOT).as_posix()}:{index + 1} «{name}» → {real}"
                    )
            path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="문서 ↔ 실물 대조 (D-0189)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--fix", action="store_true", help="축의 수를 실물로 갈아 넣는다 (D-0288)")
    args = parser.parse_args()

    if args.fix:
        changed = fix_counts()
        for line in changed:
            print(line)
        print(f"축 {len(COUNTED)}개 · 고친 자리 {len(changed)}곳")
        return 0

    problems = code_shortfall() + check_enforcers() + check_paths() + check_commands()
    problems += check_orphan_tools()
    problems += check_wiring() + check_reserved_packages() + check_counts()
    problems += check_album_lift() + check_orphan_workflows()
    if problems:
        print(f"문서가 없는 것을 가리키는 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        f"문서 대조 검사 통과 · 문서 {len(living_documents())}개"
        f"(축을 보는 코드 {len(counting_code())}개) · "
        f"추적 안 되는 규칙 {len(unenforced_rules())}개 · 도구 "
        f"{len(list((ROOT / 'tools').glob('*.py')))}개 · 축 {len(COUNTED)}개 · "
        f"워크플로 {len(list((ROOT / '.github' / 'workflows').glob('*.yml')))}개"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
