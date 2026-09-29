"""`eval chord-quality` CLI 통합 테스트 (O-64 · D-0300).

합성 크로마 시계열 `npz`를 깔아 판정 경로를 전부 돌린다. **음원도 GPU도 쓰지 않는다** —
이 명령은 이미 뽑아 둔 시계열만 읽으므로 구닥다리 기기에서 돈다.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hathor.domain.services.harmony_quality import QUALITIES
from hathor.infrastructure.chroma_series_store import load_windows, write_series
from hathor.interfaces.cli.main import main

DEGREES = 12


def plant(
    root: Path,
    *,
    quality: str,
    tracks: int,
    windows: int,
    noise: float,
    seed: int = 20260929,
    stem: str = "other",
) -> None:
    """곡마다 같은 품질의 화음이 창마다 다른 근음으로 실린 시계열."""
    generator = np.random.default_rng(seed)
    for index in range(tracks):
        frame = np.zeros((windows, DEGREES), dtype=np.float32)
        roots = generator.integers(0, DEGREES, windows)
        for window, root_note in enumerate(roots):
            for tone in QUALITIES[quality]:
                frame[window, (root_note + tone) % DEGREES] = 1.0
        frame += generator.random((windows, DEGREES)).astype(np.float32) * noise
        write_series(root, f"곡{index:03d}.flac", stem, frame)


def test_시계열이_없으면_거부한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "없음"
    code = main(
        ["eval", "chord-quality", "--out", str(tmp_path / "산출"), "--series", str(missing)]
    )
    assert code == 2
    assert "ingest keys" in capsys.readouterr().err


def test_창이_없으면_거부한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "keys-000000.series"
    empty.mkdir(parents=True)
    code = main(["eval", "chord-quality", "--out", str(tmp_path / "산출"), "--series", str(empty)])
    assert code == 2
    assert "창이 없다" in capsys.readouterr().err


def test_dom7_코퍼스에서_4음_차가_크게_나온다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """실측과 순열 귀무의 **차**가 나와야 한다. 절대 비율만으로는 판정하지 않는다."""
    series = tmp_path / "keys-000001.series"
    plant(series, quality="dom7", tracks=4, windows=25, noise=0.4)
    out = tmp_path / "산출"
    code = main(["eval", "chord-quality", "--out", str(out), "--series", str(series)])
    assert code == 0
    printed = capsys.readouterr().out
    assert "4곡 100창" in printed
    assert "순열귀무" in printed
    assert "MIR" not in printed  # 이 축에 배수는 없다
    assert "차로만 읽는다" in printed

    # `JsonEvaluationStore`가 `<out>/eval/` 아래에 쓴다 — `eval fusion`과 같은 규약이다.
    written = sorted((out / "eval").glob("*-chord-quality.eval.json"))
    assert len(written) == 1
    record = json.loads(written[0].read_text(encoding="utf-8"))
    assert record["tracks"] == 4
    assert record["windows"] == 100
    assert record["measured"]["dom7"] == pytest.approx(1.0)
    assert record["seventh_gap"] > 0.3
    assert set(record["permuted_null"]) == set(QUALITIES)


def test_꼴이_다른_파일은_건너뛴다(tmp_path: Path) -> None:
    """12열이 아닌 것이 섞이면 `vstack`이 터진다 — 곡 하나가 보고 전체를 죽인다."""
    series = tmp_path / "keys-000002.series"
    plant(series, quality="maj", tracks=2, windows=10, noise=0.2)
    write_series(series, "망가진.flac", "other", np.zeros((3, 7), dtype=np.float32))
    write_series(series, "빈것.flac", "other", np.zeros((0, DEGREES), dtype=np.float32))
    windows, tracks = load_windows(series, "other")
    assert tracks == 2
    assert windows.shape == (20, DEGREES)
