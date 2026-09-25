#!/usr/bin/env python3
"""평가 리포트를 로컬 MLflow로 옮긴다 (D-0224).

### 왜 필요한가

평가 하네스는 실행마다 `var/ingest/eval/*.eval.json`을 **새로** 남긴다 (D-0009). 덮지 않으니
비교는 되지만 **눈으로 파일을 열어 맞대야 한다.** 조건을 바꿔 가며 수십 번 재는 G3 ·
O-68(닫힘 D-0235)이 오면 파일 목록으로는 못 본다. MLflow는 그 목록을 표와 그래프로 보여 준다.

### 정본은 여전히 JSON이다

MLflow는 **보는 창**이다. 지워도 이 도구를 다시 돌리면 같은 것이 선다. 그래서

- 리포트 하나가 실행 하나다. 실행 이름은 파일 이름, 시각은 파일 이름의 시각이다.
- 이미 옮긴 리포트는 건너뛴다 (`hathor.report` 태그). **몇 번 돌려도 같다.**
- 숫자 잎만 지표로, 맨 위 문자열만 파라미터로 옮긴다. 목록(곡별 결과)은 안 옮긴다.

### 기기를 떠나지 않는다

D-0015 · D-0134가 망 접점을 센다. 이 파일은 그 목록에 있고 **로컬 주소만 받는다** —
원격 추적 서버를 주면 거절한다. 보내는 것은 평가 숫자와 라벨이며 오디오는 없다.
**MLflow · Prefect는 기본으로 사용 통계를 밖으로 보낸다** — 부르기 전에 끈다 (`quiet`).

    make up-ml                                   # mlflow · prefect 기동
    make mlflow-sync                             # 옮긴다
    python3 tools/mlflow_sync.py --dry-run       # 무엇을 옮길지 찍기만 한다 (mlflow 불필요)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = "var/ingest/eval"
SUFFIX = ".eval.json"
EXPERIMENT = "hathor-eval"
REPORT_TAG = "hathor.report"
DEFAULT_URI = "http://localhost:5000"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PARAM_LIMIT = 250
STAMP = re.compile(r"^(\d{8}T\d{6}Z)-")
UNSAFE_KEY = re.compile(r"[^0-9A-Za-z_\-. /]+")


@dataclass(frozen=True)
class Report:
    name: str
    started_ms: int
    metrics: dict[str, float]
    params: dict[str, str]


TELEMETRY_OFF = {
    "MLFLOW_DISABLE_TELEMETRY": "true",
    "DO_NOT_TRACK": "true",
    "PREFECT_SERVER_ANALYTICS_ENABLED": "false",
    "MLFLOW_DISABLE_AGENT_HINT": "1",
}
"""**둘 다 기본으로 사용 통계를 밖으로 보낸다.** 로컬 서버를 써도 그렇다 — 끈다 (D-0224)."""


def quiet() -> None:
    """사용 통계를 끈다. 셸에 이미 값이 있으면 덮지 않는다."""
    for key, value in TELEMETRY_OFF.items():
        os.environ.setdefault(key, value)


def is_local(uri: str) -> bool:
    """파일 · sqlite · 로컬 호스트만 참이다. **원격이면 오디오가 아니어도 거절한다.**

    맨 낱말은 경로가 아니다 — mlflow에서 `databricks`는 원격 작업 공간을 뜻한다.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "":
        return "/" in uri or uri.startswith(".")
    if parsed.scheme == "file" or parsed.scheme.startswith("sqlite"):
        return True
    return parsed.scheme in ("http", "https") and (parsed.hostname or "") in LOCAL_HOSTS


def flatten(record: object, prefix: str = "") -> dict[str, float]:
    """숫자 잎을 `a.b.c` 이름으로. 참거짓과 목록은 안 옮긴다."""
    found: dict[str, float] = {}
    if isinstance(record, dict):
        for key, value in record.items():
            name = UNSAFE_KEY.sub("_", str(key))
            found.update(flatten(value, f"{prefix}.{name}" if prefix else name))
    elif isinstance(record, int | float) and not isinstance(record, bool) and prefix:
        found[prefix] = float(record)
    return found


def params(record: object) -> dict[str, str]:
    """맨 위의 문자열만. 길면 자른다 — MLflow 파라미터에는 길이 상한이 있다."""
    if not isinstance(record, dict):
        return {}
    return {
        UNSAFE_KEY.sub("_", str(key)): value[:PARAM_LIMIT]
        for key, value in record.items()
        if isinstance(value, str)
    }


def started(name: str) -> int:
    """파일 이름의 시각(밀리초). 없으면 0 — MLflow가 지금 시각을 쓴다."""
    found = STAMP.match(name)
    if not found:
        return 0
    moment = datetime.strptime(found.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    return int(moment.timestamp() * 1000)


def load(eval_dir: Path) -> list[Report]:
    """리포트 전부를 이름순으로. 깨진 JSON은 조용히 넘기지 않고 멈춘다."""
    reports: list[Report] = []
    for path in sorted(eval_dir.glob(f"*{SUFFIX}")):
        record = json.loads(path.read_text(encoding="utf-8"))
        name = path.name.removesuffix(SUFFIX)
        reports.append(Report(name, started(path.name), flatten(record), params(record)))
    return reports


def sync(reports: list[Report], uri: str) -> tuple[int, int]:
    """(옮긴 수, 건너뛴 수). mlflow는 여기서만 부른다 — 없어도 나머지는 돈다."""
    quiet()
    from mlflow.entities import Metric, Param, RunTag
    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=uri)
    found = client.get_experiment_by_name(EXPERIMENT)
    experiment = found.experiment_id if found else client.create_experiment(EXPERIMENT)
    done = {
        run.data.tags.get(REPORT_TAG) for run in client.search_runs([experiment], max_results=50000)
    }
    logged = 0
    for report in reports:
        if report.name in done:
            continue
        run = client.create_run(
            experiment,
            start_time=report.started_ms or None,
            tags={REPORT_TAG: report.name},
            run_name=report.name,
        )
        stamp = report.started_ms or int(datetime.now(UTC).timestamp() * 1000)
        client.log_batch(
            run.info.run_id,
            metrics=[Metric(key, value, stamp, 0) for key, value in report.metrics.items()],
            params=[Param(key, value) for key, value in report.params.items()],
            tags=[RunTag("hathor.source", EVAL_DIR)],
        )
        client.set_terminated(run.info.run_id, end_time=stamp)
        logged += 1
    return logged, len(reports) - logged


def main() -> int:
    parser = argparse.ArgumentParser(description="평가 리포트 → 로컬 MLflow (D-0224)")
    parser.add_argument("--eval-dir", type=Path, default=ROOT / EVAL_DIR)
    parser.add_argument("--uri", default=os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_URI))
    parser.add_argument("--dry-run", action="store_true", help="옮길 것을 찍기만 한다")
    args = parser.parse_args()

    if not is_local(args.uri):
        print(f"원격 추적 서버 {args.uri}는 받지 않는다 — 로컬만 (D-0224)", file=sys.stderr)
        return 1
    reports = load(args.eval_dir)
    if not reports:
        print(f"리포트가 없다: {args.eval_dir}. `hathor eval ...`이 먼저다")
        return 0
    if args.dry_run:
        for report in reports:
            print(f"  {report.name}  지표 {len(report.metrics)} · 파라미터 {len(report.params)}")
        print(f"리포트 {len(reports)}개 → {args.uri} (옮기지 않았다)")
        return 0
    try:
        logged, skipped = sync(reports, args.uri)
    except ImportError:
        print(
            "mlflow가 없다. `make sync`",
            file=sys.stderr,
        )
        return 2
    print(f"MLflow {args.uri} · 실험 {EXPERIMENT} · 옮김 {logged} · 이미 있음 {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
