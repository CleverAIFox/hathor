import argparse
import json
from pathlib import Path

import pytest

from hathor.domain.entities.scan_event import ScanEventKind
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.interfaces.cli.main import main
from tests.conftest import scanned_track


def test_cli_writes_identical_output_for_same_seed(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        code = main(
            [
                "generate",
                "--seed",
                "42",
                "--dry-run",
                "--stages",
                "structure,harmony",
                "--out",
                str(out),
            ]
        )
        assert code == 0
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    ja.pop("job"), jb.pop("job")
    assert ja == jb


def test_cli_prints_when_no_out(capsys):
    assert main(["generate", "--seed", "1", "--dry-run"]) == 0
    assert "harmony" in capsys.readouterr().out


def test_cli_requires_dry_run(capsys):
    """**길이 둘인데 하나만 말하면 없는 길이 된다** (D-0403).

    D-0052가 MIDI 경로를 붙인 뒤에도 이 자리가 *«아직 dry-run 경로만 구현되어 있다
    (P0)»*라고 적고 있었고, **그것을 읽은 사람이 소리를 못 듣는다고 판단했다.**
    """
    assert main(["generate", "--seed", "1"]) == 2
    said = capsys.readouterr().err

    assert "--midi" in said, "쓸 수 있는 길을 안 말한다"
    assert "--dry-run" in said
    assert "아직" not in said, "구현된 것을 안 됐다고 말한다"


def test_cli_rejects_unknown_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", "mixing"])


def test_cli_rejects_empty_stage():
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "1", "--dry-run", "--stages", " , "])


def test_ingest_features_without_scan_output(tmp_path, capsys):
    """스캔 산출물이 없으면 모델을 만들기 전에 빠져나온다."""
    assert main(["ingest", "features", "--out", str(tmp_path)]) == 2
    assert "스캔 산출물이 없다" in capsys.readouterr().err


def test_ingest_features_skips_completed(tmp_path, capsys, monkeypatch):
    """전부 추출된 상태면 GPU 구현체를 만들지 않고 끝난다."""
    from hathor.infrastructure.jsonl_scan_store import JsonlScanStore
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    track = _fake_track("a.mp3")
    # **반은 객체 하나다** (D-0264). 정본에서 가져와 붙여도 `main`이 보는 것과 같은
    # 것이며, `main`을 통해 읽으면 «`main`이 그것을 내보낸다»에 기대게 된다.
    monkeypatch.setattr(JsonlScanStore, "read_tracks", lambda self: iter([track]))
    index = NpzFeatureStore(tmp_path).index_path
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"source_key": "a.mp3"}) + "\n", encoding="utf-8")

    assert main(["ingest", "features", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "건너뛴다" in out
    assert "처리할 곡이 없다" in out


def _fake_track(source_key: str) -> ScannedTrack:
    """조립은 `tests.conftest.scanned_track` 하나다 (D-0264)."""
    return scanned_track(source_key)


# ---------------------------------------------------------------- ingest compact (O-7(D-0022))


def _seed_features(root, keys, *, duplicates=()):
    """인덱스와 npz를 갖춘 산출물 디렉터리를 만든다."""
    import numpy as np

    from hathor.domain.entities.track_features import TrackFeatures
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    store = NpzFeatureStore(root)
    for key in keys:
        embedding = np.zeros((2, 768), dtype=np.float32)
        store.write_track(
            TrackFeatures(
                source_key=key,
                mixture=embedding,
                stems={name: embedding for name in ("bass", "drums", "other", "vocals")},
            )
        )
    for key in duplicates:
        embedding = np.zeros((5, 768), dtype=np.float32)
        store.write_track(
            TrackFeatures(
                source_key=key,
                mixture=embedding,
                stems={name: embedding for name in ("bass", "drums", "other", "vocals")},
            )
        )
    return store


def test_compact_without_index_exits_2(tmp_path, capsys):
    """산출물이 없는데 조용히 성공하면 잘못된 디렉터리를 짚은 것을 못 알아챈다."""
    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 2
    assert "인덱스가 없다" in capsys.readouterr().err


def test_compact_dry_run_reports_without_writing(tmp_path, capsys):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"], duplicates=["a.mp3"])
    before = store.index_path.read_bytes()

    assert main(["ingest", "compact", "--out", str(tmp_path), "--dry-run"]) == 0

    assert "중복 1줄" in capsys.readouterr().out
    assert store.index_path.read_bytes() == before


def test_compact_removes_duplicates(tmp_path, capsys):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"], duplicates=["a.mp3"])

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0

    assert store.completed_keys() == {"a.mp3", "b.mp3"}
    assert "중복 제거 1줄" in capsys.readouterr().out


def test_compact_drops_orphan_records(tmp_path, capsys):
    """npz가 없는 기록이 남으면 재개가 그 곡을 영영 건너뛴다."""
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"])
    next(store.vectors_dir.glob("*.npz")).unlink()

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0

    assert len(store.completed_keys()) == 1
    assert "npz 없는 기록 제거 1줄" in capsys.readouterr().out


def test_compact_keep_missing_preserves_orphans(tmp_path):
    store = _seed_features(tmp_path, ["a.mp3", "b.mp3"])
    next(store.vectors_dir.glob("*.npz")).unlink()

    assert main(["ingest", "compact", "--out", str(tmp_path), "--keep-missing"]) == 0

    assert store.completed_keys() == {"a.mp3", "b.mp3"}


def test_compact_reports_no_change(tmp_path, capsys):
    _seed_features(tmp_path, ["a.mp3"])
    main(["ingest", "compact", "--out", str(tmp_path)])

    assert main(["ingest", "compact", "--out", str(tmp_path)]) == 0
    assert "바꿀 것이 없었다" in capsys.readouterr().out


def test_compact_refuses_while_batch_runs(tmp_path, capsys):
    """배치가 도는 중에 인덱스를 다시 쓰면 진행 중인 기록을 잃는다."""
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore

    store = _seed_features(tmp_path, ["a.mp3"])
    with store.batch_lock():
        assert main(["ingest", "compact", "--out", str(tmp_path)]) == 3
    assert "배치가 이미 실행 중이다" in capsys.readouterr().err
    assert NpzFeatureStore(tmp_path).completed_keys() == {"a.mp3"}


def test_features_exits_3_when_batch_locked(tmp_path, capsys):
    """O-7(D-0022) 방어. 두 배치가 겹치면 인덱스에 중복이 쌓인다."""
    store = _seed_features(tmp_path, ["a.mp3"])
    with store.batch_lock():
        assert main(["ingest", "features", "--out", str(tmp_path)]) == 3
    captured = capsys.readouterr().err
    assert "배치가 이미 실행 중이다" in captured
    assert "끝내거나 죽인" in captured


# ------------------------------- 저장된 크로마로 다시 판정한다 (D-0281)


def test_재판정이_행을_다시_쓴다():
    """**음원도 GPU도 없이 프로파일을 바꿔 본다** (D-0059)."""
    from hathor.application.replay_keys import recompute

    rows: list[dict[str, object]] = [
        {"chroma": [1.0] + [0.0] * 11, "key": "옛 판정", "correlation": 0.0}
    ]

    assert recompute(rows, strength=0.0, profile="temperley") == 1
    assert rows[0]["key"] != "옛 판정"
    assert rows[0]["profile"] == "temperley"


def test_크로마가_없거나_무게가_0이면_그대로_둔다():
    """**0으로 나누면 `numpy`가 조용히 `nan`을 내고 그것이 분포 보고로 간다** (D-0281)."""
    from hathor.application.replay_keys import recompute

    rows: list[dict[str, object]] = [{"key": "그대로"}, {"chroma": [0.0] * 12, "key": "그대로"}]

    assert recompute(rows, strength=0.0, profile="temperley") == 0
    assert [row["key"] for row in rows] == ["그대로", "그대로"]


# ----------------------------------- 조용히 물러나지 않는다 (D-0429)


LYRICS = "첫 구간이다 길게 적어 둔다 여기가 하나\n\n둘째 구간이다 역시 길게 적어 둔다"
"""구간이 둘 이상이어야 `generate`가 받는다 (`MIN_SEGMENTS` · `MIN_SEGMENT_CHARS`)."""


def _scan_store(root: Path, *keys: str) -> None:
    """가사 구간이 둘 이상인 곡 몇 개를 `scan-*.jsonl`로 깔아 둔다."""
    from hathor.infrastructure.jsonl_scan_store import track_as_record

    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for key in keys:
        track = scanned_track(key)
        record = track_as_record(track, ScanEventKind.DISCOVERED)
        tags = record["tags"]
        assert isinstance(tags, dict)
        tags["lyrics_text"] = LYRICS
        rows.append(json.dumps(record, ensure_ascii=False))
    (root / "scan-20260101T000000Z.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_안_걸린_참조곡_낱말을_말한다(tmp_path, capsys):
    """**셋을 대고 하나가 안 걸려도 나머지로 곡이 나왔다** (D-0429).

    「바다가자」가 라이브러리에 없는 줄 모른 채 69곡 퓨전을 돌렸고, 돌아온 줄을
    믿었다. **하나라도 빠지면 퓨전이 달라진다** (D-0011).
    """
    _scan_store(tmp_path / "ingest", "아이유 - 밤편지.mp3", "10CM - 폰서트.mp3")

    code = main(
        [
            "generate",
            "--seed",
            "1",
            "--midi",
            str(tmp_path / "out.mid"),
            "--no-key-estimation",
            "--scan-out",
            str(tmp_path / "ingest"),
            "--reference",
            "아이유",
            "--reference",
            "바다가자",
        ]
    )
    said = capsys.readouterr().err

    assert code == 1, "안 걸린 낱말이 있는데 그냥 만들었다"
    assert "바다가자" in said
    assert "아이유" not in said, "걸린 낱말까지 안 걸렸다고 한다"


def test_하나도_안_걸려도_어느_낱말인지_말한다(tmp_path, capsys):
    _scan_store(tmp_path / "ingest", "아이유 - 밤편지.mp3")

    assert (
        main(
            [
                "generate",
                "--seed",
                "1",
                "--midi",
                str(tmp_path / "out.mid"),
                "--no-key-estimation",
                "--scan-out",
                str(tmp_path / "ingest"),
                "--reference",
                "없는곡",
            ]
        )
        == 1
    )
    assert "없는곡" in capsys.readouterr().err


def _prior_args(**fields: object) -> argparse.Namespace:
    base: dict[str, object] = {"stem_set": "other", "priors": None}
    return argparse.Namespace(**(base | fields))


def test_믹스로_물러난_까닭이_줄에_남는다(monkeypatch, capsys):
    """**「전체 믹스」 한 마디가 세 가지 까닭을 덮고 있었다** (D-0429 · D-0203).

    `--stem-set mix`라 그런 건지, 저장분이 없어 그런 건지, 참조곡이 그 저장분에
    없어 그런 건지 **돌아온 줄로는 구별이 안 됐다.** 산출물은 자기를 설명한다.
    """
    from hathor.interfaces.cli import prior_sources as cli

    monkeypatch.setattr(cli, "_harmony_prior", lambda estimates: (1.0,))

    _, mix = cli._resolve_harmony_prior(_prior_args(stem_set="mix"), [], {})
    assert mix == "전체 믹스 (--stem-set mix)"

    monkeypatch.setattr(cli, "find_keys_store", lambda root, stem_set: None)
    _, gone = cli._resolve_harmony_prior(_prior_args(), ["a.mp3"], {})
    assert gone == "전체 믹스 (스템 저장분 없음)"
    assert "못 찾았다" in capsys.readouterr().err, "조용히 물러났다"


def test_저장분은_있는데_참조곡이_없으면_그렇게_적는다(tmp_path, monkeypatch, capsys):
    from hathor.interfaces.cli import prior_sources as cli

    store = tmp_path / "keys.jsonl"
    store.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli, "_harmony_prior", lambda estimates: (1.0,))
    monkeypatch.setattr(cli, "load_stem_priors", lambda path, stem_set: {})

    _, said = cli._resolve_harmony_prior(_prior_args(priors=store), ["a.mp3"], {})

    assert said == "전체 믹스 (참조곡이 저장분에 없다)"
    assert "참조곡이 스템 저장분에 없다" in capsys.readouterr().err


def test_명시한_사전_경로가_없으면_생성이_죽는다(tmp_path, capsys):
    """**내가 적은 경로가 없으면 오타다** (D-0429).

    `core/`에서 `--priors ../var/ingest/musicfm/keys.jsonl`을 쳤다. 저장소 루트
    기준으로 풀려 엉뚱한 데를 봤고 **전체 믹스로 조용히 물러났다.** 돌아온 줄은
    *«other 스템»*이었고 그걸 믿었다 — 한 판을 통째로 버렸다.

    **메시지는 D-0326이 이미 들고 있다** — `missing_given_path` 하나다 (D-0043).
    """
    _scan_store(tmp_path / "ingest", "아이유 - 밤편지.mp3")

    code = main(
        [
            "generate",
            "--seed",
            "1",
            "--midi",
            str(tmp_path / "out.mid"),
            "--scan-out",
            str(tmp_path / "ingest"),
            "--priors",
            str(tmp_path / "없다.jsonl"),
        ]
    )
    said = capsys.readouterr().err

    assert code == 1, "없는 사전 경로를 주고도 곡이 나왔다"
    assert "--priors" in said
    assert "저장소 루트 기준" in said, "어디를 봤는지 안 말한다"


def test_명시한_시계열_경로가_없어도_죽는다(tmp_path, capsys):
    """같은 규율이다 — `--series`도 내가 적은 것이다."""
    _scan_store(tmp_path / "ingest", "아이유 - 밤편지.mp3")

    assert (
        main(
            [
                "generate",
                "--seed",
                "1",
                "--midi",
                str(tmp_path / "out.mid"),
                "--scan-out",
                str(tmp_path / "ingest"),
                "--series",
                str(tmp_path / "없다"),
            ]
        )
        == 1
    )
    assert "--series" in capsys.readouterr().err
