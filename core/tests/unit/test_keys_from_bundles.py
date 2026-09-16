"""묶음에서 옛 `keys` 규격을 다시 쓴다 (O-63 · D-0211).

**다운스트림을 안 고친 것이 설계다.** 그래서 검사는 새 코드가 아니라 **옛 로더가
새 산출물을 읽는지**를 본다 — `find_keys_store` · `load_stem_priors` ·
`find_series_root` · `load_transition_priors`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from hathor.application.keys_from_bundles import (
    LEGACY_CHROMA,
    keys_from_bundle,
    replay_guard,
)
from hathor.domain.services.key_estimation import (
    HARMONIC_STRENGTH,
    estimate_key,
    subtract_harmonics,
)
from hathor.infrastructure.chroma_series_store import find_series_root, load_transition_priors
from hathor.infrastructure.keys_jsonl_store import find_keys_store, load_stem_priors
from hathor.infrastructure.track_bundle_store import BUNDLE_DIRNAME, TrackBundleStore
from hathor.interfaces.cli.main import main

if TYPE_CHECKING:
    from pathlib import Path

C_MAJOR = np.asarray([6, 0.2, 3, 0.2, 4, 3, 0.2, 5, 0.2, 3, 0.2, 2], dtype=np.float32)
C_MAJOR = C_MAJOR / C_MAJOR.sum()


def _series(count: int = 16) -> np.ndarray:
    """도수가 실제로 바뀌는 시계열. 한 도수뿐이면 전이 사전이 빈다 (D-0107)."""
    rows = np.full((count, 12), 0.01, dtype=np.float32)
    for index in range(count):
        rows[index, (0, 5, 7, 9)[index % 4]] = 1.0
    return rows / rows.sum(axis=1, keepdims=True)


def _arrays() -> dict[str, np.ndarray]:
    arrays = {f"chroma/{name}": C_MAJOR for name in ("mixture", "bass", "drums", "other", "vocals")}
    arrays.update({f"chroma_series/{name}": _series() for name in ("mixture", "other", "bass")})
    # **MERT가 묶음 대부분이다.** 읽는 쪽이 안 여는지 보려고 넣는다.
    arrays["mert/other/layer03"] = np.zeros((4, 768), dtype=np.float32)
    return arrays


def _write_bundles(
    ingest: Path, names: list[str], manifest: dict[str, object] | None = None
) -> None:
    store = TrackBundleStore(ingest / BUNDLE_DIRNAME)
    for name in names:
        store.write(name, _arrays(), manifest or {})


# ------------------------------------------------------------------ 행


def test_옛_규격의_행을_만든다() -> None:
    made = keys_from_bundle("가.mp3", _arrays(), {}, profile="temperley")

    assert made.row["key"] == "C major"
    assert made.row["source_key"] == "가.mp3"
    stems = made.row["stems"]
    assert isinstance(stems, dict)
    assert stems["other"]["full"] == pytest.approx(C_MAJOR.tolist(), abs=1e-5)
    assert set(made.series) == {"mix", "other", "bass"}


def test_조합을_지어내지_않는다() -> None:
    """크로마는 신호의 합에 대해 선형이 아니다. **없는 것은 없다고 둔다.**"""
    made = keys_from_bundle("가.mp3", _arrays(), {}, profile="temperley")

    assert made.row["stem_sets"] == ["bass", "other", "vocals"]
    stems = made.row["stems"]
    assert isinstance(stems, dict) and "other+bass" not in stems
    assert made.row["halves"] is False


def test_manifest가_안_적은_옛_묶음은_D0203의_기본값이다() -> None:
    made = keys_from_bundle("가.mp3", _arrays(), {}, profile="temperley")
    assert made.row["harmonic"] == LEGACY_CHROMA["chroma_harmonic"] == 0.5


def test_manifest가_적은_조건이_이긴다() -> None:
    made = keys_from_bundle("가.mp3", _arrays(), {"chroma_harmonic": 0.0}, profile="temperley")
    assert made.row["harmonic"] == 0.0


def test_믹스_크로마가_없으면_올린다() -> None:
    """으뜸음이 없으면 `load_stem_priors`가 행을 **조용히 버린다.** 여기서 올린다."""
    arrays = _arrays()
    del arrays["chroma/mixture"]
    with pytest.raises(KeyError):
        keys_from_bundle("가.mp3", arrays, {}, profile="temperley")


def test_ingest_all이_크로마_조건을_manifest에_적는다(tmp_path: Path) -> None:
    """**D-0203은 기본값에 기대고 안 적었다.** 뒤로 뽑는 묶음은 스스로 말한다."""
    from datetime import UTC, datetime

    from hathor.application.ingest_all import IngestAll
    from hathor.domain.entities.audio_stream import AudioStreamProperties
    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.domain.entities.track_tags import TrackTags

    class Decoder:
        def decode(self, path):
            return np.random.default_rng(1).standard_normal((2, 44100 * 3)).astype(np.float32)

    class Separator:
        def separate(self, waveform):
            return {name: waveform * 0.5 for name in ("bass", "drums", "other", "vocals")}

    class Extractor:
        layers = (3,)

        def extract_layers(self, waveform):
            return {"layer03": np.zeros((2, 8), dtype=np.float32)}

    class Pitch:
        def track(self, waveform, *, sample_rate, fmin, fmax):
            return np.zeros(4, dtype=np.float32)

    track = ScannedTrack(
        source_key="가.mp3",
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            sample_rate_hz=44100, channels=2, duration_ms=3000, bitrate_bps=320000, codec="mp3"
        ),
        tags=TrackTags(
            title="가",
            artist="누구",
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        ),
        raw_frame_names=(),
    )
    job = IngestAll(Decoder(), Separator(), Extractor(), Pitch(), library_root=tmp_path)
    bundle = next(iter(job.run([track])))

    assert bundle.manifest["chroma_harmonic"] == HARMONIC_STRENGTH
    assert bundle.manifest["chroma_series_seconds"] == LEGACY_CHROMA["chroma_series_seconds"]
    made = keys_from_bundle("가.mp3", bundle.arrays, bundle.manifest, profile="temperley")
    assert made.row["harmonic"] == HARMONIC_STRENGTH


# ---------------------------------------------------- 옛 로더가 읽는가


def test_생성_경로의_옛_로더가_새_산출물을_읽는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = tmp_path / "var" / "ingest"
    _write_bundles(ingest, ["가.mp3", "나.mp3"])

    assert main(["ingest", "keys", "--from-bundles", "--out", str(ingest)]) == 0

    store = find_keys_store(tmp_path, "other")
    assert store is not None
    priors = load_stem_priors(store, "other")
    assert set(priors) == {"가.mp3", "나.mp3"}
    assert priors["가.mp3"][1] == 0  # C

    series = find_series_root(tmp_path, "other")
    assert series is not None and series.name == store.name.replace(".keys.jsonl", ".series")
    assert set(load_transition_priors(series, "other", ["가.mp3", "나.mp3"])) == {
        "가.mp3",
        "나.mp3",
    }
    assert "묶음 2개" in capsys.readouterr().out


def test_반쯤_쓴_파일이_사전으로_안_잡힌다(tmp_path: Path) -> None:
    """행을 못 만들면 `.keys.jsonl`이 **안 남는다.**"""
    ingest = tmp_path / "var" / "ingest"
    store = TrackBundleStore(ingest / BUNDLE_DIRNAME)
    arrays = _arrays()
    del arrays["chroma/mixture"]
    store.write("가.mp3", arrays, {})

    assert main(["ingest", "keys", "--from-bundles", "--out", str(ingest)]) == 2
    assert find_keys_store(tmp_path, "other") is None
    assert not list(ingest.glob("*.tmp"))


def test_묶음이_없으면_말한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ingest", "keys", "--from-bundles", "--out", str(tmp_path)]) == 2
    assert "ingest all" in capsys.readouterr().err


@pytest.mark.parametrize("flag", [["--separate"], ["--harmonic", "0"], ["--harmonic-sweep"]])
def test_안_걸리는_손잡이를_거절한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: list[str]
) -> None:
    _write_bundles(tmp_path, ["가.mp3"])
    assert main(["ingest", "keys", "--from-bundles", "--out", str(tmp_path), *flag]) == 2
    assert flag[0] in capsys.readouterr().err


# ------------------------------------------------ 배음을 두 번 빼지 않는다


def test_배음_0_크로마는_요청대로_뺀다() -> None:
    rows = [{"chroma": [1.0] * 12, "harmonic": 0.0}]
    assert replay_guard(rows, 0.5, sweep=False) == 0.5
    assert replay_guard(rows, 0.5, sweep=True) == 0.5


def test_이미_뺀_크로마는_더_안_뺀다() -> None:
    rows = [{"chroma": [1.0] * 12, "harmonic": 0.5}]
    assert replay_guard(rows, 0.5, sweep=False) == 0.0
    assert "두 번" in str(replay_guard(rows, 0.3, sweep=False))
    assert "두 번" in str(replay_guard(rows, 0.5, sweep=True))


def test_강도가_섞인_파일은_거절한다() -> None:
    rows = [{"chroma": [1.0] * 12, "harmonic": 0.0}, {"chroma": [1.0] * 12, "harmonic": 0.5}]
    assert isinstance(replay_guard(rows, 0.5, sweep=False), str)


def test_새_산출물에_sweep을_걸면_거절한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**D-0201의 표를 새 산출물로 재현하려 들면 감산이 두 번 걸린다.**"""
    ingest = tmp_path / "var" / "ingest"
    _write_bundles(ingest, ["가.mp3"])
    main(["ingest", "keys", "--from-bundles", "--out", str(ingest)])
    saved = next(ingest.glob("*.keys.jsonl"))

    code = main(["ingest", "keys", "--replay", str(saved), "--harmonic-sweep"])

    assert code == 2
    assert "두 번" in capsys.readouterr().err


def test_추출_때_뺀_것과_재판정_때_뺀_것이_같다() -> None:
    """**옛 파일과 새 파일을 대조할 수 있는 근거다.**

    감산은 선형 뒤 0 자르기이고 정규화는 양의 배율이라 순서를 바꿔도 같다.
    옛 파일(배음 0)을 `--harmonic 0.5`로 재판정한 것과 묶음(배음 0.5로 추출)을
    그대로 읽은 것이 **같은 조성을 내야 한다.**
    """
    rng = np.random.default_rng(211)
    for _ in range(50):
        totals = rng.gamma(0.6, size=12)
        at_extraction = subtract_harmonics(totals, HARMONIC_STRENGTH)
        at_extraction = at_extraction / at_extraction.sum()
        raw = totals / totals.sum()
        at_replay = subtract_harmonics(raw, HARMONIC_STRENGTH)
        at_replay = at_replay / at_replay.sum()

        assert at_extraction == pytest.approx(at_replay, abs=1e-12)
        left = estimate_key(at_extraction.astype(np.float32), profile="temperley")
        right = estimate_key(at_replay.astype(np.float32), profile="temperley")
        assert left.key == right.key


def test_doctor가_묶음이_있으면_재생성을_권한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**가진 크로마를 두고 GPU 1시간 40분을 시키고 있었다** (D-0211)."""
    from hathor.shared.config.paths import LIBRARY_ROOT_ENV, PATCH_DIR_ENV

    ingest = tmp_path / "var" / "ingest"
    _write_bundles(ingest, ["가.mp3"])
    monkeypatch.setattr("hathor.interfaces.cli.doctor.repo_root", lambda: tmp_path)
    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")

    main(["doctor"])
    out = capsys.readouterr().out

    assert "--from-bundles" in out
    assert "artifacts-pull" not in out
    manifest = json.loads(next((ingest / BUNDLE_DIRNAME).glob("*.manifest.json")).read_text())
    assert manifest["source_key"] == "가.mp3"
