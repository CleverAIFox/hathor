"""`*.keys.jsonl` 산출물 읽기 (D-0074 · D-0089 · D-0098).

**CLI에서 내려왔다.** 네 로더가 같은 파일을 각자 다시 파싱하고 있었고, 같은 회전
규칙(D-0073)을 네 번 적어 어긋날 자리를 넷 만들어 뒀다. 행 해석을 한 곳에 모은다.

**으뜸음은 어느 출처든 전체 믹스 추정(`key`)을 쓴다.** 스템에서 다시 추정하면
출처마다 회전 기준이 달라져 비교가 성립하지 않는다 (D-0073).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from hathor.domain.services.harmony_prior import merge_degree_priors
from hathor.domain.services.stem_sets import MIX_SOURCE
from hathor.domain.value_objects.key import PITCH_CLASSES

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from hathor.application.evaluate_time_drift import DriftObservation

Row = dict[str, object]


def iter_rows(path: Path) -> Iterator[Row]:
    """행을 하나씩 낸다. **잘린 줄은 건너뛴다.**

    끊긴 배치의 마지막 줄은 잘려 있는 것이 정상이다 (D-0075). 예외로 올리면
    이어받기로 만든 파일을 읽을 수 없다.
    """
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                found = json.loads(line)
            except ValueError:
                continue
            if isinstance(found, dict):
                yield cast("Row", found)


def chroma_of(row: Row, source: str) -> object:
    """그 출처의 곡 전체 크로마. 없으면 `None`.

    `mix`면 전체 믹스를, 아니면 그 스템 조합의 `full`을 읽는다. **한 함수가 둘을
    다 읽는다** — 경로를 나누면 전체 믹스 쪽만 회전을 빠뜨리는 식으로 어긋나고,
    그것이 D-0034 계열이 열한 번 태어난 형태다.
    """
    if source == MIX_SOURCE:
        return row.get("chroma")
    return _stem_bundle(row, source).get("full")


def halves_of(row: Row, source: str) -> tuple[object, object]:
    """그 출처의 앞뒤 반쪽 크로마. 없으면 `(None, None)`."""
    if source == MIX_SOURCE:
        return row.get("chroma_head"), row.get("chroma_tail")
    found = _stem_bundle(row, source)
    return found.get("head"), found.get("tail")


def _stem_bundle(row: Row, source: str) -> dict[str, object]:
    bundle = row.get("stems")
    found = bundle.get(source) if isinstance(bundle, dict) else None
    return cast("dict[str, object]", found) if isinstance(found, dict) else {}


def tonic_index(row: Row, field: str = "key") -> int | None:
    """조성 문자열에서 으뜸음의 피치클래스 번호. 읽을 수 없으면 `None`."""
    text = row.get(field)
    if text is None:
        return None
    tonic = str(text).rsplit(" ", 1)[0]
    return PITCH_CLASSES.index(tonic) if tonic in PITCH_CLASSES else None


def _rotate(vector: Sequence[float], tonic: int) -> tuple[float, ...]:
    """으뜸음 기준으로 회전한 12차원 도수 사전."""
    merged = merge_degree_priors([(tuple(float(value) for value in vector), tonic)])
    return tuple(float(value) for value in merged)


def find_keys_store(root: Path, stem_set: str) -> Path | None:
    """그 스템 조합이 담긴 가장 최근 산출물을 찾는다 (D-0074).

    **생성할 때 Demucs를 돌리지 않기 위한 것이다.** 돌리면 GPU 없는 기기에서 생성이
    안 된다. 참조곡은 코퍼스에서 고르므로 미리 뽑아 두면 조회로 끝나고, 디코딩조차
    사라져 지금보다 빨라진다.
    """
    ingest = root / "var" / "ingest"
    if not ingest.is_dir():
        return None
    for path in sorted(ingest.glob("*.keys.jsonl"), reverse=True):
        try:
            first = next(iter_rows(path), None)
        except OSError:
            continue
        if first is not None and "full" in _stem_bundle(first, stem_set):
            return path
    return None


def load_stem_priors(path: Path, stem_set: str) -> dict[str, tuple[tuple[float, ...], int]]:
    """`source_key → (스템 크로마, 으뜸음)` (D-0074).

    **회전하지 않은 채로 낸다.** 부르는 쪽이 여러 곡을 한 사전으로 합치면서
    회전하므로, 여기서 미리 돌리면 두 번 돈다.
    """
    found: dict[str, tuple[tuple[float, ...], int]] = {}
    for row in iter_rows(path):
        vector = chroma_of(row, stem_set)
        name, tonic = row.get("source_key"), tonic_index(row)
        if vector is None or name is None or tonic is None:
            continue
        found[str(name)] = (
            tuple(float(value) for value in cast("Sequence[float]", vector)),
            tonic,
        )
    return found


def load_degree_priors(path: Path, source: str) -> dict[str, tuple[float, ...]]:
    """`source_key → 으뜸음으로 회전된 12차원 도수 사전` (O-29)."""
    found: dict[str, tuple[float, ...]] = {}
    for row in iter_rows(path):
        vector = chroma_of(row, source)
        name, tonic = row.get("source_key"), tonic_index(row)
        if vector is None or name is None or tonic is None:
            continue
        found[str(name)] = _rotate(cast("Sequence[float]", vector), tonic)
    return found


def load_key_margins(path: Path) -> dict[str, float]:
    """`source_key → margin`. 조성 추정의 1위-2위 상관 차다 (D-0089)."""
    found: dict[str, float] = {}
    for row in iter_rows(path):
        name, margin = row.get("source_key"), row.get("margin")
        if name is not None and margin is not None:
            found[str(name)] = float(cast("float", margin))
    return found


def load_drift_observations(path: Path, left_set: str, right_set: str) -> list[DriftObservation]:
    """반쪽 크로마 둘을 **같은 회전으로** 읽어 변화 벡터를 만든다 (D-0098 · D-0099).

    **으뜸음은 앞반쪽 추정을 쓴다** — 곡 전체에서 추정하면 뒷반쪽이 회전 정렬에
    관여한다 (D-0062). 두 관측이 같은 회전을 써야 비교가 성립한다.
    """
    from hathor.application.evaluate_time_drift import DriftObservation, drift_vector

    found: list[DriftObservation] = []
    for row in iter_rows(path):
        parts = {"left": halves_of(row, left_set), "right": halves_of(row, right_set)}
        name = row.get("source_key")
        tonic = tonic_index(row, "key_head" if row.get("key_head") else "key")
        if name is None or tonic is None:
            continue
        if any(value is None for pair in parts.values() for value in pair):
            continue
        rotated = {
            side: drift_vector(
                _rotate(cast("Sequence[float]", raw_head), tonic),
                _rotate(cast("Sequence[float]", raw_tail), tonic),
            )
            for side, (raw_head, raw_tail) in parts.items()
        }
        found.append(DriftObservation(str(name), rotated["left"], rotated["right"]))
    return found
