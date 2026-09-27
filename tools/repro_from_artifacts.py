#!/usr/bin/env python3
"""산출물에서 «재현» 명령을 되살린다 (D-0251).

### 왜 되살릴 수 있는가

D-0250이 *"산출물이 없으니 명령을 추측해야 한다"*고 적고 74건을 유물로 뒀다. **그것은
과한 말이었다.** 화면에만 찍은 것은 화성 계열 넷이고, `eval retrieval`·`eval fusion`은
**조건을 산출 JSON에 그대로 박아 왔다** (`EvaluationConfig`의 독스트링 그대로:
*"산출 JSON에 그대로 박아 어떤 조건의 수치인지 남긴다"*).

    "config": {"label": ..., "view": {"keys": [...], "combine": "concat", "pool": "mean",
               "chunk_l2": false, "block_l2": false, "centered": true},
               "split": {"mode": "odd-even", "ratio": 0.5, "repeats": 1, "seed": 20240501},
               "k": 10, "seed": ..., "gate": 0.3, "force": false}

이 칸들은 `eval retrieval`의 깃발과 **1:1이다.** 그러므로 명령은 **추측이 아니라 복원**이며
GR-0.5에 걸리지 않는다.

### 어느 산출물이 어느 결정의 근거인가 — 수치로 짝짓는다

이름이나 시각으로 짝지으면 그것이 추측이다. **본문에 적힌 수치가 산출물 안에 있으면 그
산출물이 그 결정의 근거다.** 우연을 막으려고 **소수 셋 이상 일치**를 요구하고, 둘만
맞으면 보고만 하고 쓰지 않는다.

    python3 tools/repro_from_artifacts.py                  # 짝을 찾아 보고한다
    python3 tools/repro_from_artifacts.py --write          # 확실한 짝만 기록에 채운다
    python3 tools/repro_from_artifacts.py --eval-root ...  # 산출물이 교두보에 있을 때

**`--write`는 기록을 고친다.** 패치로 오가는 동안에는 보고만 받고 채우는 것은 패치가
한다 — 여기서 고치면 그 변경이 이 기기에만 있고 **다음 패치가 안 붙는다** (D-0070).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_ROOT = ROOT / "var"
RECORD = re.compile(r"^## (D-\d{4})\.", re.M)
UNKNOWN = "재현 불명"

NUMBER = re.compile(r"(?<![\w.])\d+\.\d{3,}")
"""소수 셋 이상. **정수와 두 자리는 안 본다** — 마디 수·개수·백분율이 우연히 겹친다."""

STRONG = 3
"""이 개수 이상 겹치면 근거로 인정한다. 둘은 보고만 한다."""


def trim(raw: str) -> str | None:
    """끝의 0을 떼고, 소수 셋을 못 채우면 버린다."""
    trimmed = raw.rstrip("0").rstrip(".")
    return trimmed if len(trimmed.partition(".")[2]) >= 3 else None


def numbers(text: str) -> set[str]:
    """글자에 적힌 소수. **기록 쪽은 적힌 그대로 본다.**"""
    return {value for raw in NUMBER.findall(text) if (value := trim(raw))}


def variants(raw: str) -> set[str]:
    """이 수가 **기록에 적힐 수 있는 꼴들** — 3~6자리로 반올림한 값 전부.

    첫 판이 짝을 0건 찾았다. 산출물은 `round(x, 6)`이고 **기록은 반올림해 적는다** —
    `0.917416`을 사람이 «0.9174»라고 쓴다. 문자열이 같아야 짝이라고 하면 하나도 안 맞는다.
    """
    found = {value for value in (trim(raw),) if value}
    try:
        number = float(raw)
    except ValueError:
        return found
    for digits in range(3, 7):
        if (value := trim(f"{number:.{digits}f}")) is not None:
            found.add(value)
    return found


def flatten(value: Any) -> Iterator[str]:
    """JSON 안의 모든 수를 글자로 흘린다."""
    if isinstance(value, dict):
        for item in value.values():
            yield from flatten(item)
    elif isinstance(value, list):
        for item in value:
            yield from flatten(item)
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        yield repr(value)
    elif isinstance(value, str):
        yield value


def command_of(config: dict[str, Any]) -> str:
    """`config`에서 `eval retrieval` 명령을 복원한다. **기본값은 적지 않는다.**"""
    view = config.get("view") or {}
    split = config.get("split") or {}
    parts = ["hathor eval retrieval"]

    keys = view.get("keys") or []
    if list(keys) != ["mixture"]:
        parts.append(f"--keys {','.join(str(key) for key in keys)}")
    for flag, key, default in (
        ("--combine", "combine", "concat"),
        ("--pool", "pool", "mean"),
    ):
        if view.get(key) not in (None, default):
            parts.append(f"{flag} {view[key]}")
    if view.get("chunk_l2"):
        parts.append("--chunk-l2")
    if view.get("block_l2"):
        parts.append("--block-l2")
    if view.get("centered") is False:
        parts.append("--raw")

    if split.get("mode") not in (None, "odd-even"):
        parts.append(f"--split {split['mode']}")
        if split.get("ratio") not in (None, 0.5):
            parts.append(f"--split-ratio {split['ratio']}")
        if split.get("repeats") not in (None, 1):
            parts.append(f"--split-repeats {split['repeats']}")
    if config.get("k") not in (None, 10):
        parts.append(f"--k {config['k']}")
    if config.get("gate") not in (None, 0.3):
        parts.append(f"--gate {config['gate']}")
    label = config.get("label")
    if label and label != "unnamed":
        parts.append(f"--label {label}")
    return " ".join(parts)


class Artifact:
    """산출물 하나. **명령과 수치를 같이 든다.**"""

    def __init__(self, path: Path, record: dict[str, Any]) -> None:
        self.path = path
        self.command = command_of(record.get("config") or {})
        self.numbers = {
            value for raw in NUMBER.findall(" ".join(flatten(record))) for value in variants(raw)
        }


def read_artifacts(root: Path) -> list[Artifact]:
    found: list[Artifact] = []
    for path in sorted(root.rglob("*.eval.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and record.get("config"):
            found.append(Artifact(path, record))
    return found


def unknown_records(text: str) -> list[tuple[str, str]]:
    """«재현 불명»인 결정과 그 본문."""
    parts = RECORD.split(text)
    rows: list[tuple[str, str]] = []
    for index in range(1, len(parts), 2):
        number, body = parts[index], parts[index + 1]
        if any(line.startswith(UNKNOWN) for line in body.splitlines()):
            rows.append((number, body))
    return rows


def match(body: str, artifacts: Iterable[Artifact]) -> list[tuple[int, Artifact]]:
    """본문 수치와 겹치는 산출물을 **겹친 개수가 큰 것부터** 돌려준다."""
    wanted = numbers(body)
    hits = [(len(wanted & art.numbers), art) for art in artifacts]
    return sorted((row for row in hits if row[0] >= 2), key=lambda row: -row[0])


def repro_block(commands: list[str]) -> str:
    """기록에 넣을 «재현» 절. 명령이 여럿이면 다 적는다 — 조건이 여럿이었다는 뜻이다."""
    lines = "\n".join(f"    {command}" for command in commands)
    return f"재현\n{lines}"


def explain(artifacts: list[Artifact], rows: list[tuple[str, str]]) -> None:
    """짝이 하나도 없을 때 **왜 없는지 보여 준다.** 한 번 더 돌리게 하지 않는다."""
    print("\n── 왜 안 맞았나\n")
    print(f"산출물 {len(artifacts)}개:")
    for art in artifacts[:12]:
        sample = sorted(art.numbers)[:4]
        print(f"  {art.path.name}  수치 {len(art.numbers)}개 {sample}")
        print(f"      {art.command}")

    scored = sorted(((len(numbers(body)), number, body) for number, body in rows), reverse=True)
    print("\n수치가 많은 기록:")
    for count, number, body in scored[:6]:
        best = max((len(numbers(body) & art.numbers) for art in artifacts), default=0)
        print(f"  {number}  수치 {count}개 · 최고 교집합 {best} · {sorted(numbers(body))[:4]}")

    print("\n짝이 없는 흔한 이유 셋:")
    print("  1. 산출물이 여기 없다 — 교두보에 있으면 `make artifacts-pull` 또는 --eval-root")
    print("  2. 그 실측이 이 하네스 이전이다 — 옛 조건은 산출물 규격이 달랐다")
    print("  3. 기록이 수치를 표로만 적고 소수 셋을 안 썼다 — 그러면 짝지을 열쇠가 없다")


def report(eval_root: Path, write: bool) -> int:
    decisions = ROOT / "docs" / "DECISIONS.md"
    text = decisions.read_text(encoding="utf-8")
    artifacts = read_artifacts(eval_root)
    if not artifacts:
        print(f"산출물이 없다: {eval_root}", file=sys.stderr)
        print("교두보에 있으면 `--eval-root`로 준다. 가져오려면 `make artifacts-pull`.")
        return 2

    rows = unknown_records(text)
    print(f"산출물 {len(artifacts)}개 · «{UNKNOWN}» {len(rows)}건\n")

    strong: dict[str, list[str]] = {}
    weak = 0
    for number, body in rows:
        hits = match(body, artifacts)
        if not hits:
            continue
        best = hits[0][0]
        if best < STRONG:
            weak += 1
            print(f"{number}  약함 (수치 {best}개 일치) — 안 쓴다")
            continue
        commands: list[str] = []
        for count, art in hits:
            if count == best and art.command not in commands:
                commands.append(art.command)
        strong[number] = commands[:3]
        print(f"{number}  수치 {best}개 일치 · 명령 {len(commands)}개")
        for command in strong[number]:
            print(f"      {command}")

    print(f"\n확실한 짝 {len(strong)}건 · 약한 짝 {weak}건")
    if not strong and not weak:
        explain(artifacts, rows)
    if not write:
        print("채우려면 --write")
        return 0

    for number, commands in strong.items():
        pattern = re.compile(rf"(^## {number}\..*?)(^{UNKNOWN}[^\n]*$)", re.M | re.S)
        block = repro_block(commands)
        text, count = pattern.subn(lambda m: m.group(1) + block, text, count=1)  # noqa: B023
        if count != 1:
            print(f"{number}을 못 고쳤다", file=sys.stderr)
            return 1
    decisions.write_text(text, encoding="utf-8")
    print(f"채웠다 {len(strong)}건 · 남은 «{UNKNOWN}» {len(unknown_records(text))}건")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="산출물에서 재현 명령 복원 (D-0251)")
    parser.add_argument("--eval-root", type=Path, default=DEFAULT_EVAL_ROOT)
    parser.add_argument("--write", action="store_true", help="확실한 짝만 기록에 채운다")
    args = parser.parse_args()
    return report(args.eval_root, args.write)


if __name__ == "__main__":
    raise SystemExit(main())
