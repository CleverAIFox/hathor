"""망 송신 접점 검사의 단위 검사 (D-0134).

**오디오 비이동(D-0015)은 이 저장소에서 어기면 가장 나쁜 규약이다.** 그런데 D-0132가
`강제자`를 전수로 채울 때까지 **아무것도 그것을 지키지 않았다.**
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from tests.conftest import tool_module

ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    """`tools/check_egress.py`. 싣는 자리는 `tests.conftest` 하나다 (D-0272)."""
    return tool_module("check_egress")


CHECKER = _module()


def _tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, text: str) -> list[str]:
    target = tmp_path / "core" / "hathor" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "ALLOWED", {})
    # **경로로 실은 모듈의 속성은 `mypy`가 못 본다** — 그 반환은 `Any`다 (D-0264).
    # 여기 적는 형이 곧 «이 도구가 무엇을 내는가»에 대한 시험의 주장이다.
    return cast("list[str]", CHECKER.check())


# ------------------------------------------------------------------ 잡는다


def test_새_망_접점을_잡는다(tmp_path, monkeypatch):
    problems = _tree(tmp_path, monkeypatch, "interfaces/rest/api.py", "import httpx\n")
    assert len(problems) == 1
    assert "httpx" in problems[0]


def test_from_임포트도_잡는다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a.py", "from urllib import request\n")


def test_하위_폴더까지_본다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a/b/c.py", "import socket\n")


def test_허용_목록이_실물보다_넓으면_잡는다(tmp_path, monkeypatch):
    """**목록이 실물보다 넓으면 방패가 아니라 사각지대다.**"""
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "ALLOWED", {"없는파일.py": "사유"})
    problems = CHECKER.check()
    assert problems and "없다" in problems[0]


# ------------------------------------------------------------------ 안 잡는다


def test_파일을_여는_것은_안_본다(tmp_path, monkeypatch):
    """**로컬 분석은 당연히 음원을 읽는다.** 막으려는 것은 기기 밖으로 나가는 것이다."""
    assert _tree(tmp_path, monkeypatch, "a.py", "from pathlib import Path\nopen('x.mp3')\n") == []


def test_넘파이는_망이_아니다(tmp_path, monkeypatch):
    assert _tree(tmp_path, monkeypatch, "a.py", "import numpy as np\n") == []


# ------------------------------------------------------------------ 저장소


def test_접점을_이름으로_못_박는다():
    """**구멍을 못 박아 두면 다음 구멍은 이 검사를 지나야 생긴다.**

    D-0146이 `tools`를 훑기 시작하며 하나가 늘었다 — `probe_musicbrainz.py`가
    `urllib`을 쓰는데 **검사 밖이었다.** D-0215가 셋으로 늘렸고 **D-0216이 도로 둘로
    줄였다** — 쓰지 않을 탐침을 위해 구멍을 열어 두지 않는다. D-0224가 로컬 서버에만 붙는
    둘(MLflow · Prefect)을 더했다. **D-0424가 셋째 바깥 접점을 열었다** — 논문 훑기이며
    **질의가 분야 이름과 날짜뿐이고 받기만 한다.** 오디오도 라이브러리도 안 나간다.
    """
    assert set(CHECKER.ALLOWED) == {
        "core/hathor/infrastructure/musicbrainz_lookup.py",
        "tools/probe_musicbrainz.py",
        "tools/mlflow_sync.py",
        "tools/prefect_flow.py",
        "tools/watch_papers.py",
    }
    # **밖으로 가는 것을 이름으로 센다.** 셋이고 **셋 다 오디오를 안 만진다** —
    # MusicBrainz 둘은 아티스트·제목 문자열을, 논문 훑기는 분야 이름과 날짜를 보낸다.
    outward = {name for name, reason in CHECKER.ALLOWED.items() if "로컬 주소" not in reason}
    assert outward == {
        "core/hathor/infrastructure/musicbrainz_lookup.py",
        "tools/probe_musicbrainz.py",
        "tools/watch_papers.py",
    }


def test_이름에_망이_안_보이는_클라이언트도_센다():
    """**D-0224.** `mlflow` · `prefect`는 HTTP 클라이언트인데 `requests`가 이름에 없다."""
    assert {"mlflow", "prefect"} <= set(CHECKER.NETWORK)


def test_도구도_훑는다():
    """**도구도 이 기기에서 돈다.** 나무를 빼면 그만큼이 사각지대다."""
    assert "tools" in CHECKER.TREES
    assert any(path.as_posix().endswith("probe_musicbrainz.py") for path in CHECKER.found_files())


def test_허용된_접점이_사유를_적는다():
    """**늘리지 않는 것이 목표다.** 사유 없는 줄은 다음 줄을 부른다."""
    for reason in CHECKER.ALLOWED.values():
        assert len(reason) > 30


def test_저장소가_통과한다():
    assert CHECKER.check() == []


# ------------------------------------------------------- 내역 (D-0446)


def test_내역이_총합_안에_있다():
    """`OUTWARD`는 `ALLOWED`의 부분집합이다. 어긋나면 밖+로컬이 총합과 안 맞는다."""
    assert CHECKER.pairing_problems() == []
    assert set(CHECKER.OUTWARD) <= set(CHECKER.ALLOWED)


def test_내역이_어긋나면_운다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**양성 대조** (D-0259). 심은 어긋남에 안 울면 이 자가 장식이다."""
    monkeypatch.setattr(CHECKER, "OUTWARD", frozenset({"tools/없는것.py"}))

    problems = cast("list[str]", CHECKER.pairing_problems())

    assert len(problems) == 1
    assert "없는것.py" in problems[0]


def test_내역을_훑기와_안_섞는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**`check()`는 나무만 본다** (D-0446).

    처음엔 이 약속을 `check()`에 끼웠고, `ALLOWED`를 비우고 부르는 시험 셋이 **심은
    나무마다 경고 세 줄**을 받았다 — 진짜 발견을 덮는다.
    """
    target = tmp_path / "core" / "hathor" / "a.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("import httpx\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "ALLOWED", {})

    problems = cast("list[str]", CHECKER.check())

    assert len(problems) == 1
    assert "OUTWARD" not in problems[0]


def test_밖과_로컬의_합이_총합이다():
    """축 셋이 같은 정본을 본다 (D-0304). 하나만 고쳐지는 날을 막는다.

    **첫 판은 아무것도 안 걸었다** (D-0470). `local_points()`의 몸이
    `egress_points() - outward_points()`이므로 **합이 총합인 것은 산수다** —
    측정이 아니다. 두 정규식을 다 비워 셋이 전부 0이 돼도 초록이었다.

    축이 세는 길은 **파일을 긁는 정규식**이고 정본은 **파이썬이 읽은 값**이다.
    거는 것은 그 둘이 같은가여야 한다 (GR-0.5: 안 센 것을 통과로 세지 않는다).
    """
    counts = tool_module("doc_counts")

    assert counts.egress_points() == len(CHECKER.ALLOWED)
    assert counts.outward_points() == len(CHECKER.OUTWARD)
    assert counts.local_points() == len(set(CHECKER.ALLOWED) - CHECKER.OUTWARD)
    assert set(CHECKER.ALLOWED) >= CHECKER.OUTWARD, "밖 목록에 허용 밖 경로가 있다"
    assert counts.local_points() > 0, "로컬이 0이면 빼서 내는 축이 빈 그물이다 (D-0230)"
