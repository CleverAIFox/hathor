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
| 버려진 문서 문자열 | 파이썬이 그냥 버리는 문자열 — **적어 둔 근거가 아무 데도 안 붙어 있다** |

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
    "건너뛴 시험": 15,  # D-0353. 내가 더한 둘을 없앴다 — 남은 15는 모델·바이너리 의존이다
    "삼킨 예외": 0,
    "빈 그물": 0,
    "버려진 문서 문자열": 0,
    "눈먼 접두사": 0,
}
"""프로브별 천장. **정본은 여기 하나다** (D-0223).

`건너뛴 시험`은 **2에서 15로 올렸다** (D-0289). 새로 생긴 것이 아니라 **열셋이 안 보였다** —
프로브가 데코레이터의 점 이름에서 `.skip`만 찾아서 `@requires_gpu` 같은 **이름 뒤에 숨은
건너뜀**을 한 건도 못 셌다.

그 열다섯이 **내 기기에서 안 도는 시험**이고, 그중 둘(`test_mert_feature_extractor.py:91`
· `:104`)이 사용자 기기에서 터졌다. **내 `make check` 초록은 그 둘에 대해 아무 말도 안 한다** —
그 사실을 아무도 세지 않아 나는 초록이라고 보고했다.

`버려진 문서 문자열`은 **0이 못이다** (D-0274). D-0273에서 눈으로 하나 찾았고, 눈으로
찾았다는 것은 **다음번엔 못 찾는다**는 뜻이다."""


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
    """못 읽으면 `None`. **그 파일은 `unreadable`이 따로 센다** (D-0275).

    프로브마다 여기서 죽으면 한 파일이 다섯 번 운다. 판정은 `main`이 한 번 한다."""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


FLOOR_CLAUSE = re.compile(r">=\s*(\d+)\.(\d+)")


def python_floor(root: Path = ROOT) -> tuple[int, int]:
    """저장소가 요구하는 파이썬 **하한**. 정본은 `core/pyproject.toml`이다 (D-0199).

    `tomllib`은 표준 라이브러리이므로 맨 `python3`으로 도는 규약을 깨지 않는다 (D-0256).

    **상한이 붙을 수 있다** (D-0341). 앞을 `lstrip`하고 점으로 자르던 파서가
    `">=3.12,<3.13"`에서 `'12,<3'`을 `int`에 넘기고 터졌다 — **한 가지 꼴만
    가정한 파서다.** `>=` 절만 집어낸다.
    """
    import tomllib

    raw = tomllib.loads((root / "core" / "pyproject.toml").read_text(encoding="utf-8"))
    spec = str(raw["project"]["requires-python"])
    hit = FLOOR_CLAUSE.search(spec)
    if hit is None:
        raise ValueError(f"`requires-python`에 하한이 없다: {spec!r}")
    return int(hit.group(1)), int(hit.group(2))


def too_old() -> str:
    """이 파이썬이 저장소보다 낮으면 그 사유. **낮으면 이 도구는 아무것도 못 판정한다.**

    `ast`가 `type X = …`(PEP 695)를 3.12부터 안다. 3.11에서는 그 문장이 든 파일이
    `SyntaxError`가 되고, `parsed`가 그것을 삼켜 **다섯 프로브에서 조용히 빠졌다** (D-0275).
    """
    floor = python_floor()
    if sys.version_info[:2] >= floor:
        return ""
    here = ".".join(str(part) for part in sys.version_info[:3])
    want = ".".join(str(part) for part in floor)
    return f"이 파이썬은 {here}이고 저장소는 {want} 이상을 쓴다 — 저장소를 못 읽는다"


def unreadable(root: Path = ROOT) -> list[str]:
    """**이 파이썬이 못 읽는 파일** (D-0275). 비어야 아래 다섯 수가 뜻을 갖는다.

    `parsed`가 `SyntaxError`를 삼키고 `None`을 내므로 **못 읽은 파일은 다섯 프로브 전부에서
    조용히 빠졌다.** 작성자의 컨테이너가 파이썬 3.11이고 저장소는 `type X = …`(3.12)를 쓴다 —
    9파일이 안 보였고 그래서 결함 8건을 **초록으로** 내보냈다. 사용자 기기(3.12)에서 터졌다.

    이 저장소가 반복해 당한 «검사가 있는데 안 운다»가 **그 검사 자신에게** 난 자리다.
    """
    found: list[str] = []
    for tree_name in (TEST_TREE, *CODE_TREES):
        for path in python_files(root, tree_name):
            try:
                ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as exc:
                found.append(f"{path.relative_to(root).as_posix()}:{exc.lineno}")
    return found


def _named(node: ast.AST | None) -> str:
    """호출 · 속성의 점 이름. `pytest.raises` 같은 것을 문자열로 본다.

    **`None`을 받는다** (D-0263). `except:`(맨몸)의 `node.type`은 `None`이고 이 함수는
    이미 그것을 빈 문자열로 처리하고 있었다 — 서명만 `AST`라고 거짓말했다."""
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


def _skip_aliases(tree: ast.Module) -> set[str]:
    """`requires_gpu = pytest.mark.skipif(...)` 꼴로 **이름 뒤에 숨은 건너뜀** (D-0289).

    이 프로브가 데코레이터의 점 이름에서 `.skip`만 찾았다. 그래서 `@requires_gpu`는
    **한 글자도 안 걸렸다** — 실측 선언 2건 대 실물 9건이었고, **안 보이는 일곱이 전부
    장비가 있어야 도는 시험**이었다. 그 중 둘이 사용자 기기에서 터졌고 내 기기에서는
    영원히 건너뛰므로 **내 초록은 그 둘에 대해 아무 말도 안 한다.**
    """
    aliases: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if ".skip" in _named(node.value.func):
            aliases |= {target.id for target in node.targets if isinstance(target, ast.Name)}
    return aliases


def probe_skipped(root: Path = ROOT) -> list[Hit]:
    """`skip` · `skipif`. **세는 것이 목적이다** — 장비가 필요한 시험은 건너뛰는 것이 맞다.

    **이름 뒤에 숨은 것까지 센다** (D-0289). 세는 것이 목적이라면 **안 보이는 것이 가장 나쁘다.**
    """
    found: list[Hit] = []
    for path in python_files(root, TEST_TREE):
        tree = parsed(path)
        if tree is None:
            continue
        aliases = _skip_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                marks = [_named(one) for one in node.decorator_list]
                if any(".skip" in mark or mark in aliases for mark in marks):
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


BLIND = ("startswith", "endswith")
"""빈 문자열에 **늘 맞는** 메서드. `in`은 안 본다 — `"" in text`도 늘 참이지만
그 꼴은 실물에 없고, 넣으면 `"" in collection`(정상)과 가릴 자가 필요하다."""


def blind_prefixes(tree: ast.Module) -> list[tuple[int, str]]:
    """`startswith`·`endswith`에 **빈 문자열**을 넘기는 자리 (D-0349).

    ### 이것이 D-0349의 세 사고 전부다

    `name.startswith("")`는 **늘 참**이다. 그래서 그물이 통째로 비거나, `not`을 씌운
    가지가 **한 번도 안 돈다.** 실물에서 세 자리가 났고 셋 다 지워진 이름이
    `docs/DECISIONS.md`였다.

    | 자리 | 꼴 | 무엇이 됐나 |
    |---|---|---|
    | `check_issue_mentions.SKIP_TREES` | `("",)` | 문서 축을 한 줄도 안 봤다 |
    | `check_doc_style` 강조 가지 | `not …startswith("")` | **한 번도 안 돌았다** (27곳 놓침) |
    | `check_doc_style` 기록 가지 | `…startswith("")` | 문서 넷 전부에 돌았다 |

    **D-0349가 「덫은 한 곳뿐」이라 적었고 틀렸다** — 튜플 꼴(`(("",))`)만 훑고 맨
    문자열 꼴을 안 봤다. 자는 사람이 아니라 기계가 세야 한다는 것이 D-0117이다.

    상수 하나만 비는 것은 `check_sight`가 수로 잡는다. **여기는 꼴로 잡는다** —
    `("",)`는 세면 1개라 어느 수 눈금에도 안 걸린다.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = node.func
        if not isinstance(method, ast.Attribute) or method.attr not in BLIND:
            continue
        for argument in node.args:
            pieces: list[ast.expr] = [argument]
            if isinstance(argument, ast.Tuple | ast.List | ast.Set):
                pieces = list(argument.elts)
            if any(
                isinstance(one, ast.Constant) and one.value == "" and isinstance(one.value, str)
                for one in pieces
            ):
                found.append((node.lineno, f"{method.attr}에 빈 문자열"))
    return found


def probe_blind_prefix(root: Path = ROOT) -> list[Hit]:
    """`startswith("")`처럼 **늘 참인 조건**. 그물이 통째로 비거나 가지가 안 돈다."""
    found: list[Hit] = []
    for tree_name in CODE_TREES:
        for path in python_files(root, tree_name):
            tree = parsed(path)
            if tree is None:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for line, what in blind_prefixes(tree):
                if exempt(lines, line - 1, line):
                    continue
                where = f"{path.relative_to(root).as_posix()}:{line}"
                found.append(Hit("눈먼 접두사", where, what))
    return found


def _is_text(node: ast.stmt) -> bool:
    """이 문장이 «문자열 하나만 덜렁 있는 줄»인가."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def dropped_docs(tree: ast.Module) -> list[tuple[int, str]]:
    """파이썬이 버리는 문자열 표현식. **어디까지가 문서 문자열인가**가 판정이다.

    살아 있는 셋만 남긴다.

    | 자리 | 파이썬이 | 여기서 |
    |---|---|---|
    | 몸통의 첫 문장 | `__doc__`에 넣는다 | 정상 |
    | 대입 바로 뒤 하나 | 버린다 | **정상** — 이 저장소가 근거를 적는 꼴이고 도구들이 읽는다 |
    | `type X = …` 뒤 하나 | 버린다 | **정상** — 같은 꼴. 첫 판에 빼서 8건을 거짓으로 잡았다 |
    | 그 밖의 전부 | 버린다 | **버려진 것** |

    셋째가 실제로 났다 — 대입 하나 뒤에 문자열이 **둘**이었고 둘째는 아무 데도 안 붙었다
    (D-0273). 둘 다 다른 상수를 설명하려던 것이라 **설명하려던 자리에는 설명이 없었다.**
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        for index, statement in enumerate(body):
            if index == 0 or not _is_text(statement):
                continue
            if isinstance(body[index - 1], ast.Assign | ast.AnnAssign | ast.TypeAlias):
                continue
            head = str(getattr(statement.value, "value", ""))[:40].replace("\n", " ")
            found.append((statement.lineno, head))
    return found


def probe_dropped_doc(root: Path = ROOT) -> list[Hit]:
    """적어 둔 근거가 아무 데도 안 붙어 있는 자리. **`ruff`도 `mypy`도 이 부류를 안 본다.**"""
    found: list[Hit] = []
    for tree_name in (TEST_TREE, *CODE_TREES):
        for path in python_files(root, tree_name):
            tree = parsed(path)
            if tree is None:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for line, head in dropped_docs(tree):
                if exempt(lines, line - 1, line):
                    continue
                where = f"{path.relative_to(root).as_posix()}:{line}"
                found.append(Hit("버려진 문서 문자열", where, head))
    return found


PROBES: dict[str, Callable[[Path], list[Hit]]] = {
    "무검증 시험": probe_unchecked,
    "건너뛴 시험": probe_skipped,
    "삼킨 예외": probe_swallowed,
    "빈 그물": probe_empty_net,
    "버려진 문서 문자열": probe_dropped_doc,
    "눈먼 접두사": probe_blind_prefix,
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
        "    assert True\n\n\n"
        # **이름 뒤에 숨은 건너뜀도 심는다** (D-0289). 이 꼴을 프로브가 한 건도 못 봤고,
        # 양성 대조는 인라인만 심고 있어서 **죽은 가지를 초록으로 덮고 있었다.**
        "필요하다 = pytest.mark.skipif(True, reason='이름 뒤에 숨었다')\n\n\n"
        "@필요하다\n"
        "def test_이름_뒤에_숨어_건너뛴다():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    code = folder / "tools"
    code.mkdir(parents=True)
    (code / "planted.py").write_text(
        "FILES = ('tools/xxx-없는파일.py',)\n"
        '"""붙는 문서 문자열 — 이것은 정상이다."""\n'
        '"""심은 것 — 대입 뒤 둘째 문자열은 파이썬이 버린다."""\n\n\n'
        "def run() -> None:\n"
        "    try:\n"
        "        open('x')\n"
        "    except OSError:\n"
        "        pass\n\n\n"
        # **늘 참인 조건을 심는다** (D-0349). 이 꼴이 실물에서 세 번 났고 그중 둘은
        # **가지가 한 번도 안 도는** 꼴이었다 — 어떤 수 눈금에도 안 걸린다.
        "def blind(name: str) -> bool:\n"
        '    return name.startswith("")\n',
        encoding="utf-8",
    )


def planted_unreadable() -> list[str]:
    """**양성 대조** (D-0275). 어느 파이썬도 못 읽는 파일을 심어 `unreadable`이 우는지 본다."""
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw)
        (folder / "tools").mkdir(parents=True)
        (folder / "tools" / "broken.py").write_text("def (:\n", encoding="utf-8")
        return unreadable(folder)


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

    # **버전이 낮으면 아무 수도 내지 않는다** (D-0275). 낮은 파이썬에서 «0건»은 거짓이다.
    reason = too_old()
    if reason:
        print(f"deadcheck를 돌릴 수 없다: {reason}", file=sys.stderr)
        return 1

    if args.selftest:
        dead = positive_control()
        if dead:
            print(f"심은 결함에 안 우는 프로브: {' · '.join(dead)}", file=sys.stderr)
            return 1
        if not planted_unreadable():
            print("못 읽는 파일을 심었는데 `unreadable`이 조용하다", file=sys.stderr)
            return 1
        print(f"양성 대조 통과 · 프로브 {len(PROBES)}개 · 못 읽는 파일 감지")
        return 0

    blind = unreadable()
    if blind:
        print(
            f"이 도구가 못 읽은 파일 {len(blind)}개. **아래 수는 전부 덜 센 것이다**",
            file=sys.stderr,
        )
        for line in blind:
            print(f"  - {line}", file=sys.stderr)
        return 1

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
