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
