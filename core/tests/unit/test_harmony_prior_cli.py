"""`eval harmony-prior` CLI 통합 테스트.

반쪽 크로마 JSONL을 합성해 판정 경로를 전부 돌린다. **음원도 GPU도 쓰지 않는다** —
이 명령이 광인사에서 도는 것이 설계 의도이며 테스트가 그것을 고정한다.
"""

import json

import numpy as np

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
