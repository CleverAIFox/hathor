"""관문을 만들어 놓고 **아무 데서도 안 부르는 것** (D-0121 · D-0355).

`split_decisions.py --check`는 D-0080부터 있었고 조각 표가 낡은 것을 정확히 잡았는데,
`make check`가 부르지 않아 **일곱 세션을 그냥 지났다.** 달아 놓는 것과 도는 것은 다르다.

D-0355가 「돈다」에 **CI를 넣었다** — `check_under_load`는 관문 전부를 한 번 더 도는 것이라
`make check`에 넣으면 두 배가 되고, 그러면 사람이 검사를 끈다 (D-0129). CI가 제 잡으로
돌리고 `# ci-only:` 선언이 그 차이를 적는다. **그물은 안 줄었다** — 아무 데도 안 걸린
도구는 여전히 빨개진다.

**`test_check_decisions.py`에서 떼어 왔다** — 그쪽이 706줄로 상한 700을 넘었다 (D-0355).
"""

from __future__ import annotations

import re
from pathlib import Path

from hathor.shared.config.paths import repo_root


def _recipes(makefile: str) -> dict[str, tuple[list[str], list[str]]]:
    """Makefile을 `타깃 -> (선행, 레시피)`로 읽는다. **탭이 레시피다.**"""
    targets: dict[str, tuple[list[str], list[str]]] = {}
    current: str | None = None
    for line in makefile.split("\n"):
        if line.startswith("\t"):
            if current is not None:
                targets[current][1].append(line.strip())
            continue
        head, sep, rest = line.partition(":")
        if not sep or head.startswith((".", "#", " ")) or "=" in head:
            current = None
            continue
        current = head.strip()
        prerequisites = rest.split("##")[0].split()
        targets[current] = (prerequisites, [])
    return targets


def test_check가_있는_도구는_전부_check_사슬에서_불린다():
    """**도구에 `--check`를 다는 것과 그것이 도는 것은 다르다** (D-0121).

    `split_decisions.py --check`는 D-0080부터 있었고 조각 표가 낡은 것을 정확히
    잡았는데, `make check`가 부르지 않아 일곱 세션을 그냥 지났다.
    """
    root = repo_root()
    targets = _recipes((root / "Makefile").read_text(encoding="utf-8"))
    assert "check" in targets, "Makefile에 check 타깃이 없다"

    reachable = [line for name in targets["check"][0] for line in targets.get(name, ([], []))[1]]
    chain = "\n".join(reachable)

    # **CI가 도는 것도 「돈다」다** (D-0355). D-0121이 막으려던 것은 *달아 놓고 아무 데서도
    # 안 도는 것*이다. `check_under_load`는 관문 전부를 한 번 더 도는 것이라 `make check`에
    # 넣으면 두 배가 되고, 그러면 사람이 검사를 끈다 (D-0129). CI가 제 잡으로 돌리고
    # **`# ci-only:` 선언이 그 차이를 적는다** — 그 선언이 진짜인지는 D-0219가 본다.
    flows = "\n".join(
        one.read_text(encoding="utf-8")
        for one in sorted((root / ".github" / "workflows").glob("*.yml"))
    )

    for path in sorted((root / "tools").glob("*.py")):
        # **`add_argument` 꼴로 본다** (D-0350). 느슨하게 `"--check"`만 찾으면
        # 그 문자열을 쓰는 **도서관 모듈**(`doc_counts`)이 관문으로 잡힌다.
        if not re.search(r'add_argument\(\s*"--check"', path.read_text(encoding="utf-8")):
            continue
        where = f"tools/{path.name}"
        declared = f"# ci-only: {path.name}" in flows
        assert where in chain or (where in flows and declared), (
            f"{path.name}에 --check가 있는데 아무 데서도 안 돈다. "
            "Makefile의 docs 타깃에 한 줄 더하거나, CI에 걸고 `# ci-only: <이름> <사유>`를 적는다"
        )


CHAINS = ("check", "ship", "hygiene")
"""**사슬**: 표준 흐름이 돌리는 타깃 (D-0362).

`make mutate`·`make load`는 **사슬이 아니다** — 사람이 기억해야 돌고, 그것이 이
시험이 막는 바로 그것이다. `make ship`은 사슬이다: 그가 미는 길이 그것 하나고,
`debts`의 못이 거기서만 재어진다.
"""


def _chain_and_flows() -> tuple[str, str, str]:
    """사슬 셋의 레시피 · 워크플로 전부 · 저장소 훅의 본문."""
    root = repo_root()
    targets = _recipes((root / "Makefile").read_text(encoding="utf-8"))
    wanted = [
        name
        for head in CHAINS
        for name in [head, *targets.get(head, ([], []))[0]]
        if name in targets
    ]
    chain = "\n".join(line for name in wanted for line in targets[name][1])
    flows = "\n".join(
        one.read_text(encoding="utf-8")
        for one in sorted((root / ".github" / "workflows").glob("*.yml"))
    )
    # **워크플로가 `make <타깃>`으로 부르면 그 레시피까지 읽는다.** 안 그러면 `make`를
    # 거쳐 부르는 도구가 「CI에 없다」로 거짓 실패한다 — `wiring.yml`이 그 꼴이다.
    flows += "\n" + "\n".join(
        line
        for name in re.findall(r"make ([a-z][a-z0-9-]*)", flows)
        for line in targets.get(name, ([], []))[1]
    )
    hook = (root / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    return chain, flows, hook


def _imported_from_chain(root: Path, chain: str) -> set[str]:
    """사슬이 부르는 도구에서 **임포트로 닿는** 모듈 전부 (D-0362).

    **임포트도 「돈다」다.** `decision_evidence`는 `check_decisions`가 들여오고,
    `debts`는 `doc_style_repo`를 거쳐 두 단 건너 닿는다 — **한 단만 보면 「사슬 밖」이
    거짓으로 뜬다**(실제로 그렇게 떴다). 닿는 데까지 민다.
    """
    imports: dict[str, set[str]] = {}
    for one in sorted((root / "tools").glob("*.py")):
        found = set(
            re.findall(r"(?m)^(?:from|import) ([a-z_0-9]+)", one.read_text(encoding="utf-8"))
        )
        imports[one.stem] = found
    reached = {
        one.stem for one in sorted((root / "tools").glob("*.py")) if f"tools/{one.name}" in chain
    }
    while True:
        grown = reached | {dep for name in reached for dep in imports.get(name, set())}
        if grown == reached:
            return reached - {name for name in reached if f"tools/{name}.py" in chain}
        reached = grown


def test_못을_든_도구는_전부_어느_사슬에_있다():
    """**`--check`가 없어도 관문이다** (D-0362 · D-0121의 시야를 넓힌다).

    위의 시험은 **`add_argument("--check")`를 선언한 도구만** 본다. `mutate_gate`는
    `argparse`가 아예 없어서(환경변수 `WIRING=`로 돈다) **그 그물에 안 걸렸다** —
    배선 103곳을 정확히 세우는 도구가 `make check`에도, CI에도, 훅에도 없었고
    **사람이 기억해야 돌았다.** 세샤트/토트 세션이 코드를 읽어 짚었다.

    더 날카로운 자를 쓴다: **`check_ratchets.BASELINE`이 못을 든 모듈.** 못을 박아
    두고 그 수를 **아무도 재지 않으면 그 못은 장식이다** (D-0126). 못은 두 가지로
    지켜진다 — 상수가 느슨해지는 것은 `check_ratchets`가 보고(그것은 사슬 안에 있다),
    **실측이 천장을 넘는 것은 그 도구가 돌아야** 보인다. 이 시험은 뒤쪽을 본다.

    사슬 셋을 다 받는다 — `make check` · CI(선언과 함께) · 훅. **시험 파일로 사는
    못**(`test_gate_tools` · `test_gate_types`)은 pytest가 돌리므로 사슬 안이다.
    """
    root = repo_root()
    chain, flows, hook = _chain_and_flows()
    ratchets = (root / "tools" / "check_ratchets.py").read_text(encoding="utf-8")

    owners = sorted({key.split(".")[0] for key in re.findall(r'"([a-z_0-9]+)\.[A-Z]', ratchets)})
    assert len(owners) >= 15, f"못을 든 모듈을 {len(owners)}개 읽었다 — 그물이 비었다 (D-0230)"
    reached = _imported_from_chain(root, chain)

    for name in owners:
        if not (root / "tools" / f"{name}.py").exists():
            continue  # `core/tests/`에 사는 못 — pytest가 돌린다
        where = f"tools/{name}.py"
        declared = f"# ci-only: {name}.py" in flows
        assert (
            where in chain or (where in flows and declared) or where in hook or name in reached
        ), (
            f"{name}이 못을 들고 있는데 아무 사슬에도 없다. 그 못은 장식이다 (D-0126) — "
            "`make check`에 걸거나, CI에 걸고 `# ci-only: <이름> <사유>`를 적는다"
        )
