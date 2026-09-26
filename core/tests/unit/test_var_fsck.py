"""산출물 정체·실행 묶기 검사 (D-0209)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from hathor.shared.config.paths import repo_root

_spec = importlib.util.spec_from_file_location("var_fsck", repo_root() / "tools" / "var_fsck.py")
assert _spec is not None and _spec.loader is not None
CHECKER = importlib.util.module_from_spec(_spec)
sys.modules["var_fsck"] = CHECKER
_spec.loader.exec_module(CHECKER)


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

    stamps, _size = CHECKER.runs(files)["scan"]

    assert stamps == {"20260915T133016Z"}


def test_옛_실행이_남으면_잡는다(tmp_path: Path) -> None:
    """시각이 둘 이상일 때가 진짜 잔해다."""
    files = _touch(
        tmp_path,
        "scan-20260915T133016Z.jsonl",
        "scan-20260901T010101Z.jsonl",
    )

    stamps, _size = CHECKER.runs(files)["scan"]

    assert len(stamps) == 2


def test_시각이_없는_파일은_한_실행으로_센다(tmp_path: Path) -> None:
    """`all.log`처럼 이름에 시각이 없는 것은 경고 대상이 아니다."""
    files = _touch(tmp_path, "all.log")

    stamps, _size = CHECKER.runs(files)["all"]

    assert stamps == {""}


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
