"""**아티스트는 태그에서 온다** (D-0446).

D-0374가 *첫 하이픈에서 자르는 자*를 `probe_artist` · `probe_id3`에서 고쳤는데
`probe_latent`는 손이 안 갔다. 고친 것이 *결함*이 아니라 **그 파일의 결함**이었고,
같은 자가 셋째 도구에서 넉 달을 더 살았다.

**전수는 그의 기기에서만 돈다** — 입력이 `var/ingest`다. 여기 시험은 **세는 법**과
**막는 자리**를 본다: 뭉치면 안 될 둘이 안 뭉치는지, 표가 모자라면 멈추는지.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from tests.conftest import tool_module

TOOL = tool_module("probe_latent")

# **같은 첫 토막을 가진 서로 다른 아티스트.** 옛 자는 둘 다 `g`로 읽었다.
TRACKS = (
    ("G-DRAGON-무제.mp3", "G-DRAGON"),
    ("G-DRAGON-삐딱하게.mp3", "G-DRAGON"),
    ("G-IDLE-퀸카.mp3", "G-IDLE"),
    ("Anne-Marie-2002.mp3", "Anne-Marie"),
)


def _plant(root: Path) -> None:
    """`var/ingest/scan-*.jsonl` 한 벌. `probe_artist`가 읽는 꼴 그대로다."""
    root.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"source_key": key, "tags": {"artist": artist}}, ensure_ascii=False)
        for key, artist in TRACKS
    ]
    (root / "scan-2026-10-20.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    _plant(tmp_path)
    found = cast("dict[str, str]", TOOL.load_artists(tmp_path))
    monkeypatch.setattr(TOOL, "ARTISTS", found)
    return found


def test_이름_안의_하이픈과_안_싸운다(table: dict[str, str]) -> None:
    """**`G-DRAGON`이 `g`가 되면 `G-IDLE`과 한 사람이 된다** (D-0374).

    제외 마스크가 그만큼 넓어지고, 덜어낸 후보가 **점수를 내린다** — 틀린 쪽으로
    보수적이라 수가 작게 나오고 그것이 임베딩 탓으로 읽힌다.
    """
    assert table["G-DRAGON-무제.mp3"] == table["G-DRAGON-삐딱하게.mp3"]
    assert table["G-DRAGON-무제.mp3"] != table["G-IDLE-퀸카.mp3"]
    assert table["Anne-Marie-2002.mp3"] == "anne-marie"


def test_옛_자였으면_뭉쳤다() -> None:
    """**양성 대조** (D-0259). 심은 표본이 옛 결함을 실제로 드러내는지 본다.

    이 단언이 깨지면 표본이 **아무것도 안 가르는 것**이고, 위 시험은 늘 통과한다.
    """
    old = {key: Path(key).stem.split("-", 1)[0].strip().casefold() for key, _ in TRACKS}

    assert old["G-DRAGON-무제.mp3"] == old["G-IDLE-퀸카.mp3"] == "g"


def test_제외_마스크가_아티스트를_가른다(table: dict[str, str]) -> None:
    """`masks()`가 쓰는 자리. **같은 아티스트만 제외하고 남은 둘은 안 뺀다.**"""
    keys = [key for key, _ in TRACKS]
    labels = dict.fromkeys(keys, "C major")

    _, excluded = TOOL.masks(keys, labels)

    # 0·1이 같은 아티스트, 2·3은 각자. 대각선은 늘 제외다.
    assert excluded[0][1] and excluded[1][0]
    assert not excluded[0][2]
    assert not excluded[2][3]
    assert all(excluded[index][index] for index in range(len(keys)))


def test_표에_없으면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**조용히 파일명으로 안 떨어진다** (D-0292).

    되돌아가면 옛 자가 이 도구에서만 살아나고 화면에는 아무 표시도 안 남는다.
    """
    monkeypatch.setattr(TOOL, "ARTISTS", {})

    with pytest.raises(LookupError, match="아티스트가 표에 없다"):
        TOOL.artist_of("G-DRAGON-무제.mp3")


def test_산출물이_없으면_빈_표다(tmp_path: Path) -> None:
    """`scan-*.jsonl`이 없을 때. **빈 표를 내고 멈추는 것은 `main`이 한다.**"""
    assert TOOL.load_artists(tmp_path) == {}


def test_표가_모자라면_멈춘다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**라벨이 표보다 많으면 1을 낸다** (D-0230). 덜 덮은 채 도는 것이 가장 나쁘다."""
    _plant(tmp_path)
    monkeypatch.setattr(TOOL, "ARTISTS", {})
    monkeypatch.setattr(TOOL, "labels_of", lambda _out: ({"없는곡.mp3": "C major"}, "심은 것"))
    monkeypatch.setattr("sys.argv", ["probe_latent.py", "--out", str(tmp_path)])

    assert TOOL.main() == 1
    assert "아티스트 표가 1곡을 못 덮는다" in capsys.readouterr().err


def test_마스크가_정답과_제외를_가른다(table: dict[str, str]) -> None:
    """정답은 **같은 조성 · 다른 아티스트**다. 둘을 겹쳐 놓으면 음색을 재게 된다."""
    keys = [key for key, _ in TRACKS]
    labels = {
        "G-DRAGON-무제.mp3": "C major",
        "G-DRAGON-삐딱하게.mp3": "C major",
        "G-IDLE-퀸카.mp3": "C major",
        "Anne-Marie-2002.mp3": "A minor",
    }

    relevant, _ = TOOL.masks(keys, labels)

    assert relevant[0][2], "같은 조성 · 다른 아티스트는 정답이다"
    assert not relevant[0][1], "같은 아티스트는 정답에서 빠진다"
    assert not relevant[0][3], "다른 조성은 정답이 아니다"
    assert not np.any(np.diag(relevant)), "자기 자신은 정답이 아니다"
