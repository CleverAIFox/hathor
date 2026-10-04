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
import sys
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

WIRING_CEILING = 0
"""**배선을 끊어도 안 우는 자리의 천장** (D-0353 → D-0359).

**0이다.** 관문 도구 47개의 입구에서 제 함수를 부르는 자리를 하나씩 끊어도
**전부 운다.** 여기까지 오는 데 수를 네 번 틀렸다:

| 수 | 왜 틀렸나 |
|---|---|
| 62 | `ast.unparse`가 파일을 다시 써 **소스를 읽는 시험이 변이와 무관하게** 터졌다 (D-0353) |
| 53 | 저장소가 더러워 **이미 빨간 시험**을 「내 절단 때문」으로 셌다 (D-0356) |
| 92 | 종료코드 하나만 봐서 **남의 실패도 내 공으로** 셌다 (D-0357) |
| 106 | `ast`의 열이 **바이트** 오프셋인데 글자로 잘라 **엉뚱한 자리가 잘렸다** (D-0358) |
| 103 | 바이트로 자르고 **그 호출이 정말 사라졌는지 센다** |
| **0** | 103곳에 시험을 붙였다 (D-0359) |

**0은 끝이 아니라 못이다.** 새 관문을 쓰면서 입구 배선을 시험 없이 두면 이 수가
올라가고 `check_ratchets`가 그 자리에서 막는다. **빚을 다시 쌓지 않는 장치다.**

0이 되고 나서야 보인 것: **미리 빨간 시험이 그 자리를 겨눈 시험일 수 있다.** 그
시험을 빼고 세면 수가 **위로** 부푼다 — `poisoned`가 그 판을 무효로 만든다 (D-0359).
"""


UNAIMED_CEILING = 3
"""**울었지만 「그 절단을 겨눈 시험」인지 못 보인 자리의 천장** (D-0360).

D-0359까지 이 검사는 *«절단 뒤에 새로 빨개진 시험이 하나라도 있나»*만 봤다. 그러면
**절단이 엉뚱한 것을 깨뜨려 아무 시험이나 울어도 「메워졌다」가 된다** — 0은 상한이
아니라 하한이었다. 그 사실을 D-0359가 적어 두고 **안 쟀다** (GR-0.5).

재 보니 **절단 160건 중 157건은 빨개진 시험이 그 함수 이름을 입에 올린다.** 남은
셋은 `check()`를 통째로 돌리는 시험이 울어서 이름이 안 나온다 — **손으로 셋 다
확인했고 진짜로 그 자리를 겨눈다**(`test_안_부르는_모델이_표에_남으면_잡는다` ·
`test_저장소_기획서가_정본과_맞는다` 둘).

**이름을 부르게 만드는 것이 목표가 아니다.** 통째로 돌리는 시험이 더 좋을 때가 있다.
그래서 막는 것은 **이 수가 늘어나는 것**이다 — 늘면 새로 생긴 자리를 손으로 본다.
"""


def aimed(fresh: set[str], called: str) -> bool:
    """빨개진 시험 중 **그 함수 이름을 입에 올리는 것**이 하나라도 있나 (D-0360).

    약한 증거다 — 이름을 안 불러도 겨눌 수 있다. 그래서 **판정이 아니라 수를 센다.**
    파일을 못 읽으면 **의심하지 않는다**: 못 읽은 것을 혐의로 세면 거짓 경보가 된다
    (GR-0.8).
    """
    for one in fresh:
        where = ROOT / "core" / one.split("::")[0]
        try:
            if called in where.read_text(encoding="utf-8"):
                return True
        except OSError:
            return True
    return False


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
    # **`ast`의 열은 UTF-8 바이트 오프셋이다** (D-0358). 문자 인덱스로 자르면 한글이 있는
    # 줄에서 엉뚱한 자리가 잘린다 — 이 저장소는 거의 전부 한글이라 **대부분의 절단이
    # 빗나갔고**, 빗나간 절단은 그래도 돌아가서 **「안 울었다」로 세어졌다.**
    raw = source.encode("utf-8")
    lines = raw.splitlines(keepends=True)
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
            cut_out = (raw[:at] + b"[]" + raw[to:]).decode("utf-8")
            # **정말 그 호출이 사라졌는지 센다.** 빗나간 절단을 통과시키면 그것이 빈 그물이다.
            if _calls(cut_out, name) >= _calls(source, name):
                return None
            return cut_out
    return None


def _calls(source: str, name: str) -> int:
    """그 이름의 호출이 몇 번 나오나. 문법이 깨졌으면 `-1`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return -1
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    )


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
    """배선을 하나씩 끊어 본다 (D-0353).

    `ONLY=<도구>`를 주면 **그 도구만** 잰다 (D-0358). 전수가 25분이라 106곳을 메우는
    동안 되먹임이 안 돈다 — 한 도구는 1~2분이다. **천장은 전수로만 판정한다.**
    """
    before = dirty_tools()
    tools = gate_tools()
    poisoned: list[str] = []
    unaimed: list[str] = []
    only = os.environ.get("ONLY", "").split()
    if only:
        tools = [one for one in tools if one in only]
        if not tools:
            print(f"그런 관문 도구가 없다: {only}")
            return 1
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
            poisoned.append(name)
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
            if fresh and not aimed(fresh, called):
                # **울었지만 그 절단을 겨눈 시험인지 못 보였다** (D-0360).
                mark += " · 겨눔 불명"
                unaimed.append(f"{name}:{called}")
            print(f"  {name:<24} {called}() 끊음 → {mark}")
            if not fresh:
                survived.append(f"{name}:{called}")

    left = [one for one in dirty_tools() if one not in before]
    if left:
        print(f"\n**변이가 남았다.** 되돌린다: {left}")
        subprocess.run(["git", "checkout", "--", *left], cwd=ROOT, timeout=120, check=False)

    if only:
        # **부분 측정은 천장을 판정하지 않는다** (D-0358 · GR-0.5). 일부를 전체로 읽으면
        # 「줄었다」가 거짓으로 뜬다.
        print(f"\n{only}만 쟀다 — 안 운 배선 {len(survived)}곳: {survived}")
        print(f"겨눔 불명 {len(unaimed)}곳: {unaimed}")
        print("**천장은 전수로만 판정한다.** `ONLY=` 없이 다시 돌린다.")
        return 0

    print(
        f"\n안 운 배선 {len(survived)}곳 (천장 {WIRING_CEILING}) · "
        f"겨눔 불명 {len(unaimed)}곳 (천장 {UNAIMED_CEILING}): {survived or unaimed}"
    )
    if poisoned:
        # **미리 빨간 시험은 그 자리를 겨눈 시험일 수 있다** (D-0359). 그 시험을 빼고
        # 세면 **울었어야 하는 자리가 살아남은 것으로 잡힌다** — 실제로 세 곳이 그렇게
        # 부풀었다(`doc_fsck:living_documents` · `check_args` 둘). 수가 **위로** 틀리므로
        # 천장을 내릴 때는 안 걸리고 **올릴 때 거짓 근거가 된다.**
        print(
            f"**이 수는 못 믿는다.** 미리 빨간 시험이 있는 도구 {len(poisoned)}개: {poisoned}\n"
            "먼저 초록으로 만든다 — `make docs-fix`가 흔한 까닭이다 (GR-0.5).",
            file=sys.stderr,
        )
        return 1
    if len(survived) > WIRING_CEILING:
        print(
            f"**늘었다.** 배선을 끊어도 안 우는 자리가 {len(survived)}곳이다 —"
            f" 시험을 붙이거나 `WIRING_CEILING`을 그만큼 올리고 기록을 쓴다 (D-0353)."
        )
        return 1
    if len(survived) < WIRING_CEILING:
        print(f"**줄었다.** `WIRING_CEILING`을 {len(survived)}로 내려 박는다 (D-0257).")
        return 1
    if len(unaimed) > UNAIMED_CEILING:
        # **「울었다」가 「그 자리를 겨눈 시험이 울었다」와 같지 않다** (D-0360).
        print(
            f"**겨눔 불명이 늘었다.** {len(unaimed)}곳 > 천장 {UNAIMED_CEILING} — "
            f"손으로 보고 맞으면 천장을 올리고 기록을 쓴다: {unaimed}",
            file=sys.stderr,
        )
        return 1
    if len(unaimed) < UNAIMED_CEILING:
        print(f"**줄었다.** `UNAIMED_CEILING`을 {len(unaimed)}로 내려 박는다 (D-0257).")
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
