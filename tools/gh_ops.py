#!/usr/bin/env python3
"""GitHub 쪽 일을 터미널에서 한다 — 설정 · 봇 · 배포 · 러너 (D-0226).

### 왜 필요한가

D-0222 ~ D-0225가 남긴 손 항목이 넷이었다 — Pages 첫 배포 · 머지 뒤 브랜치 자동 삭제 ·
Dependabot 로그 읽기 · 러너 토큰. **전부 웹 화면의 버튼이었고 PLAN에 줄로 쌓였다.** 버튼은
다시 누를 때 어디 있는지 잊고, 줄은 PLAN을 불린다. 전부 `gh`(GitHub CLI)로 된다.

| 명령 | 하는 일 |
|---|---|
| `setup` | 머지 뒤 브랜치 자동 삭제를 켜고 기획서 배포를 돌려 끝까지 본다. **몇 번 쳐도 같다** |
| `bot` | 열린 봇 PR과 최근 봇 실행을 찍고, 실패한 실행의 로그 끝을 보여 준다 |
| `bot --close` | 열린 봇 PR을 닫고 브랜치까지 지운다 |
| `smoke` | `gpu-smoke`를 돌리고 끝날 때까지 본다 |

러너 등록 토큰도 `gh`가 받는다 — `tools/register_runner.sh`가 인자 없이 불리면 여기서 받는다.

### 봇 로그

Dependabot은 Actions 위에서 돈다. 실행은 이벤트 `dynamic` · 이름 «Dependabot Updates»로 남고
`gh run view --log-failed`로 읽힌다. **Actions 위가 아닌 옛 갱신기로 돌았다면 CLI 길이 없다** —
그때는 찍힌 주소를 연다.

    python3 tools/gh_ops.py setup
    python3 tools/gh_ops.py bot [--close]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOT = "app/dependabot"
BOT_WORKFLOW = "Dependabot Updates"
PAGES = "proposal.yml"
SMOKE = "gpu-smoke.yml"
TAIL = 40


def gh(*arguments: str, check: bool = True) -> str:
    done = subprocess.run(["gh", *arguments], capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(f"gh {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def ready() -> str | None:
    """`gh`가 없거나 로그인 안 됐으면 이유. 되면 `None`."""
    if shutil.which("gh") is None:
        return "gh가 없다. `sudo apt install gh && gh auth login`"
    done = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
    return None if done.returncode == 0 else "gh 로그인이 안 됐다. `gh auth login`"


def failed(runs: list[dict[str, object]]) -> list[dict[str, object]]:
    """봇 실행 중 실패한 것. 이름으로 고른다 — `dynamic` 이벤트에는 다른 것도 있다."""
    return [
        run
        for run in runs
        if run.get("workflowName") == BOT_WORKFLOW and run.get("conclusion") == "failure"
    ]


def setup() -> int:
    gh("repo", "edit", "--delete-branch-on-merge")
    print("머지 뒤 브랜치 자동 삭제: 켬")
    print("기획서 배포:")
    return dispatch(PAGES)


def bot(close: bool) -> int:
    pulls = json.loads(
        gh("pr", "list", "--author", BOT, "--json", "number,title,headRefName", "--limit", "50")
    )
    print(f"열린 봇 PR {len(pulls)}개")
    for pull in pulls:
        print(f"  #{pull['number']}  {pull['title']}")
    runs = json.loads(
        gh(
            "run", "list", "--event", "dynamic", "--limit", "20",
            "--json", "databaseId,workflowName,conclusion,createdAt,displayTitle",
        )
    )  # fmt: skip
    bad = failed(runs)
    mine = sum(run.get("workflowName") == BOT_WORKFLOW for run in runs)
    print(f"최근 봇 실행 {mine}건 · 실패 {len(bad)}")
    for run in bad[:2]:
        print(f"\n── 실패 {run['databaseId']} · {run['createdAt']} · {run['displayTitle']}")
        log = gh("run", "view", str(run["databaseId"]), "--log-failed", check=False)
        print("\n".join(log.splitlines()[-TAIL:]) or "  (로그가 비었다)")
    if not runs:
        print("봇 실행이 Actions에 없다 — 옛 갱신기다. 오류 알림의 주소를 연다")
    if close:
        for pull in pulls:
            gh("pr", "close", str(pull["number"]), "--delete-branch")
        print(f"봇 PR {len(pulls)}개를 닫고 브랜치를 지웠다. 다음 달에 한 PR로 다시 온다")
    return 0


def newest(workflow: str) -> str:
    return gh("run", "list", "--workflow", workflow, "--limit", "1",
              "--json", "databaseId", "--jq", ".[0].databaseId").strip()  # fmt: skip


def latest(workflow: str, before: str) -> str | None:
    """방금 건 실행의 번호. **전의 번호와 달라질 때까지** 기다린다 — 곧바로 물으면 지난 실행이 온다.
    `gh run watch`에 번호가 없으면 목록을 묻고 멈춘다."""
    for _ in range(10):
        time.sleep(3)
        found = newest(workflow)
        if found and found != before:
            return found
    return None


def dispatch(workflow: str) -> int:
    """돌리고 끝날 때까지 본다. 실패하면 1."""
    before = newest(workflow)
    gh("workflow", "run", workflow)
    run = latest(workflow, before)
    if run is None:
        print(f"{workflow} 실행 번호를 못 받았다. `gh run list --workflow {workflow}`")
        return 1
    print(f"{workflow} · 실행 {run}. 끊으면(Ctrl-C) 실행을 취소한다")
    try:
        return subprocess.run(["gh", "run", "watch", run, "--exit-status"], check=False).returncode
    except KeyboardInterrupt:
        # 대기열에 남기면 러너가 뜨는 순간 몰래 돈다.
        gh("run", "cancel", run, check=False)
        print(f"\n실행 {run}을 취소했다")
        return 130


def wanted_labels(root: Path = ROOT) -> set[str]:
    """`gpu-smoke.yml`의 `runs-on`. 라벨을 여기 다시 적지 않는다."""
    text = (root / ".github" / "workflows" / SMOKE).read_text(encoding="utf-8")
    found = re.search(r"runs-on: \[([^\]]+)\]", text)
    if found is None:
        raise RuntimeError(f"{SMOKE}에서 runs-on을 못 읽었다")
    return {name.strip().lower() for name in found.group(1).split(",")}


def usable(runners: list[dict[str, object]], wanted: set[str]) -> list[str]:
    """켜져 있고 라벨을 다 가진 러너의 이름. **비었으면 돌려 봐야 대기열에서 멈춘다.**"""
    picked: list[str] = []
    for runner in runners:
        raw = runner.get("labels")
        names = (
            {str(label.get("name", "")).lower() for label in raw}
            if isinstance(raw, list)
            else set()
        )
        if runner.get("status") == "online" and wanted <= names:
            picked.append(str(runner.get("name")))
    return picked


def smoke() -> int:
    """러너부터 본다. D-0226 첫 판은 라벨 없는 러너에 걸어 대기열에서 멈췄다."""
    runners = json.loads(gh("api", "repos/{owner}/{repo}/actions/runners")).get("runners", [])
    wanted = wanted_labels()
    ready_ones = usable(runners, wanted)
    if not ready_ones:
        seen = [f"{r.get('name')}({r.get('status')})" for r in runners] or ["없음"]
        print(f"라벨 {sorted(wanted)}을 가진 켜진 러너가 없다 — 등록된 러너: {' · '.join(seen)}")
        print("`make runner`가 라벨 · 서비스를 맞춘다")
        return 1
    print(f"러너: {' · '.join(ready_ones)}")
    return dispatch(SMOKE)


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub 쪽 일을 터미널에서 (D-0226)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="브랜치 자동 삭제 · 기획서 배포")
    closing = commands.add_parser("bot", help="봇 PR · 실행 · 실패 로그")
    closing.add_argument("--close", action="store_true", help="열린 봇 PR을 닫는다")
    commands.add_parser("smoke", help="gpu-smoke를 돌린다")
    args = parser.parse_args()

    reason = ready()
    if reason:
        print(reason, file=sys.stderr)
        return 2
    try:
        if args.command == "setup":
            return setup()
        if args.command == "bot":
            return bot(args.close)
        return smoke()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
