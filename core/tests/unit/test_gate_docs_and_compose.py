"""문서 중복 · compose 메모리 · 추출 창 (D-0262).

§3의 «설계 판단에 강제 수단이 없다» 가운데 **만들 수 있는 셋**이다.

| 결정 | 적어 두고 안 지킨 것 |
|---|---|
| D-0043 | *"문서 4종에서 3줄 이상 연속 일치를 기계로 검사해 0건"* — **그 기계가 없었다** |
| D-0001 | *"메모리 상한 합계 약 2.3GB → 약 2.8GB"* — **세는 명령이 없었다** |
| D-0104 | *"창 길이는 분석 인자이며 추출 인자가 아니다"* — **고정을 아무도 안 봤다** |

셋 다 «강제자»와 «재현»이 같은 자리다. 세는 것이 곧 막는 것이다.
"""

from __future__ import annotations

from hathor.shared.config.paths import repo_root
from tests.conftest import tool_module as _tool

STYLE = _tool("check_doc_style")
# **저장소 전체를 보는 넷은 `doc_style_repo`로 뗐다** (D-0356 · 611줄 > 상한 600).
STYLE_REPO = _tool("doc_style_repo")
COMPOSE = _tool("check_compose")


# ------------------------------------------------------------------ 문서 중복


def test_문서가_세_줄을_겹치지_않는다() -> None:
    """**D-0043이 열여덟 달 전에 손으로 한 번 세고 끝냈다.** 재 보니 1건이 있었다."""
    assert STYLE_REPO.check_duplicates() == []


def test_겹치는_세_줄을_잡는다() -> None:
    same = "가나다\n라마바\n사아자"

    assert set(STYLE.shingles(f"머리\n{same}\n꼬리")) & set(STYLE.shingles(f"다른\n{same}"))


def test_빈_줄이_낀_자리는_안_센다() -> None:
    """빈 줄을 세면 **인용 부호나 표 구분선만으로 우연히 겹친다.**"""
    assert STYLE.shingles("가\n\n나\n") == {}
    assert STYLE.shingles("가\n나\n다\n")


def test_두_줄만_같으면_안_잡는다() -> None:
    """문턱이 낮으면 표 머리마다 걸리고, **그러면 사람이 검사를 끈다.**"""
    assert STYLE.SHINGLE == 3
    assert not set(STYLE.shingles("가\n나\n")) & set(STYLE.shingles("가\n나\n"))


# ------------------------------------------------------------------ compose


def test_core_합계가_천장과_같다() -> None:
    """**8GB 노트북이 기준이다** (D-0001). core는 늘 켜져 있다."""
    found = COMPOSE.services((repo_root() / "docker-compose.yml").read_text(encoding="utf-8"))
    sums = COMPOSE.totals(found)

    assert COMPOSE.verdict(sums, COMPOSE.CEILING) == []
    assert sums["core"] == COMPOSE.CEILING["core"]


def test_프로파일이_없으면_core다() -> None:
    """`profiles:`를 안 적은 서비스가 core다 — **늘 켜지는 쪽이 기본값이어야 한다.**"""
    text = "services:\n  a:\n    mem_limit: 512m\n  b:\n    mem_limit: 256m\n    profiles: [ml]\n"

    assert COMPOSE.totals(COMPOSE.services(text)) == {"core": 512, "ml": 256}


def test_기가와_메가를_같은_단위로_센다() -> None:
    text = "services:\n  a:\n    mem_limit: 1g\n  b:\n    mem_limit: 512m\n"

    assert COMPOSE.totals(COMPOSE.services(text))["core"] == 1536


def test_늘어도_줄어도_말한다() -> None:
    """**D-0117의 규율이다.** 줄어든 것을 안 말하면 천장이 헐거운 채로 남는다."""
    assert COMPOSE.verdict({"core": 3000}, {"core": 2816})
    assert COMPOSE.verdict({"core": 2000}, {"core": 2816})
    assert COMPOSE.verdict({"core": 2816}, {"core": 2816}) == []


def test_천장_없는_프로파일을_잡는다() -> None:
    """프로파일을 새로 만들고 천장을 안 적으면 **그 묶음은 세도 안 막힌다.**"""
    assert COMPOSE.verdict({"core": 2816, "gpu": 4096}, {"core": 2816})


# ------------------------------------------------------------------ 추출 창


def test_크로마_창은_추출_인자가_아니다() -> None:
    """**«창 길이는 분석 인자이며 추출 인자가 아니다»** (D-0104).

    1초로 뽑아 두고 묶는 것과 처음부터 그 길이로 뽑는 것이 같다는 것이 그 결정의 전제다.
    추출을 창 길이별로 다시 돌리기 시작하면 **1004곡 배치가 창마다 한 번씩** 돈다.
    """
    from hathor.application import ingest_all

    assert ingest_all.CHROMA_SERIES_SECONDS == 1.0

    source = (repo_root() / "core" / "hathor" / "application" / "ingest_all.py").read_text(
        encoding="utf-8"
    )
    assert "window_seconds=CHROMA_SERIES_SECONDS" in source, (
        "추출이 상수를 안 쓰고 인자를 받기 시작하면 D-0104가 깨진다"
    )


def test_창_길이가_산출물에_적힌다() -> None:
    """어떤 창으로 뽑았는지 **산출물이 들어야** 나중에 묶는 쪽이 계산할 수 있다."""
    source = (repo_root() / "core" / "hathor" / "application" / "ingest_all.py").read_text(
        encoding="utf-8"
    )

    assert '"chroma_series_seconds": CHROMA_SERIES_SECONDS' in source
