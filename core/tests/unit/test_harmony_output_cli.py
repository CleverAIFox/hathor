"""`eval harmony-output` CLI 통합 테스트 (O-29 · D-0079).

**인코더 테스트는 배선을 보지 않는다** (D-0047). 서비스가 옳아도 CLI가 인자를
안 넘기면 조용히 기본값으로 돈다 — 그 부류를 여기서 고정한다.

크로마 JSONL을 합성해 전 경로를 돌린다. **음원도 GPU도 쓰지 않는다.**
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from hathor.interfaces.cli.main import load_degree_priors, main

DEGREES = 12
PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def write_keys(path, *, count=40, mix_contrast=0.45, stem_contrast=0.95, seed=11):
    """전체 믹스와 `other` 스템을 한 파일에 담는다. 스템 쪽이 더 뾰족하다."""
    rng = np.random.default_rng(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for index in range(count):
            tonic = int(rng.integers(0, DEGREES))
            shape = rng.dirichlet(np.full(DEGREES, 0.6))
            flat = np.full(DEGREES, 1.0 / DEGREES)
            row = {
                "chroma_mode": "cq",
                "profile": "krumhansl",
                "aggregate": "mean",
                "separated": True,
                "halves": False,
                "source_key": f"아티스트{index % 7}-곡{index:03d}.flac",
                "key": f"{PITCHES[tonic]} major",
                "margin": 0.2,
                "chroma": [
                    round(float(v), 6) for v in (1 - mix_contrast) * flat + mix_contrast * shape
                ],
                "stems": {
                    "other": {
                        "full": [
                            round(float(v), 6)
                            for v in (1 - stem_contrast) * flat + stem_contrast * shape
                        ]
                    }
                },
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


FAST = ["--seeds", "80", "--pairs", "10"]


def test_두_출처를_짝지어_비교한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    assert main(["eval", "harmony-output", "--priors", str(path), *FAST]) == 0
    out = capsys.readouterr().out
    assert "[other]" in out and "[mix]" in out
    assert "짝지은 비교 (mix → other)" in out
    assert "하네스 건전" in out
    # **상한과 바닥이 리포트에 있어야 한다** (O-25 (3)). 없으면 어떤 값도 못 읽는다.
    assert "identical" in out and "onehot" in out and "극한" in out


def test_기준_출처를_끄면_한_쪽만_낸다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    assert main(["eval", "harmony-output", "--priors", str(path), "--against", "none", *FAST]) == 0
    out = capsys.readouterr().out
    assert "[other]" in out
    assert "[mix]" not in out
    assert "짝지은 비교" not in out


def test_마디_수_인자가_실제로_걸린다(tmp_path, capsys):
    """**선언된 인자가 결과를 바꾸는지 본다** (D-0064 · O-25).

    `--bars`가 안 걸리면 `마디 환산`이 8마디 기준으로 남아 조용히 틀린다.
    """
    path = write_keys(tmp_path / "keys.jsonl")
    assert main(["eval", "harmony-output", "--priors", str(path), "--bars", "16", *FAST]) == 0
    assert "16마디" in capsys.readouterr().out


def test_시드가_같으면_같은_수를_낸다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    outputs = []
    for _ in range(2):
        assert main(["eval", "harmony-output", "--priors", str(path), *FAST]) == 0
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]


def test_시드를_바꾸면_수가_달라진다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    assert main(["eval", "harmony-output", "--priors", str(path), *FAST]) == 0
    first = capsys.readouterr().out
    assert main(["eval", "harmony-output", "--priors", str(path), "--seed", "999", *FAST]) == 0
    assert capsys.readouterr().out != first


def test_마디_훑기가_극한으로_내려간다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    assert (
        main(
            [
                "eval",
                "harmony-output",
                "--priors",
                str(path),
                "--against",
                "none",
                "--bar-sweep",
                "8,64",
                *FAST,
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "마디 수 훑기" in out
    rows = [
        match
        for line in out.splitlines()
        if (match := re.match(r"\s+\d+마디\s+([\d.]+)", line)) is not None
    ]
    values = [float(match.group(1)) for match in rows]
    assert len(values) == 2
    assert values[0] > values[1]


def test_없는_출처를_주면_비정상_종료한다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl")
    assert (
        main(["eval", "harmony-output", "--priors", str(path), "--stem-set", "없는스템", *FAST])
        == 1
    )
    assert "그 출처가 없다" in capsys.readouterr().err


def test_사전_파일이_없으면_비정상_종료한다(tmp_path, capsys):
    assert main(["eval", "harmony-output", "--priors", str(tmp_path / "없다.jsonl"), *FAST]) == 1
    assert "찾지 못했다" in capsys.readouterr().err


# ------------------------------------------------------------------ 로더


def test_로더가_두_출처를_같은_회전으로_읽는다(tmp_path):
    """**으뜸음은 어느 출처든 전체 믹스 추정을 쓴다** (D-0073).

    출처마다 다시 추정하면 회전 기준이 갈려 비교가 성립하지 않는다.
    """
    path = write_keys(tmp_path / "keys.jsonl", count=6, mix_contrast=1.0, stem_contrast=1.0)
    mix = load_degree_priors(path, "mix")
    stem = load_degree_priors(path, "other")
    assert set(mix) == set(stem)
    for key in mix:
        # 같은 대비로 만들었으므로 회전까지 같으면 두 벡터가 일치해야 한다.
        assert mix[key] == pytest.approx(stem[key], abs=1e-6)


def test_로더는_회전해서_낸다(tmp_path):
    """도수 사전은 **인덱스 0이 으뜸음**이다. 회전을 빠뜨리면 조성이 섞인다."""
    path = tmp_path / "keys.jsonl"
    path.write_text(
        json.dumps(
            {
                "source_key": "곡.flac",
                "key": "D major",  # 피치클래스 2
                "chroma": [0.0, 0.0, 1.0] + [0.0] * 9,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    prior = load_degree_priors(path, "mix")["곡.flac"]
    assert prior[0] == pytest.approx(1.0)


def test_로더는_잘린_줄을_건너뛴다(tmp_path):
    """끊긴 배치의 마지막 줄은 잘려 있는 것이 정상이다 (D-0075)."""
    path = write_keys(tmp_path / "keys.jsonl", count=3)
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린곡.flac", "key": "C maj')
    assert len(load_degree_priors(path, "mix")) == 3


# ------------------------------------------------------------------ O-31 배선


def test_도수_제한_손실을_낸다(tmp_path, capsys):
    """`eval degree-restriction` 배선 (O-31 · D-0083). **인코더 테스트는 배선을 안 본다.**"""
    path = write_keys(tmp_path / "keys.jsonl")
    assert main(["eval", "degree-restriction", "--priors", str(path), "--pairs", "20"]) == 0
    out = capsys.readouterr().out
    assert "observed" in out and "shuffled" in out
    assert "비음계 몫" in out and "판정" in out


def test_선법을_바꾸면_버리는_칸이_달라진다(tmp_path, capsys):
    """**선언한 인자가 결과를 바꾸는지 본다** (D-0064 · O-25)."""
    path = write_keys(tmp_path / "keys.jsonl")
    outputs = []
    for key in ("C major", "A minor"):
        command = ["eval", "degree-restriction", "--priors", str(path), "--pairs", "20"]
        assert main([*command, "--key", key]) == 0
        outputs.append(capsys.readouterr().out)
    assert "반음 1, 3, 6, 8, 10, 11" in outputs[0]
    assert "반음 1, 2, 4, 6, 9, 11" in outputs[1]
    assert outputs[0] != outputs[1]


def test_제한_손실도_사전_파일이_없으면_비정상_종료한다(tmp_path, capsys):
    assert main(["eval", "degree-restriction", "--priors", str(tmp_path / "없다.jsonl")]) == 1
    assert "찾지 못했다" in capsys.readouterr().err


# ------------------------------------------------------------------ O-33 배선


def test_반음계_정체를_낸다(tmp_path, capsys):
    """`eval chromatic-origin` 배선 (O-33 · D-0089)."""
    path = write_keys(tmp_path / "keys.jsonl", count=60)
    assert main(["eval", "chromatic-origin", "--priors", str(path)]) == 0
    out = capsys.readouterr().out
    assert "치환 짝" in out and "눈금선" in out and "판정" in out


def test_신뢰도_분할이_묶음을_셋으로_만든다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", count=60)
    assert main(["eval", "chromatic-origin", "--priors", str(path), "--margin-split"]) == 0
    out = capsys.readouterr().out
    assert "추정 확실" in out and "추정 불확실" in out
    assert "역인과가 있다" in out


def test_선법을_바꾸면_치환_짝이_달라진다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", count=60)
    outputs = []
    for key in ("C major", "A minor"):
        command = ["eval", "chromatic-origin", "--priors", str(path)]
        assert main([*command, "--key", key]) == 0
        outputs.append(capsys.readouterr().out)
    assert "1<-2" in outputs[0]
    assert "1<-0" in outputs[1]


def test_반음계_정체도_사전이_없으면_비정상_종료한다(tmp_path, capsys):
    assert main(["eval", "chromatic-origin", "--priors", str(tmp_path / "없다.jsonl")]) == 1
    assert "찾지 못했다" in capsys.readouterr().err


def test_신뢰도를_읽는다(tmp_path):
    from hathor.interfaces.cli.main import load_key_margins

    path = write_keys(tmp_path / "keys.jsonl", count=5)
    margins = load_key_margins(path)
    assert len(margins) == 5
    assert all(value == pytest.approx(0.2) for value in margins.values())


# ------------------------------------------------------------------ 표 그리기 (D-0092)


def _tables(out: str) -> list[list[list[str]]]:
    """구분선을 기준으로 **표 하나씩** 끊는다. 한 리포트에 표가 여럿이다."""
    lines = out.splitlines()
    found: list[list[list[str]]] = []
    for index, line in enumerate(lines):
        if set(line.strip()) != {"-"} or index == 0:
            continue
        block = [lines[index - 1].split()]
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].strip():
            block.append(lines[cursor].split())
            cursor += 1
        found.append(block)
    return found


def test_표_그리기가_열_수를_강제한다():
    """**머리글과 값을 따로 쓰다가 이름표가 두 칸 밀린 채 실측을 냈다** (D-0092)."""
    from hathor.interfaces.cli.main import render_table

    with pytest.raises(ValueError, match="열 수가 머리글과 다르다"):
        render_table((("가", "<6"), ("나", ">6.2f")), [("하나", 1.0, 2.0)])


def test_표_그리기가_머리글을_같은_폭으로_낸다():
    from hathor.interfaces.cli.main import render_table

    lines = render_table((("가", "<6"), ("나", ">8.2f")), [("하나", 1.0)])
    assert len(lines) == 3
    assert lines[0].startswith("가")
    assert lines[2].strip().endswith("1.00")


@pytest.mark.parametrize("command", ["degree-restriction", "chromatic-origin"])
def test_리포트_표의_이름표와_값이_안_어긋난다(tmp_path, capsys, command):
    """**이름표 수와 값 수가 같아야 한다.** 하나만 고치면 조용히 어긋난다."""
    path = write_keys(tmp_path / "keys.jsonl", count=60)
    extra = ["--pairs", "20"] if command == "degree-restriction" else []
    assert main(["eval", command, "--priors", str(path), *extra]) == 0
    tables = _tables(capsys.readouterr().out)
    assert tables, "표를 못 찾았다"
    for block in tables:
        header, rows = block[0], block[1:]
        assert rows, f"{command}: 값이 없는 표가 있다"
        for row in rows:
            assert len(row) == len(header), (
                f"{command}: 값 {len(row)}개 대 이름표 {len(header)}개 — {header} / {row}"
            )


def test_삼총사_칸을_리포트에_적는다(tmp_path, capsys):
    path = write_keys(tmp_path / "keys.jsonl", count=60)
    assert main(["eval", "chromatic-origin", "--priors", str(path)]) == 0
    assert "단조 차용 삼총사: 3, 8, 10" in capsys.readouterr().out


def test_열_이름에_공백을_금지한다():
    """**공백이 들어가면 표를 다시 읽을 수 없다** (D-0092)."""
    from hathor.interfaces.cli.main import render_table

    with pytest.raises(ValueError, match="공백"):
        render_table((("가 나", "<6"),), [("하나",)])
