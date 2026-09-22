#!/usr/bin/env python3
"""인제스트 → 평가 → MLflow를 한 흐름으로 (D-0224).

### 왜 필요한가

인제스트는 곡 1,000여 개를 GPU로 수십 분 돈다. 지금은 `make`를 손으로 차례로 치고, 중간에
죽으면 **어디서 죽었는지 로그를 뒤져야 한다.** Prefect는 단계마다 상태 · 시간 · 재시도를 남기고
화면(`localhost:4200`)으로 보여 준다. 장비가 바뀌면 이 흐름이 새 기기에서 첫 인제스트를 돈다.

### 새 논리를 넣지 않는다

단계는 **이미 있는 CLI를 부르기만 한다.** 흐름이 인제스트를 다시 구현하면 두 벌이 된다.
Prefect를 빼도 `--plan`이 찍는 명령을 손으로 치면 같은 결과다.

| 단계 | 명령 | 장비 |
|---|---|---|
| scan | `hathor ingest scan` | CPU |
| all | `hathor ingest all` | GPU — `--skip-gpu`로 뺀다 |
| retrieval | `hathor eval retrieval` | CPU |
| mlflow | `tools/mlflow_sync.py` | — |

### 기기를 떠나지 않는다

Prefect API 주소가 비어 있으면 임시 로컬 서버를 쓰고, 있으면 **로컬 주소만 받는다** (D-0134).
보내는 것은 단계 이름 · 상태 · 로그이며 오디오는 없다.

    python3 tools/prefect_flow.py --plan                 # 명령만 찍는다 (prefect 불필요)
    make flow LIMIT=20                                   # 20곡으로 흐름을 돈다
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import mlflow_sync

ROOT = Path(__file__).resolve().parent.parent
CLI = ("uv", "run", "--no-sync", "python", "-m", "hathor.cli")
FLOW_NAME = "hathor-ingest-eval"


@dataclass(frozen=True)
class Step:
    name: str
    argv: tuple[str, ...]
    gpu: bool
    limited: bool


STEPS: tuple[Step, ...] = (
    Step("scan", ("ingest", "scan"), gpu=False, limited=False),
    Step("all", ("ingest", "all"), gpu=True, limited=True),
    Step("retrieval", ("eval", "retrieval"), gpu=False, limited=False),
)
"""**CLI에 없는 명령을 여기 적으면 시험이 빨개진다** — 흐름이 CLI를 앞질러 가지 않는다."""


def commands(limit: int | None, skip_gpu: bool) -> list[tuple[str, list[str]]]:
    """(단계, 명령). `core/`에서 돈다."""
    picked: list[tuple[str, list[str]]] = []
    for step in STEPS:
        if step.gpu and skip_gpu:
            continue
        extra = ["--limit", str(limit)] if (limit is not None and step.limited) else []
        picked.append((step.name, [*CLI, *step.argv, *extra]))
    return picked


def api_is_local(url: str | None) -> bool:
    """비었으면 임시 로컬 서버다. 있으면 로컬 주소여야 한다."""
    return not url or mlflow_sync.is_local(url)


def run(argv: list[str]) -> None:
    subprocess.run(argv, cwd=ROOT / "core", check=True)


def build(limit: int | None, skip_gpu: bool, uri: str) -> object:
    """Prefect 흐름을 만든다. prefect는 여기서만 부른다 — 사용 통계를 끈 뒤에."""
    mlflow_sync.quiet()
    from prefect import flow, task

    @task(retries=1, retry_delay_seconds=30)
    def step(name: str, argv: list[str]) -> str:
        run(argv)
        return name

    @task
    def mirror() -> tuple[int, int]:
        return mlflow_sync.sync(mlflow_sync.load(ROOT / mlflow_sync.EVAL_DIR), uri)

    @flow(name=FLOW_NAME, log_prints=True)
    def pipeline() -> tuple[int, int]:
        for name, argv in commands(limit, skip_gpu):
            step.with_options(name=name)(name, argv)
        return mirror()

    return pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="인제스트 → 평가 → MLflow 흐름 (D-0224)")
    parser.add_argument("--plan", action="store_true", help="명령만 찍는다")
    parser.add_argument("--limit", type=int, default=None, help="곡 수 상한 (시험용)")
    parser.add_argument("--skip-gpu", action="store_true", help="GPU 단계를 뺀다")
    parser.add_argument(
        "--mlflow", default=os.environ.get("MLFLOW_TRACKING_URI", mlflow_sync.DEFAULT_URI)
    )
    args = parser.parse_args()

    if args.plan:
        for name, argv in commands(args.limit, args.skip_gpu):
            print(f"  {name:<10} (core/) {' '.join(argv)}")
        print(f"  {'mlflow':<10} tools/mlflow_sync.py → {args.mlflow}")
        return 0
    api = os.environ.get("PREFECT_API_URL")
    if not api_is_local(api) or not mlflow_sync.is_local(args.mlflow):
        print("원격 Prefect · MLflow 주소는 받지 않는다 — 로컬만 (D-0224)", file=sys.stderr)
        return 1
    try:
        pipeline = build(args.limit, args.skip_gpu, args.mlflow)
    except ImportError:
        print(
            "prefect가 없다. `cd core && uv sync --all-extras --dev --group mlops`",
            file=sys.stderr,
        )
        return 2
    logged, skipped = pipeline()  # type: ignore[operator]
    print(f"흐름 끝 · MLflow 옮김 {logged} · 이미 있음 {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
