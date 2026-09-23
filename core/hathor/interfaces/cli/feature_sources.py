"""특징 산출물을 여는 자리 (D-0233).

### 왜 `main.py` 밖인가

`--features`를 푸는 일과 **산출물 모양을 보고 읽는 쪽을 고르는 일**이 한 덩어리다.
`main.py`는 이미 3천 줄이고 그 빚이 §3에 적혀 있다 (D-0133). 새로 늘리지 않는다.

### 두 모양이 있다

| 모양 | 어디 | 어떻게 읽나 |
|---|---|---|
| 인덱스 저장소 | `var/ingest/clap/features/` | `NpzFeatureStore` — 인덱스 + `vectors/` |
| 곡 묶음 (D-0203) | `var/ingest/audio/` | `BundleFeatureSource` — `--keys`가 말한 배열만 |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from hathor.shared.config.paths import resolve_path

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from hathor.domain.ports.audio_analysis import Embedding


def parse_feature_stores(raw: list[str] | None, fallback: Path) -> list[tuple[str, Path]]:
    """`--features` 값을 (이름, 경로) 목록으로 만든다.

    하나뿐이면 이름을 비워 키를 그대로 쓴다. 기존 단일 저장소 사용법이 그대로
    유지된다. 둘 이상이면 두 저장소가 모두 `mixture` 키를 갖고 있어 충돌하므로
    이름을 강제하고 키를 `이름:mixture`로 네임스페이스한다.
    """
    if not raw:
        return [("", fallback)]
    parsed: list[tuple[str, Path]] = []
    for entry in raw:
        name, separator, path = entry.partition("=")
        # **`resolve_path`를 거친다** (D-0069). `Path()`로 받으면 `var/ingest/clap`이
        # 실행한 폴더(`core/`) 기준이 돼 **없는 곳을 가리킨 채 «인덱스가 없다»고 말한다.**
        if separator:
            parsed.append((name.strip(), resolve_path(path.strip())))
        else:
            parsed.append(("", resolve_path(entry.strip())))
    if len(parsed) > 1 and any(not name for name, _ in parsed):
        raise SystemExit("저장소를 둘 이상 줄 때는 전부 `이름=경로` 형식이어야 한다")
    names = [name for name, _ in parsed]
    if len(set(names)) != len(names):
        raise SystemExit("저장소 이름이 중복됐다")
    return parsed


class FeatureSource(Protocol):
    """검색 하네스가 산출물에 요구하는 전부다 (D-0233).

    두 모양이 이것을 만족한다 — 인덱스 저장소(`NpzFeatureStore`)와 묶음(`BundleFeatureSource`).
    **여기 적힌 것보다 더 요구하면 한쪽이 못 들어온다.**
    """

    @property
    def index_path(self) -> Path: ...

    def iter_vectors(self) -> Iterator[tuple[str, dict[str, Embedding]]]: ...


def store_keys(name: str, keys: tuple[str, ...]) -> tuple[str, ...]:
    """이 저장소에서 읽어야 할 키만 고른다. 이름이 붙으면 `이름:`을 떼고 본다."""
    if not name:
        return keys
    prefix = f"{name}:"
    return tuple(key.removeprefix(prefix) for key in keys if key.startswith(prefix))


def open_feature_source(root: Path, keys: tuple[str, ...]) -> FeatureSource:
    """산출물 모양을 보고 읽는 쪽을 고른다 (D-0233).

    **곡마다 manifest가 있으면 묶음이다** (D-0203). 묶음은 열 배열을 골라야 하므로
    `--keys`를 그대로 넘긴다. 아니면 옛 인덱스 저장소다.
    """
    from hathor.infrastructure.bundle_feature_source import BundleFeatureSource, holds_bundles
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    if holds_bundles(root):
        return BundleFeatureSource(root, keys)
    return NpzFeatureStore(root)


def namespaced(name: str, key: str) -> str:
    return f"{name}:{key}" if name else key
