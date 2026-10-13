"""`eval musicfm`의 **산출물 설명** (D-0203 · D-0417).

### 왜 이 시험이 지금 생겼나

D-0413이 명령을 세울 때는 **실물로 한 번도 안 돌았다.** 그 상태에서 배치 경로에
시험을 붙이면 가짜 위에 가짜를 세우는 것이고, 실제로 그 사이에 실물이 세 번 떨어졌다
(torchaudio · 받다 만 가중치 · `hidden_states`). **돌고 나서 붙인다.**

### 모델을 안 올리고 잰다

`run()`은 **모델을 적재하기 전에** manifest를 쓴다 — 곡이 하나도 안 남은 재실행에서도
`var_fsck`가 *«정체 불명»*을 면해야 하기 때문이다. 그래서 `--limit 0`이면 1.3GB
가중치 없이 그 자리까지 간다. **가짜가 거의 없다** — 저장소도 잠금도 실물이다.

### 무엇을 지키나

**79분짜리 배치**를 설정을 바꿔 두 번 돌리면 어느 산출물이 무엇인지 사람이 못 가린다.
층과 체크포인트와 커밋이 거기 적혀 있어야 하고, **라이선스는 코드와 가중치를 갈라
적어야 한다** (D-0217 · D-0413).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hathor.infrastructure.artifact_manifest import SUFFIX
from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
from hathor.infrastructure.musicfm_feature_extractor import (
    DEFAULT_CHECKPOINT,
    DEFAULT_MODEL,
    MUSICFM_COMMIT,
    MUSICFM_DIMENSION,
    MUSICFM_SAMPLE_RATE,
)
from hathor.interfaces.cli import eval_musicfm


def _only(root: Path) -> Path:
    """쓰인 설명 한 장. **자리를 손으로 안 적는다** — 저장소가 `features/` 아래로
    한 겹 더 들어가고, 그 자리는 `NpzFeatureStore`의 것이지 이 시험의 것이 아니다."""
    found = sorted(root.rglob(f"*{SUFFIX}"))
    assert len(found) == 1, f"설명이 {len(found)}장이다: {found}"
    return found[0]


def _written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **extra: Any) -> dict[str, Any]:
    """`--limit 0`으로 돌려 manifest만 받는다. **모델은 안 올라간다.**"""
    monkeypatch.setattr(
        JsonlScanStore,
        "read_tracks",
        lambda self: iter([SimpleNamespace(source_key="곡.mp3")]),
    )
    args = argparse.Namespace(
        out=tmp_path,
        features=None,
        limit=0,
        force=True,
        home=None,
        layers="",
        checkpoint=None,
        root=None,
        **extra,
    )

    assert eval_musicfm.run(args, tmp_path) == 0

    return dict(json.loads(_only(tmp_path).read_text(encoding="utf-8")))


def test_모델을_올리기_전에_설명을_쓴다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**곡이 하나도 안 남은 재실행에서도 적힌다** (D-0203).

    가중치 1.3GB 없이 여기까지 온다 — 그 자체가 *«모델보다 먼저»*라는 증거다.
    """
    found = _written(monkeypatch, tmp_path)

    assert found["model"] == DEFAULT_MODEL
    assert found["dimension"] == MUSICFM_DIMENSION
    assert found["sample_rate"] == MUSICFM_SAMPLE_RATE
    assert found["commit"] == MUSICFM_COMMIT


def test_라이선스를_코드와_가중치로_갈라_적는다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**코드 라이선스를 가중치에 넘겨 적으면 그것이 추측이다** (D-0217 · D-0413).

    산출물이 *«MIT»*라고만 말하면 뒤에 읽는 사람이 **제품에 써도 된다고 읽는다.**
    """
    found = _written(monkeypatch, tmp_path)

    assert "가중치 미명시" in found["license"]
    assert found["license"] != "MIT"


def test_어느_판으로_뽑았는지_적는다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**FMA 판과 MSD 판은 학습 데이터가 다르다** (D-0413).

    둘을 섞어 쌓고 나중에 못 가리면 그 산출물은 못 쓴다.
    """
    assert _written(monkeypatch, tmp_path)["checkpoint"] == DEFAULT_CHECKPOINT
    assert DEFAULT_CHECKPOINT.endswith("_fma.pt"), "기본이 FMA 판이 아니다"


def test_고른_층이_설명에_실린다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**79분짜리 배치를 두 번 돌리면 어느 게 뭔지 모른다** (D-0417).

    층은 `--layers`가 정하고 기본은 `mixture` 하나다. 적어 두지 않으면 **산출물을
    열어 키를 세야** 안다.
    """
    monkeypatch.setattr(
        JsonlScanStore,
        "read_tracks",
        lambda self: iter([SimpleNamespace(source_key="곡.mp3")]),
    )
    args = argparse.Namespace(
        out=tmp_path,
        features=None,
        limit=0,
        force=True,
        home=None,
        layers="3,7",
        checkpoint="pretrained_msd.pt",
        root=None,
    )

    assert eval_musicfm.run(args, tmp_path) == 0
    found = json.loads(_only(tmp_path).read_text(encoding="utf-8"))

    assert found["layers"] == [3, 7]
    assert found["checkpoint"] == "pretrained_msd.pt"


def test_스캔_산출물이_없으면_2를_낸다(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """**빈 그물로 배치를 돌리지 않는다** (D-0230). 1004곡을 기다렸는데 0곡이면 늦다."""
    monkeypatch.setattr(JsonlScanStore, "read_tracks", lambda self: iter([]))
    args = argparse.Namespace(
        out=tmp_path,
        features=None,
        limit=None,
        force=True,
        home=None,
        layers="",
        checkpoint=None,
        root=None,
    )

    assert eval_musicfm.run(args, tmp_path) == 2
    assert not (tmp_path / eval_musicfm.DIRNAME).exists(), "설명만 남기고 끝나면 안 된다"
