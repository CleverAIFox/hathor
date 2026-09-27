#!/usr/bin/env python3
"""관문 도구를 하나씩 망가뜨려 **시험이 실제로 우는지** 본다 (D-0259).

### 왜

`test_gate_tools.py`가 «시험이 이 도구를 연다»를 세지만, **여는 것과 미는 것은 다르다.**
실측으로 확인했다 — `register_runner.sh`에 `exit 7`을 넣어도 아무 시험도 안 울었다.
그 시험들은 소스 텍스트에서 문자열을 찾을 뿐 스크립트를 돌리지 않는다.

### 어떻게

비교 연산자를 전부 뒤집는다 — `<`↔`>=` · `==`↔`!=` · `in`↔`not in`. 판정 로직이 있는
도구라면 어느 시험이든 빨개져야 한다. **안 빨개지면 그 도구는 이름만 걸려 있다.**

### 관문에는 안 붙인다

26개를 하나씩 망가뜨리고 매번 전체 시험을 도는 데 25분이 걸린다. `make check`에 넣으면
사람이 검사를 끄게 된다 (D-0126 · D-0129에서 되풀이해 확인한 것이다). **손으로 부른다.**

    make mutate
"""

from __future__ import annotations

import ast
import re
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


def main() -> int:
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
