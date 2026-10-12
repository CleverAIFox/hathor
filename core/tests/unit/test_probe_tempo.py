"""코퍼스 템포 전수 — 정본의 상류 (D-0397).

**실측은 그의 기기에서만 된다** (D-0015). 여기서 보는 것은 **세는 법**이다 — 합성
포락선이라 정답을 알고, 1004곡의 수는 `make measure`가 낸다.

### 왜 이 상류가 생겼나

기본 템포 126은 D-0206이 **손으로 옮긴 수**였고 같은 측정을 두고 수가 네 곳에서
달랐다. 이제 도구가 세고 `measured.py`가 상수와 대조한다 (GR-0.7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from hathor.infrastructure.onset_store import write_envelope
from tests.conftest import tool_module

if TYPE_CHECKING:
    from pathlib import Path

TOOL = tool_module("probe_tempo")
CANON = tool_module("measured")

HOP = 0.01
"""그의 산출물과 같은 홉 (`keys-0.01s.onsets` · `RULER`에 적혀 있다)."""


def _pulse(bpm: float, seconds: float = 20.0) -> np.ndarray:
    frames = int(seconds / HOP)
    envelope = np.zeros(frames, dtype=np.float64)
    envelope[:: max(1, round(60.0 / bpm / HOP))] = 1.0
    return envelope


def _folder(root: Path, bpms: list[float], *, silent: int = 0) -> Path:
    folder = root / f"keys-{HOP:g}s.onsets"
    for index, bpm in enumerate(bpms):
        write_envelope(folder, f"곡{index}.mp3", _pulse(bpm), hop_seconds=HOP)
    for index in range(silent):
        write_envelope(
            folder, f"조용한곡{index}.mp3", np.zeros(2000, dtype=np.float64), hop_seconds=HOP
        )
    return folder


def test_선언한_키만_정확히_낸다(tmp_path: Path) -> None:
    """**선언과 실물이 다르면 정본이 조용히 낡는다** (D-0371 · 양방향)."""
    counts = TOOL.counted(_folder(tmp_path, [120.0, 128.0, 132.0, 140.0]))

    assert set(counts) == set(TOOL.EMITS)
    assert all(isinstance(value, int) for value in counts.values()), "정본은 정수만 든다"


def test_못_읽은_곡을_수로_든다(tmp_path: Path) -> None:
    """**0으로 안 센다** (GR-0.5). 그의 실측은 1004곡에 못 읽은 곡 0이었다."""
    counts = TOOL.counted(_folder(tmp_path, [120.0, 128.0, 132.0, 140.0], silent=2))

    assert counts["beat_read"] == 4
    assert counts["beat_missing"] == 2


def test_접기_전과_후를_둘_다_든다(tmp_path: Path) -> None:
    """**차이가 전부 배수 모호성이다** (D-0054 · D-0206). 74 → 130이 그 차다.

    60으로 읽힌 곡이 셋이면 **원값 중앙은 60쯤이고 접은 중앙은 120쯤**이다.
    """
    counts = TOOL.counted(_folder(tmp_path, [60.0, 62.0, 64.0, 130.0, 132.0]))

    assert counts["bpm_raw_median"] < 90
    assert counts["bpm_folded_median"] > 90


def test_사분위가_중앙을_감싼다(tmp_path: Path) -> None:
    """**사분위는 거울의 한 칸이다** — 뒤집히면 「113 ~ 144」가 거짓말이 된다."""
    counts = TOOL.counted(_folder(tmp_path, [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]))

    assert counts["bpm_folded_q1"] <= counts["bpm_folded_median"] <= counts["bpm_folded_q3"]


def test_하나도_못_읽으면_운다(tmp_path: Path) -> None:
    """**박이 없으면 수를 안 낸다.** 0을 적으면 정본이 「중앙 0 BPM」이 된다."""
    with pytest.raises(LookupError):
        TOOL.counted(_folder(tmp_path, [], silent=3))


def test_빈_폴더도_운다(tmp_path: Path) -> None:
    with pytest.raises(LookupError):
        TOOL.counted(tmp_path)


def test_엔진이_접는_법을_그대로_쓴다(tmp_path: Path) -> None:
    """**접는 법을 두 벌로 만들지 않는다** (D-0117).

    탐침이 제 손으로 접으면 엔진이 `OCTAVE_FLOOR`를 바꿀 때 **정본이 조용히 낡는다.**
    그래서 판정(`from_envelopes`)에서 `folded`를 받아 사분위만 여기서 낸다.
    """
    source = (TOOL.ROOT / "tools" / "probe_tempo.py").read_text(encoding="utf-8")

    assert "from_envelopes" in source
    assert "folded_tempo" not in source, "탐침이 제 손으로 접고 있다"


def test_자의_이름이_정본과_같다() -> None:
    """**자가 바뀌면 다시 재라고 운다** (D-0374). 홉도 자의 일부다 (D-0145)."""
    assert CANON.canon()["onset"]["ruler"] == TOOL.RULER
    assert "홉" in TOOL.RULER, "자에 홉이 안 적혀 있다"


def test_집중도를_천분율_정수로_낸다(tmp_path: Path) -> None:
    """**정본은 정수만 든다** (D-0366 · D-0399). 비율은 천분율로 적고 거울이 찍는다."""
    folder = _folder(tmp_path, [120.0, 124.0, 128.0, 132.0])
    counts = TOOL.explored(TOOL.envelopes(folder))

    assert set(counts) == set(TOOL.PHASE)
    for key in (one for one in TOOL.PHASE if one.endswith("_permille")):
        assert 0 <= counts[key] <= 1000, key
    assert counts["phase_beat_q1_permille"] <= counts["phase_beat_top_permille"]
    assert counts["phase_beat_top_permille"] <= counts["phase_beat_max_permille"]


def test_박_읽기와_마디_읽기를_둘_다_낸다(tmp_path: Path) -> None:
    """**D-0206의 말이 두 가지로 읽혔다** (D-0399). 둘을 섞어 적으면 비교선이 거짓이 된다.

    또박또박 치는 합성 곡에서는 **박에 몰리고 마디엔 고르다** — 두 수가 크게 갈린다.
    """
    folder = _folder(tmp_path, [120.0, 124.0, 128.0, 132.0])
    counts = TOOL.explored(TOOL.envelopes(folder))

    assert counts["phase_beat_top_permille"] > counts["phase_bar_top_permille"] + 100


def test_선언과_정본이_같다() -> None:
    """**양방향이다** (D-0371). 안 세는 수도, 세고 버리는 수도 둘 다 결함이다.

    D-0399가 **차례를 둘로** 나눴다 — 수를 찍고, 받아서 정본을 짓는다. 이 판(D-0401)이
    그 둘째이고 `PHASE`는 이제 `EMITS`의 부분집합이다.
    """
    assert set(TOOL.EMITS) == set(CANON.canon()["onset"]["counts"])
    assert set(TOOL.PHASE) < set(TOOL.EMITS), "PHASE는 EMITS에서 끌어낸다"
    assert len(TOOL.PHASE) == 9


def test_선언을_글자로_읽을_수_있다() -> None:
    """**읽는 쪽이 글자다** (D-0401 · D-0256).

    `measured.emitted()`는 도구를 임포트하지 않고 `EMITS = (...)` 안의 **따옴표 친
    이름**을 센다 — `(*PHASE, …)`로 펼쳤더니 아홉이 안 보여 상류 검사가 울었다.
    """
    assert CANON.emitted("probe_tempo", "EMITS") == set(TOOL.EMITS)


def test_입구가_정본의_수를_찍는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` → `counted()` **배선** (D-0400 · D-0353).

    위의 열은 `counted()`를 직접 부르므로 **입구에서 그 호출이 끊겨도 안 운다** —
    전수 변이가 그것을 잡았다. 화면에 수가 없으면 `make measure`를 돌린 사람이
    **무엇이 바뀌었는지 모른다** (D-0269).
    """
    folder = _folder(tmp_path, [120.0, 128.0, 132.0])
    monkeypatch.setattr(TOOL, "counted", lambda _folder: dict.fromkeys(TOOL.EMITS, 7))
    monkeypatch.setattr("sys.argv", ["probe_tempo.py", "--out", str(folder)])

    assert TOOL.main() == 0
    said = " ".join(capsys.readouterr().out.split())

    assert "bpm_folded_median 7" in said, "counted()가 끊겼다"
    assert "phase_bar_top_permille 7" in said, "집중도가 화면에 없다"


def test_집중도가_정본의_수에_함께_든다(tmp_path: Path) -> None:
    """**`counted()`가 `explored()`를 품는다** (D-0401).

    D-0399에서는 둘이 갈려 있었다 — 정본에 키가 없어서 찍기만 했다. 이제 한 벌이고,
    `explored()`가 끊기면 **선언한 열다섯 중 아홉이 사라진다.**
    """
    counts = TOOL.counted(_folder(tmp_path, [120.0, 124.0, 128.0, 132.0]))

    assert set(counts) == set(TOOL.EMITS)
