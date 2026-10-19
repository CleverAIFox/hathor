"""입구를 실제로 지나는 시험 (D-0432).

### 왜 이 파일이 따로 있는가

`mutate_gate`는 **`main()` 안에서 제 함수를 부르는 줄을 끊고** 그 도구를 여는 시험이
우는지 본다 (D-0353). 주 1회 전수가 **안 운 배선 9곳**을 들고 왔다 —
`watch_papers` 셋 · `tree_guard` 넷 · `check_patch` 하나 · `probe_tempo` 하나.

넷 다 시험은 있었다. 다만 **함수를 직접 불렀다.** `WATCH.arxiv(8)`처럼 부르면
`main()`에서 그 줄을 지워도 시험은 멀쩡하다 — **재는 것이 셈이지 배선이 아니었다.**

그래서 여기 있는 시험은 전부 **`main()`을 부른다.** 셈을 다시 재지 않는다 — 그쪽은
각 도구의 시험 파일이 이미 본다. 여기서 보는 것은 **그 셈이 입구에 걸려 있는가**다
(D-0126).

**천장을 안 올렸다** (D-0117). `WIRING_CEILING = 0`은 그대로다.
"""

from __future__ import annotations

import collections
import json
import sys
from typing import TYPE_CHECKING

import pytest

from tests.conftest import tool_module

if TYPE_CHECKING:
    from pathlib import Path

ATOM = (
    b"<feed><entry><id>http://arxiv.org/abs/2610.00001v1</id>"
    b"<title>Chord aware music generation</title>"
    b"<summary>Symbolic MIDI preference study. Second sentence.</summary>"
    b"<published>2026-10-13T00:00:00Z</published></entry></feed>"
)


# ------------------------------------------------------------------ watch_papers


def test_논문_훑기_입구가_셋을_다_부른다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`arxiv()` · `lines()` · `write()` — **셋 다 `main()`에 걸려 있어야 한다.**

    끊어 보면 각각 이렇게 드러난다. 후보가 안 나오거나(`arxiv`), 제목이 안 찍히거나
    (`lines`), `PLAN`이 안 바뀐다(`write`).
    """
    watch = tool_module("watch_papers")
    monkeypatch.setattr(watch, "fetch", lambda url, timeout=30: ATOM)
    plan = tmp_path / "PLAN.md"
    plan.write_text("# 계획\n\n## 4. 읽을 후보\n\n설명 줄\n", encoding="utf-8")
    monkeypatch.setattr(watch, "PLAN", plan)
    monkeypatch.setattr(watch, "ROOT", tmp_path)

    assert watch.main(["--write"]) == 0
    said = capsys.readouterr().out
    after = plan.read_text(encoding="utf-8")

    assert "2610.00001" in said, "후보를 안 물었다 — arxiv()가 입구에 없다"
    assert "Chord aware" in said, "줄을 안 만들었다 — lines()가 입구에 없다"
    assert "훑은 날" in after, "PLAN에 안 붙였다 — write()가 입구에 없다"
    assert "설명 줄" in after, "본문을 지웠다"


# ------------------------------------------------------------------ tree_guard


def _watched(root: Path, count: int) -> None:
    (root / "tools").mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (root / "tools" / f"t{index}.py").write_text("x = 1\n", encoding="utf-8")


def test_나무_지킴이_입구가_넷을_다_부른다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`fingerprint()` · `where()` 둘 · `changed()` — **실물 트리는 안 건드린다.**

    `ROOT`를 가짜로 돌리고 `WATCHED`를 한 갈래로 줄인다. 이 도구가 막으려는 사고가
    *«시험이 실물 저장소를 고쳤다»*이므로 **이 시험이 그 사고를 내면 안 된다** (D-0398).
    """
    guard = tool_module("tree_guard")
    fake = tmp_path / "저장소"
    _watched(fake, guard.FLOOR + 1)
    spot = tmp_path / "지문.json"
    monkeypatch.setattr(guard, "ROOT", fake)
    monkeypatch.setattr(guard, "WATCHED", ("tools",))
    monkeypatch.setattr(guard, "where", lambda: spot)

    monkeypatch.setattr(sys, "argv", ["tree_guard.py", "--snapshot"])
    assert guard.main() == 0, "지문을 못 떴다 — fingerprint()가 입구에 없다"
    assert spot.exists(), "지문을 안 썼다 — where()가 입구에 없다"
    assert len(json.loads(spot.read_text(encoding="utf-8"))) == guard.FLOOR + 1

    monkeypatch.setattr(sys, "argv", ["tree_guard.py", "--check"])
    assert guard.main() == 0, "안 바뀐 트리를 바뀌었다고 한다"

    (fake / "tools" / "t0.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    assert guard.main() == 1, "고쳐진 파일을 못 봤다 — changed()가 입구에 없다"
    assert "t0.py" in capsys.readouterr().err


# ------------------------------------------------------------------ check_patch


def test_패치_검사_입구가_합본을_가른다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`merged_head()`가 **요약 줄에 걸려 있어야 한다** (D-0426 · GR-0.5).

    끊으면 합본 커밋에서도 *«뽑기 실측 1판»*이 찍힌다 — **안 돌린 것을 돌렸다고
    적는 것**이고, 그것이 D-0426이 막으려던 자리다.
    """
    patch = tool_module("check_patch")
    for name in ("check_heads", "check_floor", "check_after_table", "pull_once"):
        monkeypatch.setattr(patch, name, lambda: [])
    monkeypatch.setattr(patch, "has_parent", lambda: True)
    monkeypatch.setattr(patch, "merged_head", lambda: True)
    monkeypatch.setattr(sys, "argv", ["check_patch.py", "--check"])

    assert patch.main() == 0
    said = capsys.readouterr().out

    assert "건너뜀" in said, "합본인데 돌렸다고 적는다 — merged_head()가 입구에 없다"
    assert "실측 1판" not in said


# ------------------------------------------------------------------ probe_tempo


def test_템포_반쪽_입구가_포락선을_읽는다(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`envelopes()`가 **`--split`에 걸려 있어야 한다** (D-0410).

    끊으면 빈 손이 `parted()`로 가고, 그러면 **0곡으로 낸 수**가 화면에 찍힌다 —
    못 잰 것을 잰 것으로 적는 자리다 (GR-0.5).
    """
    probe = tool_module("probe_tempo")

    def _parted(loaded: list[object]) -> dict[str, int]:
        if not loaded:
            raise LookupError("반쪽을 낸 곡이 없다")
        counts: dict[str, int] = collections.defaultdict(int)
        counts["split_read"] = len(loaded)
        return counts

    monkeypatch.setattr(probe, "find_envelope_root", lambda root: tmp_path)
    monkeypatch.setattr(probe, "envelopes", lambda folder: [object(), object()])
    monkeypatch.setattr(probe, "parted", _parted)
    monkeypatch.setattr(sys, "argv", ["probe_tempo.py", "--split"])

    assert probe.main() == 0
    assert "반쪽을 낸 곡 2개" in capsys.readouterr().out, "envelopes()가 입구에 없다"
