#!/usr/bin/env python3
"""**부르는 쪽이 주는 인자를 받는 쪽이 받나** (D-0350 · `fire-lane`의 `argcheck`).

### 사용자가 돌린 명령이 조용히 아무것도 안 했다

```
$ make tidy YES=1 FIX=1
치웠다 · 1종 · 실패 0          ← 바이트코드 20개는 그대로다
```

`make ship`이 *"치우려면 `make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 찍는다. 읽으면
**둘 다 `tidy`에 주는 것처럼 보인다.** 그런데 `FIX=1`은 `make ship`의 것이고
(`ship.py --fix`), `tidy`의 레시피는 `YES`만 넘긴다 — **`FIX=1`은 그 자리에서 사라졌다.**

`make hygiene FIX=1`도 같은 자리를 지나갔다 — `$(MAKE) tidy FIX=1`로 넘기는데 받는
쪽이 안 썼다.

### 조용히 무시되는 인자는 D-0064가 이미 닫은 부류다

D-0064가 *"인자가 조용히 무시된다"*를 고쳤고, **검사를 안 넣었더니 네 시간 뒤 같은
부류가 다시 나왔다** (D-0069). 그리고 이번에 **세 번째**다. `fire-lane`은 같은 자리를
`argcheck.py`로 세며 호출 55종 · 인자 17종을 본다.

### 보는 것 둘

| | 묻는 것 |
|---|---|
| **플래그** | 레시피가 `python3 tools/X.py --flag`를 치면 `X.py`가 `--flag`를 받나 |
| **넘기는 변수** | 레시피가 `$(MAKE) 타깃 VAR=1`을 하면 그 타깃이 `$(VAR)`를 쓰나 |

둘째가 이 사고다. **주는 쪽만 보면 안 보인다** — 받는 쪽이 안 쓰는 것이 결함이다.

    python3 tools/check_args.py            # 검사한다
    python3 tools/check_args.py --list     # 호출과 인자를 찍는다
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"
HOOK = ROOT / ".githooks" / "pre-commit"


def shells() -> list[Path]:
    """도구를 부르는 **셸 스크립트 전부** (D-0352).

    첫 판은 `Makefile`과 훅만 봤다. **그러면 셸에서 부르는 자리는 영원히 안 본다** —
    그리고 셸이 부르는 도구가 사라지면 사람이 돌려 보고서야 안다.
    """
    found = [HOOK, *sorted((ROOT / "tools").glob("*.sh"))]
    found += sorted((ROOT / ".devcontainer").glob("*.sh"))
    return [one for one in found if one.exists()]


def workflows() -> list[Path]:
    """워크플로 전부. `run:` 블록이 도구와 `make`를 부른다 (D-0352)."""
    return sorted((ROOT / ".github" / "workflows").glob("*.yml"))


TARGET = re.compile(r"(?m)^([a-z][a-z0-9-]*):")
"""Makefile 타깃 머리. 들여쓴 줄이 그 타깃의 레시피다."""

CALL = re.compile(r"(?m)python3 (tools/[a-z_0-9]+\.py)([^\n]*)$")
r"""도구 호출과 **그 줄의 나머지**.

**줄을 넘지 않는다.** 첫 판이 `\s+`로 꼬리를 받아 **다음 줄들의 플래그까지 끌어왔고**
`gh_ops.py`에 `--ratchet`을 준다고 네 건을 거짓으로 냈다 — 그것이 GR-0.8이다.
"""

ANY_CALL = re.compile(r"(?m)(?:uv run )?python3? (?:\.\./)?(tools/[a-z_0-9]+\.py)([^\n|&;)]*)")
r"""셸·워크플로의 도구 호출 (D-0352).

`Makefile`은 늘 `python3 tools/X.py`지만 워크플로는 `cd core`한 뒤 `uv run python
../tools/X.py`라 **`CALL`이 한 건도 못 읽었다** — 그물이 비어 있던 것이 아니라 **그물을
안 던졌다.**

**꼬리는 `)`에서도 끊는다.** 안 끊으니 `release.yml`의

    gh release create … --title "$(python3 tools/release_notes.py --title)" --notes-file notes.md

에서 `--notes-file`을 그 도구의 인자로 읽고 **거짓 경보를 냈다.** 그것은 `gh`의 인자다.
셸에서 안 가린 `)`는 명령 치환의 끝이다 (GR-0.8).
"""

MAKE_CALL = re.compile(
    r"(?m)(?:^|[|&;(`]|\$\()[ \t]*(?:@)?make[ \t]+(?!-)([a-z][a-z0-9-]*)([^\n|&;)]*)"
)
r"""**명령 자리에 있는 `make <타깃>`만** (D-0352).

실측으로 먼저 틀렸다. `\bmake [a-z]+`로 훑으니 `.devcontainer/post-create.sh`의
`apt-get install -y … make ffmpeg graphviz …`에서 **`make ffmpeg`를 집어 「없는
타깃」이라고 울었다.** `ffmpeg`는 apt 꾸러미 이름이다 — `make`는 거기서 명령이 아니라
인자다. **첫 판이 `--no-print-directory`의 `no`를 집은 것과 같은 자리다** (D-0350).
"""

FLAG = re.compile(r"--[a-z][a-z-]*")
ACCEPTS = re.compile(r'add_argument\(\s*"(--[a-z][a-z-]*)"')
SUBMAKE = re.compile(r"\$\(MAKE\)([^\n]*)")
"""`$(MAKE)` 뒤 꼬리. **타깃은 정규식으로 안 집는다.**

첫 판이 `\b([a-z][a-z0-9-]*)\b`로 집었고 `--no-print-directory`의 **`no`**를 타깃으로
삼아 `tidy`를 지나쳤다 — **그래서 이 검사를 만든 결함을 이 검사가 못 잡았다.** 꼬리를
토큰으로 쪼개 **아는 타깃 이름과 맞는 것**만 쓴다.
"""

HANDED = re.compile(r"([A-Z_]+)=")
"""`$(MAKE)` 꼬리에서 넘기는 변수 이름. `$(if $(FIX),FIX=1,)` 꼴도 잡는다."""

USES = re.compile(r"\$\(([A-Z_]+)\)")

SKIP_FLAGS = ("--help",)
"""argparse가 저절로 주는 것. **목록이 길어지면 검사가 꺼진 것과 같다** — 하나다."""

FLOOR = {"바깥 파일": 10, "도구 호출": 40, "make 호출": 3, "쓰임새 주석": 10}
"""**읽은 수의 바닥 — 조이는 쪽으로만** (D-0352 · D-0230 · D-0058).

워크플로 쪽은 `CALL`이 `python3 tools/…` 꼴만 알아 **한 건도 못 읽고 통과했다.** 화면에
수가 없으니 0인 줄도 몰랐다.

**바닥은 실측이고 올라갈 뿐이다.** 결과에 맞춰 고른 문턱이 아니라 *"여기서 줄면 그물이
줄었다"*는 못이다 — `check_sight`가 상수에 하는 것과 같은 규율이다. 실측은 바깥 파일 10 ·
도구 호출 47 · make 호출 3 · 쓰임새 주석 10이고, 바닥은 그보다 낮게 둔다(도구 호출은 40).
`make 호출`이 3인 것은 **CI가 도구를 바로 부르기 때문**이다 — 워크플로의 `make check`은
전부 주석 안이었고, 처음 그것을 14로 세어 바닥을 12로 잡았다가 틀렸다.
"""

USAGE = re.compile(r"(?m)^#\s+make ([a-z][a-z0-9-]*)([^\n]*)")
"""셸 스크립트 머리의 **쓰임새 주석**. 사람이 그대로 치는 줄이다 (D-0352).

`check_advice`가 파이썬이 찍는 문자열에 하는 것과 같은 자리다 — 타깃 이름을 바꾸면
스크립트 제 설명이 거짓이 되고, **그것을 읽은 사람이 없는 명령을 친다.**
"""


DOC_RUN = re.compile(r"(?m)^\s{4}(python3?) (\S+\.py)([^\n]*)$")
"""도구 독스트링의 **쓰임새 명령 줄**. 사람이 그대로 치는 줄이다 (D-0367)."""

VENV_FREE = 0
"""맨 `python3`로 적어 두고 **묶음이 없으면 못 도는** 도구의 천장 (D-0367).

### 사용자가 그 줄을 그대로 쳤고 터졌다

`probe_id3.py`의 독스트링이 `python3 tools/probe_id3.py --emit`이라 적고 있었다.
`mutagen`은 프로젝트 묶음에 있고 맨 `python3`에는 없다 — **`ModuleNotFoundError`가
그의 터미널에서 났다.** 작성자는 제 컨테이너에서 `uv run`으로 돌려 보고 그 차이를
독스트링에 안 적었다.

`check_usage`는 쓰임새 주석의 **`make` 타깃이 실재하는지**만 봤다 — *«그 인터프리터가
임포트를 할 수 있는지»*는 아무도 안 봤다. **0이 못이다.**

**최상위 임포트만 센다.** `mlflow_sync --dry-run`·`prefect_flow --plan`은 묶음을
늦게 들여오므로 맨 `python3`로 정말 돈다 — 그 둘을 세면 거짓 경보다 (GR-0.8).
"""

OWN_ENV_ALLOWED = ("sync_artifacts", "tidy")
"""`HATHOR_*`를 **제 손으로** 읽어도 되는 도구 — 수가 아니라 이름이다 (D-0367 · D-0363).

정본 해결기는 `hathor.shared.config.paths`다 — `.env`를 읽고 셸 값을 덮지 않는다
(D-0066). 도구가 제 손으로 `os.environ`을 보면 **`.env`가 안 읽힌다.**

둘은 사유가 있다: **맨 `python3`로 돌아야 해서** `hathor`를 못 들여온다 (D-0256과 같은
자리 — `tomllib`은 표준이라 괜찮지만 `hathor`는 설치가 필요하다). 그래서 각자 작은
`.env` 독자를 든다.

`probe_id3`가 세 번째였고 **`.env`를 아예 안 읽었다.** 그가 `.env`에 경로를 적어도
아무 일도 안 일어났을 것이다 — `paths.py` 독스트링이 적어 둔 네 아픔 중 셋째가
**그대로 재발했다.** `uv run`으로 도는 도구이므로 정본 해결기를 쓰게 고쳤다.
"""

STDLIB = frozenset(sys.stdlib_module_names)
"""표준 라이브러리. **`sys`가 들고 있다** — 손으로 적으면 파이썬 판마다 어긋난다."""


def top_level_third_party(tree: ast.Module, local: frozenset[str]) -> set[str]:
    """그 모듈이 **최상위에서** 들여오는 바깥 묶음."""
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            found |= {one.name.split(".")[0] for one in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found - STDLIB - local - {"__future__"}


ENV_NAME = re.compile(r'(?m)^[A-Z_]+ = "(HATHOR_[A-Z_]+)"')
"""도구가 **제 이름으로** 든 `HATHOR_*` 상수. 상수를 거쳐 읽는 자리를 잡는다.

첫 자는 `os.environ.get("HATHOR_…")` **글자 그대로**만 찾았고 **`sync_artifacts`도
`tidy`도 못 봤다** — 둘은 `os.environ.get(STORE_ENV)`처럼 상수를 거친다. 둘을 허락
목록에 넣어 둔 채 자가 둘을 못 보면 **「좋아졌으니 허락을 빼라」가 거짓으로 뜬다.**
"""

ENV_LITERAL = re.compile(r'os\.(?:environ(?:\.get)?[(\[]|getenv\()\s*"(HATHOR_[A-Z_]+)"')
"""글자 그대로 읽는 자리. 상수를 안 두고 바로 읽는 쪽이다 — `probe_id3`가 그랬다."""


def check_own_env() -> list[str]:
    """정본 해결기를 건너뛰고 환경변수를 직접 읽는 자리 (D-0367). **양방향이다.**"""
    seen = set()
    for path in sorted((ROOT / "tools").glob("*.py")):
        body = path.read_text(encoding="utf-8")
        if ENV_LITERAL.search(body) or (ENV_NAME.search(body) and "os.environ" in body):
            seen.add(path.stem)
    extra = sorted(seen - set(OWN_ENV_ALLOWED))
    gone = sorted(set(OWN_ENV_ALLOWED) - seen)
    return [
        f"tools/{name}.py가 `HATHOR_*`를 제 손으로 읽는다 — `.env`가 안 읽힌다. "
        f"`hathor.shared.config.paths`를 쓰거나 `OWN_ENV_ALLOWED`에 사유와 함께 적는다 "
        f"(D-0367 · D-0066)"
        for name in extra
    ] + [
        f"`OWN_ENV_ALLOWED`의 {name}이 더 이상 환경변수를 직접 안 읽는다. "
        f"**좋아졌으면 박는다** — 허락을 빼지 않으면 비어 있는 허가증이다 (D-0363)"
        for name in gone
    ]


def check_venv_usage() -> list[str]:
    """바깥 묶음을 쓰는 도구가 맨 `python3`로 쓰임새를 적었나 (D-0367)."""
    tools = sorted((ROOT / "tools").glob("*.py"))
    local = frozenset({one.stem for one in tools} | {"hathor", "tests"})
    problems: list[str] = []
    for path in tools:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        third = top_level_third_party(tree, local)
        if not third:
            continue
        doc = ast.get_docstring(tree) or ""
        for found in DOC_RUN.finditer(doc):
            problems.append(
                f"tools/{path.name}: 쓰임새가 `{found.group(1)} {found.group(2)}`인데 "
                f"{sorted(third)}를 최상위에서 들여온다 — 묶음이 없으면 못 돈다. "
                f"`cd core && uv run python ../{found.group(2)}`로 적는다 (D-0367)"
            )
    return problems


def recipes(text: str) -> dict[str, list[str]]:
    """타깃 → 그 레시피 줄들. **들여쓴 줄만 센다.**"""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        head = TARGET.match(line)
        if head:
            current = head.group(1)
            found.setdefault(current, [])
            continue
        if current and line.startswith(("\t", "    ")):
            found[current].append(line)
        elif line and not line.startswith((" ", "\t", "#")):
            current = None
    return found


def accepted(tool: str) -> set[str]:
    """그 도구가 받는 플래그. **`argparse`를 안 돌린다** — 소스에서 읽는다."""
    path = ROOT / tool
    if not path.exists():
        raise LookupError(f"{tool}이 없다. 정본이 사라졌다")
    return set(ACCEPTS.findall(path.read_text(encoding="utf-8")))


def check_flags(text: str, where: str) -> list[str]:
    """레시피가 주는 플래그를 도구가 받나."""
    problems: list[str] = []
    for tool, tail in CALL.findall(text):
        if not (ROOT / tool).exists():
            problems.append(f"{where}: `{tool}`을 부르는데 그 파일이 없다")
            continue
        takes = accepted(tool)
        problems.extend(
            f"{where}: `{tool}`에 `{flag}`를 주는데 그 도구가 안 받는다 — "
            f"**조용히 무시된다** (D-0064 · D-0069)"
            for flag in dict.fromkeys(FLAG.findall(tail))
            if flag not in takes and flag not in SKIP_FLAGS
        )
    return problems


def check_passthrough(text: str) -> list[str]:
    """`$(MAKE) 타깃 VAR=1`을 넘기면 그 타깃이 `$(VAR)`를 쓰나 (D-0350).

    **받는 쪽을 봐야 보인다.** 주는 쪽만 보면 `FIX=1`은 멀쩡해 보인다.
    """
    made = recipes(text)
    problems: list[str] = []
    for caller, lines in sorted(made.items()):
        for line in lines:
            for tail in SUBMAKE.findall(line):
                tokens = re.split(r"[\s=,)]+", tail)
                targets = [one for one in tokens if one in made]
                if not targets:
                    continue
                body = "\n".join(made[targets[0]])
                used = set(USES.findall(body))
                problems.extend(
                    f"Makefile: `{caller}`가 `{targets[0]}`에 `{variable}=1`을 넘기는데 "
                    f"`{targets[0]}`이 `$({variable})`를 안 쓴다 — **그 자리에서 사라진다**"
                    for variable in dict.fromkeys(HANDED.findall(tail))
                    if variable not in used
                )
    return problems


STEP = re.compile(r"(?m)^      - ")
"""워크플로의 단계 머리. 단계마다 제 `working-directory`를 가질 수 있다."""

DEFAULT_DIR = re.compile(r"(?m)^defaults:\n  run:\n    working-directory: (\S+)")
WHERE = re.compile(r"(?m)^        working-directory:\s*(\S+)")
UP_CALL = re.compile(r"(?m)(?:uv run )?python3? ((?:\.\./)?tools/[a-z_0-9]+\.py)")


def check_workdir(text: str, where: str) -> list[str]:
    """워크플로가 도구를 **맞는 디렉터리에서** 부르나 (D-0356).

    실측으로 CI가 빨개져서 알았다 — `ci.yml`은 `defaults: working-directory: core`를
    두고, 관문 단계마다 `working-directory: .`를 **다시 적는다.** 스물셋이 그렇게 적혀
    있었고 **내가 더한 하나만 빠뜨렸다.** CI는 *"No such file or directory"* 한 줄을 냈다.

    `core`에서 돌면 `../tools/X.py`, 뿌리에서 돌면 `tools/X.py`다. **둘이 어긋나면 잡는다.**
    `actionlint`도 `test_ci_parity`도 이 자리를 안 본다.
    """
    found = DEFAULT_DIR.search(text)
    base = found.group(1) if found else "."
    problems: list[str] = []
    for step in STEP.split(text)[1:]:
        here = WHERE.search(step)
        folder = here.group(1) if here else base
        at_root = folder in {".", "./"}
        for tool in UP_CALL.findall(step):
            up = tool.startswith("../")
            if at_root is up:
                problems.append(
                    f"{where}: `{tool}`을 `working-directory: {folder}`에서 부른다 — "
                    f"**그 자리에 그 파일이 없다** (D-0356)"
                )
    return problems


def run_blocks(text: str) -> str:
    """워크플로의 `run:` 블록만 모은다 (D-0352).

    `with:`·`env:`의 값까지 훑으면 **설정 문자열을 명령으로 읽는다.** 블록 스칼라(`|`)와
    한 줄 꼴을 둘 다 받고, 들여쓰기가 `run:`보다 깊은 동안만 이어 붙인다.
    """
    lines = text.splitlines()
    kept: list[str] = []
    depth: int | None = None
    for line in lines:
        bare = line.lstrip()
        if depth is not None:
            if not bare:
                kept.append("")
                continue
            if len(line) - len(bare) > depth:
                kept.append(bare)
                continue
            depth = None
        head = re.match(r"(\s*)-?\s*run:\s*(.*)$", line)
        if head:
            depth = len(head.group(1))
            rest = head.group(2).strip()
            if rest and rest not in {"|", ">", "|-", ">-"}:
                kept.append(rest)
    return "\n".join(kept)


def check_any_calls(text: str, where: str) -> list[str]:
    """셸·워크플로가 부르는 도구와 플래그 (D-0352)."""
    problems: list[str] = []
    for tool, tail in ANY_CALL.findall(text):
        if not (ROOT / tool).exists():
            problems.append(f"{where}: `{tool}`을 부르는데 그 파일이 없다")
            continue
        takes = accepted(tool)
        problems.extend(
            f"{where}: `{tool}`에 `{flag}`를 주는데 그 도구가 안 받는다 — "
            f"**조용히 무시된다** (D-0064 · D-0069)"
            for flag in dict.fromkeys(FLAG.findall(tail))
            if flag not in takes and flag not in SKIP_FLAGS
        )
    return problems


def check_usage(text: str, where: str, made: dict[str, list[str]]) -> list[str]:
    """쓰임새 주석이 실재하는 타깃을 가리키나 (D-0352)."""
    return [
        f"{where}: 쓰임새 주석이 `make {target}`을 알려 주는데 그 타깃이 없다"
        for target, _ in USAGE.findall(text)
        if target not in made
    ]


def check_make_calls(text: str, where: str, made: dict[str, list[str]]) -> list[str]:
    """셸·워크플로가 부르는 `make <타깃>`이 실재하나, 넘기는 변수를 쓰나 (D-0352).

    **타깃 이름을 셸에 손으로 적는 자리가 열넷이다.** 하나가 사라지면 CI나 컨테이너가
    처음 뜰 때 터지고, 그때는 아무도 안 보고 있다.
    """
    problems: list[str] = []
    for target, tail in MAKE_CALL.findall(text):
        if target not in made:
            problems.append(f"{where}: `make {target}`을 부르는데 그 타깃이 없다")
            continue
        used = set(USES.findall("\n".join(made[target])))
        problems.extend(
            f"{where}: `make {target} {variable}=1`을 주는데 "
            f"`{target}`이 `$({variable})`를 안 쓴다 — **그 자리에서 사라진다**"
            for variable in dict.fromkeys(re.findall(r"([A-Z_]+)=", tail))
            if variable not in used
        )
    return problems


def printed_strings(path: Path) -> list[tuple[int, str]]:
    """그 파일이 **화면에 찍을 수 있는 문자열**. 문서 문자열은 뺀다 (D-0350).

    문서 문자열까지 훑으면 **이 파일이 사고를 설명하는 문장**에 제 검사가 걸린다 —
    첫 판이 그랬다. 설명과 출력은 다르다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs: set[int] = set()
    # **홀로 선 문자열 문장은 출력이 아니다.** 첫 판은 블록의 **첫 줄**만 문서로 봤고,
    # 그래서 `X = re.compile(...)` 아래 붙는 **속성 문서 문자열**을 출력으로 읽었다 —
    # 이 파일이 `make ffmpeg graphviz`라는 apt 줄을 설명하자 제 검사가 거기 걸렸다.
    # 찍는 문자열은 늘 **인자이거나 대입된 값**이고, 문장으로 홀로 서지 않는다 (D-0352).
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            docs.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.lineno not in docs
    ]


def check_advice() -> list[str]:
    """화면이 알려 주는 명령이 실제로 그 일을 하나 (D-0350 · D-0310과 같은 자리).

    `ship`이 *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 찍었고 **읽으면 둘 다
    `tidy`에 주는 것으로 읽힌다.** 사용자가 그대로 쳤고 아무 일도 안 났다.

    여기서는 **도구가 찍는 문자열 안의 `make <타깃> <VAR>=1`**을 훑어 그 타깃이 그
    변수를 쓰는지 본다 — 화면이 거짓을 알려 주면 그것은 **없는 명령을 주는 것**이다.
    """
    made = recipes(MAKEFILE.read_text(encoding="utf-8"))
    advice = re.compile(r"make ([a-z][a-z0-9-]*)(.*)")
    """`make <타깃>`과 **그 뒤 전부.**

    첫 판은 `(?:\\s+[A-Z_]+=1)+`로 **붙어 있는 것만** 봤다. 그런데 사고가 난 문장은
    *"`make tidy YES=1` · 바이트코드는 `FIX=1`"*이라 `FIX=1`이 **떨어져 있었고**
    사용자는 둘을 같이 쳤다. **읽는 대로 잡는다.**
    """
    problems: list[str] = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        for number, line in printed_strings(path):
            for target, tail in advice.findall(line):
                if target not in made:
                    problems.append(
                        f"{path.relative_to(ROOT).as_posix()}:{number}: "
                        f"`make {target}`을 알려 주는데 그 타깃이 없다"
                    )
                    continue
                body = "\n".join(made[target])
                problems.extend(
                    f"{path.relative_to(ROOT).as_posix()}:{number}: "
                    f"`make {target} {variable}=1`을 알려 주는데 "
                    f"`{target}`이 `$({variable})`를 안 쓴다 — **화면이 거짓을 준다**"
                    for variable in re.findall(r"([A-Z_]+)=1", tail)
                    if variable not in set(USES.findall(body))
                )
    return problems


def sources() -> list[tuple[str, str]]:
    """검사할 (이름, 본문) 전부. **셋을 한 자리에서 센다** (D-0352 · D-0230).

    셸은 본문 그대로, 워크플로는 `run:` 블록만 본다.
    """
    found: list[tuple[str, str]] = []
    for path in shells():
        found.append((path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))
    for path in workflows():
        name = path.relative_to(ROOT).as_posix()
        found.append((f"{name} (run:)", run_blocks(path.read_text(encoding="utf-8"))))
    return found


def check_workflow_dirs() -> list[str]:
    """워크플로 전부의 `working-directory` 대조 (D-0356)."""
    problems: list[str] = []
    for path in workflows():
        name = path.relative_to(ROOT).as_posix()
        problems += check_workdir(path.read_text(encoding="utf-8"), name)
    return problems


def check() -> list[str]:
    make = MAKEFILE.read_text(encoding="utf-8")
    made = recipes(make)
    problems = check_flags(make, "Makefile")
    for where, text in sources():
        problems += check_any_calls(text, where)
        problems += check_make_calls(text, where, made)
        problems += check_usage(text, where, made)
    problems += check_venv_usage() + check_own_env()
    return problems + check_passthrough(make) + check_advice() + check_workflow_dirs()


def main() -> int:
    parser = argparse.ArgumentParser(description="부르는 쪽 ↔ 받는 쪽 인자 대조 (D-0350)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="호출과 인자를 찍는다")
    args = parser.parse_args()

    make = MAKEFILE.read_text(encoding="utf-8")
    calls = CALL.findall(make)
    if args.list:
        for tool, tail in calls:
            flags = " ".join(dict.fromkeys(FLAG.findall(tail))) or "—"
            print(f"  {tool:34s} {flags}")
        return 0

    # **던진 그물을 전부 센다** (D-0230). 워크플로 쪽은 `CALL`이 한 건도 못 읽고 있었고
    # 통과가 떴다 — 수가 화면에 없었으니 아무도 0인 것을 몰랐다 (D-0352).
    outside = sources()
    read = {
        "바깥 파일": len(outside),
        "도구 호출": sum(len(ANY_CALL.findall(text)) for _, text in outside),
        "make 호출": sum(len(MAKE_CALL.findall(text)) for _, text in outside),
        "쓰임새 주석": sum(len(USAGE.findall(text)) for _, text in outside),
    }
    short = [f"{key} {got}(바닥 {FLOOR[key]})" for key, got in read.items() if got < FLOOR[key]]
    if not calls or short:
        print(
            f"읽은 것이 바닥 아래다 — Makefile 호출 {len(calls)} · " + " · ".join(short or ["—"]),
            file=sys.stderr,
        )
        print("**그물이 비었다** (D-0230)", file=sys.stderr)
        return 1

    problems = check()
    if problems:
        print(f"주는 인자와 받는 인자가 어긋난 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    tools = len({tool for tool, _ in calls})
    print(
        f"인자 대조 검사 통과 · 호출 {len(calls)}종 · 도구 {tools}개 · "
        f"바깥 파일 {read['바깥 파일']}개(도구 {read['도구 호출']} · make {read['make 호출']} · "
        f"쓰임새 {read['쓰임새 주석']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
