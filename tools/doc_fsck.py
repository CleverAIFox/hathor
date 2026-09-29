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
from collections.abc import Callable
from pathlib import Path

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


def contract_count() -> int:
    """`import-linter` 계약의 실제 수."""
    body = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    return body.count("[[tool.importlinter.contracts]]")


LEDGER = ("<!-- decision-ledger:begin -->", "<!-- decision-ledger:end -->")
"""결정 대장이 사는 자리. **표식 밖의 `| D-xxxx |` 행은 안 센다** — `MASTER`에는
기록 번호를 드는 표가 대장 말고도 있고, 전부 세면 230과 223처럼 **말없이 갈린다.**"""


def _ledger() -> list[str]:
    """대장 행의 `자료` 칸. 행 수는 길이다."""
    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    if LEDGER[0] not in body:
        return []
    inside = body.split(LEDGER[0])[1].split(LEDGER[1])[0]
    return [source.strip() for source in re.findall(r"(?m)^\| D-\d{4} \|.*\| ([^|]+) \|$", inside)]


def ledger_rows() -> int:
    """결정 대장의 행 수 — **강제자를 적은 기록의 수**다 (D-0193)."""
    return len(_ledger())


def synthetic_rows() -> int:
    """대장에서 **`자료 합성`으로만 선 판단**의 수 (D-0265). PLAN §3이 이 수를 든다."""
    return sum(1 for source in _ledger() if source == "합성")


def unknown_reproductions() -> int:
    """`재현 불명`으로 남은 기록의 수 (D-0307). PLAN §3의 빚 행이 이 수를 든다.

    **PLAN이 16이라 적고 실물은 11이었다.** 다섯이 어디서 줄었는지 아무도 모른다 — 수가
    틀려도 아무 일이 안 일어나는 자리이기 때문이다 (D-0263의 논거 그대로).

    `재현`은 *"지금 이 수치를 다시 내는 명령"*이라 **현재 사실이고 조사할 수 있다**
    (D-0136). 조사하면 줄어드는 수이므로 **세는 자리가 필요하다.**
    """
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(r"(?m)^재현 불명", body))


def open_issues() -> int:
    """열린 질문의 수. **`check_decisions`가 표 자체는 이미 보고, 여기는 산문의 수를 본다.**"""
    body = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    inside = body.split("<!-- open-issues:begin -->")[-1].split("<!-- open-issues:end -->")[0]
    return len(re.findall(r"(?m)^\| O-\d+ \|", inside))


BOLD = r"\*{0,2}(\d+)\*{0,2}\s*"
"""수 하나. **굵게를 양쪽 다 받는다** — 이 문서들은 크기를 `**24**`로 적는다.

한쪽만 받다가 `대장 **201**건`을 못 찾았다. 못 찾는 축은 **조용히 통과한다** — 그것이
`docnum_check`가 2026-09-02에 메운 구멍과 같은 꼴이다."""


COUNTED: tuple[tuple[str, re.Pattern[str], Callable[[], int]], ...] = (
    ("import-linter 계약", re.compile(rf"(?:계약|import-linter)\s*{BOLD}종"), contract_count),
    ("결정 대장", re.compile(rf"대장\s*{BOLD}건\s*중"), ledger_rows),
    ("합성으로만 선 판단", re.compile(rf"합성\s*{BOLD}\s*·"), synthetic_rows),
    ("열린 질문", re.compile(rf"열린 질문\s*{BOLD}건"), open_issues),
    ("재현 불명", re.compile(rf"재현 불명\s*{BOLD}건"), unknown_reproductions),
)
"""문서가 **세어서 적은 수**와 실물 (D-0263).

D-0261이 여섯째 계약을 넣고 **`MASTER`의 «계약 5종» 세 곳을 안 고쳤다.** 경로도
도구도 실재하므로 이 검사의 다른 눈에는 안 걸렸다 — **숫자만 틀렸다.**

경로가 틀리면 명령이 죽어서 알게 되지만, **수가 틀리면 아무 일도 안 일어난다.**
읽는 사람만 틀린 것을 배운다. 그래서 세는 자리를 여기 둔다.

### 축이 하나에서 넷이 됐다 (D-0288)

`fire-lane`이 같은 자리를 `docgen.py`로 풀었다 — 정본이 있는 값마다 **축**을 선언하고,
문서는 그 수를 **들기만 한다.** 그쪽 실측이 이랬다: 전수 절 수가 **하루에 네 번** 손으로
맞춰졌고(1,004 → 1,017 → 1,030 → 1,033 → 1,036), *"손으로 적으면 낡는다"*고 적은 절
자신이 낡아 있었다.

우리도 같은 값을 물었다. **「대장 201건 중」이 실물 223일 때까지 아무도 안 셌다** — 그
줄이 사는 표의 머리말이 *"크기를 재서 적는다. 안 재고 적으면 영원히 다음 세션이다"*다.

**블록 표식(`<!--gen: 축-->`)은 안 쓴다.** 그쪽 수는 제목 줄에 살고 우리 수는 **표 칸
안에** 사는데, 빈 줄이 표를 끊는다(`check_doc_style`). 대신 **라벨 옆의 수**를 읽는다 —
그쪽이 2026-09-02에 「정답이 파일 어딘가에 있나」만 보던 구멍을 메운 방식이다.

**정본이 없는 값은 축으로 안 만든다.** «1004곡»·«281판»은 그때의 실측이고 축이 아니다."""


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


def check_counts() -> list[str]:
    """문서가 적은 수가 실물과 같은가 (D-0263)."""
    problems: list[str] = []
    for name, pattern, count in COUNTED:
        real = count()
        for path in living_documents():
            where = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                problems += [
                    f"{where}:{number} «{name}»을 {said}이라 적었는데 실물은 {real}이다. "
                    "`make docs-fix` (D-0263 · D-0288)"
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

    problems = check_paths() + check_commands() + check_orphan_tools()
    problems += check_wiring() + check_reserved_packages() + check_counts()
    problems += check_album_lift()
    if problems:
        print(f"문서가 없는 것을 가리키는 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        f"문서 대조 검사 통과 · 문서 {len(living_documents())}개 · 도구 "
        f"{len(list((ROOT / 'tools').glob('*.py')))}개"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
