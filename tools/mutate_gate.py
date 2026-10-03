#!/usr/bin/env python3
"""관문 도구를 하나씩 망가뜨려 **시험이 실제로 우는지** 본다 (D-0259).

### 왜

`test_gate_tools.py`가 «시험이 이 도구를 연다»를 세지만, **여는 것과 미는 것은 다르다.**
실측으로 확인했다 — `register_runner.sh`에 `exit 7`을 넣어도 아무 시험도 안 울었다.
그 시험들은 소스 텍스트에서 문자열을 찾을 뿐 스크립트를 돌리지 않는다.

### 어떻게

비교 연산자를 전부 뒤집는다 — `<`↔`>=` · `==`↔`!=` · `in`↔`not in`. 판정 로직이 있는
도구라면 어느 시험이든 빨개져야 한다. **안 빨개지면 그 도구는 이름만 걸려 있다.**

### 배선도 끊어 본다 (D-0353)

비교를 뒤집는 것으로는 **호출을 지우는 결함**을 못 잡는다. 실측으로 두 번 물렸다 —
`check()`에서 `check_usage(…)` 한 줄을, `main()`에서 `check_heads()`를, 그리고 다시
`check()`에서 `verdict(here, BASELINE)`을 지워도 **아무 시험도 안 울었다.** 시험이 그
함수를 **직접** 부르고 있었기 때문이다. **부품은 재고 배선은 안 쟀다.**

`--wiring`은 관문 도구의 `check()`·`main()` 안에서 **제 모듈 함수를 부르는 문장을 하나씩
지운다.** 지웠는데 안 울면 그 배선은 아무도 안 보고 있다. 전체 시험이 아니라 **그 도구의
시험 파일만** 돌려 빠르다.

### 관문에는 안 붙인다

26개를 하나씩 망가뜨리고 매번 전체 시험을 도는 데 25분이 걸린다. `make check`에 넣으면
사람이 검사를 끄게 된다 (D-0126 · D-0129에서 되풀이해 확인한 것이다). **손으로 부른다.**

    make mutate            # 비교를 뒤집는다. 25분
    make mutate WIRING=1   # 배선을 끊는다. 빠르다
"""

from __future__ import annotations

import ast
import contextlib
import os
import re
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLIP = {
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}


class Flipper(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        self.generic_visit(node)
        new = []
        for op in node.ops:
            swap = FLIP.get(type(op))
            if swap is None:
                new.append(op)
            else:
                new.append(swap())
                self.count += 1
        node.ops = new
        return node


def gate_tools() -> list[str]:
    callers = [
        ROOT / "Makefile",
        ROOT / ".githooks" / "pre-commit",
        *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
    ]
    blob = "\n".join(p.read_text(encoding="utf-8") for p in callers if p.exists())
    return sorted(set(re.findall(r"tools/([a-z_0-9]+)\.py", blob)))


ENTRIES = ("check", "main")
"""배선을 보는 자리. 관문의 입구다."""

WIRING_CEILING = 106
"""**배선을 끊어도 안 우는 자리의 천장** (D-0353).

실측 **106곳**이다. 거기까지 오는 데 세 번 틀렸다:

| 수 | 왜 틀렸나 |
|---|---|
| 62 | `ast.unparse`가 파일을 다시 써 **소스를 읽는 시험이 변이와 무관하게** 터졌다 (D-0353) |
| 53 | 저장소가 더러워 **이미 빨간 시험**을 「내 절단 때문」으로 셌다 (D-0356) |
| 92 | 종료코드 하나만 봐서 **남의 실패도 내 공으로** 셌다 (D-0357) |
| **106** | 빨간 **이름**을 대조한다. 두 판을 돌려 **수도 목록도 같았다** |

한 판에 다 메울 수 있는 수가 아니고, **메우는 척하지도 않는다** —
이 수는 `check_ratchets`가 못으로 들고 있어서 **올라가면 빨개지고 내려가면 조인다.**
0이 되는 날이 이 빚을 다 갚은 날이다.

`check_doc_style`·`encoding_check`의 열둘은 D-0356에서 메웠다.
"""


def own_functions(tree: ast.Module) -> set[str]:
    """그 모듈이 가진 최상위 함수 이름."""
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def wiring(tree: ast.Module) -> list[tuple[int, str]]:
    """`check()`·`main()` 안에서 **제 모듈 함수를 부르는 문장**의 (줄, 이름)."""
    mine = own_functions(tree)
    found: list[tuple[int, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in ENTRIES:
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Name):
                continue
            if inner.func.id in mine and inner.func.id not in ENTRIES:
                found.append((inner.lineno, inner.func.id))
    return sorted(set(found))


def cut(source: str, line: int, name: str) -> str | None:
    """그 호출 하나를 **빈 목록으로** 바꾼다. 없으면 `None`.

    **글자 단위로 자른다.** 첫 판은 `ast.unparse`로 파일을 통째로 다시 썼고, 그러면
    **소스를 읽는 시험이 변이와 무관하게 터진다** — `BASELINE` 블록이 한 줄로 합쳐져
    `check_ratchets`의 배선 다섯이 전부 「울었다」로 나왔다. **거짓 빨강은 거짓 초록보다
    나쁘다** — 메울 자리를 가린다 (GR-0.8 · D-0353).
    """
    lines = source.splitlines(keepends=True)
    starts = [0]
    for one in lines:
        starts.append(starts[-1] + len(one))
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and node.lineno == line
            and node.end_lineno is not None
            and node.end_col_offset is not None
        ):
            at = starts[node.lineno - 1] + node.col_offset
            to = starts[node.end_lineno - 1] + node.end_col_offset
            return source[:at] + "[]" + source[to:]
    return None


def tests_for(name: str) -> list[str]:
    """그 도구를 여는 시험 파일. **없으면 빈 목록** — 그것 자체가 결함이다 (D-0257)."""
    found = []
    for path in sorted((ROOT / "core" / "tests" / "unit").glob("test_*.py")):
        if name in path.read_text(encoding="utf-8"):
            found.append(f"tests/unit/{path.name}")
    return found


FAILED = re.compile(r"(?m)^FAILED (\S+)")


def failing(targets: list[str]) -> set[str]:
    """그 시험 묶음에서 **빨간 시험의 이름**을 돌려준다 (D-0357).

    첫 판은 **종료코드 하나**만 봤다. 그러면 *"내 절단 때문에 울었다"*와 *"원래 빨갰다"*가
    구분이 안 된다 — 실측으로 생존자 수가 **53 ↔ 92**로 흔들렸고 53이 틀렸다 (D-0356).
    D-0356은 「이미 빨가면 못 쟀다고 적고 막는다」로 때웠는데, **그러면 빨간 날에는 아예
    못 잰다.**

    이름을 받아 오면 **새로 빨개진 것만** 보면 된다. 원래 빨간 것이 있어도 잴 수 있다.
    `-x`도 뗀다 — 첫 실패에서 멈추면 **기준 판의 목록이 잘려** 없던 실패가 새 실패로 보인다.
    """
    done = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "pytest",
            *targets,
            "-q",
            "--no-cov",
            "--tb=no",
            "-rf",
            "-p",
            "no:randomly",
        ],
        cwd=ROOT / "core",
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    found = set(FAILED.findall(done.stdout))
    if not found and done.returncode != 0:
        # 수집 오류·임포트 실패는 이름이 안 찍힌다. **모르는 것을 0으로 세지 않는다** (GR-0.5).
        return {"(이름 없는 실패)"}
    return found


def restore_on_death(path: Path, original: str) -> None:
    """**죽어도 되돌린다** (D-0353).

    첫 배선 판이 시간 제한에 `SIGKILL`로 죽으면서 `sync_artifacts.py`를 **변이된 채로
    남겼다.** `finally`는 그때 안 돈다. `check_args`가 *"`--full`을 안 받는다"*로
    잡아서야 알았다 — **잡은 것이 다행이고, 남긴 것이 결함이다.** 변이 도구가 저장소를
    망가뜨린 채 끝나면 그 다음 사람이 그것을 커밋한다.
    """

    def put_back(*_: object) -> None:
        path.write_text(original, encoding="utf-8")
        raise SystemExit(130)

    for which in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        with contextlib.suppress(ValueError, OSError):
            signal.signal(which, put_back)


def dirty_tools() -> list[str]:
    """`tools/`에 커밋 안 된 변경. **시작 전과 끝난 뒤에 본다.**"""
    done = subprocess.run(
        ["git", "status", "--porcelain", "--", "tools/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return [line[3:] for line in done.stdout.split("\n") if line]


def cut_wiring() -> int:
    """배선을 하나씩 끊어 본다 (D-0353)."""
    before = dirty_tools()
    tools = gate_tools()
    print(f"관문 도구 {len(tools)}개의 배선을 끊어 본다\n")
    survived: list[str] = []
    for name in tools:
        path = ROOT / "tools" / f"{name}.py"
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        restore_on_death(path, original)
        wires = wiring(ast.parse(original))
        targets = tests_for(name)
        if not wires:
            print(f"  {name:<24} 입구에서 제 함수를 안 부른다 — 건너뛴다")
            continue
        if not targets:
            print(f"  {name:<24} **여는 시험이 없다**")
            survived.append(f"{name}(시험 없음)")
            continue
        # **자르기 전에 한 번 돌려 빨간 이름을 적어 둔다** (D-0356 → D-0357). 그래야
        # *"내 절단 때문에 울었다"*와 *"원래 빨갰다"*가 갈린다. 이름을 보므로 **원래 빨간
        # 것이 있어도 잴 수 있다** — D-0356은 그때 아예 못 쟀다.
        was_red = failing(targets)
        if was_red:
            print(f"  {name:<24} 미리 빨간 시험 {len(was_red)}개 — 그것 말고 센다")
        for line, called in wires:
            maimed = cut(original, line, called)
            if maimed is None or maimed == original:
                continue
            try:
                ast.parse(maimed)
            except SyntaxError:
                print(f"  {name:<24} {called}() 끊으면 문법이 깨진다 — 건너뛴다")
                continue
            path.write_text(maimed, encoding="utf-8")
            try:
                now_red = failing(targets)
            finally:
                path.write_text(original, encoding="utf-8")
            fresh = now_red - was_red
            mark = f"울었다 ({len(fresh)}건)" if fresh else "**안 울었다**"
            print(f"  {name:<24} {called}() 끊음 → {mark}")
            if not fresh:
                survived.append(f"{name}:{called}")

    left = [one for one in dirty_tools() if one not in before]
    if left:
        print(f"\n**변이가 남았다.** 되돌린다: {left}")
        subprocess.run(["git", "checkout", "--", *left], cwd=ROOT, timeout=120, check=False)

    print(f"\n안 운 배선 {len(survived)}곳 (천장 {WIRING_CEILING}): {survived}")
    if len(survived) > WIRING_CEILING:
        print(
            f"**늘었다.** 배선을 끊어도 안 우는 자리가 {len(survived)}곳이다 —"
            f" 시험을 붙이거나 `WIRING_CEILING`을 그만큼 올리고 기록을 쓴다 (D-0353)."
        )
        return 1
    if len(survived) < WIRING_CEILING:
        print(f"**줄었다.** `WIRING_CEILING`을 {len(survived)}로 내려 박는다 (D-0257).")
        return 1
    return 0


def main() -> int:
    if os.environ.get("WIRING"):
        return cut_wiring()
    tools = gate_tools()
    print(f"관문 도구 {len(tools)}개를 하나씩 망가뜨린다\n")
    survived: list[str] = []
    for name in tools:
        path = ROOT / "tools" / f"{name}.py"
        original = path.read_text(encoding="utf-8")
        tree = ast.parse(original)
        flipper = Flipper()
        tree = flipper.visit(tree)
        if flipper.count == 0:
            print(f"  {name:<24} 비교가 없다 — 건너뛴다")
            continue
        path.write_text(ast.unparse(ast.fix_missing_locations(tree)), encoding="utf-8")
        try:
            done = subprocess.run(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "pytest",
                    "tests/unit",
                    "-x",
                    "-q",
                    "--no-cov",
                    "-p",
                    "no:randomly",
                ],
                cwd=ROOT / "core",
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
        finally:
            path.write_text(original, encoding="utf-8")
        mark = "울었다" if done.returncode != 0 else "**안 울었다**"
        print(f"  {name:<24} 비교 {flipper.count:>3}개 뒤집음 → {mark}")
        if done.returncode == 0:
            survived.append(name)

    print(f"\n안 운 도구 {len(survived)}개: {survived}")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
