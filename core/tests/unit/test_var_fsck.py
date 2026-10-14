"""산출물 정체·실행 묶기 검사 (D-0209)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module

CHECKER = tool_module("var_fsck")


def _touch(root: Path, *names: str) -> list[Path]:
    made = []
    for name in names:
        path = root / name
        path.write_text("", encoding="utf-8")
        made.append(path)
    return made


def test_한_실행이_낸_파일_셋을_한_묶음으로_센다(tmp_path: Path) -> None:
    """**정상을 잔해로 부르면 진짜 잔해가 가려진다** (D-0209).

    `ingest scan`은 한 번 돌면 `.jsonl` · `.failures.jsonl` · `.summary.json`
    **셋**을 낸다. 접두사만 세면 «여럿»으로 찍히고, 그 경고가 매번 뜨면 사람이
    읽기를 그만둔다.
    """
    files = _touch(
        tmp_path,
        "scan-20260915T133016Z.jsonl",
        "scan-20260915T133016Z.failures.jsonl",
        "scan-20260915T133016Z.summary.json",
    )

    sizes = CHECKER.runs(files)["scan"]

    assert set(sizes) == {"20260915T133016Z"}


def test_옛_실행이_남으면_잡는다(tmp_path: Path) -> None:
    """시각이 둘 이상일 때가 진짜 잔해다."""
    files = _touch(
        tmp_path,
        "scan-20260915T133016Z.jsonl",
        "scan-20260901T010101Z.jsonl",
    )

    sizes = CHECKER.runs(files)["scan"]

    assert len(sizes) == 2


def test_시각이_없는_파일은_한_실행으로_센다(tmp_path: Path) -> None:
    """`all.log`처럼 이름에 시각이 없는 것은 경고 대상이 아니다."""
    files = _touch(tmp_path, "all.log")

    sizes = CHECKER.runs(files)["all"]

    assert set(sizes) == {""}


def test_한_단계_아래_manifest도_읽는다(tmp_path: Path) -> None:
    """**D-0244의 강제자.** `NpzFeatureStore`는 `<루트>/features/`에 쓴다.

    D-0233이 `eval clap`에 manifest를 달았는데 `var_fsck`는 여전히 «정체 불명»이라 찍었다 —
    쓰는 자리와 찾는 자리가 한 단계 달랐고 **아무도 그 초록을 확인하지 않았다.**
    """
    store = tmp_path / "clap" / "features"
    store.mkdir(parents=True)
    (store / "clap.manifest.json").write_text(
        '{"model": "laion/larger_clap_music", "layers": [], "dtype": "float32", "revision": "abc"}',
        encoding="utf-8",
    )

    said = CHECKER.describe(tmp_path / "clap")

    assert "manifest 1건" in said and "manifest 없음" not in said
    assert "float32" in said and "abc" in said


def test_옛_실행이_남으면_관문이_막는다(tmp_path: Path) -> None:
    """**D-0245의 강제자.** 알리기만 하는 경고는 다음 주에도 그대로 있다.

    실측으로 `keys` 13회 · `scan` 4회가 교두보에 쌓여 있었다 — O-62(닫힘 D-0245)가 말한 그것이다.
    """
    _touch(tmp_path, "keys-20260101T000000Z.jsonl", "keys-20260202T000000Z.jsonl")

    assert CHECKER.report(tmp_path) == 0, "찍기만 할 때는 막지 않는다"
    assert CHECKER.report(tmp_path, ratchet=True) == 1


def test_정체_불명은_관문이_아니다(tmp_path: Path) -> None:
    """D-0203 이전 산출물이다. **다시 뽑는 것 말고 길이 없으니** 관문으로 두면 영원히 빨갛다."""
    (tmp_path / "옛묶음").mkdir()
    (tmp_path / "옛묶음" / "a.npz").write_text("", encoding="utf-8")

    assert CHECKER.report(tmp_path, ratchet=True) == 0


# ------------------------------------------- 최신이 정본이 아닐 때 (D-0325 · D-0422)


def _sized(root: Path, pairs: dict[str, int]) -> list[Path]:
    """`이름 → 바이트`로 파일을 만든다. **크기가 이 검사의 자료다.**"""
    made = []
    for name, size in pairs.items():
        path = root / name
        path.write_bytes(b"x" * size)
        made.append(path)
    return made


def test_실행마다_크기를_따로_센다(tmp_path: Path) -> None:
    """**이름별로 합치면 어느 실행이 큰지 모른다** (D-0422).

    그 상태에서 *«최신만 남긴다»*는 **날짜만 보고 하는 말**이 된다.
    """
    files = _sized(
        tmp_path, {"keys-20260916T000000Z.jsonl": 900, "keys-20260930T000000Z.jsonl": 10}
    )

    sizes = CHECKER.runs(files)["keys"]

    assert sizes == {"20260916T000000Z": 900, "20260930T000000Z": 10}


def test_최신이_가장_작으면_지우라고_안_한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**정본 1004곡이 가장 오래된 실행이었다** (D-0325).

    40곡 실험본이 최신이다. 거기서 *«최신만 남긴다»*를 따르면 **정본을 지운다.**
    """
    _sized(tmp_path, {"keys-20260916T000000Z.jsonl": 900, "keys-20260930T000000Z.jsonl": 10})

    assert CHECKER.report(tmp_path, ratchet=True) == 1
    printed = capsys.readouterr()

    assert "최신이 가장 작다" in printed.out
    assert "곡 수를 먼저 본다" in printed.err
    assert "최신만 남기고 옛 실행은 지운다" not in printed.err, "위험한 안내가 그대로 나갔다"


def test_최신이_가장_크면_지우라고_한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**거짓 경보를 늘리지 않는다** (GR-0.8). 보통은 최신이 맞고 그때는 그냥 말한다."""
    _sized(tmp_path, {"scan-20260916T000000Z.jsonl": 10, "scan-20260930T000000Z.jsonl": 900})

    assert CHECKER.report(tmp_path, ratchet=True) == 1
    printed = capsys.readouterr()

    assert "최신이 가장 작다" not in printed.out
    assert "최신만 남기고 옛 실행은 지운다" in printed.err
