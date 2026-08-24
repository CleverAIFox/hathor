"""조성 추출 이어받기 (D-0075).

**1004곡 배치가 원자적이었다.** 메모리에 쌓고 마지막에 한 번 썼으므로 중간에 끊기면
전부 사라졌다. GPU로 한 시간 반짜리 작업에서 실제로 20분을 버렸다.
"""

import argparse
import json
import os

import pytest

from hathor.interfaces.cli.main import BatchLock, _keys_settings, _resume_target


def settings(**overrides):
    base = {
        "chroma": "cq",
        "profile": "krumhansl",
        "gamma": 0.0,
        "harmonic": 0.0,
        "aggregate": "mean",
        "separate": True,
        "halves": False,
        "series": None,
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
    target, done, _ = _resume_target(tmp_path, settings())
    assert target.name.startswith("keys-")
    assert done == set()


def test_조건이_같으면_이어받는다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 5))
    target, done, _ = _resume_target(tmp_path, config)
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
    target, done, _ = _resume_target(tmp_path, settings(**{field: value}))
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_잘린_마지막_줄을_건너뛴다(tmp_path):
    """끊기면 마지막 줄이 잘려 있을 수 있다. 그 한 줄 때문에 전부 못 쓰면 안 된다."""
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 3))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린')
    target, done, _ = _resume_target(tmp_path, config)
    assert target == path
    assert len(done) == 3


def test_가장_최근_파일을_고른다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260101T000000Z.keys.jsonl", rows_for(config, 2))
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 7, start=100))
    target, done, _ = _resume_target(tmp_path, config)
    assert target.name == "keys-20260821T100000Z.keys.jsonl"
    assert len(done) == 7


def test_조건_미기록_옛_산출물은_잇지_않는다(tmp_path):
    """D-0073 이전 파일에는 조건이 없다. 이어받으면 무엇을 섞는지 모른다."""
    write(
        tmp_path / "keys-20260818T000000Z.keys.jsonl",
        [{"source_key": "옛곡.mp3", "chroma": [1 / 12] * 12}],
    )
    target, done, _ = _resume_target(tmp_path, settings())
    assert target.name != "keys-20260818T000000Z.keys.jsonl"
    assert done == set()


def test_빈_파일은_건너뛴다(tmp_path):
    (tmp_path / "keys-20260821T100000Z.keys.jsonl").write_text("", encoding="utf-8")
    _, done, _broken = _resume_target(tmp_path, settings())
    assert done == set()


def test_설정에_크로마_벡터와_겹치는_이름이_없다():
    """**`chroma`는 이미 12차원 벡터다** (D-0075).

    설정 키를 `chroma`로 두면 행에서 벡터에 덮이고, 그러면 이어받기가 영영 안 걸린다.
    실제로 그렇게 썼다가 잡았다.
    """
    assert "chroma" not in settings()
    assert "chroma_mode" in settings()


# ------------------------------------------------ 동시 실행 방지 (D-0077)


def test_살아_있는_다른_프로세스의_락에는_막힌다(tmp_path):
    """**같은 파일에 둘이 append하면 줄이 섞여 파일이 깨진다.**

    D-0075 이전에는 실행마다 새 파일이라 겹칠 일이 없었다. 이어받기를 넣은 순간
    생긴 문제이고, 실제로 배치가 둘 떠서 49곡짜리 파일이 5곡으로 보였다.

    PID 1(init)은 항상 살아 있고 우리 프로세스가 아니다. 다른 프로세스가 잡고 있는
    상태를 그것으로 흉내낸다.
    """
    lock = BatchLock(tmp_path)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text("1", encoding="utf-8")
    assert lock.acquire() == 1
    assert lock.path.read_text(encoding="utf-8").strip() == "1"


def test_같은_프로세스는_다시_잡을_수_있다(tmp_path):
    lock = BatchLock(tmp_path)
    assert lock.acquire() is None
    assert lock.acquire() is None


def test_죽은_프로세스의_락은_가져간다(tmp_path):
    """**손으로 지우게 하면 결국 지우고 돌린다.**

    강제 종료 뒤 유령 락이 남아 막히면, 사람은 락을 지우는 습관을 들이고 그러면
    락이 없는 것과 같아진다. 죽은 PID면 그냥 가져간다.
    """
    lock = BatchLock(tmp_path)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text("999999", encoding="utf-8")  # 없을 가능성이 매우 높은 PID
    assert lock.acquire() is None
    assert lock.path.read_text(encoding="utf-8").strip() == str(os.getpid())


def test_깨진_락_파일은_무시한다(tmp_path):
    lock = BatchLock(tmp_path)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text("피디가아님", encoding="utf-8")
    assert lock.acquire() is None


def test_해제하면_다른_실행이_잡는다(tmp_path):
    lock = BatchLock(tmp_path)
    lock.acquire()
    lock.release()
    assert not lock.path.exists()


def test_남의_락은_해제하지_않는다(tmp_path):
    lock = BatchLock(tmp_path)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text("999999", encoding="utf-8")
    lock.release()
    assert lock.path.exists()


# ------------------------------------------------ 손상 감지 (D-0077)


def test_깨진_줄이_많으면_세어_낸다(tmp_path):
    """**조용히 건너뛰면 49곡이 5곡으로 보인다.** 그 상태로 이어 쓰면 더 깨진다."""
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 4))
    with path.open("a", encoding="utf-8") as stream:
        for _ in range(10):
            stream.write('{"source_key": "섞인\n')
    _, done, broken = _resume_target(tmp_path, config)
    assert len(done) == 4
    assert broken == 10


def test_잘린_한_줄은_손상으로_보지_않는다(tmp_path):
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 30))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린')
    _, done, broken = _resume_target(tmp_path, config)
    assert len(done) == 30
    assert broken == 1


def test_스템_조합이_조건에_들어간다():
    """**`separated`만으로는 모자란다** (D-0100).

    `STEM_SETS`에 조합을 하나 더해도 조건이 같아 보이면 **새 스템이 없는 파일에
    이어붙는다.** D-0099가 `bass`를 더한 뒤 실제로 그 일이 났다.
    """
    from hathor.interfaces.cli.main import STEM_SETS

    assert settings()["stem_sets"] == sorted(STEM_SETS)
    assert settings(separate=False)["stem_sets"] == []


def test_스템_조합이_늘면_새_파일이다(tmp_path):
    old = settings()
    old["stem_sets"] = ["other"]
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(old, 5))
    target, done, _ = _resume_target(tmp_path, settings())
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_스템_조합이_안_적힌_옛_산출물은_이어받지_않는다(tmp_path):
    """부재는 불일치다. **없는 스템을 찾다가 0곡이 되는 것보다 다시 뽑는 편이 낫다.**"""
    old = settings()
    del old["stem_sets"]
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(old, 5))
    target, _, _ = _resume_target(tmp_path, settings())
    assert target.name != "keys-20260821T100000Z.keys.jsonl"


def test_이어받지_않는_이유를_알린다(tmp_path, capsys):
    """**조용히 새 파일을 열지 않는다** (D-0100). 모르면 한 시간 반을 다시 쓴다."""
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(settings(), 5))
    _resume_target(tmp_path, settings(halves=True))
    error = capsys.readouterr().err
    assert "이어받지 않는다" in error
    assert "halves" in error


def test_시계열_창_길이가_조건에_들어간다():
    """**다른 창으로 뽑은 산출물에 이어붙으면 창 길이가 섞인다** (D-0105).

    섞인 시계열은 무엇을 잰 것인지 알 수 없다 — D-0073이 조건을 적기로 한 이유다.
    """
    assert settings()["series_seconds"] is None
    assert settings(series=1.0)["series_seconds"] == 1.0


def test_시계열_창_길이가_다르면_새_파일이다(tmp_path):
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(settings(series=1.0), 5))
    target, done, _ = _resume_target(tmp_path, settings(series=2.0))
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()
