#!/usr/bin/env python3
"""내보내도 되는가 — 푸시 전후를 한 줄로 잇는다 (D-0147).

    make ship              검사만 한다. 아무것도 안 바꾼다
    make ship PUSH=1       통과하면 push 하고 교두보까지 보낸다

### 왜 만들었나

도구는 열다섯이고 **파이프라인이 없었다.** `make check`가 여섯 단계를 묶는 것이
전부이고, 푸시 전후의 순서는 사람 머리에 있었다.

    make check  &&  git push  &&  make artifacts-push ONLY=keys

**손으로 기억하는 목록은 언젠가 하나를 빠뜨린다.** 이 세션만 해도 `make check` 없이
패치를 붙인 적이 있고, 교두보 보내기를 잊은 채 다음 작업으로 넘어간 적이 있다.

### 지우지 않는다

찌꺼기를 **세어서 보고만 한다.** 무엇이 쌓이는지 실측하지 않은 채 지우는 정책을
### 지우는 것과 세는 것 (D-0279)

| 부류 | 무엇 | 왜 |
|---|---|---|
| 자동으로 지운다 | `__pycache__` · 도구 캐시 | **다시 만들어진다** — `make clean` · `clean-all` |
| 세기만 한다 | `.backup/` · `.o7-*/` · 루트 `*.sh` | 사람이 넣은 것일 수 있다. 판정은 사람이 |
| 안 본다 | `.venv/` · `var/` · `node_modules/` | 재생성이 수십 분이다 |

**재생성 가능성이 «지워도 되는가»를 가른다** — `artifacts.toml`의 R2와 같은 기준이다.

만들면 그것이 지어낸 규칙이다 (GR-0.5). `.backup/`과 `.o7-*/`는 D-0072가 없앤
유물이라 지금은 안 쌓여야 하고, **쌓여 있다면 그 사실이 소식이다.**

`--fix`는 `make clean`이 이미 하는 것만 한다 — 파이썬 바이트코드다.

### `make check`와 겹치지 않는다

| | 무엇을 보는가 |
|---|---|
| `make check` | **코드와 문서가 규약과 맞는가** |
| `make ship` | **내보내도 되는가** — 위 + git 상태 + 위생 + 산출물 |

`ship`이 `make check`를 부른다. **중복 구현하지 않는다.**
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import tidy

ROOT = Path(__file__).resolve().parent.parent

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
OFF = "\033[0m"

LEFTOVERS = (".backup", ".o7-*")
"""D-0072가 없앤 유물. **쌓여 있다면 그 사실이 소식이다.**"""

REGENERABLE = ("__pycache__",)
"""**자동으로 지운다** — 다시 만들어지는 것 (D-0279). `make clean`이 이것을 지운다.

정본은 여기이고 `Makefile`의 `clean:`이 같아야 한다 — `test_hygiene`이 대조한다."""

COUNTED = (*LEFTOVERS, "*.sh")
"""**세기만 한다** — 다시 만들어지지 않는 것 (D-0279).

`.backup/`·`.o7-*/`에는 사람이 넣은 것이 들어 있을 수 있고 루트의 `*.sh`는 일회성
스크립트다. **재생성 가능성이 «지워도 되는가»를 가른다** — `artifacts.toml`의 R2가
`.gitignore`에 대해 말하는 것과 같은 기준이다.

`var/`를 지우지 않는 근거가 바로 이것이고(`clean-all`이 «수십 분»이라 적었다), 그 기준을
찌꺼기에도 그대로 쓴다. **세는 것과 지우는 것을 가르는 규칙이 적혀 있지 않았다** — 그것이
PLAN §3의 «정리 정책이 `__pycache__`뿐이다»였다."""

OUTSIDE = (".venv", "var", "node_modules")
"""세지 않는 나무 (D-0148).

첫 실측이 `__pycache__` **449개**였고 **그중 대부분이 `.venv`였다** — 이 저장소
사본에서 재니 45개 중 27개(60%)가 거기였다. 기기에는 `torch`·`demucs`가 들어 있어
비율이 더 높다.

**세는 수가 틀리면 그 수를 보고 한 행동도 틀린다.** `make clean`이 그 바이트코드를
지우면 다음 실행이 전부 다시 컴파일한다.

`var/`도 안 센다. **산출물은 찌꺼기가 아니다** (D-0067)."""


def _run(*command: str) -> tuple[int, str]:
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return done.returncode, (done.stdout + done.stderr).strip()


SAME_COMMAND = "**같은 명령이 여기서 빨갰다.** 위 꼬리에 터진 자리가 있다."
PUSH_NOTE = "**밀지 못했다.** 원격이 앞서 있으면 `git pull --rebase` 뒤 다시 친다."
BRIDGE_NOTE = "   **교두보로 못 보냈다.** 고친 뒤 `make artifacts-push` (커밋은 이미 밀었다)"
"""기본 사유 문구. 부르는 쪽이 자기 문구를 준다 (D-0283)."""

KEEP_LINES = 30
"""막혔을 때 보여 줄 꼬리 줄 수 (D-0282). **판정하면서 근거를 버리지 않는다.**"""


def blocked(text: str, *, note: str = SAME_COMMAND, keep: int = KEEP_LINES) -> list[str]:
    """`make check`가 막혔을 때 찍을 줄. **잡은 출력의 꼬리를 그대로 낸다** (D-0282).

    예전에는 **마지막 한 줄**만 찍었다.

        막힘  make[1]: *** [Makefile:74: test] Error 1

    그 줄은 «어느 단계»만 알려 주고 «어느 시험»은 안 알려 준다. 그리고 안내가
    *"`make check`를 먼저 초록으로 만든다"*였는데, 사용자는 **바로 앞에서 그것을 초록으로
    돌린 뒤**였다 — 같은 명령이 한 번은 초록이고 한 번은 빨갰으므로 그 안내는 **거짓말이고
    사람을 제자리에 세운다.**

    도구가 판정을 내면 그 근거를 같이 내야 한다. `make ship`이 산출물 판정을 수로 찍게 만든
    것과 같은 규율이다 (D-0269 — *"가리키기만 하면 안 본다"*).
    """
    lines = text.strip().splitlines() if text.strip() else []
    head = f"{RED}   막힘{OFF}  {lines[-1] if lines else '(출력이 없다)'}"
    if len(lines) <= 1:
        return [head, "", note, ""]
    tail = lines[-keep:]
    return [
        head,
        f"{DIM}   ── 잡은 출력 마지막 {len(tail)}줄{OFF}",
        *(f"   {line}" for line in tail),
        "",
        note,
        "",
    ]


def _git(*arguments: str) -> str:
    code, text = _run("git", *arguments)
    return text if code == 0 else ""


def check_git() -> list[str]:
    """워킹트리 · 브랜치 · 원격과의 거리. **깨끗하지 않으면 내보내지 않는다.**

    **원격을 읽고 판정한다** (D-0283). 예전에는 `git fetch` 없이 `@{upstream}..HEAD`를 셌고,
    그 기준은 **마지막으로 읽은 원격**이다 — 그 사이 원격이 움직이면 *"미푸시 커밋 2개"*로
    초록을 찍어 놓고 곧바로 `git push`가 거절당한다. 사용자가 그것을 두 판 연속 맞았다.

    **못 읽으면 못 읽었다고 말한다.** 망이 없는 기기에서 «0개»라고 찍으면 그것이 거짓이다.
    """
    problems: list[str] = []
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        problems.append(f"워킹트리에 커밋 안 된 변경이 {len(dirty.splitlines())}개 있다")
    if not _git("rev-parse", "--abbrev-ref", "@{upstream}"):
        problems.append("upstream이 없다. `git push -u origin <브랜치>`")
        return problems
    code, _text = _run("git", "fetch", "--quiet")
    if code != 0:
        problems.append("원격을 못 읽었다 (`git fetch` 실패). 거리를 모르므로 판정하지 않는다")
        return problems
    behind = _git("rev-list", "--count", "HEAD..@{upstream}")
    if behind and behind != "0":
        problems.append(f"원격이 {behind}개 앞선다. `git pull --rebase` 뒤에 다시 친다")
    return problems


def last_decision() -> str:
    """대장의 **마지막 결정 번호와 건수** (D-0287).

    **왜 내보내는 자리에서 찍나.** 다음 판을 짜는 쪽이 *"어디까지 붙었나"*를 모르면
    이미 붙은 패치를 또 붙이라고 적는다. 실제로 그랬다 — D-0283이 푸시까지 끝난 뒤
    *"아직 안 붙었다"*는 지시가 나갔고, 사람은 **자기가 뭘 지웠나** 의심했다.

    이 한 줄이 그 자리를 막는다. `make ship` 출력에 번호가 찍히면 **그 번호가 다음
    지시의 기준**이 된다 — D-0283이 「낡은 자료로 내린 초록이 빨강보다 나쁘다」고
    적은 것과 같은 자리이고, 이번에는 그 낡은 자료가 **사람의 머릿속**에 있었다.
    """
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    found = re.findall(r"^## (D-\d{4})\.", text, re.MULTILINE)
    return f"{found[-1]} · 총 {len(found)}건" if found else "(없다)"


def count_leftovers() -> list[str]:
    """찌꺼기를 **센다. 지우지 않는다.**"""
    found: list[str] = []
    for pattern in LEFTOVERS:
        hits = [path for path in ROOT.glob(pattern) if path.exists()]
        if hits:
            found.append(f"{pattern}가 {len(hits)}개 있다. D-0072가 없앤 유물이다")
    caches = [
        path
        for path in ROOT.rglob("__pycache__")
        if not any(part in OUTSIDE for part in path.relative_to(ROOT).parts)
    ]
    if caches:
        found.append(f"저장소 `__pycache__` {len(caches)}개. `make clean` 또는 `FIX=1`")
    scripts = [path.name for path in ROOT.glob("*.sh")]
    if scripts:
        found.append(f"루트에 일회성 스크립트 {len(scripts)}개: {' · '.join(scripts[:3])}")
    return found


DEFAULT_ONLY = "keys,eval"
"""교두보로 보내는 세트 (D-0253).

D-0119가 `keys`만 보내게 했다 — 1.7GB · 17192개에서 O-37이 읽는 것이 `keys-*` 74MB뿐이고
**DrvFs에서는 크기보다 개수가 아프다.** 옳은 판단이었는데 **`eval/`이 같이 빠졌다.**

그 대가를 나중에 물었다. 광인사가 죽을 때(D-0122) 옛 평가 산출물이 함께 사라졌고,
그래서 결정 기록 74건의 수치를 **다시 낼 명령을 찾을 수 없다** (D-0251 · D-0252).
`eval/`은 열네 개 · 수십 KB다. **개수가 아픈 쪽이 아니었다.**"""


def only_flags(raw: str) -> list[str]:
    """`keys,eval` → `--only keys --only eval`. `sync_artifacts`는 여러 번 받는다."""
    flags: list[str] = []
    for part in raw.split(","):
        if part.strip():
            flags += ["--only", part.strip()]
    return flags


PASSING = ("success", "skipped", "neutral")
"""**초록으로 칠 결론.** 나머지는 전부 빨강이다 (D-0255).

이름이 `GREEN`이었다가 **48행의 색 코드를 덮었다** (D-0257). `make ship`이 섹션
제목마다 `('success', 'skipped', 'neutral')`을 찍는 채로 통과했다.

`failure`만 거르는 차단 목록을 썼다가 `timed_out` · `cancelled` · `action_required`가
새는 것을 확인했다. **모르는 값을 통과시키는 그물은 모르는 사고를 통과시킨다.**"""


def ci_verdict() -> list[str]:
    """`main`의 최근 워크플로 결론 (D-0254).

    **빨간 CI를 아무도 안 보고 있었다.** D-0246이 `python-docx`를 시험에 끌어들인 뒤
    CI가 계속 빨갰고, 로컬 `make check`는 초록이라 여덟 판을 그 위에 쌓았다.
    내보내기 전에 **직전 커밋이 어떻게 됐는지** 여기서 말한다.

    `gh`가 없거나 로그인 안 된 기기도 있다. **막지 않고 알리기만 한다** (D-0068).
    없는 명령을 `_run`에 넘기면 `FileNotFoundError`로 배가 가라앉는다 — 실측으로 확인했다.
    """
    if shutil.which("gh") is None:
        return [f"{DIM}못 읽었다 — `gh`가 없다{OFF}"]
    code, text = _run(
        "gh",
        "run",
        "list",
        "--branch",
        "main",
        "--limit",
        "6",
        "--json",
        "conclusion,name,headSha",
    )
    if code != 0 or not text.strip():
        return [f"{DIM}못 읽었다 — `gh`가 없거나 로그인 안 됐다{OFF}"]
    try:
        runs = json.loads(text)
    except json.JSONDecodeError:
        return [f"{DIM}못 읽었다 — `gh` 출력이 JSON이 아니다{OFF}"]

    newest = runs[0]["headSha"] if runs else ""
    latest = [run for run in runs if run.get("headSha") == newest]
    # **모르는 결론은 빨강이다** (D-0255). `failure`만 걸렀더니 `timed_out` ·
    # `cancelled` · `action_required`가 초록으로 샜다 — 차단 목록은 모르는 것을 통과시킨다.
    failed = [run for run in latest if run.get("conclusion") not in (*PASSING, None, "")]
    if failed:
        names = " · ".join(str(run.get("name", "?")) for run in failed)
        return [
            f"{RED}빨강{OFF}  {names}",
            f"{DIM}      `gh run list` · 고치고 나서 다음 것을 쌓는다{OFF}",
        ]
    if any(run.get("conclusion") in (None, "") for run in latest):
        return [f"{DIM}도는 중{OFF}"]
    return [f"{GREEN}초록{OFF}  {len(latest)}개"]


def main() -> int:
    parser = argparse.ArgumentParser(description="내보내도 되는가 (D-0147)")
    parser.add_argument("--push", action="store_true", help="통과하면 push하고 교두보로 보낸다")
    parser.add_argument("--fix", action="store_true", help="바이트코드를 지운다")
    parser.add_argument(
        "--only",
        default=DEFAULT_ONLY,
        help=f"교두보로 보낼 세트. 쉼표로 여럿 (기본 {DEFAULT_ONLY}) (D-0119 · D-0253)",
    )
    args = parser.parse_args()

    if args.fix:
        # **`make clean`을 부른다.** 지우는 범위를 두 곳에 적으면 어긋난다 (D-0148).
        _run("make", "clean")

    print(f"{DIM}── 규약 (make check){OFF}")
    code, text = _run("make", "check")
    if code != 0:
        for line in blocked(text):
            print(line)
        return 1
    print(f"{GREEN}   통과{OFF}")

    print(f"{DIM}── git{OFF}")
    problems = check_git()
    for line in problems:
        print(f"{RED}   막힘{OFF}  {line}")
    if problems:
        # **막힘이라고 찍고 밀지 않는다** (D-0283). 예전에는 찍기만 하고 그대로 내려가
        # `git push`를 쳤다 — 그 자리에서 거절당했고 사람은 **빨간 줄을 두 번** 봤다.
        if args.push:
            print("\n`git` 쪽을 먼저 정리한다. **밀지 않았다.**")
            return 1
    else:
        ahead = _git("rev-list", "--count", "@{upstream}..HEAD")
        print(f"{GREEN}   통과{OFF}  미푸시 커밋 {ahead or '0'}개")

    print(f"{DIM}── 기록{OFF}")
    print(f"   마지막 결정  {last_decision()}")

    print(f"{DIM}── CI (직전 커밋){OFF}")
    for line in ci_verdict():
        print(f"   {line}")

    print(f"{DIM}── 위생 (세기만 한다){OFF}")
    # git 찌꺼기는 `tidy.py`가 센다. 규칙을 여기 다시 적지 않는다 (D-0225).
    leftovers = count_leftovers() + tidy.report(tidy.survey())
    for line in leftovers or ["깨끗하다"]:
        print(f"{DIM}   {line}{OFF}")
    if leftovers:
        print(f"{DIM}   치우려면 `make tidy YES=1` · 바이트코드는 `FIX=1`{OFF}")

    print(f"{DIM}── 산출물 (교두보){OFF}")
    code, text = _run("python3", "tools/sync_artifacts.py", "status")
    if code != 0:
        # **교두보가 없는 기기도 있다.** 막지 않고 알리기만 한다 (D-0068).
        print(f"{DIM}   교두보를 못 읽었다. `make setup`{OFF}")
    else:
        for line in text.splitlines()[-3:]:
            print(f"{DIM}   {line.strip()}{OFF}")

    # **대장 판정을 수로 찍는다** (D-0269). 가리키기만 하면 안 본다 — 작성자가 대장을
    # 네 판 연속 틀린 채 내보냈고, 그 넷 다 `--audit` 한 번이면 그 자리에서 드러났다.
    # 막지는 않는다. `--audit`이 판정하고 여기는 **숫자를 눈앞에 둔다.**
    _, verdict = _run("python3", "tools/check_artifacts.py", "--audit")
    summary = next((line for line in verdict.splitlines() if "정상" in line), "")
    if summary:
        print(f"{DIM}   대장 {summary.strip()}{OFF}")
        print(f"{DIM}   어긋나면: make artifacts-audit{OFF}")

    if problems:
        return 1
    if not args.push:
        print("\n내보낼 준비가 됐다. `make ship PUSH=1`")
        return 0

    print(f"\n{DIM}── push{OFF}")
    code, text = _run("git", "push")
    if code != 0:
        for line in blocked(text, note=PUSH_NOTE):
            print(line)
        return 1
    print(text.strip().splitlines()[-1] if text else "")
    code, text = _run("python3", "tools/sync_artifacts.py", "push", *only_flags(args.only))
    if code != 0:
        for line in blocked(text, note=BRIDGE_NOTE):
            print(line)
        # **교두보가 배를 가라앉히지 않는다** (D-0068 · D-0239). `git push`는 이미 끝났고,
        # 외장 드라이브가 빠졌거나 DrvFs가 토라진 것으로 «내보내기 실패»를 찍으면
        # 사람은 무엇이 밀려갔는지 모른 채 다시 친다.
        return 0
    print(text.strip().splitlines()[-1] if text else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
