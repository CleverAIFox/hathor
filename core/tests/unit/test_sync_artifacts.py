"""산출물 교두보 도구를 **검사한다** (D-0119).

### 왜 이 파일이 뒤늦게 생겼는가

D-0118은 합성 자료로 왕복만 확인하고 냈다. **왕복은 전부 통과했다.** 그런데 실제
리전에서 처음 쓸 때 세 자리에서 걸렸다 — 교두보가 비었을 때, 못 쓰는 곳일 때,
복사가 도중에 막힐 때. **가장 흔한 경우를 하나도 안 봤다.**

권한 실패는 셸에서 재현할 수 없다(root는 검사를 통과한다). 그래서 여기서 강제한다.
"""

from __future__ import annotations

import errno
import pathlib
import sys
from pathlib import Path

import pytest

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import sync_artifacts as tool

ROOT = repo_root()


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
    """실측 1.7GB 중 O-37·D-0125이 읽는 것은 `keys-*` 74MB뿐이다."""
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


# ------------------------------------------------------------------ 훑기 (D-0239)


def test_흘려보내며_훑는다(tmp_path: Path) -> None:
    """**전량을 세우지 않는다.** 만 이천 개를 세우다 교두보에서 메모리가 터졌다."""
    base = tmp_path / "ingest"
    (base / "audio" / "깊은곳").mkdir(parents=True)
    (base / "audio" / "a.npz").write_bytes(b"12345")
    (base / "audio" / "깊은곳" / "b.npz").write_bytes(b"67")
    (base / "audio" / "c.npz.part").write_bytes(b"half")

    found = dict(tool.iter_files(base))

    assert found == {"audio/a.npz": 5, "audio/깊은곳/b.npz": 2}, "`.part`는 세지 않는다"
    assert tool.walk(base) == found


def test_못_읽는_폴더에서_멈추지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**DrvFs는 한 폴더에서 토라진다** — 거기서 죽으면 나머지도 못 본다 (D-0239)."""
    base = tmp_path / "ingest"
    (base / "막힌곳").mkdir(parents=True)
    (base / "보이는곳").mkdir()
    (base / "보이는곳" / "a.npz").write_bytes(b"1")

    real = tool.os.scandir

    def hostile(path):  # type: ignore[no-untyped-def]
        if str(path).endswith("막힌곳"):
            raise OSError(12, "Cannot allocate memory")
        return real(path)

    monkeypatch.setattr(tool.os, "scandir", hostile)

    assert dict(tool.iter_files(base)) == {"보이는곳/a.npz": 1}
    assert "읽지 못했다" in capsys.readouterr().err


def test_없는_곳은_빈손이다(tmp_path: Path) -> None:
    assert dict(tool.iter_files(tmp_path / "없음")) == {}


# ------------------------------------------------------------------ 복사 (D-0240)


def test_버퍼_하나만_쓰고_옮긴다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**`shutil.copyfile`은 `sendfile`로 간다** — DrvFs가 거기서 ENOMEM을 낸다."""
    source, target = tmp_path / "a.npz", tmp_path / "밖" / "a.npz"
    source.write_bytes(b"x" * (3 << 20))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("copyfile을 쓰면 안 된다 (D-0240)")

    monkeypatch.setattr(tool.shutil, "copyfile", forbidden)
    tool.copy_one(source, target)

    assert target.read_bytes() == source.read_bytes()
    assert not list(tmp_path.rglob(f"*{tool.PART}")), "반쪽을 안 남긴다"


def test_메모리가_모자라면_더_잘게_다시_쓴다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """드라이브가 큰 덩어리를 못 받는 순간이 있다. **포기하지 않고 잘게 나눈다.**"""
    source, target = tmp_path / "a.npz", tmp_path / "밖" / "a.npz"
    source.write_bytes(b"y" * 4096)
    real, seen = tool.shutil.copyfileobj, []

    def flaky(reading: object, writing: object, size: int) -> None:
        seen.append(size)
        if len(seen) == 1:
            raise OSError(errno.ENOMEM, "Cannot allocate memory")
        real(reading, writing, size)  # type: ignore[arg-type]

    monkeypatch.setattr(tool.shutil, "copyfileobj", flaky)
    tool.copy_one(source, target)

    assert seen == [tool.CHUNK, tool.SMALL_CHUNK]
    assert target.read_bytes() == source.read_bytes()


def test_다른_실패는_반쪽을_지우고_올린다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ENOMEM이 아니면 다시 안 쓴다 — 디스크가 찼는데 또 쓰면 더 나쁘다."""
    source, target = tmp_path / "a.npz", tmp_path / "밖" / "a.npz"
    source.write_bytes(b"z" * 16)

    def full(reading: object, writing: object, size: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(tool.shutil, "copyfileobj", full)
    with pytest.raises(OSError, match="No space"):
        tool.copy_one(source, target)
    assert not list(tmp_path.rglob("*")) or not list(tmp_path.rglob(f"*{tool.PART}"))


# ------------------------------------------------------------------ 대조 (D-0242)


@pytest.fixture
def pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """양쪽이 선 교두보와 저장소. 봉인지는 시험마다 따로 둔다."""
    local = tmp_path / "repo" / "var" / "ingest"
    store = tmp_path / "ssd"
    (local / "audio").mkdir(parents=True)
    (store / tool.SUBTREE / "audio").mkdir(parents=True)
    monkeypatch.setattr(tool, "SEAL", tmp_path / "seal.jsonl")
    return local, store


def _put(local: Path, store: Path, name: str, mine: bytes, yours: bytes | None) -> None:
    (local / name).write_bytes(mine)
    if yours is not None:
        (store / tool.SUBTREE / name).write_bytes(yours)


def test_크기가_다르면_다르다고_말한다(
    pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """**이름만 보던 옛 판은 이것을 «이미 있음»으로 셌다** — 영원히 안 고쳐진다."""
    local, store = pair
    _put(local, store, "audio/a.npz", b"1234", b"1234")
    _put(local, store, "audio/b.npz", b"short", b"much longer")

    assert tool.verify(local, store, full=False) == 1
    said = capsys.readouterr()
    assert "audio/b.npz" in said.err
    assert "audio" in said.out


def test_크기가_같아도_내용이_다르면_잡는다(
    pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """크기 대조는 싸고 내용 대조는 비싸다. **비싼 것은 `--full`이 한다.**"""
    local, store = pair
    _put(local, store, "audio/c.npz", b"ABCD", b"WXYZ")

    assert tool.verify(local, store, full=False) == 0, "크기만 보면 같아 보인다"
    assert tool.verify(local, store, full=True) == 1
    assert "내용이 다르다" in capsys.readouterr().err


def test_봉인한_것은_다시_안_읽는다(
    pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**이것이 CDC다.** `(크기, mtime)`이 양쪽 다 그대로면 해시를 다시 안 뜬다."""
    local, store = pair
    _put(local, store, "audio/a.npz", b"1234", b"1234")
    assert tool.verify(local, store, full=True) == 0

    seen: list[Path] = []
    real = tool.digest

    def watched(path: Path) -> str:
        seen.append(path)
        return str(real(path))

    monkeypatch.setattr(tool, "digest", watched)
    assert tool.verify(local, store, full=True) == 0
    assert seen == [], "봉인이 있으면 안 읽는다"

    (local / "audio" / "a.npz").write_bytes(b"5678")
    assert tool.verify(local, store, full=True) == 1, "바뀌면 다시 읽고 다름을 잡는다"
    assert seen, "바뀐 것은 읽어야 한다"


def test_계열로_접어_보여_준다() -> None:
    """9240개를 열두 줄로. **스탬프는 별표로 접는다.**"""
    assert tool.series("keys-20260823T091233Z.series/x.npz") == "keys-*.series"
    assert tool.series("audio/f40090f19f984895.npz") == "audio"
    assert tool.series("scan-20260916T115536Z.jsonl") == "scan-*.jsonl"


def test_잠금과_반쪽은_산출물이_아니다(tmp_path: Path) -> None:
    """**D-0243의 강제자.** 교두보에 밀려간 `.batch.lock` 하나가 8059개의 «같음»을 덮었다."""
    base = tmp_path / "ingest"
    (base / "features").mkdir(parents=True)
    (base / "features" / "a.npz").write_bytes(b"1")
    (base / "features" / ".batch.lock").write_bytes(b"")
    (base / "features" / "b.npz.part").write_bytes(b"half")

    assert dict(tool.iter_files(base)) == {"features/a.npz": 1}


def test_위생은_한_이름으로_모인다() -> None:
    """기기 · 저장소 · 산출물이 목표 셋에 흩어져 있어 **무엇을 돌릴지부터 헷갈렸다** (D-0243)."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = makefile.split("hygiene:", 1)[1].split("\n\n", 1)[0]
    assert all(name in block for name in ("doctor", "tidy", "var-fsck"))
