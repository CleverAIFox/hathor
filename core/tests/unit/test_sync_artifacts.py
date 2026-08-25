"""산출물 교두보 도구를 **검사한다** (D-0119).

### 왜 이 파일이 뒤늦게 생겼는가

D-0118은 합성 자료로 왕복만 확인하고 냈다. **왕복은 전부 통과했다.** 그런데 실제
리전에서 처음 쓸 때 세 자리에서 걸렸다 — 교두보가 비었을 때, 못 쓰는 곳일 때,
복사가 도중에 막힐 때. **가장 흔한 경우를 하나도 안 봤다.**

권한 실패는 셸에서 재현할 수 없다(root는 검사를 통과한다). 그래서 여기서 강제한다.
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import sync_artifacts as tool


@pytest.fixture
def store(tmp_path) -> Path:
    """붙어 있고 산출물도 있는 교두보."""
    root = tmp_path / "ssd"
    (root / tool.SUBTREE).mkdir(parents=True)
    return root


# ------------------------------------------------------------------ probe (D-0119)


def test_경로를_안_적었으면_안_붙은_것이다():
    state, note = tool.probe(None)
    assert state == tool.MISSING
    assert tool.STORE_ENV in note


def test_없는_경로는_안_붙은_것이다(tmp_path):
    state, note = tool.probe(tmp_path / "없다")
    assert state == tool.MISSING
    assert "SSD가 안 붙었거나" in note


def test_못_쓰는_곳은_안_붙은_것이다(store, monkeypatch):
    """root로 돌면 권한 검사가 통과하므로 여기서 강제한다."""

    def 막힌다(*_args, **_kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(pathlib.Path, "write_bytes", 막힌다)
    state, note = tool.probe(store)
    assert state == tool.MISSING
    assert "쓸 수 없다" in note
    assert "Operation not permitted" in note


def test_쓰기_확인은_진짜로_써_본다(store):
    """`os.access`는 DrvFs에서 참을 내고도 쓰기가 막힐 수 있다 (D-0120)."""
    assert tool.can_write(store) == (True, "")
    assert not list(store.glob(".hathor-probe*")), "확인용 파일을 남기지 않는다"


def test_폴더는_있고_산출물만_없으면_비었다다(tmp_path):
    """**어제 여기서 멈췄다** (D-0119).

    D-0118은 이것도 "SSD가 안 붙었거나 경로가 틀렸다"고 말했다. 붙어 있는데.
    **첫 push 직전이 가장 흔한 상태이고, 거기에 가장 무서운 문구를 주고 있었다.**
    """
    root = tmp_path / "ssd"
    root.mkdir()
    state, note = tool.probe(root)
    assert state == tool.EMPTY
    assert "아직 비었다" in note


def test_산출물이_있으면_붙은_것이다(store):
    assert tool.probe(store)[0] == tool.ATTACHED


def test_비었을_때_status는_실패가_아니다(tmp_path, capsys):
    """붙어 있는데 비었을 뿐이면 **고칠 것이 없다.**"""
    root = tmp_path / "ssd"
    root.mkdir()
    assert tool.status(tmp_path / "var" / "ingest", root) == 0
    assert "artifacts-push" in capsys.readouterr().out


# ------------------------------------------------------------------ 거르개 (D-0119)


def test_거르개가_없으면_전부다():
    names = {"keys-X.keys.jsonl": 1, "lyrics-8192/v.npz": 2}
    assert tool.keep(names, None) == names
    assert tool.keep(names, []) == names


def test_접두어로_거른다():
    """실측 1.7GB 중 O-37이 읽는 것은 `keys-*` 74MB뿐이다."""
    names = {
        "keys-X.keys.jsonl": 1,
        "keys-X.series/a-other.npz": 2,
        "lyrics-8192/v.npz": 3,
        "mert-layers/m.npz": 4,
    }
    assert set(tool.keep(names, ["keys"])) == {"keys-X.keys.jsonl", "keys-X.series/a-other.npz"}
    assert set(tool.keep(names, ["lyrics", "mert"])) == {"lyrics-8192/v.npz", "mert-layers/m.npz"}


# ------------------------------------------------------------------ 실패 모양 (D-0119)


def test_복사가_막히면_한_줄로_말한다(tmp_path, monkeypatch, capsys):
    """**역추적을 뿜지 않는다.**

    D-0118은 `PermissionError`를 스택 4겹으로 냈다. 이 저장소의 다른 도구는 전부
    `실패: ` 한 줄이며, 스택은 무엇을 해야 하는지 알려주지 않는다.
    """
    source = tmp_path / "여기" / "var" / "ingest"
    source.mkdir(parents=True)
    (source / "a.npz").write_bytes(b"x")

    def 막힌다(*_args):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(tool, "copy_one", 막힌다)
    assert tool.transfer(source, tmp_path / "저기", "보냄", dry_run=False) == 1

    err = capsys.readouterr().err
    assert err.count("\n") <= 3
    assert "실패:" in err
    assert "Traceback" not in err
    assert "이어받는다" in err


def test_dry_run은_아무것도_쓰지_않는다(tmp_path):
    source = tmp_path / "여기"
    source.mkdir()
    (source / "a.npz").write_bytes(b"x")
    target = tmp_path / "저기"

    assert tool.transfer(source, target, "보냄", dry_run=True) == 0
    assert not target.exists()


def test_이미_있으면_건너뛴다(tmp_path):
    """**추가 전용이다.** 몇 번을 돌려도 같다 (D-0118)."""
    source, target = tmp_path / "여기", tmp_path / "저기"
    source.mkdir()
    (source / "a.npz").write_bytes(b"first")

    assert tool.transfer(source, target, "보냄", dry_run=False) == 0
    (source / "a.npz").write_bytes(b"second")
    assert tool.transfer(source, target, "보냄", dry_run=False) == 0
    assert (target / "a.npz").read_bytes() == b"first"


def test_chmod가_막혀도_복사된다(tmp_path, monkeypatch):
    """**DrvFs가 `chmod`를 못 한다** (D-0120).

    `copy2`는 내용을 옮긴 뒤 권한까지 옮기려다 `Operation not permitted`로 죽었다.
    **권한도 시각도 쓰지 않는데** 그것 때문에 6036개가 한 개도 못 갔다.
    """

    def 막힌다(*_args, **_kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(tool.os, "chmod", 막힌다)
    monkeypatch.setattr(tool.shutil, "copystat", 막힌다)

    source, target = tmp_path / "여기" / "a.npz", tmp_path / "저기" / "a.npz"
    source.parent.mkdir()
    source.write_bytes(b"payload")

    tool.copy_one(source, target)
    assert target.read_bytes() == b"payload"
    assert not list(target.parent.glob("*" + tool.PART))


def test_part_는_목록에_안_들어간다(tmp_path):
    """반쯤 받은 것을 받은 것으로 치면 영원히 건너뛴다 (D-0118)."""
    base = tmp_path / "여기"
    base.mkdir()
    (base / "a.npz").write_bytes(b"x")
    (base / ("b.npz" + tool.PART)).write_bytes(b"y")
    assert set(tool.walk(base)) == {"a.npz"}
