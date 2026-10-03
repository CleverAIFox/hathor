#!/usr/bin/env python3
"""**래칫을 느슨하게 박은 자리를 세는 자가 없었다** (D-0352 · D-0350에서 넘어온 빚).

### 느슨해진 래칫은 초록으로 위장한다

`check_sight`가 *"`--update --loosen`에는 결정 기록이 필요하다"*고 화면에 적는다.
**규약이고, 아무도 안 셌다.** 못을 내려 박고 기록을 안 쓰면 그 판은 영원히 초록이다 —
`fire-lane`은 커버리지 래칫이 14인데 실물이 그 아래인 것을 **나흘 몰랐다.**

### 세는 법 — **가장 조였던 값**을 들고 있는다

첫 판은 **부모 커밋**과 비교했다. 그러면 한 판에 1씩 내려가도 **둘째 판부터 영원히
초록이다** — 1 → 1은 느슨해진 것이 아니고, **원래가 0이었다는 사실을 아무도 안 들고
있다.** D-0352가 *"커밋 하나만 본다"*고 적어 둔 그 구멍이고, 실측으로 재서 확인했다.

그래서 `BASELINE`에 **지금까지 가장 조였던 값**을 박아 둔다. 거기서 느슨해지면 몇 판이
걸렸든 빨개진다. `--update`는 **조이는 쪽으로만** 쓴다 — 내려 박으려면 `--update
--loosen`이고, 그때 **`docs/DECISIONS.md`가 같은 변경에 들어 있어야 한다.** 규약을
화면에만 적으면 아무도 안 쓴다 (D-0126) — `check_sight`가 그렇게 적고 아무도 안 썼다.

**git 이력을 안 쓴다.** 얕은 클론에서도 돌고, 부모가 없어도 *"안 돌렸다"*가 아니다.

### 어떤 상수가 못인가 — 이름으로 가린다

정수 상수 74개를 세어 보니 대부분 **시험 치수**(`DIM` · `DEGREES` · `SR`)였다. 눈으로
골랐으면 다음 판에 또 골라야 하고 빠뜨린다. 그래서 **이름 어휘**로 가린다 — `FLOOR` ·
`CEILING` · `UNTESTED` · `UNTYPED` · `UNKNOWN` · `…_FROM`. 어휘에 걸린 이름은 **반드시
`NAILS`에 방향이 선언돼 있어야 한다** (`check_sight`가 상수에 하는 것과 같다).

`check_sight.PINNED`는 여기서 안 본다 — **정본은 하나다** (D-0117). 그쪽은 저 자신이
방향을 알고 `--loosen`을 막는다.

    python3 tools/check_ratchets.py                     # 가장 조였던 값과 대조한다
    python3 tools/check_ratchets.py --list              # 못과 방향을 찍는다
    python3 tools/check_ratchets.py --update            # 조이는 쪽으로 다시 박는다
    python3 tools/check_ratchets.py --update --loosen   # 내려 박는다. **기록이 필요하다**
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAST = "docs/DECISIONS.md"

VOCABULARY = ("FLOOR", "CEILING", "UNTESTED", "UNTYPED", "UNKNOWN")
"""못임을 알리는 이름 조각. 끝이 `_FROM`인 것도 못이다 (강제 시작점)."""

OWNED_ELSEWHERE = ("check_sight.PINNED",)
"""저 자신이 방향을 알고 `--loosen`을 막는 것. **정본은 하나다** (D-0117)."""

NAILS = {
    "허용": "천장",
    "천장": "천장",
    "바닥": "바닥",
    "강제 시작": "천장",
}
"""부류 → 느슨해지는 방향. **「천장」은 오르면 느슨하고, 「바닥」은 내리면 느슨하다.**

`강제 시작`(`…_FROM`)이 천장인 것이 헷갈린다 — **늦게 강제하면 덜 강제한다.**
`FORMAT_ENFORCED_FROM = 80`을 81로 올리면 기록 하나가 형식 검사 밖으로 빠진다.
"""

KINDS = {
    "FLOOR": "바닥",
    "CEILING": "천장",
    "UNTESTED": "천장",
    "UNTYPED": "천장",
    "UNKNOWN": "천장",
}
"""이름 조각 → 부류. `_FROM`은 아래에서 따로 붙인다."""

SOURCES = ("tools/*.py", "core/tests/unit/test_*.py")


def kind(name: str) -> str | None:
    """그 상수가 어느 부류의 못인가. 못이 아니면 `None`."""
    for piece, which in KINDS.items():
        if piece in name:
            return which
    return "강제 시작" if name.endswith("_FROM") else None


def nails(text: str) -> dict[str, int]:
    """한 파일의 못. 정수는 그 값, 정수 묶음은 **키마다 한 못**이다.

    **`ast`로 읽는다** — 임포트하면 그 파일의 부작용이 돈다 (`check_sight`와 같은 규율).
    """
    found: dict[str, int] = {}
    for node in ast.parse(text).body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for one in targets:
            if not isinstance(one, ast.Name) or not one.id.isupper() or not kind(one.id):
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, int):
                found[one.id] = value.value
            elif isinstance(value, ast.Dict):
                for key, item in zip(value.keys, value.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and isinstance(item, ast.Constant)
                        and isinstance(item.value, int)
                    ):
                        found[f"{one.id}[{key.value}]"] = item.value
    return found


def here_text(path: str) -> str:
    """지금 작업 트리에서 읽는다."""
    return (ROOT / path).read_text(encoding="utf-8")


def measure(read: Callable[[str], str] = here_text) -> dict[str, int]:
    """저장소 전체의 못. 키는 `모듈.상수`다.

    `read`를 주면 그것으로 파일을 읽는다 — 부모 커밋을 같은 코드로 재는 데 쓴다.
    """
    opened = read
    found: dict[str, int] = {}
    for pattern in SOURCES:
        for path in sorted(ROOT.glob(pattern)):
            short = path.relative_to(ROOT).as_posix()
            try:
                text = opened(short)
            except (OSError, subprocess.CalledProcessError):
                continue
            for name, value in nails(text).items():
                found[f"{path.stem}.{name}"] = value
    return {key: value for key, value in found.items() if key not in OWNED_ELSEWHERE}


def at(commit: str) -> dict[str, int]:
    """그 커밋의 못. **지금의 파일 목록으로 훑는다** — 새 파일은 부모에 없으니 건너뛴다."""

    def read(path: str) -> str:
        return subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        ).stdout

    return measure(read)


def moved(key: str, after: dict[str, int]) -> str | None:
    """그 못이 **다른 모듈로 이사했나** (D-0353).

    키가 `모듈.상수`라서 **이사가 사라짐으로 보인다.** 실측: 이력을 훑으니
    `check_decisions.UNKNOWN_EVIDENCE`가 「사라졌다」로 떴는데 `decision_evidence.py`로
    옮겨간 것이었다 — **거짓 경보다** (GR-0.8). 같은 상수 이름이 다른 모듈에 있으면
    이사이고, 그때는 **값을 그 자리에서 비교한다.**
    """
    tail = key.split(".", 1)[1]
    for other in after:
        if other != key and other.split(".", 1)[1] == tail:
            return other
    return None


def loosened(before: dict[str, int], after: dict[str, int]) -> list[str]:
    """느슨해진 자리. **사라진 못은 늘 느슨해지는 쪽이다** (D-0349)."""
    report: list[str] = []
    for key, was in sorted(before.items()):
        name = key.split(".", 1)[1].split("[", 1)[0]
        which = NAILS[kind(name) or "천장"]
        now = after.get(key)
        if now is None and (elsewhere := moved(key, after)) is not None:
            key, now = elsewhere, after[elsewhere]
        if now is None:
            report.append(f"{key}: {was} → **사라졌다**")
        elif which == "천장" and now > was:
            report.append(f"{key}: 천장 {was} → {now} (올랐다)")
        elif which == "바닥" and now < was:
            report.append(f"{key}: 바닥 {was} → {now} (내렸다)")
    return report


def git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    return done.stdout


def pending() -> set[str]:
    """아직 커밋 안 된 변경. 추적 안 된 파일까지 (D-0222의 그 자리)."""
    return {
        line[3:].strip('"') for line in git("status", "--porcelain", "-uall").split("\n") if line
    }


def rendered(seen: dict[str, int]) -> str:
    """`BASELINE` 블록을 다시 적는다. **사람이 손으로 안 적는다** (GR-0.7)."""
    rows = "".join(f'    "{key}": {value},\n' for key, value in sorted(seen.items()))
    return f"BASELINE: dict[str, int] = {{\n{rows}}}\n"


def verdict(seen: dict[str, int], pinned: dict[str, int]) -> list[str]:
    """지금 값이 **가장 조였던 값**보다 느슨한 자리, 그리고 **안 박힌 새 못**."""
    return loosened(pinned, seen) + [
        f"{key}: {value} — **못에 없다.** `--update`로 조인다"
        for key, value in sorted(seen.items())
        if key not in pinned
    ]


def tightest_in_history() -> dict[str, int]:
    """**이력 전체에서 가장 조였던 값** (D-0353).

    기준선을 *지금* 값에서 시작하면 **이미 침식된 것을 모른다** (GR-0.5). 그래서 못 파일을
    건드린 커밋만 훑어 못마다 가장 조였던 값을 고른다. 실측: 내 미러 125판에서
    `deadcheck.CEILING["건너뛴 시험"]`의 가장 조였던 값이 **2**였고 지금은 15다 — 열셋이
    여러 판에 걸쳐 쌓였고 **부모만 보는 검사는 그것을 영원히 못 본다.**

    느리다(내 미러 125판에 70초). `--update --from-history`로만 쓴다.
    """
    commits = git("rev-list", "--all", "--", "tools/", "core/tests/unit/").split()
    tightest: dict[str, int] = {}
    for one in commits:
        try:
            seen = at(one)
        except (OSError, SyntaxError, ValueError):
            continue
        for key, value in seen.items():
            name = key.split(".", 1)[1].split("[", 1)[0]
            which = NAILS[kind(name) or "천장"]
            if key not in tightest:
                tightest[key] = value
            elif which == "천장":
                tightest[key] = min(tightest[key], value)
            else:
                tightest[key] = max(tightest[key], value)
    return tightest


def update(allow_loosening: bool = False, from_history: bool = False) -> int:
    """못을 다시 박는다. **조이는 쪽으로만** 쓴다."""
    text = HERE.read_text(encoding="utf-8")
    if not BLOCK.search(text):
        print("`BASELINE` 블록을 못 찾았다. 정본이 사라졌다", file=sys.stderr)
        return 1
    seen = measure()
    if from_history:
        # **이력의 가장 조였던 값을 기준선으로 가져온다.** 지금 값이 거기서 느슨하면
        # `--loosen`과 기록 없이는 못 박는다 — 그것이 이 모드의 값이다.
        older = tightest_in_history()
        print(f"이력에서 못 {len(older)}개를 읽었다")
        seen = {key: older.get(key, value) for key, value in seen.items()}
        for key, value in older.items():
            seen.setdefault(key, value)
        seen = {key: value for key, value in seen.items() if key in measure()}
    slack = loosened(BASELINE, seen)
    if slack and not allow_loosening:
        print(f"못이 느슨해지는 쪽이다. {len(slack)}곳이다 — 안 쓴다.", file=sys.stderr)
        for line in slack:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\n**느슨해진 래칫은 초록으로 위장한다.** 내린 것이 **맞다면**"
            f" `--update --loosen`과 `{PAST}` 한 줄이 필요하다 (D-0118의 `GROW=1`).",
            file=sys.stderr,
        )
        return 1
    if slack and PAST not in pending():
        print(
            f"내려 박으려면 `{PAST}`가 같은 변경에 있어야 한다. 무엇을 왜 내렸는지 쓴다.",
            file=sys.stderr,
        )
        return 1
    swapped = BLOCK.sub(lambda _: rendered(seen), text, count=1)
    if swapped == text:
        print(f"못은 이미 실측과 같다 · 못 {len(seen)}개")
        return 0
    HERE.write_text(swapped, encoding="utf-8")
    print(
        f"못을 {'느슨하게 다시 박았다' if slack else '조였다'} · 못 {len(seen)}개."
        f" **{PAST}에 무엇을 왜 바꿨는지 쓴다**"
    )
    return 0


def check() -> tuple[list[str], str]:
    """느슨해진 자리와 **무엇을 쟀는지**. 못 쟀으면 그렇게 말한다 (GR-0.5)."""
    here = measure()
    if len(here) < FLOOR_NAILS:
        return (
            [f"못을 {len(here)}개 읽었다(바닥 {FLOOR_NAILS}). **그물이 비었다** (D-0230)"],
            "못 쟀다",
        )
    if len(BASELINE) < FLOOR_NAILS:
        return (
            [f"박힌 못이 {len(BASELINE)}개다(바닥 {FLOOR_NAILS}). **빈 그물이다** (D-0230)"],
            "못 쟀다",
        )
    problems = verdict(here, BASELINE)
    if problems:
        return (
            [
                *problems,
                "**가장 조였던 값에서 느슨해졌다.** 맞다면 `--update --loosen`과"
                f" `{PAST}` 한 줄이다 (D-0353)",
            ],
            f"박힌 못 {len(BASELINE)}개와 대조 · 어긋남 {len(problems)}곳",
        )
    return [], f"가장 조였던 값과 같다 · 박힌 못 {len(BASELINE)}개"


FLOOR_NAILS = 25
"""읽어야 하는 못의 **바닥** (D-0230). 실측 29개 — 어휘가 망가지면 0이 되고 통과한다."""

HERE = Path(__file__).resolve()
BLOCK = re.compile(r"^BASELINE: dict\[str, int\] = \{\n.*?^\}\n", re.MULTILINE | re.DOTALL)
"""**블록 자신을 겨눈다. 표식 주석을 안 쓴다** (D-0353).

첫 판은 `# ---- 못 시작 ----` 꼴 표식을 썼고, 그 표식을 정의하는 `OPEN = "…"` 줄이
**제 정규식에 먼저 걸려** `--update`가 상수 정의까지 집어삼켰다 — 파일이 문법 오류로
죽었다. `check_sight`가 `PINNED = {`를 바로 겨누는 것이 그 이유다.
"""

BASELINE: dict[str, int] = {
    "check_args.FLOOR[make 호출]": 3,
    "check_args.FLOOR[도구 호출]": 40,
    "check_args.FLOOR[바깥 파일]": 10,
    "check_args.FLOOR[쓰임새 주석]": 10,
    "check_artifacts.QUARANTINE_CEILING": 0,
    "check_artifacts.TRANSIENT_CEILING": 1,
    "check_artifacts.UNDER_STUDY_CEILING": 1,
    "check_compose.CEILING[core]": 2816,
    "check_compose.CEILING[ml]": 2304,
    "check_compose.CEILING[obs]": 768,
    "check_decisions.FORMAT_ENFORCED_FROM": 80,
    "check_doc_style.ENFORCER_FROM": 1,
    "check_doc_style.REPRODUCE_FROM": 1,
    "check_doc_style.UNKNOWN_UNTIL": 249,
    "check_issue_mentions.FLOOR[문서]": 3,
    "check_issue_mentions.FLOOR[코드]": 250,
    "check_patch.BASE_REQUIRED_FROM": 351,
    "check_ratchets.FLOOR_NAILS": 25,
    "check_under_load.FLOOR": 15,
    "deadcheck.CEILING[건너뛴 시험]": 15,
    "deadcheck.CEILING[눈먼 접두사]": 0,
    "deadcheck.CEILING[무검증 시험]": 0,
    "deadcheck.CEILING[버려진 문서 문자열]": 0,
    "deadcheck.CEILING[빈 그물]": 0,
    "deadcheck.CEILING[삼킨 예외]": 0,
    "debts.STALE_FLOOR": 10,
    "decision_evidence.NODE_FROM": 270,
    "decision_evidence.UNKNOWN_EVIDENCE": 0,
    "mutate_gate.WIRING_CEILING": 49,
    "test_gate_tools.UNTESTED": 0,
    "test_gate_types.UNTYPED_FAKES": 0,
}
"""**지금까지 가장 조였던 값** (D-0353). 여기서 느슨해지면 몇 판이 걸렸든 빨개진다."""


def main() -> int:
    parser = argparse.ArgumentParser(description="래칫이 느슨해진 자리 (D-0352 · D-0353)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--list", action="store_true", help="못과 방향을 찍는다")
    parser.add_argument("--update", action="store_true", help="조이는 쪽으로 다시 박는다")
    parser.add_argument(
        "--loosen", action="store_true", help="내려 박는 것을 허락한다. **기록이 필요하다**"
    )
    parser.add_argument(
        "--from-history",
        action="store_true",
        help="이력 전체에서 가장 조였던 값을 가져온다. 느리다",
    )
    args = parser.parse_args()

    if args.update:
        return update(allow_loosening=args.loosen, from_history=args.from_history)
    if args.loosen:
        print("`--loosen`은 `--update`와 함께 쓴다", file=sys.stderr)
        return 1

    here = measure()
    if args.list:
        for key, value in sorted(here.items()):
            name = key.split(".", 1)[1].split("[", 1)[0]
            print(f"  {key:46s} {NAILS[kind(name) or '천장']:4s} {value}")
        print(f"  못 {len(here)}개")
        return 0

    problems, what = check()
    if problems:
        print(f"래칫이 느슨해졌다 — {what}", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1
    print(f"래칫 검사 통과 · 못 {len(here)}개 · {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
