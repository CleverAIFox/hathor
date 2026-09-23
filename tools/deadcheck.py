#!/usr/bin/env python3
"""검사가 죽었는가 (D-0230).

### 왜 필요한가

이 저장소가 반복해서 당한 형태는 **«검사가 있는데 안 운다»**다. 실측 —

- 검사 코드 타입 래칫이 `make check`에만 있고 **CI에서 빠져 있었다** (D-0219).
- 커버리지 바닥이 두 곳에 있어 한쪽만 고쳐졌다 (D-0223).
- 망 접점 검사가 `mlflow` · `prefect`를 **이름으로 몰랐다** (D-0224).

**검사를 늘리는 것으로는 못 잡는다.** 늘린 검사도 같은 병에 걸린다. 그래서 검사를 **대상으로
삼는** 도구가 하나 필요하다 — fire-lane `deadcheck.py`의 규율을 가져왔다.

| 프로브 | 무엇을 세나 |
|---|---|
| 무검증 시험 | `assert`도 `raises`도 없는 `test_…` — 영원히 통과한다 |
| 건너뛴 시험 | `skip` · `skipif` — 도는 줄 알았는데 안 돈다 |
| 삼킨 예외 | `except …: pass` — 실패가 소리 없이 사라진다 |
| 빈 그물 | 코드에 박힌 경로 · 글롭이 **아무것도 안 가리킨다** — 훑을 것이 0개다 |

### 생사는 합성 트리에서 묻는다

**실제 저장소에서 0건인 것은 «깨끗하다»이지 «프로브가 죽었다»가 아니다.** 프로브가 살아 있는지는
`CONTROLS`가 결함을 일부러 심은 임시 트리에서 묻는다(`--selftest`). fire-lane은 이 둘을 섞어
`--selftest`를 관문으로 쓰다가 **결함이 많을수록 확실히 통과하는** 관문을 1년 가까이 돌렸다.

관문은 `--ratchet`이다 — 프로브별 건수가 `CEILING`과 **같아야** 한다. 늘면 새로 죽은 것이고,
줄면 고친 것이니 천장을 조인다. 파일 길이 래칫(D-0117)과 같은 규율이다.

    python3 tools/deadcheck.py             # 전건을 찍는다
    python3 tools/deadcheck.py --selftest  # 프로브가 심은 결함에 우는가 (양성 대조)
    python3 tools/deadcheck.py --ratchet   # 관문. `make check`이 이것을 돈다
    python3 tools/deadcheck.py --update    # 천장을 실측으로 맞춘다 (줄었을 때)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_TREE = "core/tests"
CODE_TREES = ("core/hathor", "tools")
NET_TREES = ("core/", "tools/", "docs/", "site/", ".github/", "infra/", "docker/")
"""«빈 그물»이 판정할 경로의 머리. **`var/`는 안 본다** — 산출물은 기기마다 있거나 없다."""

NET = re.compile(r"^[\w.*/-]+$")
OK = "deadcheck: ok"
"""면제 선언. **사유와 함께 적는다** — 선언 없는 면제는 없다 (D-0219와 같은 규율).

`무검증 시험`은 함수 안 아무 줄에, 나머지는 그 줄이나 바로 윗줄에 적는다."""
CEILING = {
    "무검증 시험": 0,
    "건너뛴 시험": 2,
    "삼킨 예외": 0,
    "빈 그물": 0,
}
"""프로브별 천장. **정본은 여기 하나다** (D-0223).

`건너뛴 시험` 둘은 실제 음원과 경로 아닌 인자를 건너뛴다 — 장비가 있어야 도는 것이 맞다."""


@dataclass(frozen=True)
class Hit:
    probe: str
    where: str
    what: str


def python_files(root: Path, tree: str) -> list[Path]:
    base = root / tree
    return (
        sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
        if base.is_dir()
        else []
    )


def exempt(lines: list[str], first: int, last: int) -> bool:
    """`first`~`last` 줄 안에 면제 선언이 있는가. 줄 번호는 1부터다."""
    return any(OK in line for line in lines[max(first - 1, 0) : last])


def parsed(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def _named(node: ast.AST) -> str:
    """호출 · 속성의 점 이름. `pytest.raises` 같은 것을 문자열로 본다."""
    return ast.unparse(node) if isinstance(node, ast.expr) else ""


def probe_unchecked(root: Path = ROOT) -> list[Hit]:
    """`assert`도 `raises`도 없는 시험. **통과가 아니라 아무것도 안 본 것이다.**"""
    found: list[Hit] = []
    for path in python_files(root, TEST_TREE):
        tree = parsed(path)
        if tree is None:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            body = list(ast.walk(node))
            if any(isinstance(inner, ast.Assert) for inner in body):
                continue
            # `pytest.raises` · `pytest.fail`도 판정이다. 안 세면 멀쩡한 시험이 걸린다.
            calls = [_named(inner.func) for inner in body if isinstance(inner, ast.Call)]
            if any(name.endswith(("raises", "fail")) for name in calls):
                continue
            if exempt(lines, node.lineno, node.end_lineno or node.lineno):
                continue
            found.append(Hit("무검증 시험", f"{path.name}:{node.lineno}", node.name))
    return found


def probe_skipped(root: Path = ROOT) -> list[Hit]:
    """`skip` · `skipif`. **세는 것이 목적이다** — 장비가 필요한 시험은 건너뛰는 것이 맞다."""
    found: list[Hit] = []
    for path in python_files(root, TEST_TREE):
        tree = parsed(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                marks = [_named(one) for one in node.decorator_list]
                if any(".skip" in mark for mark in marks):
                    found.append(Hit("건너뛴 시험", f"{path.name}:{node.lineno}", node.name))
            elif isinstance(node, ast.Call) and _named(node.func).endswith("pytest.skip"):
                found.append(Hit("건너뛴 시험", f"{path.name}:{node.lineno}", "pytest.skip()"))
    return found


def probe_swallowed(root: Path = ROOT) -> list[Hit]:
    """`except …: pass`. **`contextlib.suppress`는 안 센다** — 그것은 적어 둔 것이다."""
    found: list[Hit] = []
    for tree_name in CODE_TREES:
        for path in python_files(root, tree_name):
            tree = parsed(path)
            if tree is None:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                if not all(isinstance(one, ast.Pass) for one in node.body):
                    continue
                # 한 줄짜리는 바로 윗줄의 선언도 받는다.
                if exempt(lines, node.lineno - 1, node.lineno):
                    continue
                where = f"{path.relative_to(root).as_posix()}:{node.lineno}"
                found.append(Hit("삼킨 예외", where, _named(node.type) or "bare except"))
    return found


def net_strings(tree: ast.Module) -> list[tuple[int, str]]:
    """코드에 박힌 경로 · 글롭 문자열. 주소(`http…`)와 문장은 아니다."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if NET.match(text) and text.startswith(NET_TREES):
            found.append((node.lineno, text))
    return found


def probe_empty_net(root: Path = ROOT) -> list[Hit]:
    """훑을 것이 0개인 경로 · 글롭. **파일을 옮기면 검사가 조용히 빈다.**"""
    found: list[Hit] = []
    for tree_name in CODE_TREES:
        for path in python_files(root, tree_name):
            tree = parsed(path)
            if tree is None:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for line, text in net_strings(tree):
                hits = list(root.glob(text)) if "*" in text else [root / text]
                if not any(one.exists() for one in hits) and not exempt(lines, line - 1, line):
                    where = f"{path.relative_to(root).as_posix()}:{line}"
                    found.append(Hit("빈 그물", where, text))
    return found


PROBES: dict[str, Callable[[Path], list[Hit]]] = {
    "무검증 시험": probe_unchecked,
    "건너뛴 시험": probe_skipped,
    "삼킨 예외": probe_swallowed,
    "빈 그물": probe_empty_net,
}


def _plant(folder: Path) -> None:
    """프로브마다 결함 하나씩을 심은 합성 트리. **여기서 안 울면 프로브가 죽은 것이다.**"""
    tests = folder / TEST_TREE
    tests.mkdir(parents=True)
    (tests / "test_planted.py").write_text(
        "import pytest\n\n\n"
        "def test_아무것도_안_본다():\n"
        "    value = 1 + 1\n"
        "    print(value)\n\n\n"
        "@pytest.mark.skipif(True, reason='심은 것')\n"
        "def test_건너뛴다():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    code = folder / "tools"
    code.mkdir(parents=True)
    (code / "planted.py").write_text(
        "FILES = ('tools/xxx-없는파일.py',)\n\n\n"
        "def run() -> None:\n"
        "    try:\n"
        "        open('x')\n"
        "    except OSError:\n"
        "        pass\n",
        encoding="utf-8",
    )


def positive_control() -> list[str]:
    """심은 결함에 안 우는 프로브의 이름. 비어야 살아 있다."""
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw)
        _plant(folder)
        return [name for name, probe in PROBES.items() if not probe(folder)]


def survey(root: Path = ROOT) -> list[Hit]:
    return [hit for probe in PROBES.values() for hit in probe(root)]


def counted(hits: list[Hit]) -> dict[str, int]:
    return {name: sum(1 for hit in hits if hit.probe == name) for name in PROBES}


def verdict(seen: dict[str, int], ceiling: dict[str, int]) -> list[str]:
    """천장과 어긋난 것. **늘어도 줄어도 말한다** (D-0117)."""
    problems: list[str] = []
    for name, top in ceiling.items():
        got = seen.get(name, 0)
        if got > top:
            problems.append(f"{name} {got}건 > 천장 {top} — 새로 죽은 검사가 있다")
        elif got < top:
            problems.append(f"{name} {got}건 < 천장 {top} — 고쳤으면 `--update`로 조인다")
    return problems


def update(seen: dict[str, int], path: Path) -> None:
    """천장을 실측으로 맞춘다. 숫자는 이 파일 하나에만 산다."""
    text = path.read_text(encoding="utf-8")
    for name, got in seen.items():
        text = re.sub(rf'"{name}": \d+,', f'"{name}": {got},', text)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="검사가 죽었는가 (D-0230)")
    parser.add_argument("--selftest", action="store_true", help="양성 대조. 관문이 아니다")
    parser.add_argument("--ratchet", action="store_true", help="관문. 천장과 대조한다")
    parser.add_argument("--update", action="store_true", help="천장을 실측으로 맞춘다")
    args = parser.parse_args()

    if args.selftest:
        dead = positive_control()
        if dead:
            print(f"심은 결함에 안 우는 프로브: {' · '.join(dead)}", file=sys.stderr)
            return 1
        print(f"양성 대조 통과 · 프로브 {len(PROBES)}개")
        return 0

    hits = survey()
    seen = counted(hits)
    if args.update:
        update(seen, Path(__file__))
        print(f"천장을 맞췄다 · {seen}")
        return 0
    if not args.ratchet:
        for hit in hits:
            print(f"  {hit.probe:<10} {hit.where}  {hit.what}")
        print(" · ".join(f"{name} {got}" for name, got in seen.items()))
        return 0

    problems = verdict(seen, CEILING)
    if problems:
        print(f"죽은 검사 래칫이 {len(problems)}곳 어긋난다.", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        print("무엇인지 보려면 `python3 tools/deadcheck.py`", file=sys.stderr)
        return 1
    print(" · ".join(f"{name} {got}" for name, got in seen.items()) + " · 천장과 같다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
