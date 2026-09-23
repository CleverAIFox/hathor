"""묶음을 검색 하네스에 먹이는 어댑터 (D-0233).

**형식이 갈려서 O-68을 못 재고 있었다** — CLAP은 인덱스 저장소, MERT는 묶음이다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hathor.infrastructure.bundle_feature_source import BundleFeatureSource, holds_bundles
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.infrastructure.track_bundle_store import TrackBundleStore

KEY = "mert/mixture/layer00"


def _bundle(root: Path, source_key: str = "가수/노래.mp3") -> TrackBundleStore:
    store = TrackBundleStore(root)
    store.write(
        source_key,
        {
            KEY: np.ones((4, 8), dtype=np.float32),
            "mert/mixture/layer03": np.zeros((4, 8), dtype=np.float32),
            "chroma/mixture": np.zeros((12,), dtype=np.float32),
        },
        {"model": "m-a-p/MERT-v1-95M", "dtype": "float32"},
    )
    return store


def test_묶음_폴더를_알아본다(tmp_path: Path) -> None:
    """**manifest가 있어야 묶음이다.** 인덱스 저장소를 묶음으로 오인하면 빈손이 된다."""
    bundles = tmp_path / "audio"
    _bundle(bundles)
    assert holds_bundles(bundles)
    assert not holds_bundles(tmp_path / "clap")
    NpzFeatureStore(tmp_path / "clap").vectors_dir.mkdir(parents=True)
    assert not holds_bundles(tmp_path / "clap")


def test_요청한_키만_연다(tmp_path: Path) -> None:
    """묶음 하나에 MERT가 65벌이다. 전부 열면 1004곡이 메모리에 안 들어간다."""
    bundles = tmp_path / "audio"
    _bundle(bundles)
    found = dict(BundleFeatureSource(bundles, (KEY,)).iter_vectors())
    assert list(found) == ["가수/노래.mp3"]
    assert list(found["가수/노래.mp3"]) == [KEY]
    assert found["가수/노래.mp3"][KEY].shape == (4, 8)


def test_곡_키는_파일_이름이_아니라_manifest가_든다(tmp_path: Path) -> None:
    """파일 이름은 해시다 (D-0203). 이름에서 키를 복원하려 들면 못 푼다."""
    bundles = tmp_path / "audio"
    _bundle(bundles, source_key="가수/다른 노래 (Live).mp3")
    keys = [key for key, _ in BundleFeatureSource(bundles, (KEY,)).iter_vectors()]
    assert keys == ["가수/다른 노래 (Live).mp3"]


def test_없으면_없다고_말할_자리가_있다(tmp_path: Path) -> None:
    """하네스는 `index_path`로 «없다»를 말한다. 묶음에는 폴더가 그 자리다."""
    source = BundleFeatureSource(tmp_path / "없는곳", (KEY,))
    assert not source.index_path.exists()


def test_2차원이_아닌_배열은_임베딩이_아니다(tmp_path: Path) -> None:
    """묶음에는 크로마(12,)도 들어 있다. 하네스에 넣으면 축이 어긋난 채 숫자가 나온다."""
    bundles = tmp_path / "audio"
    _bundle(bundles)
    with pytest.raises(ValueError, match="2차원"):
        dict(BundleFeatureSource(bundles, ("chroma/mixture",)).iter_vectors())
