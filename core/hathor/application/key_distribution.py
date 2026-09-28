"""코퍼스 조성 분포를 **수로** 낸다 (O-22 닫힘 D-0201 · D-0280).

### 왜 이 파일이 생겼나

이 계산이 `interfaces/cli`에 있었다. `keys_report`가 중앙값을 재고 `tables`가 불 마스크로
비율을 냈다 — **표시 계층이 `numpy`를 들이고 있었고** GR-2.2가 금지하는 자리다 (D-0278이
그것을 세기 시작했고 D-0279가 둘을 옮겼다).

여기는 **수만 낸다.** 글자는 `tables`가 만든다. 그렇게 갈라 놓으면 «분모가 무엇인가»를
시험이 직접 물을 수 있다 — D-0057과 D-0182가 둘 다 분모를 틀린 자리이고, 그때는 수와 글자가
한 함수에 있어서 **출력 문자열로만 확인할 수 있었다.**

### 맞다는 증명이 아니다

정답 라벨이 없으므로 분포와 무작위 베이스라인으로 **틀렸다는 신호만** 잡는다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from hathor.domain.services.key_estimation import (
    BLACK_KEYS,
    KEY_MARGIN_FLOOR,
    random_baseline,
    relative_key,
)
from hathor.domain.value_objects.key import Key, Mode

OFF_CENTS = 10.0
"""이보다 크게 벗어난 조율을 «틀어졌다»로 센다 (D-0057)."""


@dataclass(frozen=True, slots=True)
class ModeShare:
    """한 선법의 몫 (O-54)."""

    name: str
    count: int
    ambiguous: float
    relative: float
    relative_in_ambiguous: float | None
    """애매한 곡 안에서의 나란한조 비율. **애매한 곡이 없으면 `None`이다** — 0.0과 다르다."""


@dataclass(frozen=True, slots=True)
class Tuning:
    """조율 편차 요약 (D-0057)."""

    median_cents: float
    off_count: int
    off_share: float


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """조성 애매함 (O-22 닫힘 D-0201 · O-54 · D-0185).

    **바닥은 하나다.** `random_baseline`은 무작위 크로마 2000개이며 곡과 짝이 없고 어느
    선법인지도 안 낸다 — 선법별로 가를 수 없으므로 둘 다 같은 값과 견준다. **전체 바닥을
    부분집합에 갖다 대는 것과는 다르다** (D-0182에서 그렇게 틀렸다).
    """

    total: int
    ambiguous: int
    ambiguous_share: float
    floor: float
    relative_share: float
    relative_in_ambiguous: tuple[int, float] | None
    """(수, 비율). **분모가 애매한 곡이다** (D-0057) — 전체 대비로 재면 확신도 높은 곡의
    2등까지 섞여 희석된다. 애매한 곡이 없으면 `None`이다."""
    modes: tuple[ModeShare, ...]
    tuning: Tuning | None


@dataclass(frozen=True, slots=True)
class Distribution:
    """분포 전체. `keys_report`가 이것을 찍는다."""

    total: int
    modes: tuple[tuple[str, int], ...]
    cross: tuple[tuple[str, int, int], ...]
    """(으뜸음, 장조, 단조). 잦은 으뜸음 순이다."""
    black: int
    """검은건반 으뜸음 곡 수 — O-23 지표 (D-0061)."""
    metrics: tuple[tuple[str, float, float, float], ...]
    """(이름, 코퍼스 중앙값, 무작위 중앙값, 차이)."""
    ambiguity: Ambiguity


def _key(text: str) -> Key:
    tonic, mode = str(text).rsplit(" ", 1)
    return Key(tonic=tonic, mode=Mode(mode))


def ambiguity(
    *,
    modes: list[str],
    ambiguous: list[bool],
    relative: list[bool],
    floor: float,
    tunings: list[float],
) -> Ambiguity:
    """애매함을 수로 낸다. **글자는 만들지 않는다.**"""
    kinds = np.asarray(modes)
    flags = np.asarray(ambiguous, dtype=bool)
    near = np.asarray(relative, dtype=bool)
    total = len(kinds)
    held = int(flags.sum())

    shares: list[ModeShare] = []
    for name in ("major", "minor"):
        picked = kinds == name
        count = int(picked.sum())
        if not count:
            continue
        inside = near[picked & flags]
        shares.append(
            ModeShare(
                name=name,
                count=count,
                ambiguous=float(flags[picked].mean()),
                relative=float(near[picked].mean()),
                relative_in_ambiguous=float(inside.mean()) if inside.size else None,
            )
        )

    tuning: Tuning | None = None
    # **`if tunings`로 거르지 않는다.** 0.0이 거짓이라 정확히 0센트인 곡이 통째로 빠진다 —
    # D-0057에서 분모 오류를 적어놓고 같은 세션에 또 냈다.
    if len(tunings):
        cents = np.asarray(tunings, dtype=float)
        off = int((np.abs(cents) > OFF_CENTS).sum())
        tuning = Tuning(
            median_cents=float(np.median(cents)),
            off_count=off,
            off_share=off / len(cents),
        )

    return Ambiguity(
        total=total,
        ambiguous=held,
        ambiguous_share=held / total if total else 0.0,
        floor=floor,
        relative_share=float(near.mean()) if total else 0.0,
        relative_in_ambiguous=(int(near[flags].sum()), float(near[flags].mean())) if held else None,
        modes=tuple(shares),
        tuning=tuning,
    )


def summarize(rows: list[dict[str, object]], *, harmonic: float) -> Distribution:
    """행에서 분포를 낸다. **행이 비면 부르지 않는다** — 부르는 쪽이 먼저 본다."""
    total = len(rows)
    keys = [_key(str(row["key"])) for row in rows]
    runner_ups = [_key(str(row["runner_up"])) for row in rows]
    margins = np.asarray([float(str(row["margin"])) for row in rows])
    correlations = np.asarray([float(str(row["correlation"])) for row in rows])

    counted: Counter[str] = Counter(key.mode.value for key in keys)
    tonics: Counter[str] = Counter(key.tonic for key in keys)
    cross = tuple(
        (
            tonic,
            sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MAJOR),
            sum(1 for key in keys if key.tonic == tonic and key.mode is Mode.MINOR),
        )
        for tonic, _ in tonics.most_common()
    )

    # **베이스라인도 같은 프로파일로 잰다** (D-0059). 하한이 프로파일마다 달라
    # (Krumhansl 0.6192 · Temperley 0.5488) 고정값을 쓰면 비교가 성립하지 않는다.
    profile = str(rows[0].get("profile", "krumhansl"))
    base_correlation, base_margin = random_baseline(profile=profile, harmonic=harmonic)
    metrics = tuple(
        (
            name,
            float(np.median(actual)),
            float(np.median(base)),
            float(np.median(actual) - np.median(base)),
        )
        for name, actual, base in (
            ("상관", correlations, base_correlation),
            ("격차", margins, base_margin),
        )
    )

    return Distribution(
        total=total,
        modes=tuple(counted.most_common()),
        cross=cross,
        black=sum(1 for key in keys if key.tonic in BLACK_KEYS),
        metrics=metrics,
        ambiguity=ambiguity(
            modes=[key.mode.value for key in keys],
            ambiguous=[bool(flag) for flag in margins < KEY_MARGIN_FLOOR],
            relative=[
                relative_key(key) == other for key, other in zip(keys, runner_ups, strict=True)
            ],
            floor=float((base_margin < KEY_MARGIN_FLOOR).mean()),
            tunings=[float(str(row["tuning_cents"])) for row in rows if "tuning_cents" in row],
        ),
    )
