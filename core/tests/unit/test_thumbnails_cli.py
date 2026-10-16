"""`hathor ingest thumbnails` 배선 (D-0430).

**시계열 폴더를 손으로 깔고 돈다.** 오디오는 안 쓴다 — 이 명령이 읽는 것은
`chroma_series`뿐이고, 그것이 «새로 뽑는 것이 없다»는 이 판의 전제다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hathor.infrastructure import artifact_manifest
from hathor.infrastructure.chroma_series_store import write_series
from hathor.interfaces.cli.main import main

RNG = np.random.default_rng(430)
SPAN = 2.0


def _series(*, length: int, motif: int, at: tuple[int, ...]) -> np.ndarray:
    frames = RNG.random((length, 12))
    block = RNG.random((motif, 12))
    for start in at:
        frames[start : start + motif] = block
    return frames


def _folder(root: Path, *, songs: int = 3, declare: bool = True) -> Path:
    series = root / "keys-20260101T000000Z.series"
    series.mkdir(parents=True, exist_ok=True)
    for index in range(songs):
        write_series(series, f"곡{index}.mp3", "other", _series(length=120, motif=12, at=(20, 80)))
    if declare:
        (series / f"{series.name}{artifact_manifest.SUFFIX}").write_text(
            json.dumps({"series_seconds": SPAN, "stem_set": "other"}), encoding="utf-8"
        )
    return series


def _rows(path: Path) -> list[dict[str, float]]:
    """줄을 읽어 수만 돌려준다 — `source_key`는 이 검사에서 안 본다."""
    found: list[dict[str, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        found.append({key: float(value) for key, value in row.items() if key != "source_key"})
    return found


# ------------------------------------------------------------------ 도는가


def test_곡마다_한_줄을_적는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**창 번호가 아니라 초로 적는다** — 사람이 그 자리를 들어 볼 수 있어야 한다."""
    series = _folder(tmp_path)
    out = tmp_path / "thumbs.jsonl"

    code = main(
        [
            "ingest",
            "thumbnails",
            "--series",
            str(series),
            "--seconds",
            "24",
            "--out",
            str(out),
        ]
    )

    assert code == 0
    rows = _rows(out)
    assert len(rows) == 3
    assert rows[0]["start_sec"] == pytest.approx(20 * SPAN), "심어 둔 무늬 자리가 아니다"
    assert rows[0]["end_sec"] == pytest.approx(32 * SPAN)
    assert rows[0]["repeat_sec"] == pytest.approx(80 * SPAN), "짝이 어디인지 안 적었다"
    assert rows[0]["score"] > 0.99
    assert "곡 3" in capsys.readouterr().out


def test_점수가_낮은_쪽부터_찍는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**맞는 것을 백 번 봐도 새로 아는 것이 없다.** 사람 시간은 낮은 점수에 쓴다."""
    series = _folder(tmp_path, songs=0)
    write_series(series, "또렷.mp3", "other", _series(length=120, motif=12, at=(20, 80)))
    write_series(series, "흐릿.mp3", "other", RNG.random((120, 12)))
    (series / f"{series.name}{artifact_manifest.SUFFIX}").write_text(
        json.dumps({"series_seconds": SPAN}), encoding="utf-8"
    )

    assert main(["ingest", "thumbnails", "--series", str(series), "--sample", "1"]) == 0
    listed = capsys.readouterr().out

    assert "흐릿.mp3" in listed
    assert "또렷.mp3" not in listed.split("들어 본다")[-1], "점수 높은 곡을 먼저 들으라 한다"


# ------------------------------------------------------------------ 못 재면 죽는다


def test_창_길이_선언이_없으면_죽는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**창 번호를 초로 옮기는 셈이 통째로 틀린다** (GR-0.5).

    틀린 초를 사람이 들어 보면 **도구가 아니라 논문이 틀렸다고 읽는다** (D-0292).
    """
    series = _folder(tmp_path, declare=False)

    assert main(["ingest", "thumbnails", "--series", str(series)]) == 1
    assert "series_seconds" in capsys.readouterr().err


def test_없는_폴더를_주면_죽는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """D-0429와 같은 선 — 내가 적은 경로가 없으면 오타다."""
    assert main(["ingest", "thumbnails", "--series", str(tmp_path / "없다")]) == 1
    assert "--series" in capsys.readouterr().err


def test_한_곡도_못_고르면_죽는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**빈 jsonl을 적고 0으로 끝내면 «후렴이 없는 라이브러리»가 된다** (D-0230)."""
    series = _folder(tmp_path, songs=0)
    write_series(series, "짧다.mp3", "other", RNG.random((8, 12)))
    (series / f"{series.name}{artifact_manifest.SUFFIX}").write_text(
        json.dumps({"series_seconds": SPAN}), encoding="utf-8"
    )

    assert main(["ingest", "thumbnails", "--series", str(series), "--seconds", "24"]) == 1
    assert "못 골랐다" in capsys.readouterr().err
