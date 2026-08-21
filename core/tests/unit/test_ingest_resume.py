"""조성 추출 이어받기 (D-0075).

**1004곡 배치가 원자적이었다.** 메모리에 쌓고 마지막에 한 번 썼으므로 중간에 끊기면
전부 사라졌다. GPU로 한 시간 반짜리 작업에서 실제로 20분을 버렸다.
"""

import argparse
import json

import pytest

from hathor.interfaces.cli.main import _keys_settings, _resume_target


def settings(**overrides):
    base = {
        "chroma": "cq",
        "profile": "krumhansl",
        "gamma": 0.0,
        "harmonic": 0.0,
        "aggregate": "mean",
        "separate": True,
        "halves": False,
    }
    base.update(overrides)
    return _keys_settings(argparse.Namespace(**base))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    return path


def rows_for(config, count, *, start=0):
    return [
        {**config, "source_key": f"가수-곡{index}.mp3", "chroma": [1 / 12] * 12}
        for index in range(start, start + count)
    ]


def test_산출물이_없으면_새_파일을_연다(tmp_path):
    target, done = _resume_target(tmp_path, settings())
    assert target.name.startswith("keys-")
    assert done == set()


def test_조건이_같으면_이어받는다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 5))
    target, done = _resume_target(tmp_path, config)
    assert target.name == "keys-20260821T100000Z.keys.jsonl"
    assert len(done) == 5
    assert "가수-곡0.mp3" in done


@pytest.mark.parametrize(
    "field,value",
    [
        ("separate", False),
        ("halves", True),
        ("aggregate", "median"),
        ("profile", "temperley"),
        ("harmonic", 0.5),
        ("chroma", "linear"),
    ],
)
def test_조건이_하나라도_다르면_새_파일이다(tmp_path, field, value):
    """**조건이 섞인 산출물은 무엇을 잰 것인지 알 수 없다** (D-0073)."""
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(settings(), 5))
    target, done = _resume_target(tmp_path, settings(**{field: value}))
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_잘린_마지막_줄을_건너뛴다(tmp_path):
    """끊기면 마지막 줄이 잘려 있을 수 있다. 그 한 줄 때문에 전부 못 쓰면 안 된다."""
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 3))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린')
    target, done = _resume_target(tmp_path, config)
    assert target == path
    assert len(done) == 3


def test_가장_최근_파일을_고른다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260101T000000Z.keys.jsonl", rows_for(config, 2))
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 7, start=100))
    target, done = _resume_target(tmp_path, config)
    assert target.name == "keys-20260821T100000Z.keys.jsonl"
    assert len(done) == 7


def test_조건_미기록_옛_산출물은_잇지_않는다(tmp_path):
    """D-0073 이전 파일에는 조건이 없다. 이어받으면 무엇을 섞는지 모른다."""
    write(
        tmp_path / "keys-20260818T000000Z.keys.jsonl",
        [{"source_key": "옛곡.mp3", "chroma": [1 / 12] * 12}],
    )
    target, done = _resume_target(tmp_path, settings())
    assert target.name != "keys-20260818T000000Z.keys.jsonl"
    assert done == set()


def test_빈_파일은_건너뛴다(tmp_path):
    (tmp_path / "keys-20260821T100000Z.keys.jsonl").write_text("", encoding="utf-8")
    _, done = _resume_target(tmp_path, settings())
    assert done == set()


def test_설정에_크로마_벡터와_겹치는_이름이_없다():
    """**`chroma`는 이미 12차원 벡터다** (D-0075).

    설정 키를 `chroma`로 두면 행에서 벡터에 덮이고, 그러면 이어받기가 영영 안 걸린다.
    실제로 그렇게 썼다가 잡았다.
    """
    assert "chroma" not in settings()
    assert "chroma_mode" in settings()
