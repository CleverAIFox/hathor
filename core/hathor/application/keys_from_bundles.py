"""곡별 묶음에서 옛 `keys` 규격을 다시 만든다 (O-63 · D-0211).

### 왜 어댑터가 아니라 재생성인가

D-0203이 산출물 규격을 곡별 묶음으로 바꾸고 **읽는 쪽을 안 봤다.** 옛 규격을
읽는 자리가 다섯이다 — `keys_jsonl_store` · `chroma_series_store` · `env` ·
`doctor` · `onset_store`. 어댑터를 붙이면 그만큼 새 버그 자리가 생기고 검증된
`load_stem_priors`·`load_transition_priors`를 다시 검증해야 한다. **옛 규격을
다시 쓰면 다운스트림이 한 줄도 안 바뀐다.**

### 음원도 GPU도 필요 없다

조성 추정은 크로마만 쓴다. 묶음에 `chroma/<소스>`·`chroma_series/<소스>`가 있고
`DEFAULT_STEM_SET`이 `other` 하나라 **조합을 합칠 일이 없다.**

### 조합은 만들지 않는다

`other+bass`는 묶음에 없다. 스템 크로마를 더해 만들 수 있어 보이나 **크로마는
크기 스펙트럼이라 신호의 합에 대해 선형이 아니다** — `ingest keys --separate`가
조합마다 실제로 뽑은 이유와 같다. 근사를 끼우지 않고 **없는 것은 없다고 둔다.**
반쪽(`--halves`)도 같은 이유로 없다.

### 묶음 크로마는 이미 배음을 뺐다

D-0203은 D-0201 뒤에 돌았고 `cq_chroma` 기본값이 **배음 0.5**였다. 옛 `keys`
파일은 배음 0으로 뽑혀 `--replay`가 감산을 **나중에** 걸었다. 새 행에 강도를
적지 않으면 `--replay`가 **한 번 더 뺀다** — 그래서 행의 `harmonic`이 묶음의
실제 강도를 든다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hathor.domain.services.key_estimation import (
    AGGREGATE_MEAN,
    CHROMA_CQ,
    estimate_key,
)
from hathor.domain.services.stem_sets import MIX_SOURCE, STEM_SETS

if TYPE_CHECKING:
    from collections.abc import Mapping

    type Array = np.ndarray[tuple[int, ...], np.dtype[np.float32]]

BUNDLE_MIX = "mixture"
"""묶음이 전체 믹스를 부르는 이름. 옛 규격은 `mix`라 부른다 (`MIX_SOURCE`)."""

LEGACY_CHROMA: dict[str, object] = {
    "chroma_mode": CHROMA_CQ,
    "chroma_harmonic": 0.5,
    "chroma_gamma": 0.0,
    "chroma_series_seconds": 1.0,
}
"""크로마 조건을 **안 적은** D-0203 묶음이 실제로 쓴 값.

**추측이 아니라 그때의 기본값이다.** D-0203의 `ingest_all`이 `cq_chroma(mono)` ·
`chroma_series(mono)`를 인자 없이 불렀고, 그 커밋에서 기본값이 `cq` · 배음 0.5
(D-0201) · gamma 0 · 창 1초였다. **상수를 참조하지 않고 값을 박는다** — 뒤에
기본값이 바뀌면 옛 묶음의 사실도 따라 바뀐 것처럼 보인다. 뒤로 뽑는 묶음은
manifest에 직접 적는다.
"""


def bundle_chroma(manifest: Mapping[str, object]) -> dict[str, object]:
    """묶음이 크로마를 어떤 조건으로 뽑았나. **manifest가 우선이다.**"""
    return {name: manifest.get(name, value) for name, value in LEGACY_CHROMA.items()}


def single_stem_sets(available: set[str]) -> list[str]:
    """묶음에서 만들 수 있는 조합 — **스템 하나짜리만.**"""
    return sorted(
        name
        for name, parts in STEM_SETS.items()
        if len(parts) == 1 and f"chroma/{parts[0]}" in available
    )


def settings_for(
    chroma: Mapping[str, object], profile: str, stem_sets: list[str]
) -> dict[str, object]:
    """행에 적히는 조건. **`_keys_settings`와 같은 이름을 쓴다** (D-0073).

    이름이 다르면 `find_keys_store`·`--replay`·`doctor`가 조건을 못 읽는다.
    """
    return {
        "chroma_mode": chroma["chroma_mode"],
        "profile": profile,
        "gamma": chroma["chroma_gamma"],
        "harmonic": chroma["chroma_harmonic"],
        "aggregate": AGGREGATE_MEAN,
        "separated": bool(stem_sets),
        "halves": False,
        "stem_sets": stem_sets,
        "series_seconds": chroma["chroma_series_seconds"],
    }


@dataclass(frozen=True, slots=True)
class KeysFromBundle:
    """곡 하나의 옛 규격 행과 시계열. **파일을 쓰지 않는다.**"""

    row: dict[str, object]
    series: dict[str, Array]


def keys_from_bundle(
    source_key: str,
    arrays: Mapping[str, Array],
    manifest: Mapping[str, object],
    *,
    profile: str,
) -> KeysFromBundle:
    """묶음 하나를 옛 `keys` 행으로 옮긴다.

    **으뜸음은 전체 믹스 크로마에서 추정한다** (D-0073). 스템에서 다시 추정하면
    출처마다 회전 기준이 달라진다. 믹스 크로마가 없으면 행을 못 만든다 —
    `load_stem_priors`가 으뜸음 없는 행을 버리므로 **조용히 빠지느니 여기서 올린다.**
    """
    mix = arrays.get(f"chroma/{BUNDLE_MIX}")
    if mix is None:
        raise KeyError(f"chroma/{BUNDLE_MIX}가 없다: {source_key}")
    vector = np.asarray(mix, dtype=np.float32)
    if vector.shape != (12,) or float(vector.sum()) <= 0.0:
        raise ValueError(f"믹스 크로마가 비었다: {source_key}")

    chroma = bundle_chroma(manifest)
    stem_sets = single_stem_sets(set(arrays))
    estimate = estimate_key(vector, profile=profile)
    row: dict[str, object] = {
        **settings_for(chroma, profile, stem_sets),
        "window_seconds": None,
        "limit": None,
        "source_key": source_key,
        **estimate.as_record(),
        "tuning_cents": 0.0,
        "chroma": _rounded(vector),
        # **어디서 왔는지 적는다** (D-0203의 규율). 디코딩으로 뽑은 행과 섞이면
        # 무엇이 무엇인지 산출물만 보고는 모른다.
        "origin": "bundle",
        "bundle_revision": manifest.get("revision", "unknown"),
    }
    if stem_sets:
        row["stems"] = {
            name: {"full": _rounded(np.asarray(arrays[f"chroma/{STEM_SETS[name][0]}"]))}
            for name in stem_sets
        }

    series: dict[str, Array] = {}
    for key, value in arrays.items():
        if not key.startswith("chroma_series/"):
            continue
        source = key.removeprefix("chroma_series/")
        series[MIX_SOURCE if source == BUNDLE_MIX else source] = value
    return KeysFromBundle(row=row, series=series)


def replay_guard(rows: list[dict[str, object]], requested: float, *, sweep: bool) -> float | str:
    """`--replay`가 저장된 크로마에 **더** 뺄 강도. 못 하면 사유 한 줄.

    감산은 음수를 0으로 자르므로 **두 번에 나눠 뺀 것이 한 번에 뺀 것과 다르다.**
    그래서 이미 뺀 크로마는 같은 강도로만 읽을 수 있고, 강도를 훑는 `--harmonic-sweep`은
    **배음 0으로 뽑은 크로마에서만** 성립한다 — D-0201의 표가 그 전제 위에 있다.

    이 검사가 없던 동안 D-0201 뒤에 뽑은 `keys`를 기본값으로 재판정하면 배음이
    **조용히 두 번** 빠졌다.
    """
    stored = {
        float(str(row.get("harmonic") or 0.0)) for row in rows if row.get("chroma") is not None
    }
    if len(stored) > 1:
        return f"행마다 저장된 배음 강도가 다르다: {sorted(stored)}. 한 강도로 재판정할 수 없다"
    base = stored.pop() if stored else 0.0
    if base == 0.0:
        return requested
    if sweep:
        return (
            f"저장된 크로마는 이미 배음 {base:g}를 뺐다. --harmonic-sweep은 배음 0 크로마에서만 "
            "성립한다 — 감산이 두 번 걸린다. 배음 0으로 뽑은 산출물로 잰다"
        )
    if requested == base:
        return 0.0
    return (
        f"저장된 크로마는 이미 배음 {base:g}를 뺐다. --harmonic {requested:g}로 다시 못 잰다 — "
        f"감산이 두 번 걸린다. --harmonic {base:g}를 주거나 배음 0 산출물로 잰다"
    )


def _rounded(vector: Array) -> list[float]:
    return [round(float(value), 6) for value in np.asarray(vector).reshape(-1)]
