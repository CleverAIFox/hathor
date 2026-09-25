"""묶음(D-0203)을 검색 하네스에 그대로 먹인다 (D-0233).

### 왜 필요했나

D-0027의 하네스는 `NpzFeatureStore`(인덱스 한 줄 + `vectors/<해시>.npz`)를 읽는다. 그런데
**지금 MERT 산출물은 묶음이다** — `var/ingest/audio/<해시>.npz`에 `mert/<소스>/<층>` 꼴로
들어 있고 곡마다 manifest가 붙는다. 형식이 갈린 채로 O-68(«MERT vs CLAP» · 닫힘 D-0235)을 재려 하면
**CLAP만 재고 MERT는 못 재는** 자리에 선다.

두 길이 있었다. 옛 `mert-layers` 산출물을 백업에서 끌어오는 것과, 묶음을 읽는 어댑터를
두는 것. **어댑터가 이긴다** — 백업은 그 산출물이 무엇으로 뽑혔는지 안 들고 있고(D-0203),
어댑터는 앞으로 뽑는 것에도 계속 쓰인다.

### 읽을 키를 받아서 그것만 연다

묶음 하나에 MERT 65벌이다. 전부 열면 1004곡에 4.5GB가 메모리에 뜬다. `--keys`가
말한 배열만 연다 — `npz`는 연 배열만 푼다.

    hathor eval retrieval --features var/ingest/audio --keys mert/mixture/layer00
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from hathor.infrastructure.track_bundle_store import MANIFEST_NAME, TrackBundleStore

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from hathor.domain.ports.audio_analysis import Embedding


def matrix(name: str, array: object) -> Embedding:
    """(청크, 차원)만 임베딩이다 (D-0233).

    묶음에는 크로마(12,)나 무음 열처럼 **1차원 배열도 들어 있다.** 그것을 그대로
    하네스에 넣으면 유사도 행렬이 엉뚱한 축으로 선다.
    """
    found = cast("Embedding", array)
    if found.ndim != 2:
        raise ValueError(f"묶음 배열 {name}이 2차원이 아니다: {found.shape}")
    return found


def holds_bundles(root: Path) -> bool:
    """이 폴더가 묶음 저장소인가. **manifest가 있어야 묶음이다** (D-0203의 규약)."""
    return root.is_dir() and any(root.glob(f"*.{MANIFEST_NAME}"))


class BundleFeatureSource:
    """묶음 폴더를 `NpzFeatureStore`와 같은 두 가지 모양으로 낸다.

    하네스가 보는 것은 `index_path`(없으면 «인덱스가 없다»고 말할 자리)와
    `iter_vectors`뿐이다. 그 둘만 맞추면 평가 경로를 안 건드린다.
    """

    def __init__(self, root: Path, keys: tuple[str, ...]) -> None:
        self._store = TrackBundleStore(root)
        self._root = root
        self._keys = keys

    @property
    def index_path(self) -> Path:
        """묶음에는 인덱스가 없다. **폴더 자체가 그 자리다** — 없으면 없다고 말한다."""
        return self._root

    def iter_vectors(self) -> Iterator[tuple[str, dict[str, Embedding]]]:
        """(곡 키, {배열 이름: 행렬}). **요청한 키만 연다.**

        묶음은 곡마다 manifest로 완료를 표시하므로 중복 키가 나오지 않는다 —
        옛 인덱스가 O-7(D-0022)로 겪은 자리가 구조적으로 없다.
        """
        for source_key, bundle, _manifest in self._store.manifests():
            arrays = TrackBundleStore.read(bundle, self._keys)
            yield (
                source_key,
                {name: matrix(name, arrays[name]) for name in self._keys if name in arrays},
            )
