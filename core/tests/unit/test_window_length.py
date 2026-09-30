"""창 길이 대조 — 실물 두 폴더를 맞대는 판정 (D-0104 · D-0320).

**뽑기와 판정을 갈라 두는 자리다.** D-0319가 `ingest keys --series 2`를 「닫힌다」의
자리에 적었고 그 명령은 자료만 낸다 — 돌려도 D-0104는 그대로 열려 있었다.

### 0곡을 통과로 읽으면 안 된다

두 폴더가 다른 스템으로 뽑혔으면 짝이 0이고 **거리 목록이 빈다.** 빈 목록의 최대값을
0으로 내면 «전제가 선다»로 읽힌다 — 그래서 `None`이고, **왜 0인지도 화면에 적는다.**
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hathor.application.evaluate_window_length import (
    PRODUCTION_CEILING,
    WindowMatch,
    compare,
    pairs,
    stems,
    sweep,
)
from hathor.infrastructure.chroma_series_store import write_series
from hathor.interfaces.cli.eval_window import empty_notice, factor_of, window_seconds
from hathor.interfaces.cli.main import main

DEGREES = 12


def plant(root: Path, names: list[str], *, stem: str, windows: int, seed: int) -> None:
    """곡별 시계열을 깐다. **창 수만 다르고 곡 이름이 같으면 짝이 된다.**"""
    generator = np.random.default_rng(seed)
    for index, name in enumerate(names):
        frame = generator.random((windows, DEGREES)).astype(np.float32)
        frame /= frame.sum(axis=1, keepdims=True)
        write_series(root, name, stem, frame)
        del index


def grouped_pair(root_short: Path, root_long: Path, names: list[str], *, stem: str) -> None:
    """긴 창을 **짧은 창을 묶어서** 만든다 — 거리가 정확히 0이어야 한다."""
    from hathor.domain.services.key_estimation import group_series

    generator = np.random.default_rng(5)
    for name in names:
        short = generator.random((8, DEGREES)).astype(np.float32)
        short /= short.sum(axis=1, keepdims=True)
        write_series(root_short, name, stem, short)
        write_series(root_long, name, stem, group_series(short, 2))


def test_묶어서_만든_긴_창은_거리가_0이다(tmp_path: Path) -> None:
    """**자가 무엇을 재는지 고정한다.** 0이 안 나오면 대조 자체가 틀린 것이다."""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    grouped_pair(short, long, ["가.flac", "나.flac"], stem="other")
    found = compare(short, long, "other", 2)
    assert found.songs == 2
    assert found.max_gap == pytest.approx(0.0, abs=1e-6)
    assert found.holds is True


def test_다른_자료면_거리가_선다(tmp_path: Path) -> None:
    """**늘 0을 내는 자는 0을 내도 뜻이 없다** (D-0071 · O-25 (1))."""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    plant(short, ["가.flac"], stem="other", windows=8, seed=1)
    plant(long, ["가.flac"], stem="other", windows=4, seed=99)
    found = compare(short, long, "other", 2)
    assert found.songs == 1
    assert found.max_gap is not None
    assert found.max_gap > PRODUCTION_CEILING
    assert found.holds is False


def test_짝이_없으면_0이_아니라_없음이다(tmp_path: Path) -> None:
    """**빈 목록의 최대값을 0으로 내면 통과로 읽힌다** (GR-0.5)."""
    empty = WindowMatch(stem="other", factor=2, gaps=(), short_windows=0, long_windows=0)
    assert empty.songs == 0
    assert empty.median_gap is None
    assert empty.max_gap is None
    assert empty.holds is None


def test_겹치는_스템만_잰다(tmp_path: Path) -> None:
    """**분리 여부가 다르면 스템이 안 겹친다** — 실제로 그렇게 났다 (D-0320)."""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    plant(short, ["가.flac"], stem="other", windows=8, seed=1)
    plant(long, ["가.flac"], stem="mix", windows=4, seed=1)
    assert stems(short) == ("other",)
    assert stems(long) == ("mix",)
    assert sweep(short, long, 2) == ()
    assert pairs(short, long, "other") == []


def test_왜_0인지_화면에_적는다(tmp_path: Path) -> None:
    """**«0곡»만 찍으면 사람이 자기가 뭘 잘못했는지 찾기 시작한다** (D-0292와 같은 자리)."""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    plant(short, ["가.flac"], stem="other", windows=8, seed=1)
    plant(long, ["가.flac"], stem="mix", windows=4, seed=1)
    said = "\n".join(empty_notice(short, long))
    assert "겹치는 스템이 없다" in said
    assert "--separate" in said

    plant(long, ["나.flac"], stem="other", windows=4, seed=1)
    said = "\n".join(empty_notice(short, long))
    assert "곡이 안 겹친다" in said
    assert "--limit" in said


def test_배수를_짐작하지_않는다(tmp_path: Path) -> None:
    """**선언이 없으면 `None`이다.** 1로 두면 조용히 «같은 창»을 재게 된다."""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    short.mkdir()
    long.mkdir()
    assert window_seconds(short) is None
    assert factor_of(short, long, None) is None
    assert factor_of(short, long, 2) == 2
    assert factor_of(short, long, 0) is None


def test_폴더가_없으면_거부한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["eval", "window-length", "--short", str(tmp_path / "없음"), "--long", str(tmp_path)]
    )
    assert code == 2
    assert "시계열 폴더가 없다" in capsys.readouterr().err


def test_짝이_0이면_비정상_종료한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**못 쟀는데 0으로 끝나면 자동화가 통과로 읽는다.**"""
    short, long = tmp_path / "짧은", tmp_path / "긴"
    plant(short, ["가.flac"], stem="other", windows=8, seed=1)
    plant(long, ["가.flac"], stem="mix", windows=4, seed=1)
    code = main(
        ["eval", "window-length", "--short", str(short), "--long", str(long), "--factor", "2"]
    )
    assert code == 2
    printed = capsys.readouterr().out
    assert "못 쟀다" in printed
    assert "겹치는 스템이 없다" in printed


def test_보고가_표와_판정을_찍는다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    short, long = tmp_path / "짧은", tmp_path / "긴"
    grouped_pair(short, long, ["가.flac", "나.flac", "다.flac"], stem="other")
    out = tmp_path / "산출"
    code = main(
        [
            "eval",
            "window-length",
            "--out",
            str(out),
            "--short",
            str(short),
            "--long",
            str(long),
            "--factor",
            "2",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "창 길이 대조" in printed
    assert "창 길이는 분석 인자다" in printed
    assert "최대를 든다" in printed

    record = json.loads(next((out / "eval").glob("*-window-length.eval.json")).read_text("utf-8"))
    assert record["songs"] == 3
    assert record["factor"] == 2
    assert record["stems"][0]["holds"] is True


# ------------------------------------------- 폴더를 스스로 고른다 (D-0321)


def _folder(root: Path, stamp: str, *, seconds: float, stem: str, names: list[str]) -> Path:
    """`var/ingest/keys-<stamp>.series`를 깔고 선언까지 쓴다."""
    from hathor.infrastructure import artifact_manifest

    folder = root / "var" / "ingest" / f"keys-{stamp}.series"
    plant(folder, names, stem=stem, windows=8, seed=1)
    artifact_manifest.write(
        folder,
        folder.name,
        {"what": "시험용", "window_seconds": seconds, "stems": [stem]},
    )
    return folder


def test_폴더를_스스로_고른다(tmp_path: Path) -> None:
    """**복사해 붙일 수 없는 명령은 안내가 아니다** (D-0321).

    폴더 이름이 실행 시각이라 미리 알 수 없다 — D-0320이 안내에 빈칸을 남겼다.
    """
    from hathor.interfaces.cli.eval_window import pick_pair

    names = ["가.flac", "나.flac"]
    short = _folder(tmp_path, "20260101T000000Z", seconds=1.0, stem="other", names=names)
    long = _folder(tmp_path, "20260102T000000Z", seconds=2.0, stem="other", names=names)
    picked = pick_pair(tmp_path)
    assert picked is not None
    assert picked == (short, long, 2)


def test_스템이_안_겹치면_안_고른다(tmp_path: Path) -> None:
    """**분리 여부가 다르면 짝이 0이다** (D-0320). 고르고 나서 0을 내면 안 된다."""
    from hathor.interfaces.cli.eval_window import pick_pair

    _folder(tmp_path, "20260101T000000Z", seconds=1.0, stem="other", names=["가.flac"])
    _folder(tmp_path, "20260102T000000Z", seconds=2.0, stem="mix", names=["가.flac"])
    assert pick_pair(tmp_path) is None


def test_정수배가_아니면_안_고른다(tmp_path: Path) -> None:
    """`group_series`가 정수배만 만든다. **1.5배를 2로 반올림하면 다른 것을 잰다.**"""
    from hathor.interfaces.cli.eval_window import pick_pair

    _folder(tmp_path, "20260101T000000Z", seconds=1.0, stem="other", names=["가.flac"])
    _folder(tmp_path, "20260102T000000Z", seconds=1.5, stem="other", names=["가.flac"])
    assert pick_pair(tmp_path) is None


def test_못_고르면_폴더_목록을_낸다(tmp_path: Path) -> None:
    """**«없다»만 찍으면 사람이 자기가 뭘 잘못했는지 찾기 시작한다** (D-0292)."""
    from hathor.interfaces.cli.eval_window import folder_lines

    assert "`keys-*.series`가 없다" in "\n".join(folder_lines(tmp_path))
    _folder(tmp_path, "20260101T000000Z", seconds=1.0, stem="other", names=["가.flac"])
    said = "\n".join(folder_lines(tmp_path))
    assert "keys-20260101T000000Z.series" in said
    assert "1초" in said and "other" in said
    assert "--separate" in said


def test_형제_jsonl의_이름도_읽는다(tmp_path: Path) -> None:
    """**선언 파일은 `window_seconds`, 형제 `jsonl`은 `series_seconds`다** (D-0073 · D-0305).

    하나만 보면 D-0295 이전에 뽑은 폴더가 전부 «선언 없음»이 된다.
    """
    from hathor.interfaces.cli.eval_window import window_seconds

    folder = tmp_path / "var" / "ingest" / "keys-20260101T000000Z.series"
    plant(folder, ["가.flac"], stem="other", windows=4, seed=1)
    sibling = folder.with_suffix(".keys.jsonl")
    sibling.write_text(json.dumps({"series_seconds": 1.0}) + "\n", encoding="utf-8")
    assert window_seconds(folder) == 1.0


def test_인자를_안_줘도_돌아간다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**이것이 D-0321의 요점이다.** 이름을 몰라도 돌아간다."""
    import hathor.shared.config.paths as paths

    names = ["가.flac", "나.flac", "다.flac"]
    short = _folder(tmp_path, "20260101T000000Z", seconds=1.0, stem="other", names=names)
    long = tmp_path / "var" / "ingest" / "keys-20260102T000000Z.series"
    from hathor.domain.services.key_estimation import group_series
    from hathor.infrastructure import artifact_manifest
    from hathor.infrastructure.chroma_series_store import series_path, write_series

    for name in names:
        with np.load(series_path(short, name, "other"), allow_pickle=False) as bundle:
            frame = np.asarray(bundle["series"], dtype=np.float32)
        write_series(long, name, "other", group_series(frame, 2))
    artifact_manifest.write(
        long, long.name, {"what": "시험용", "window_seconds": 2.0, "stems": ["other"]}
    )

    original = paths.repo_root
    paths.repo_root = lambda: tmp_path  # type: ignore[assignment]
    try:
        code = main(["eval", "window-length", "--out", str(tmp_path / "산출")])
    finally:
        paths.repo_root = original  # type: ignore[assignment]
    assert code == 0
    printed = capsys.readouterr().out
    assert "골랐다" in printed
    assert "창 길이는 분석 인자다" in printed
