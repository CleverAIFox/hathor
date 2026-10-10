#!/usr/bin/env python3
"""**패치 머리를 네 곳에 적어 놓고 아무도 대조하지 않았다** (D-0352 · D-0043).

### `make check`이 뽑는 쪽을 안 봤다

D-0351이 `make patch`를 만들었고 **`make check`은 그것을 한 번도 안 불렀다.** 뽑는 쪽이
망가지면 다음 패치를 뽑을 때 알게 되고, 그때는 받는 쪽에서 터진다 — D-0350이 그 꼴이다.

### 머리는 네 곳에 산다

| 곳 | 하는 일 |
|---|---|
| `tools/make_patch.sh` | **쓴다** |
| `tools/apply_patch.sh` | **읽는다** |
| `tools/render_figures.py` | 기획서 파이프 그림에 **그린다** |
| `README.md` | 표로 **적는다** |

**두 곳에 적으면 어긋난다** (D-0043). 넷이면 넷 다 어긋난다 — 실제로 D-0287이 선행
관문을 세운 뒤 **그림과 README가 안 따라왔다.**

### 그리고 실제로 뽑아 본다

머리 이름만 맞춰 두면 *"적혀 있다"*까지다. 이 검사는 **`HEAD`를 패치로 뽑아 기준 위에서
붙여 보고 버린다** — 통과한 커밋은 반드시 패치가 된다. 부모가 없는 얕은 클론에서는 못
돌리므로 **그 사실을 화면에 적는다** (GR-0.5). CI는 `fetch-depth: 2`로 받는다.

    python3 tools/check_patch.py            # 검사한다
    python3 tools/check_patch.py --no-live  # 뽑아 보기를 건너뛴다 (얕은 클론)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKER = ROOT / "tools" / "make_patch.sh"
TAKER = ROOT / "tools" / "apply_patch.sh"
FIGURES = ROOT / "tools" / "render_figures.py"
README = ROOT / "README.md"

HEADS = ("hathor-commit", "hathor-needs", "hathor-base")
"""**모든 패치가 드는** 머리 셋. 늘면 네 곳이 같이 늘어야 한다 (D-0352)."""

OPTIONAL_HEADS = ("hathor-after",)
"""**걸릴 때만 드는** 머리 (D-0377). 네 곳에 적혀 있어야 하지만 모든 패치에 있지는 않다.

`HEADS`에 넣으면 *«모든 패치가 들어야 한다»*가 되고, 그러면 아무것도 안 만드는 패치도
`# hathor-after:`를 달아야 한다 — 거짓 선언이 늘고 아무도 안 읽는다 (GR-0.8).
"""

AFTER_RULES = (("docs/proposal.docx", "proposal"),)
"""**패치에 안 싣고 받는 쪽이 다시 만드는 것** → 그것을 만드는 `make` 목표 (D-0377).

docx는 zip이라 같은 입력에서 같은 바이트가 안 나오고, 그리는 `dot`의 판이 기기마다
다르다 (D-0376). 그래서 **패치에 안 담는다** — 담으면 받는 쪽의 blob과 어긋나 `git
apply`가 이진 전제에서 바로 터진다. 실측으로 **한 번 터졌다.**

그 자리에 「붙인 뒤 할 일」을 적는다. D-0375가 *«이런 경우가 한 번이고, 한 번을 보고
머리를 늘리지 않는다»*(D-0364)고 적었고 D-0376이 둘째였다. **셋째는 그 기록을 쓴 날
왔다** — 내가 docx를 손으로 뺐고(GR-0.7), 그가 `git apply`를 경로 없이 쳐서 패치가 안
붙은 채로 `make proposal`이 돌았다. 세 번이면 만든다.
"""

AFTER_ALLOWED = tuple(dict.fromkeys(target for _, target in AFTER_RULES))
"""`# hathor-after:`가 가질 수 있는 값 전부.

**패치 머리에서 임의 셸이 돌면 그것이 구멍이다.** 값은 `make` 목표 이름 하나씩이고,
받는 쪽은 이 목록에 있는 것만 돌린다. 목록은 **여기 한 곳**이고 셸 둘이 읽는다 (D-0043).
"""

AFTER_FLOOR = 1
"""규칙의 **바닥** (D-0230). 표가 비면 「아무 패치도 뒤처리가 필요 없다」가 거짓으로 참이 된다."""

BASE_REQUIRED_FROM = 351
"""`# hathor-base:`를 **반드시** 갖는 첫 결정 번호 (D-0352).

**소급 바닥이다.** 그 앞의 패치 350판에는 그 머리가 없고 소급해 넣지 않는다 — 추가
전용이 그쪽 방어선이다. 대신 **이 번호 이후를 선행으로 선언한 패치는 머리가 없으면
막는다.** 머리가 없는 것을 영원히 통과시키면 관문이 선택 사항이 되고, 선택 사항인
관문은 관문이 아니다 (D-0126). `check_decisions.FORMAT_ENFORCED_FROM`과 같은 규율이다.
"""


def figure() -> str:
    """파이프 그림의 **본문만** 떼어 온다. 다른 그림의 글자가 섞이면 대조가 거짓이 된다."""
    text = FIGURES.read_text(encoding="utf-8")
    start = text.index("def patch_pipe")
    return text[start : text.index('return render(out, "patch_pipe"', start)]


def places() -> dict[str, str]:
    """머리가 적혀 있어야 하는 네 곳의 본문."""
    return {
        "tools/make_patch.sh": MAKER.read_text(encoding="utf-8"),
        "tools/apply_patch.sh": TAKER.read_text(encoding="utf-8"),
        "tools/render_figures.py (patch_pipe)": figure(),
        "README.md": README.read_text(encoding="utf-8"),
    }


def check_heads() -> list[str]:
    """머리가 네 곳에 다 있나 (D-0043). **걸릴 때만 드는 것도 적혀 있어야 한다.**"""
    return [
        f"{where}: `# {head}:`를 안 든다 — 네 곳이 어긋났다 (D-0043)"
        for where, text in places().items()
        for head in (*HEADS, *OPTIONAL_HEADS)
        if f"# {head}:" not in text
    ]


def check_after_table() -> list[str]:
    """규칙 표와 받는 쪽의 허용 목록이 같은가 (D-0043 · D-0230)."""
    if len(AFTER_RULES) < AFTER_FLOOR:
        return [f"뒤처리 규칙이 {len(AFTER_RULES)}개다(바닥 {AFTER_FLOOR}). **그물이 비었다**"]
    taker = TAKER.read_text(encoding="utf-8")
    problems = [
        "tools/apply_patch.sh: 허용 목록을 `check_patch.AFTER_ALLOWED`에서 안 읽는다 (D-0043)"
    ] * ("AFTER_ALLOWED" not in taker)
    maker = MAKER.read_text(encoding="utf-8")
    problems += ["tools/make_patch.sh: 규칙을 `check_patch.AFTER_RULES`에서 안 읽는다 (D-0043)"] * (
        "AFTER_RULES" not in maker
    )
    return problems


def after_for(paths: list[str]) -> list[str]:
    """그 경로들이 부르는 뒤처리 목표. **선언이 정본이다** — 손으로 안 적는다 (GR-0.7)."""
    return list(dict.fromkeys(target for trigger, target in AFTER_RULES if trigger in paths))


def after_drift(touched: list[str], declared: str) -> list[str]:
    """뽑힌 머리와 **건드린 경로가 부르는 것**이 같은가 (D-0377).

    **양방향이다** (D-0363). 없어야 하는데 적힌 것도 든다 — 거짓 선언은 받는 쪽에서
    쓸데없는 빌드를 돌리고, 그것이 쌓이면 아무도 그 줄을 안 읽는다 (GR-0.8).
    """
    want, got = sorted(after_for(touched)), sorted(declared.split())
    if want == got:
        return []
    return [
        f"`# hathor-after:`가 «{' '.join(got) or '없다'}»인데 "
        f"건드린 경로는 «{' '.join(want) or '없다'}»를 부른다 (D-0377)"
    ]


def check_floor() -> list[str]:
    """소급 바닥이 받는 쪽과 여기서 같은 수인가 (D-0043).

    **두 곳에 적은 수는 어긋난다.** 받는 쪽이 셸이라 상수를 공유할 수 없으니 **대조한다.**
    """
    found = re.search(r"(?m)^BASE_FROM=([0-9]+)$", TAKER.read_text(encoding="utf-8"))
    if not found:
        return ["tools/apply_patch.sh: `BASE_FROM=`을 못 찾았다 — 소급 바닥이 사라졌다"]
    if int(found.group(1)) != BASE_REQUIRED_FROM:
        return [
            f"소급 바닥이 어긋난다 — `apply_patch.sh`는 {found.group(1)}, "
            f"여기는 {BASE_REQUIRED_FROM} (D-0043)"
        ]
    return []


def has_parent() -> bool:
    """`HEAD`에 부모가 있나. 얕은 클론에서는 없다."""
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", "HEAD^{commit}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if done.returncode != 0:
        return False
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", "HEAD^^{commit}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return done.returncode == 0


def touched_by_head() -> list[str]:
    """`HEAD`가 건드린 경로. **시험이 손에 쥘 수 있게 함수로 뗀다** (D-0379).

    이것을 `pull_once()` 안에 박아 두면 시험이 **그날의 `HEAD`에 매인다** — 실제로
    그랬다: D-0378의 커밋이 제출본을 안 담은 판에서 시험 둘이 빨개졌고, **시험이
    아니라 그 커밋이 틀렸는데** 판정은 시험을 가리켰다.
    """
    return subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    ).stdout.split()


def pull_once() -> list[str]:
    """**`HEAD`를 실제로 뽑아 본다.** 뽑기 자신이 기준 위에서 붙여 보고 트리까지 맞춘다."""
    with tempfile.TemporaryDirectory() as box:
        out = Path(box) / "시험.patch"
        done = subprocess.run(
            ["bash", str(MAKER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env={"PATH": __import__("os").environ["PATH"], "OUT": str(out), "REV": "HEAD"},
        )
        if done.returncode != 0:
            tail = (done.stderr or done.stdout).strip().splitlines()
            return [f"`HEAD`를 패치로 못 뽑는다 — {tail[-1] if tail else '까닭 모름'}"]
        body = out.read_text(encoding="utf-8", errors="replace")
        heads = dict(
            line[2:].split(": ", 1) for line in body.splitlines() if line.startswith("# hathor-")
        )
        problems = [
            f"뽑은 패치에 `# {head}:`가 없다 — 머리를 안 쓰고 있다"
            for head in HEADS
            if head not in heads
        ]
        # **뒤처리가 걸리는 커밋이면 그 머리가 있어야 한다** (D-0377). 없으면 받는 쪽은
        # 「다시 만들라」는 말을 못 듣고, 산출물이 낡은 채로 커밋된다.
        problems += [
            f"뽑은 패치의 {one}"
            for one in after_drift(touched_by_head(), heads.get("hathor-after", ""))
        ]
        return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="패치 머리와 뽑기 검사 (D-0352)")
    parser.add_argument("--check", action="store_true", help="기본 동작. 배선을 위해 받는다")
    parser.add_argument("--no-live", action="store_true", help="뽑아 보기를 건너뛴다")
    args = parser.parse_args()

    problems = check_heads() + check_floor() + check_after_table()
    live = not args.no_live and has_parent()
    if live:
        problems += pull_once()

    if problems:
        print(f"패치 머리·뽑기가 어긋난 자리가 {len(problems)}곳 있다.", file=sys.stderr)
        for text in problems:
            print(f"  - {text}", file=sys.stderr)
        return 1

    # **못 잰 것을 통과로 적지 않는다** (GR-0.5). 안 돌렸으면 안 돌렸다고 찍는다.
    ran = "뽑기 실측 1판" if live else "뽑기 **안 돌렸다**(부모 없음 · 얕은 클론)"
    print(
        f"패치 검사 통과 · 머리 {len(HEADS) + len(OPTIONAL_HEADS)}종 x 곳 {len(places())}개 · "
        f"뒤처리 규칙 {len(AFTER_RULES)}개 · 소급 바닥 D-{BASE_REQUIRED_FROM:04d} · {ran}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
