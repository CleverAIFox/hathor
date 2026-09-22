"""MLflow · Prefect · GPU 스모크 (D-0224).

mlflow · prefect는 CI에 없다 — 검사와 시험은 그것 없이 돈다. 그래서 **둘을 부르기 전의
판단**(무엇을 옮기나 · 어디로 보내나 · 무슨 명령을 치나)을 여기서 고정하고, 서버에 붙는
자리는 가짜 클라이언트로 재실행 동작만 본다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import gpu_smoke  # noqa: E402
import mlflow_sync  # noqa: E402
import prefect_flow  # noqa: E402

from hathor.interfaces.cli.main import build_parser  # noqa: E402

# ------------------------------------------------------------------ 무엇을 옮기나


def test_숫자_잎만_지표가_된다() -> None:
    record = {
        "n": 3,
        "ok": True,
        "M1": {"p@10": 0.4, "random": 0.05},
        "per_track": [1, 2],
        "label": "x",
    }
    assert mlflow_sync.flatten(record) == {"n": 3.0, "M1.p_10": 0.4, "M1.random": 0.05}


def test_맨_위_문자열만_파라미터가_되고_길면_자른다() -> None:
    record = {"label": "a" * 400, "nested": {"note": "안 간다"}, "n": 1}
    found = mlflow_sync.params(record)
    assert list(found) == ["label"]
    assert len(found["label"]) == mlflow_sync.PARAM_LIMIT


def test_실행_시각은_파일_이름에서_온다() -> None:
    assert mlflow_sync.started("20260101T000000Z-m1.eval.json") == 1767225600000
    assert mlflow_sync.started("손으로-만든.eval.json") == 0


def test_리포트를_이름순으로_읽는다(tmp_path: Path) -> None:
    for name in ("20260102T000000Z-b", "20260101T000000Z-a"):
        (tmp_path / f"{name}.eval.json").write_text(json.dumps({"m": 1}), encoding="utf-8")
    (tmp_path / "other.json").write_text("{}", encoding="utf-8")
    assert [r.name for r in mlflow_sync.load(tmp_path)] == [
        "20260101T000000Z-a",
        "20260102T000000Z-b",
    ]


# ------------------------------------------------------------------ 어디로 보내나


@pytest.mark.parametrize(
    ("uri", "local"),
    [
        ("http://localhost:5000", True),
        ("http://127.0.0.1:5055", True),
        ("sqlite:///var/mlflow.db", True),
        ("file:///tmp/mlruns", True),
        ("var/mlruns", True),
        ("https://mlflow.example.com", False),
        ("http://192.168.0.10:5000", False),
        ("databricks", False),
        ("databricks://profile", False),
    ],
)
def test_로컬_주소만_받는다(uri: str, local: bool) -> None:
    """**D-0224의 강제자 하나.** 원격 추적 서버가 망 접점 넷째를 밖으로 만든다."""
    assert mlflow_sync.is_local(uri) is local


def test_원격이면_아무것도_안_하고_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["mlflow_sync", "--uri", "https://example.com"])
    assert mlflow_sync.main() == 1


def test_사용_통계를_끈다(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in mlflow_sync.TELEMETRY_OFF:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    mlflow_sync.quiet()
    import os

    assert os.environ["MLFLOW_DISABLE_TELEMETRY"] == "true"
    assert os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] == "false"
    assert os.environ["DO_NOT_TRACK"] == "1"


def test_Prefect_주소는_비었거나_로컬이어야_한다() -> None:
    assert prefect_flow.api_is_local(None)
    assert prefect_flow.api_is_local("http://localhost:4200/api")
    assert not prefect_flow.api_is_local("https://api.prefect.cloud/api/accounts/x")


# ------------------------------------------------------------------ 몇 번 돌려도 같다


class _FakeClient:
    runs: ClassVar[list[SimpleNamespace]] = []

    def __init__(self, tracking_uri: str) -> None:
        self.uri = tracking_uri

    def get_experiment_by_name(self, name: str) -> SimpleNamespace | None:
        return SimpleNamespace(experiment_id="1") if self.runs else None

    def create_experiment(self, name: str) -> str:
        return "1"

    def search_runs(self, ids: list[str], max_results: int) -> list[SimpleNamespace]:
        return list(self.runs)

    def create_run(
        self, experiment: str, start_time: int | None, tags: dict[str, str], run_name: str
    ) -> SimpleNamespace:
        run = SimpleNamespace(
            info=SimpleNamespace(run_id=run_name), data=SimpleNamespace(tags=tags)
        )
        self.runs.append(run)
        return run

    def log_batch(
        self, run_id: str, metrics: list[object], params: list[object], tags: list[object]
    ) -> None:
        assert metrics

    def set_terminated(self, run_id: str, end_time: int) -> None:
        pass


def test_이미_옮긴_리포트는_건너뛴다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entities = ModuleType("mlflow.entities")
    tracking = ModuleType("mlflow.tracking")
    for name in ("Metric", "Param", "RunTag"):
        setattr(entities, name, lambda *args: args)
    tracking.MlflowClient = _FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlflow", ModuleType("mlflow"))
    monkeypatch.setitem(sys.modules, "mlflow.entities", entities)
    monkeypatch.setitem(sys.modules, "mlflow.tracking", tracking)
    monkeypatch.setattr(_FakeClient, "runs", [])

    (tmp_path / "20260101T000000Z-a.eval.json").write_text('{"m": 0.4}', encoding="utf-8")
    reports = mlflow_sync.load(tmp_path)
    assert mlflow_sync.sync(reports, "http://localhost:5000") == (1, 0)
    assert mlflow_sync.sync(reports, "http://localhost:5000") == (0, 1)


# ------------------------------------------------------------------ 흐름


def test_흐름은_CLI에_있는_명령만_부른다() -> None:
    """흐름이 CLI를 앞질러 가면 새 기기의 첫 인제스트가 중간에서 죽는다."""
    parser = build_parser()
    for _, argv in prefect_flow.commands(limit=3, skip_gpu=False):
        assert argv[: len(prefect_flow.CLI)] == list(prefect_flow.CLI)
        parser.parse_args(argv[len(prefect_flow.CLI) :])


def test_GPU_단계를_빼고_곡_수는_GPU_단계에만_건다() -> None:
    names = [name for name, _ in prefect_flow.commands(limit=None, skip_gpu=True)]
    assert names == ["scan", "retrieval"]
    limited = {name: argv for name, argv in prefect_flow.commands(limit=5, skip_gpu=False)}
    assert limited["all"][-2:] == ["--limit", "5"]
    assert "--limit" not in limited["scan"]


# ------------------------------------------------------------------ GPU 스모크


def test_재개_조건은_PLAN에서_읽는다() -> None:
    assert gpu_smoke.required_vram() == 16


def test_1660Ti는_재개_조건을_못_넘는다() -> None:
    """G0이 떨어진 기기의 실측 — 6GB · bf16 없음 (D-0218)."""
    short = gpu_smoke.verdict(5.8, bf16=False, fp16_finite=True, required=16)
    assert len(short) == 2
    assert gpu_smoke.verdict(24.0, bf16=True, fp16_finite=True, required=16) == []
