"""`eval harmony-prior` CLI 통합 테스트.

반쪽 크로마 JSONL을 합성해 판정 경로를 전부 돌린다. **음원도 GPU도 쓰지 않는다** —
이 명령이 광인사에서 도는 것이 설계 의도이며 테스트가 그것을 고정한다.
"""

import json

import numpy as np
import pytest

from hathor.interfaces.cli.main import main

DEGREES = 12


def write_keys(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def synth_rows(count, *, informative, seed=20260819, margin=0.2):
    """곡 고유 신호가 있는/없는 합성 코퍼스."""
    rng = np.random.default_rng(seed)
    shared = rng.dirichlet(np.full(DEGREES, 0.4))
    rows = []
    for index in range(count):
        latent = rng.dirichlet(np.full(DEGREES, 0.4)) if informative else shared
        rows.append(
            {
                "source_key": f"곡{index:03d}.flac",
                "key": "C major",
                "correlation": 0.9,
                "runner_up": "A minor",
                "margin": margin,
                "chroma_head": [
                    round(float(value), 6)
                    for value in 0.75 * latent + 0.25 * rng.dirichlet(np.full(DEGREES, 5.0))
                ],
                "chroma_tail": [
                    round(float(value), 6)
                    for value in 0.75 * latent + 0.25 * rng.dirichlet(np.full(DEGREES, 5.0))
                ],
                "key_head": "C major",
                "margin_head": margin,
            }
        )
    return rows


def test_신호가_있으면_정보_있음을_낸다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", synth_rows(120, informative=True))
    assert main(["eval", "harmony-prior", "--replay", str(path)]) == 0
    out = capsys.readouterr().out
    assert "정보 있음" in out
    # **귀무 λ*의 위치는 검사하지 않는다** (D-0065). 독립 자료에서도 0이 아니다.
    # 낙폭이 자기선에 비해 작은지가 검사할 것이다.
    assert "귀무 λ*" in out


def test_신호가_없으면_정보_없음을_낸다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", synth_rows(120, informative=False))
    assert main(["eval", "harmony-prior", "--replay", str(path)]) == 0
    out = capsys.readouterr().out
    # **λ*의 위치는 검사하지 않는다** (D-0065). 신호가 없으면 곡선이 평평해
    # argmin이 부동소수점 잡음에 흔들린다. 판정 자체가 검사할 것이다.
    assert "정보 없음" in out


def test_반쪽_크로마가_없으면_안내하고_실패한다(tmp_path, capsys):
    rows = [{"source_key": "a.flac", "key": "C major", "chroma": [1 / 12] * DEGREES}]
    path = write_keys(tmp_path / "keys.jsonl", rows)
    assert main(["eval", "harmony-prior", "--replay", str(path)]) == 1
    assert "--halves" in capsys.readouterr().err


def test_조건_플래그가_리포트에_반영된다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", synth_rows(40, informative=True, margin=0.01))
    assert (
        main(
            [
                "eval",
                "harmony-prior",
                "--replay",
                str(path),
                "--harmonic",
                "0.3",
                "--smoothing",
                "0.02",
                "--blend-steps",
                "6",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "배음 0.3" in out
    assert "평활 0.02" in out
    # 격차 0.01은 기본 하한 0.05 미만이므로 전량 애매로 잡혀야 한다.
    assert "애매 40곡" in out


def test_애매_제외가_곡_수를_줄인다(tmp_path, capsys):
    rows = synth_rows(60, informative=True)
    for row in rows[:20]:
        row["margin_head"] = 0.01
    path = write_keys(tmp_path / "keys.jsonl", rows)
    assert main(["eval", "harmony-prior", "--replay", str(path), "--confident-only"]) == 0
    out = capsys.readouterr().out
    assert "곡 40개" in out
    assert "애매 제외" in out


def test_곡이_하나면_거부한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", synth_rows(1, informative=True))
    assert main(["eval", "harmony-prior", "--replay", str(path)]) == 1
    assert "1개다" in capsys.readouterr().err


# ------------------------------------------- 스템 조합 (O-27 (a) · D-0073)


def stem_rows(count, *, stem_set="other+bass", informative=True, seed=7):
    """분리 산출물 형태. 전체 믹스와 스템 조합이 한 행에 함께 있다."""
    rows = synth_rows(count, informative=informative, seed=seed)
    rng = np.random.default_rng(seed + 1)
    for row in rows:
        latent = rng.dirichlet(np.full(DEGREES, 0.3))
        row["separated"] = True
        row["aggregate"] = "mean"
        row["halves"] = True
        row["limit"] = count
        row["stems"] = {
            stem_set: {
                side: [
                    round(float(value), 6)
                    for value in 0.8 * latent + 0.2 * rng.dirichlet(np.full(DEGREES, 5.0))
                ]
                for side in ("head", "tail")
            }
        }
    return rows


def test_스템_조합을_고르면_그것으로_판정한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", stem_rows(120))
    assert main(["eval", "harmony-prior", "--replay", str(path), "--stem-set", "other+bass"]) == 0
    out = capsys.readouterr().out
    assert "스템 other+bass" in out


def test_스템을_안_고르면_전체_믹스를_쓴다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", stem_rows(120))
    assert main(["eval", "harmony-prior", "--replay", str(path)]) == 0
    assert "스템 전체 믹스" in capsys.readouterr().out


def test_같은_파일에서_조합에_따라_결과가_다르다(tmp_path, capsys):
    """**전체 믹스와 스템 조합이 같은 수를 내면 배관이 안 이어진 것이다.**"""
    path = write_keys(tmp_path / "keys.jsonl", stem_rows(120))
    main(["eval", "harmony-prior", "--replay", str(path)])
    plain = capsys.readouterr().out
    main(["eval", "harmony-prior", "--replay", str(path), "--stem-set", "other+bass"])
    stemmed = capsys.readouterr().out
    assert plain != stemmed


def test_없는_조합을_고르면_안내하고_실패한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", stem_rows(20))
    assert main(["eval", "harmony-prior", "--replay", str(path), "--stem-set", "drums"]) == 1
    assert "--separate" in capsys.readouterr().err


def test_분리_안_된_산출물에_조합을_고르면_실패한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", synth_rows(20, informative=True))
    assert main(["eval", "harmony-prior", "--replay", str(path), "--stem-set", "other"]) == 1
    assert "--separate" in capsys.readouterr().err


# ------------------------------------------------ 산출물 조건 기록 (D-0073)


def test_doctor가_산출물_조건을_요약한다(tmp_path, monkeypatch, capsys):
    from hathor.interfaces.cli.main import main as cli
    from hathor.shared.config.paths import LIBRARY_ROOT_ENV, PATCH_DIR_ENV

    ingest = tmp_path / "var" / "ingest"
    write_keys(ingest / "keys-A.keys.jsonl", stem_rows(3))
    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: tmp_path)
    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")
    cli(["doctor"])
    out = capsys.readouterr().out
    assert "keys-A.keys.jsonl" in out
    assert "mean" in out
    assert "분리" in out


def test_조건이_없는_옛_산출물도_다룬다(tmp_path, monkeypatch, capsys):
    from hathor.interfaces.cli.main import main as cli
    from hathor.shared.config.paths import LIBRARY_ROOT_ENV, PATCH_DIR_ENV

    ingest = tmp_path / "var" / "ingest"
    write_keys(ingest / "keys-old.keys.jsonl", synth_rows(2, informative=True))
    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: tmp_path)
    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")
    cli(["doctor"])
    assert "조건 미기록" in capsys.readouterr().out


# ------------------------------------------ 스템 사전 조회 (D-0074)


def prior_rows(count, *, stem_set="other", seed=11):
    """생성 경로가 읽는 형태. `full`이 있고 `key`가 전체 믹스 추정이다."""
    rng = np.random.default_rng(seed)
    rows = []
    for index in range(count):
        latent = rng.dirichlet(np.full(DEGREES, 0.3))
        rows.append(
            {
                "source_key": f"가수-곡{index}.mp3",
                "key": "C major",
                "aggregate": "mean",
                "separated": True,
                "halves": False,
                "stems": {
                    stem_set: {"full": [round(float(v), 6) for v in latent]},
                },
            }
        )
    return rows


def test_스템_사전을_찾고_읽는다(tmp_path):
    from hathor.interfaces.cli.main import find_stem_prior_store, load_stem_priors

    ingest = tmp_path / "var" / "ingest"
    write_keys(ingest / "keys-20260101T000000Z.keys.jsonl", synth_rows(3, informative=True))
    write_keys(ingest / "keys-20260821T000000Z.keys.jsonl", prior_rows(5))

    found = find_stem_prior_store(tmp_path, "other")
    assert found is not None
    assert found.name == "keys-20260821T000000Z.keys.jsonl"

    table = load_stem_priors(found, "other")
    assert len(table) == 5
    vector, tonic = table["가수-곡0.mp3"]
    assert len(vector) == DEGREES
    assert tonic == 0


def test_full이_없으면_사전으로_치지_않는다(tmp_path):
    """반쪽만 있는 판정용 산출물은 생성에 못 쓴다."""
    from hathor.interfaces.cli.main import find_stem_prior_store

    ingest = tmp_path / "var" / "ingest"
    write_keys(ingest / "keys-A.keys.jsonl", stem_rows(3))
    assert find_stem_prior_store(tmp_path, "other+bass") is None


def test_다른_조합을_고르면_못_찾는다(tmp_path):
    from hathor.interfaces.cli.main import find_stem_prior_store

    ingest = tmp_path / "var" / "ingest"
    write_keys(ingest / "keys-A.keys.jsonl", prior_rows(3, stem_set="other"))
    assert find_stem_prior_store(tmp_path, "other+bass+vocals") is None


def test_산출물이_없으면_None이다(tmp_path):
    from hathor.interfaces.cli.main import find_stem_prior_store

    assert find_stem_prior_store(tmp_path, "other") is None


def test_으뜸음이_다르면_도수_공간에서_합친다(tmp_path):
    """**피치클래스 공간에서 더하면 조성이 겹쳐 뭉개진다** (D-0063).

    같은 도수 분포를 서로 다른 조성으로 저장해 두고 합치면, 도수 공간에서는
    원래 모양이 살아 있어야 한다.
    """
    from hathor.domain.services.harmony_prior import merge_degree_priors
    from hathor.interfaces.cli.main import load_stem_priors

    shape = np.zeros(DEGREES)
    shape[0], shape[7] = 0.6, 0.4
    rows = []
    for index, (key_text, tonic) in enumerate((("C major", 0), ("F# major", 6))):
        rows.append(
            {
                "source_key": f"곡{index}.mp3",
                "key": key_text,
                "stems": {"other": {"full": [float(v) for v in np.roll(shape, tonic)]}},
            }
        )
    path = write_keys(tmp_path / "keys.jsonl", rows)
    table = load_stem_priors(path, "other")
    merged = merge_degree_priors(list(table.values()))
    assert float(merged[0]) == pytest.approx(0.6, abs=1e-6)
    assert float(merged[7]) == pytest.approx(0.4, abs=1e-6)
