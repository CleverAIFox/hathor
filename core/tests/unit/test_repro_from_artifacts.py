"""산출물에서 «재현» 명령을 되살린다 (D-0251).

**D-0250이 «산출물이 없다»고 74건을 유물로 뒀고 그것은 과한 말이었다.** `eval retrieval`은
조건을 산출 JSON에 박아 왔다. 여기가 «복원이지 추측이 아니다»를 못 박는다 — 그 경계가
무너지면 지어낸 명령이 기록에 박히고, 그것은 빈칸보다 나쁘다 (GR-0.5).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from hathor.shared.config.paths import repo_root
from tests.conftest import tool_module

TOOL = tool_module("repro_from_artifacts")

BASE: dict[str, Any] = {
    "label": "unnamed",
    "view": {
        "keys": ["mixture"],
        "combine": "concat",
        "pool": "mean",
        "chunk_l2": False,
        "block_l2": False,
        "centered": True,
    },
    "split": {"mode": "odd-even", "ratio": 0.5, "repeats": 1, "seed": 20240501},
    "k": 10,
    "seed": 7,
    "gate": 0.3,
    "force": False,
}


def _config(**changes: Any) -> dict[str, Any]:
    config = copy.deepcopy(BASE)
    for key, value in changes.items():
        if key in ("keys", "combine", "pool", "chunk_l2", "block_l2", "centered"):
            config["view"][key] = value
        elif key in ("mode", "ratio", "repeats"):
            config["split"][key] = value
        else:
            config[key] = value
    return config


# ------------------------------------------------------------------ 명령 복원


def test_기본값만이면_깃발이_없다() -> None:
    """**기본값을 다 적으면 읽는 사람이 무엇이 조건인지 못 본다.**"""
    assert TOOL.command_of(_config()) == "hathor eval retrieval"


def test_바꾼_것만_적는다() -> None:
    command = TOOL.command_of(
        _config(keys=["drums", "bass"], combine="mean", chunk_l2=True, centered=False)
    )

    assert command == ("hathor eval retrieval --keys drums,bass --combine mean --chunk-l2 --raw")


def test_중심화를_끈_것은_raw다() -> None:
    """`centered: false`가 `--raw`다 (D-0031). 이름이 다르므로 표를 봐야 안다."""
    assert "--raw" in TOOL.command_of(_config(centered=False))
    assert "--raw" not in TOOL.command_of(_config())


def test_무작위_분할은_비율과_반복까지_적는다() -> None:
    """`--split-repeats 1`은 표본 하나다 — **적히지 않으면 그대로 인용된다.**"""
    command = TOOL.command_of(_config(mode="random", ratio=0.3, repeats=8))

    assert "--split random" in command
    assert "--split-ratio 0.3" in command
    assert "--split-repeats 8" in command


def test_홀짝이면_분할_깃발이_안_붙는다() -> None:
    assert "--split" not in TOOL.command_of(_config(ratio=0.3, repeats=8))


def test_라벨이_있으면_적는다() -> None:
    assert "--label o12-random-8192" in TOOL.command_of(_config(label="o12-random-8192"))
    assert "--label" not in TOOL.command_of(_config())


# ------------------------------------------------------------------ 짝짓기


def _artifact(tmp_path: Path, name: str, values: list[float], **changes: Any) -> None:
    (tmp_path / f"{name}.eval.json").write_text(
        json.dumps(
            {
                "config": _config(**changes),
                "metrics": [{"measured": {"map": value}} for value in values],
            }
        ),
        encoding="utf-8",
    )


def test_수치_셋이_겹치면_근거다(tmp_path: Path) -> None:
    _artifact(tmp_path, "a", [0.9174, 0.8650, 0.4312], keys=["drums"])
    body = "MAP 0.9174 · M1 0.8650 · M2 0.4312를 얻었다."

    (hit,) = TOOL.match(body, TOOL.read_artifacts(tmp_path))

    assert hit[0] == 3
    assert "--keys drums" in hit[1].command


def test_수치_하나만_겹치면_짝이_아니다(tmp_path: Path) -> None:
    """**우연이 겹친다.** 0.5나 0.3333은 아무 데나 나온다."""
    _artifact(tmp_path, "a", [0.9174, 0.1111, 0.2222])

    assert TOOL.match("0.9174 하나뿐이다", TOOL.read_artifacts(tmp_path)) == []


def test_끝의_0은_같은_수로_본다(tmp_path: Path) -> None:
    """기록은 `0.917`, 산출물은 `0.9170`일 수 있다."""
    _artifact(tmp_path, "a", [0.9170, 0.8650, 0.4310])

    assert TOOL.match("0.917 · 0.865 · 0.431", TOOL.read_artifacts(tmp_path))[0][0] == 3


def test_두_자리_소수는_안_본다() -> None:
    """마디 수·백분율이 우연히 겹친다. **소수 셋부터가 지표다.**"""
    assert TOOL.numbers("0.41 · 0.44 · 2.8배") == set()
    assert TOOL.numbers("0.4123") == {"0.4123"}


def test_참_거짓은_수로_세지_않는다(tmp_path: Path) -> None:
    """`True`가 `1`로 세어지면 모든 산출물이 모든 기록에 걸린다."""
    assert "True" not in list(TOOL.flatten({"a": True}))
    assert list(TOOL.flatten({"a": True})) == []


def test_조건이_없는_파일은_산출물이_아니다(tmp_path: Path) -> None:
    """`config`가 없으면 명령을 복원할 수 없다 — 그것이 이 도구의 전제다."""
    (tmp_path / "x.eval.json").write_text(json.dumps({"metrics": []}), encoding="utf-8")

    assert TOOL.read_artifacts(tmp_path) == []


def test_깨진_JSON은_건너뛴다(tmp_path: Path) -> None:
    (tmp_path / "깨짐.eval.json").write_text("{", encoding="utf-8")
    _artifact(tmp_path, "a", [0.1234, 0.2345, 0.3456])

    assert len(TOOL.read_artifacts(tmp_path)) == 1


def test_재현_절을_들여쓴_블록으로_만든다() -> None:
    """`check_doc_style`이 그 형식만 «재현»으로 읽는다 (D-0136)."""
    block = TOOL.repro_block(["hathor eval retrieval", "hathor eval retrieval --raw"])

    assert block.startswith("재현\n    hathor")
    assert block.endswith("--raw")
    assert "\n    hathor eval retrieval --raw" in block


# ------------------------------------------------------------------ 반올림


def test_기록이_반올림해_적어도_맞는다(tmp_path: Path) -> None:
    """**첫 판이 짝을 0건 찾았다.** 산출물은 `round(x, 6)`이고 사람은 «0.9174»라고 쓴다."""
    _artifact(tmp_path, "a", [0.917416, 0.864952, 0.431087])

    hits = TOOL.match("MAP 0.9174 · M1 0.8650 · M2 0.4311", TOOL.read_artifacts(tmp_path))

    assert hits and hits[0][0] == 3


def test_반올림_꼴을_세_자리까지_넓힌다() -> None:
    assert TOOL.variants("0.917416") == {"0.917416", "0.91742", "0.9174", "0.917"}


def test_두_자리로_줄어드는_꼴은_안_넣는다() -> None:
    """`0.9`가 열쇠가 되면 아무 데나 걸린다. **하나도 안 내놓는 것이 맞다.**"""
    assert TOOL.variants("0.9") == set()
    assert TOOL.variants("0.4312") == {"0.4312", "0.431"}


# ------------------------------------------------------------------ 비율과 라벨


def test_기록이_수치를_많이_적었으면_셋_겹치는_것으로는_안_된다(tmp_path: Path) -> None:
    """**오짝 여섯 건이 이렇게 붙었다.** 산출물 하나에 수치가 수백 개다."""
    _artifact(tmp_path, "a", [0.1111, 0.2222, 0.3333])
    body = "0.1111 · 0.2222 · 0.3333 " + " ".join(f"0.{n:04d}" for n in range(5000, 5012))

    assert len(TOOL.numbers(body)) == 14, "겹치는 셋에 열한 개를 더한 기록이다"
    assert TOOL.match(body, TOOL.read_artifacts(tmp_path)) == [], "셋은 3/14이고 8이 필요하다"


def test_기록_수치의_대부분이_있으면_근거다(tmp_path: Path) -> None:
    """**그 산출물이 근거라면 기록이 적은 수치가 거기 있어야 한다.**"""
    _artifact(tmp_path, "a", [0.1111, 0.2222, 0.3333, 0.4444])
    body = "0.1111 · 0.2222 · 0.3333 · 0.4444 · 0.9999"

    assert TOOL.match(body, TOOL.read_artifacts(tmp_path))[0][0] == 4


def test_라벨이_본문에_있으면_그것이_증거다(tmp_path: Path) -> None:
    """`mert-mean-std`는 사람이 지은 이름이다 — **우연히 안 겹친다.**"""
    _artifact(tmp_path, "a", [0.1111, 0.2222, 0.3333], label="o12-random-8192")
    body = "라벨 o12-random-8192로 돌렸다. " + " ".join(f"0.{n:04d}" for n in range(5000, 5020))

    hits = TOOL.match(body, TOOL.read_artifacts(tmp_path))

    assert hits and hits[0][1].label == "o12-random-8192"


def test_기록에_수치가_없으면_짝이_없다(tmp_path: Path) -> None:
    """짝지을 열쇠가 없다. **그 건은 진짜 유물이다.**"""
    _artifact(tmp_path, "a", [0.1111, 0.2222, 0.3333])

    assert TOOL.match("수치를 안 적은 기록이다", TOOL.read_artifacts(tmp_path)) == []


def test_라벨이_unnamed면_열쇠가_아니다(tmp_path: Path) -> None:
    """기본 라벨은 **모든 산출물이 같이 든다.**"""
    _artifact(tmp_path, "a", [0.1111, 0.2222, 0.3333])

    assert TOOL.read_artifacts(tmp_path)[0].label == ""


def test_도구_바이트코드를_안_남긴다() -> None:
    """**낡은 `.pyc`가 시험을 거짓말하게 만든다** (D-0252). `conftest`가 막는다."""
    assert not (repo_root() / "tools" / "__pycache__").exists()
