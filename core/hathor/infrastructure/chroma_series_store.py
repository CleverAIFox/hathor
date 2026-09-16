"""크로마 시계열 `npz` 읽기·쓰기 (O-32 · D-0105 · D-0112).

**CLI에서 내려왔다.** 쓰는 쪽과 읽는 쪽이 파일 이름 규칙(sha1 앞 16자리)을 각자
적고 있었다. 한쪽만 고치면 조용히 0곡이 되고, 그것이 D-0100이 겪은 부류다.
이름 짓기를 `series_path` 하나로 모아 어긋날 자리를 없앤다.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.chord_rhythm import hold_probability
from hathor.domain.services.transition_prior import is_empty, transition_prior

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


def series_path(root: Path, source_key: str, stem: str) -> Path:
    """곡·스템 하나의 시계열 파일 위치.

    이름은 `source_key`의 해시다. **파일 이름에 곡 제목을 쓰지 않는다** — 슬래시와
    유니코드가 섞여 있고 기기마다 다르게 정규화된다 (D-0043 계열).
    """
    stamp = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:16]
    return root / f"{stamp}-{stem}.npz"


def write_series(root: Path, source_key: str, stem: str, series: object) -> None:
    """곡·스템 하나의 크로마 시계열을 `npz`로 쓴다 (O-32 · D-0105).

    **곡마다 파일을 나눈다.** 하나로 모으면 이어받기 중간에 죽었을 때 통째로
    날아가고, 그것이 D-0075가 이어받기를 만든 이유였다. 파일이 있으면 건너뛰므로
    이어받기와 자연히 맞는다.
    """
    root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        series_path(root, source_key, stem),
        series=np.asarray(series, dtype=np.float32),
        source_key=source_key,
    )


def find_series_root(root: Path, stem_set: str) -> Path | None:
    """가장 최근 시계열 폴더 (O-32 · D-0110).

    `keys-*.series` 안에 `<해시>-<스템>.npz`가 있다. 그 스템이 하나도 없으면 건너뛴다 —
    **`other`로 뽑은 폴더에 `bass`를 찾으러 가면 0곡이 된다** (D-0100이 겪은 부류다).
    """
    ingest = root / "var" / "ingest"
    if not ingest.is_dir():
        return None
    for path in sorted(ingest.glob("keys-*.series"), reverse=True):
        if any(path.glob(f"*-{stem_set}.npz")):
            return path
    return None


def load_transition_priors(
    root: Path, stem_set: str, source_keys: Sequence[str], *, tonics: Mapping[str, int]
) -> dict[str, tuple[tuple[float, ...], ...]]:
    """곡별 전이 사전을 시계열 폴더에서 읽는다 (O-32 · D-0112 · D-0213).

    **빈 사전은 뺀다** (D-0107). 창이 둘 미만이거나 한 도수만 나온 곡이며,
    **없는 것을 조건으로 쓰지 않는다.**

    ### 으뜸음으로 회전한다 (D-0213)

    `transition_prior`는 *"들어오는 시계열은 이미 으뜸음으로 회전돼 있어야 한다"*고
    적었고 **아무도 안 돌렸다.** 시계열은 피치클래스 그대로 저장되므로 사전의 행·열이
    **절대음**이었고, 생성기는 그것을 **도수**로 읽었다. E장조 곡에서 I의 행은
    C(♭VI)의 행이었다 — 으뜸화음이 곡에서 사라졌다.

    **으뜸음이 없는 곡은 뺀다.** 0으로 두면 C장조로 읽은 것이 되고 그것이 이 결함이다.
    """
    found: dict[str, tuple[tuple[float, ...], ...]] = {}
    for source_key in source_keys:
        path = series_path(root, source_key, stem_set)
        tonic = tonics.get(source_key)
        if tonic is None or not path.exists():
            continue
        with np.load(path, allow_pickle=False) as bundle:
            series = np.asarray(bundle["series"], dtype=np.float64)
        matrix = transition_prior(np.roll(series, -tonic, axis=1))
        if not is_empty(matrix):
            found[source_key] = tuple(tuple(float(v) for v in row) for row in matrix)
    return found


def load_hold_probabilities(
    root: Path, stem_set: str, source_keys: Sequence[str]
) -> dict[str, float]:
    """곡별 화음 유지 확률을 시계열 폴더에서 읽는다 (O-37 · D-0123).

    **전이 사전과 같은 파일에서 나온다** — 같은 곡의 같은 크로마 시계열이다.
    그래서 `prior`·`transition`과 같은 부류이고 **고를 값이 없다**.

    반감점이 안 나오거나 뒤섞음보다 낮은 곡은 `hold_probability`가 `0.0`을 낸다
    (실측 49곡 · 4.9%). **그 곡들은 지금까지와 똑같이 매 마디 바뀐다** — 빼지 않는
    이유가 그것이다. 여기서 빼면 `transition`은 있는데 `hold`만 없는 곡이 생겨
    판정 표본이 선마다 달라진다.

    시계열 파일이 아예 없는 곡만 뺀다. **없는 것을 0.0이라고 말하지 않는다** (GR-0.5).
    """
    found: dict[str, float] = {}
    for source_key in source_keys:
        path = series_path(root, source_key, stem_set)
        if not path.exists():
            continue
        with np.load(path, allow_pickle=False) as bundle:
            series = np.asarray(bundle["series"], dtype=np.float64)
        found[source_key] = hold_probability(series)
    return found
