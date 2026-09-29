"""교란 두 축이 **번짐과 진짜를 반대 방향으로 가르는가** (O-64 · D-0302).

`eval chord-quality`의 첫 실측(1004곡)이 `m7` +0.0478 · `dom7` -0.1094를 냈다. 4음
편향으로는 반대 부호가 설명되지 않아 진짜 신호로 보이는데, **창이 화음 전환을 걸쳤을
때도 같은 모양이 난다** — C maj와 A min이 한 창에 들어가면 정확히 `Am7`의 음들이다.

**자가 그 둘을 가를 수 있는지 먼저 확인한다** (O-25 둘째 줄 — 비교선이 이길 수 있는지).
못 가르는 자를 붙여 두면 아무것도 못 잡는 하네스가 되고 그것이 D-0071이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hathor.application.evaluate_chord_quality import FLOORS, GROUPS, difference, stack
from hathor.domain.services.harmony_quality import (
    DEGREE_COUNT,
    QUALITIES,
    SUSTAINED_FLOOR,
    sustained_mask,
)
from hathor.domain.services.stem_sets import SERIES_STEMS
from hathor.infrastructure.chroma_series_store import (
    load_series,
    series_settings,
    write_series,
)
from hathor.interfaces.cli.eval_quality import MISSING, warnings
from hathor.interfaces.cli.main import main

HOLD = 3
SONGS = 60
NOISE = 0.2


def _vector(root: int, quality: str) -> np.ndarray:
    row = np.zeros(DEGREE_COUNT)
    for tone in QUALITIES[quality]:
        row[(root + tone) % DEGREE_COUNT] = 1.0
    return row


def corpus(*, smeared: bool, seed: int = 8, songs: int = SONGS) -> list[np.ndarray]:
    """두 화음을 번갈아 쓰는 곡. **마지막 창이 다음 화음과 50/50으로 섞인다.**

    `smeared`면 3화음 둘(I <-> vi)이라 `m7`은 전환 창에서만 생긴다. 아니면 `m7`이
    지속되므로 전환을 걸러도 남아야 한다.
    """
    generator = np.random.default_rng(seed)
    built: list[np.ndarray] = []
    for _ in range(songs):
        key = int(generator.integers(0, DEGREE_COUNT))
        pair = (
            (_vector(key, "maj"), _vector((key + 9) % DEGREE_COUNT, "min"))
            if smeared
            else (_vector(key, "m7"), _vector((key + 5) % DEGREE_COUNT, "m7"))
        )
        windows: list[np.ndarray] = []
        for current, following in (pair, pair[::-1]) * 6:
            windows += [current] * (HOLD - 1) + [(current + following) / 2]
        frame = np.asarray(windows) + generator.random((len(windows), DEGREE_COUNT)) * NOISE
        built.append(frame)
    return built


def _m7(songs: list[np.ndarray], **kwargs: object) -> float:
    found = difference(stack(songs, **kwargs), seed=1)  # type: ignore[arg-type]
    assert found is not None
    return found.quality["m7"]


def test_번짐만으로_생긴_m7은_두_자에서_뒤집힌다() -> None:
    """**이것이 자가 쓸모 있다는 증거다.** 원본에서 양수인 것이 둘 다에서 음수가 된다."""
    songs = corpus(smeared=True)
    assert _m7(songs) > 0.15, "번짐이 `m7`을 만들지 못했다 — 합성 자료가 질문을 안 만든다"
    assert _m7(songs, factor=2) < 0.0
    assert _m7(songs, floor=SUSTAINED_FLOOR) < 0.0


def test_진짜_m7은_두_자에서_더_커진다() -> None:
    """**같은 자가 반대로 움직여야 한다.** 둘 다 죽이면 자가 신호를 죽이는 것뿐이다."""
    songs = corpus(smeared=False)
    base = _m7(songs)
    assert base > 0.5
    assert _m7(songs, factor=2) > base
    assert _m7(songs, floor=SUSTAINED_FLOOR) > base


def test_인접_이웃으로는_못_가른다() -> None:
    """**첫 판이 인접 이웃을 썼고 못 잡았다** (D-0302).

    50/50 블렌드 창은 양옆 순수 화음과 코사인이 0.93쯤이라 문턱 0.90을 통과한다.
    건너뛴 이웃은 잡는다 — 이 시험이 그 차이를 고정한다.
    """
    songs = corpus(smeared=True)
    unit = [
        series / np.maximum(np.linalg.norm(series, axis=1, keepdims=True), 1e-12)
        for series in songs
    ]
    adjacent = np.concatenate([np.einsum("ij,ij->i", rows[:-1], rows[1:]) for rows in unit])
    skipped = np.concatenate([np.einsum("ij,ij->i", rows[:-2], rows[2:]) for rows in unit])
    assert float(np.median(adjacent)) > 0.90, "인접 이웃이 이미 0.90 밑이면 이 함정이 아니다"
    assert float(np.median(skipped)) < float(np.median(adjacent))


def test_창이_셋_미만이면_아무것도_남기지_않는다() -> None:
    assert not sustained_mask(np.zeros((2, DEGREE_COUNT))).any()
    assert not sustained_mask(np.zeros((0, DEGREE_COUNT))).any()
    # 양 끝 창은 건너뛸 이웃이 한쪽뿐이라 빠진다.
    keep = sustained_mask(np.ones((5, DEGREE_COUNT)), floor=0.0)
    assert list(keep) == [False, True, True, True, False]


def test_잴_창이_없으면_None이다() -> None:
    """**0.0을 내지 않는다** (GR-0.5). 0.0은 «차가 없다»로 읽히고 그것이 거짓이다."""
    assert difference(np.zeros((0, DEGREE_COUNT)), seed=1) is None
    # 평평한 창만 있으면 판정이 하나도 안 남는다.
    assert difference(np.full((8, DEGREE_COUNT), 0.3), seed=1) is None


def test_곡_경계를_넘어_묶지_않는다() -> None:
    """넘어서 묶으면 어떤 곡의 마지막 창과 다음 곡 첫 창이 한 화음으로 평균된다."""
    left = np.tile(_vector(0, "maj"), (3, 1))
    right = np.tile(_vector(6, "maj"), (3, 1))
    joined = stack([left, right], factor=3)
    assert joined.shape == (2, DEGREE_COUNT)
    assert np.allclose(joined[0] / joined[0].sum(), left[0] / left[0].sum())


def test_보고가_창_길이와_근음_경고를_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**창 길이가 화면에 없었다** (D-0302). 같은 표를 다른 창으로 두 번 내면 못 가른다."""
    series = tmp_path / "keys-000003.series"
    for index, frame in enumerate(corpus(smeared=True, songs=4)):
        write_series(series, f"곡{index}.flac", "other", frame.astype(np.float32))
    out = tmp_path / "산출"
    assert main(["eval", "chord-quality", "--out", str(out), "--series", str(series)]) == 0
    printed = capsys.readouterr().out
    assert "근음을 버린다" in printed, "근음 없는 스템을 경고하지 않는다"
    assert "묶기1" in printed
    assert f"문턱{FLOORS[0]:.2f}" in printed
    record = json.loads(next((out / "eval").glob("*-chord-quality.eval.json")).read_text("utf-8"))
    assert set(record["grouped"]) == {f"묶기{factor}" for factor in GROUPS}
    assert record["window_seconds"] == "?", "선언이 없으면 물음표다 — 0으로 채우지 않는다"


def test_선언이_있으면_창_길이를_읽는다(tmp_path: Path) -> None:
    series = tmp_path / "keys-000004.series"
    write_series(series, "곡.flac", "other", np.ones((4, DEGREE_COUNT), dtype=np.float32))
    (series / f"{series.name}.manifest.json").write_text(
        json.dumps({"window_seconds": 2.0}), encoding="utf-8"
    )
    assert series_settings(series)["window_seconds"] == 2.0
    assert series_settings(tmp_path / "없음") == {}
    assert len(load_series(series, "other")) == 1


def test_빈_칸_표식이_수가_아니다() -> None:
    """표에 `—`가 들어가려면 열이 문자열이어야 한다. 수 형식이면 0으로 채워진다."""
    assert MISSING == "—"


# ---------------- 스템마다 무엇을 놓치는지 찍는다 (D-0302 · D-0303)


def test_스템별_경고가_갈린다() -> None:
    """**둘은 다른 결함이다.** 근음 누락은 판정을 기울이고 단선율은 뜻을 없앤다.

    `bass`는 근음을 담으므로 교란 1 경고가 없지만 **단선율이라 화음 판정 대상이 아니다** —
    첫 판에서 근음만 물어 `bass`가 경고 없이 통과했다 (D-0303).
    """
    assert warnings("mix") == []
    assert [len(warnings(stem)) for stem in ("other", "bass", "vocals")] == [1, 1, 2]
    assert "근음을 버린다" in warnings("other")[0]
    assert "단선율" in warnings("bass")[0]


def test_단선율_경고가_인용하지_말라고_적는다() -> None:
    """**수가 나오는 것과 뜻이 있는 것은 다르다.** `argmax`는 늘 하나를 고른다."""
    assert "인용하지 않는다" in warnings("bass")[0]


@pytest.mark.parametrize("stem", SERIES_STEMS)
def test_시계열이_있는_스템만_고를_수_있다(stem: str) -> None:
    """**D-0106이 조합은 안 뽑기로 했다.** `other+bass`를 고르면 «창이 없다»로 끝난다."""
    assert stem in ("mix", "other", "bass", "vocals")
    assert "+" not in stem
