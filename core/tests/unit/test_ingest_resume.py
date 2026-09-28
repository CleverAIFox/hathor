"""조성 추출 이어받기 (D-0075).

**1004곡 배치가 원자적이었다.** 메모리에 쌓고 마지막에 한 번 썼으므로 중간에 끊기면
전부 사라졌다. GPU로 한 시간 반짜리 작업에서 실제로 20분을 버렸다.
"""

import argparse
import json
import os

import pytest

from hathor.infrastructure.batch_lock import BatchAlreadyRunningError, batch_lock, lock_path
from hathor.interfaces.cli.keys_resume import keys_settings, resume_target
from tests.conftest import tool_module as _tool

LEDGER = _tool("check_artifacts")


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
    return keys_settings(argparse.Namespace(**base))


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
    target, done, _ = resume_target(tmp_path, settings())
    assert target.name.startswith("keys-")
    assert done == set()


def test_조건이_같으면_이어받는다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 5))
    target, done, _ = resume_target(tmp_path, config)
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
    target, done, _ = resume_target(tmp_path, settings(**{field: value}))
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_잘린_마지막_줄을_건너뛴다(tmp_path):
    """끊기면 마지막 줄이 잘려 있을 수 있다. 그 한 줄 때문에 전부 못 쓰면 안 된다."""
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 3))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린')
    target, done, _ = resume_target(tmp_path, config)
    assert target == path
    assert len(done) == 3


def test_가장_최근_파일을_고른다(tmp_path):
    config = settings()
    write(tmp_path / "keys-20260101T000000Z.keys.jsonl", rows_for(config, 2))
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 7, start=100))
    target, done, _ = resume_target(tmp_path, config)
    assert target.name == "keys-20260821T100000Z.keys.jsonl"
    assert len(done) == 7


def test_조건_미기록_옛_산출물은_잇지_않는다(tmp_path):
    """D-0073 이전 파일에는 조건이 없다. 이어받으면 무엇을 섞는지 모른다."""
    write(
        tmp_path / "keys-20260818T000000Z.keys.jsonl",
        [{"source_key": "옛곡.mp3", "chroma": [1 / 12] * 12}],
    )
    target, done, _ = resume_target(tmp_path, settings())
    assert target.name != "keys-20260818T000000Z.keys.jsonl"
    assert done == set()


def test_빈_파일은_건너뛴다(tmp_path):
    (tmp_path / "keys-20260821T100000Z.keys.jsonl").write_text("", encoding="utf-8")
    _, done, _broken = resume_target(tmp_path, settings())
    assert done == set()


def test_설정에_크로마_벡터와_겹치는_이름이_없다():
    """**`chroma`는 이미 12차원 벡터다** (D-0075).

    설정 키를 `chroma`로 두면 행에서 벡터에 덮이고, 그러면 이어받기가 영영 안 걸린다.
    실제로 그렇게 썼다가 잡았다.
    """
    assert "chroma" not in settings()
    assert "chroma_mode" in settings()


# ------------------------------------------------ 동시 실행 방지 (D-0077 · D-0278)


def test_잡은_동안_다른_실행은_막힌다(tmp_path):
    """**같은 파일에 둘이 append하면 줄이 섞여 파일이 깨진다.**

    D-0075 이전에는 실행마다 새 파일이라 겹칠 일이 없었다. 이어받기를 넣은 순간 생긴
    문제이고, 실제로 배치가 둘 떠서 49곡짜리 파일이 5곡으로 보였다.

    **`flock`은 열린 파일 기술자에 붙는다** — 같은 프로세스에서 두 번 열어도 막힌다
    (D-0278). 예전 PID 파일은 같은 PID면 그냥 통과시켰다.
    """
    with (
        batch_lock(tmp_path, "ingest-keys"),
        pytest.raises(BatchAlreadyRunningError),
        batch_lock(tmp_path, "ingest-keys"),
    ):
        pass


def test_풀리면_다음_실행이_잡는다(tmp_path):
    """나가면 커널이 푼다. **나가는 길이 몇이든 푼다** — 그것이 PID 파일과 다른 점이다."""
    with batch_lock(tmp_path, "ingest-keys"):
        pass

    entered = False
    with batch_lock(tmp_path, "ingest-keys"):
        entered = True
    assert entered, "풀린 잠금을 다시 못 잡았다"


def test_예외로_나가도_풀린다(tmp_path):
    """**옛 `BatchLock`은 나가는 길마다 `release()`를 손으로 불렀다** (셋이었다)."""
    with pytest.raises(RuntimeError), batch_lock(tmp_path, "ingest-keys"):
        raise RuntimeError("도중에 죽는다")

    entered = False
    with batch_lock(tmp_path, "ingest-keys"):
        entered = True
    assert entered, "예외로 나간 뒤 잠금이 남았다"


def test_잠금_파일은_남고_대장에_등재돼_있다(tmp_path):
    """**지워서 없애지 않는다** (D-0278).

    `flock`은 파일을 지우지 않는다. 지우면 등재할 것이 사라지지만 그것은 R3가 금지하는
    자리이고 **사실상 격리와 이름만 다르다** — 사용자의 판정이다.
    """
    with batch_lock(tmp_path, "ingest-keys"):
        pass
    path = lock_path(tmp_path, "ingest-keys")
    assert path.exists(), "잠금 파일이 사라졌다. 지우면 대장에 등재할 것이 없어진다"
    assert path.name == ".ingest-keys.lock"

    entries = LEDGER.load()
    assert path.name in entries, "잠금 파일이 대장에 없다 (R3)"
    assert entries[path.name]["state"] == "임시"
    assert entries[path.name]["store"] is False


def test_내용은_사람이_읽는_것이다(tmp_path):
    """잠금 판정에는 쓰지 않는다. **깨진 내용도 잠금을 망치지 않는다.**"""
    path = lock_path(tmp_path, "ingest-keys")
    path.write_text("피디가아님", encoding="utf-8")
    with batch_lock(tmp_path, "ingest-keys"):
        assert f"pid={os.getpid()}" in path.read_text(encoding="utf-8")


def test_배치_잠금_기법이_한_자리에만_있다():
    """**기법을 두 번 적으면 근거가 갈린다** (D-0278).

    합치기 전에 둘이었고 **두 문서 문자열이 서로의 방식을 «나쁜 쪽»으로 적고 있었다** —
    한쪽은 「손으로 지우면 결국 지운다」며 PID 파일을 고르고, 다른 쪽은 「PID 파일이면
    죽은 잠금이 다음을 막는다」며 버렸다. 늘리려면 결정 기록이 필요하다 (D-0118).

    **`LOCK_NB`로 센다.** `npz_feature_store`가 인덱스 append에 `LOCK_EX`(차단)를 하나 더
    쓰는데 그것은 **다른 일**이다 — 그 자리 주석이 «O_APPEND 자체로 이미 원자적이고 잠금은
    그 보장을 코드에 드러내기 위한 것»이라 적고 있다. 배치 중복을 막는 것은 비차단 잠금뿐이다.
    **첫 실행에 그 셋째 자리를 잡았고**, 그래서 세는 낱말을 좁혔다 — 남이 선언해 둔 의도를
    정규식이 편하려고 지우지 않는다.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "hathor"
    found = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if "LOCK_NB" in path.read_text(encoding="utf-8")
    )
    assert found == ["infrastructure/batch_lock.py"], found


# ------------------------------------------------ 손상 감지 (D-0077)


def test_깨진_줄이_많으면_세어_낸다(tmp_path):
    """**조용히 건너뛰면 49곡이 5곡으로 보인다.** 그 상태로 이어 쓰면 더 깨진다."""
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 4))
    with path.open("a", encoding="utf-8") as stream:
        for _ in range(10):
            stream.write('{"source_key": "섞인\n')
    _, done, broken = resume_target(tmp_path, config)
    assert len(done) == 4
    assert broken == 10


def test_잘린_한_줄은_손상으로_보지_않는다(tmp_path):
    config = settings()
    path = write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(config, 30))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"source_key": "잘린')
    _, done, broken = resume_target(tmp_path, config)
    assert len(done) == 30
    assert broken == 1


def test_스템_조합이_조건에_들어간다():
    """**`separated`만으로는 모자란다** (D-0100).

    `STEM_SETS`에 조합을 하나 더해도 조건이 같아 보이면 **새 스템이 없는 파일에
    이어붙는다.** D-0099가 `bass`를 더한 뒤 실제로 그 일이 났다.
    """
    from hathor.domain.services.stem_sets import STEM_SETS

    assert settings()["stem_sets"] == sorted(STEM_SETS)
    assert settings(separate=False)["stem_sets"] == []


def test_스템_조합이_늘면_새_파일이다(tmp_path):
    old = settings()
    old["stem_sets"] = ["other"]
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(old, 5))
    target, done, _ = resume_target(tmp_path, settings())
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_스템_조합이_안_적힌_옛_산출물은_이어받지_않는다(tmp_path):
    """부재는 불일치다. **없는 스템을 찾다가 0곡이 되는 것보다 다시 뽑는 편이 낫다.**"""
    old = settings()
    del old["stem_sets"]
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(old, 5))
    target, _, _ = resume_target(tmp_path, settings())
    assert target.name != "keys-20260821T100000Z.keys.jsonl"


def test_이어받지_않는_이유를_알린다(tmp_path, capsys):
    """**조용히 새 파일을 열지 않는다** (D-0100). 모르면 한 시간 반을 다시 쓴다."""
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(settings(), 5))
    resume_target(tmp_path, settings(halves=True))
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
    target, done, _ = resume_target(tmp_path, settings(series=2.0))
    assert target.name != "keys-20260821T100000Z.keys.jsonl"
    assert done == set()


def test_이어받지_않는_이유를_한_줄로_찍는다(tmp_path, capsys):
    """**후보가 열 개면 열 줄이 나왔다** (D-0106).

    조건이 가장 적게 다른 하나만 찍는다 — 그것이 "무엇을 바꾸면 이어받는가"에
    가장 가까운 답이다.
    """
    write(tmp_path / "keys-20260821T100000Z.keys.jsonl", rows_for(settings(), 5))
    write(
        tmp_path / "keys-20260820T100000Z.keys.jsonl",
        rows_for(settings(profile="temperley", separate=False), 5),
    )
    resume_target(tmp_path, settings(halves=True))
    lines = [line for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    assert "halves" in lines[0]
    assert "다른 후보 1개" in lines[0]


def test_시계열은_낱개_스템만_뽑는다():
    """**조합은 아무도 안 쓴다** (D-0106).

    `other+bass`류는 화성 사전을 고르려고 만든 것이고(D-0073), 순서 작업이 쓰는
    것은 `other`와 `bass`다. 시계열 한 번이 전곡 크로마 한 번과 같은 비용이다.
    """
    from hathor.domain.services.stem_sets import STEM_SETS

    singles = [name for name, parts in STEM_SETS.items() if len(parts) == 1]
    assert set(singles) == {"other", "bass", "vocals"}
