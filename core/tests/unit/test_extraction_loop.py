"""추출 배치 공용 루프 (D-0250 · D-0417).

### 왜 이 시험이 생겼나

**`--force`로 다시 돌리면 색인에 같은 키가 두 줄이 됐다.** 색인은 덧붙이는 기록이고
(재개가 그 위에 선다) `--force`는 npz만 덮었다. 그 줄이 남으면 **읽는 쪽이 전부
멈춘다** — `eval retrieval`·`search`·`eval fusion`이 중복 키를 거부한다.

실물에서 났다. 1004곡 79분을 돌린 직후 판정 네 줄이 모두 같은 자리에서 죽었고,
원인은 **그 전에 돌린 3곡 시험**이었다. 사람이 `ingest compact`를 기억해 쳐야만
다음 명령이 도는 구조였다 — **기억에 기대는 것은 관문이 아니다** (D-0126).

여기는 MERT·MFCC·CLAP·MusicFM이 **함께 쓰는 한 자리**다 (D-0043). 넷 다 같은
함정을 팠고 여기서 치우면 넷 다 낫는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np

from hathor.domain.entities.track_features import TrackFeatures
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.extraction import drive_extraction

if TYPE_CHECKING:  # pragma: no cover - 형만 쓴다
    from hathor.application.extract_features import ExtractFeatures
    from hathor.domain.entities.scanned_track import ScannedTrack


class _Extractor:
    """`ExtractFeatures`의 자리를 메운다 — 루프가 보는 것은 이 셋뿐이다.

    **상수 프레임을 안 낸다.** `seed`로 값이 달라지므로 *«나중 줄을 남긴다»*를
    시험이 실제로 확인할 수 있다 (D-0069).
    """

    def __init__(self, keys: tuple[str, ...], *, seed: int) -> None:
        self._keys = keys
        self._seed = seed
        self.processed = 0
        self.failed: list[tuple[str, str]] = []

    def run(self, tracks: list[ScannedTrack]) -> object:
        del tracks
        for index, key in enumerate(self._keys):
            self.processed += 1
            yield TrackFeatures(
                source_key=key,
                mixture=np.full((3, 4), float(self._seed + index), dtype=np.float32),
                stems={},
            )


def _records(store: NpzFeatureStore) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in store.index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _drive(root: Path, keys: tuple[str, ...], *, seed: int) -> None:
    store = NpzFeatureStore(root)
    fake = cast("ExtractFeatures", _Extractor(keys, seed=seed))
    assert drive_extraction(fake, store, [], seconds_per_track=1.0) == 0


def test_다시_돌려도_색인에_같은_키가_두_줄_안_된다(tmp_path: Path) -> None:
    """**`--force`가 npz만 덮고 색인은 덧붙였다** (D-0417).

    3곡을 먼저 돌리고 1004곡을 `--force`로 돌린 실물 그대로다. 겹친 3곡이
    두 줄로 남아 뒤따르는 명령이 전부 죽었다.
    """
    _drive(tmp_path, ("가.mp3", "나.mp3"), seed=10)
    _drive(tmp_path, ("가.mp3", "나.mp3", "다.mp3"), seed=20)

    found = _records(NpzFeatureStore(tmp_path))
    keys = [record["source_key"] for record in found]

    assert keys == ["가.mp3", "나.mp3", "다.mp3"], f"색인이 {len(keys)}줄이다: {keys}"


def test_겹치면_나중에_쓴_것을_남긴다(tmp_path: Path) -> None:
    """**npz는 덮어써졌으므로 파일과 짝이 맞는 것은 나중 줄이다.**

    먼저 쓴 줄을 남기면 색인이 가리키는 값과 npz 안의 값이 **조용히 어긋난다** —
    아무 데서도 안 죽고 유사도만 틀린다.
    """
    _drive(tmp_path, ("가.mp3",), seed=10)
    _drive(tmp_path, ("가.mp3",), seed=20)

    store = NpzFeatureStore(tmp_path)
    (written,) = store.iter_vectors()
    assert float(written[1]["mixture"][0][0]) == 20.0, "먼저 쓴 값이 남았다"


def test_깨끗하면_정리했다고_안_떠든다(tmp_path: Path, capsys: object) -> None:
    """**거짓 경보를 늘리지 않는다** (GR-0.8). 한 번만 돌린 배치는 치울 것이 없다."""
    _drive(tmp_path, ("가.mp3", "나.mp3"), seed=10)

    printed = capsys.readouterr().out  # type: ignore[attr-defined]  # pytest 픽스처
    assert "색인 정리" not in printed, printed


def test_치웠으면_몇_줄을_치웠는지_말한다(tmp_path: Path, capsys: object) -> None:
    """**말없이 지우지 않는다** (D-0203). 색인 줄이 준 것은 사람이 알아야 한다."""
    _drive(tmp_path, ("가.mp3",), seed=10)
    capsys.readouterr()  # type: ignore[attr-defined]  # 앞 판 출력을 버린다
    _drive(tmp_path, ("가.mp3",), seed=20)

    printed = capsys.readouterr().out  # type: ignore[attr-defined]  # pytest 픽스처
    assert "색인 정리: 2줄 -> 1줄 (중복 1)" in printed, printed
