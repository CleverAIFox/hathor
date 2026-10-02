"""관문 시야 못의 단위 검사 (D-0349).

**못도 관문이라 자기 시험이 있어야 한다** — D-0257이 `check_coverage`와 `deadcheck`를
그렇게 셌다. 톱니를 지키는 것을 지키는 것이 없으면 조용히 헐거워진 판정이 몇 판이고
통과한다.

**여기 있는 셋은 카나리아다** — `("",)`를 되살리고, 상수를 비우고, 빼는 목록을 늘려서
**못이 우는지** 본다. 그 셋이 D-0349가 실제로 당한 꼴이다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import tool_module as _tool

SIGHT = _tool("check_sight")
ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ 방향


@pytest.mark.parametrize("name", ["SKIP_TREES", "SKIP_FILES", "ALLOWED", "IGNORE_X", "EXCLUDE"])
def test_빼는_목록은_천장이다(name: str) -> None:
    """**늘면 그물이 줄어든다.** 이쪽만 반대 방향이다."""
    assert SIGHT.is_ceiling(name)


@pytest.mark.parametrize("name", ["DOCUMENTS", "TREES", "NETWORK", "CEILING", "FLOOR"])
def test_모으는_목록은_바닥이다(name: str) -> None:
    assert not SIGHT.is_ceiling(name)


def test_방향표가_비면_모든_천장이_뒤집힌다() -> None:
    """`WIDENS`가 비면 `startswith(())`가 늘 거짓이 되어 **천장이 전부 바닥이 된다.**

    그래서 `check_sight.WIDENS`를 못 장부에 넣어 뒀다 — **자기를 안 보는 검사**가 바로
    D-0257이 센 그것이다.
    """
    assert SIGHT.WIDENS, "빈 머리표는 모든 천장을 바닥으로 뒤집는다"
    assert "" not in SIGHT.WIDENS, '`startswith("")`는 늘 참이다 (D-0349)'
    assert "check_sight.WIDENS" in SIGHT.PINNED


# ------------------------------------------------------------------ 읽기


def test_상수를_실행하지_않고_읽는다(tmp_path: Path) -> None:
    """**AST로 읽는다.** 임포트하면 못이 검사 대상의 부작용에 매인다."""
    planted = tmp_path / "터진다.py"
    planted.write_text(
        'raise SystemExit("나를 실행하면 안 된다")\nA = ("하나", "둘")\n', encoding="utf-8"
    )

    assert SIGHT.collections(planted) == {"A": ("하나", "둘")}


def test_사전은_열쇠를_센다(tmp_path: Path) -> None:
    planted = tmp_path / "사전.py"
    planted.write_text('LIMITS = {"code": 300, "test": 500}\n', encoding="utf-8")

    assert SIGHT.collections(planted) == {"LIMITS": ("code", "test")}


def test_문자열이_아닌_묶음은_안_센다(tmp_path: Path) -> None:
    """수의 묶음은 그물이 아니다. **세면 `--update`가 매번 울고 못이 소음이 된다** (GR-0.8)."""
    planted = tmp_path / "수.py"
    planted.write_text('WINDOWS = (1024, 2048)\nNAMES = ("가",)\n', encoding="utf-8")

    assert SIGHT.collections(planted) == {"NAMES": ("가",)}


def test_소문자는_안_센다(tmp_path: Path) -> None:
    """상수만 본다. 지역 변수까지 세면 못이 구현을 못 고치게 막는다."""
    planted = tmp_path / "소문자.py"
    planted.write_text('wanted = ("가", "나")\nWANTED = ("가",)\n', encoding="utf-8")

    assert SIGHT.collections(planted) == {"WANTED": ("가",)}


def test_장부_자신은_안_센다() -> None:
    """**고정점이 있어야 한다.** 장부를 세면 못 하나 박을 때마다 장부 크기가 바뀐다."""
    assert SIGHT.REGISTRY not in SIGHT.measure()


# ------------------------------------------------------------------ 판정 (카나리아)


def test_빈_문자열에_운다() -> None:
    """**그날의 사고를 그대로 되살린다** — `SKIP_TREES = ("",)`.

    세는 수로는 1개라 바닥에도 천장에도 안 걸린다. **빈 문자열 규칙만이 이것을 잡는다.**
    """
    problems = SIGHT.verdict({"x.SKIP_TREES": ("",)}, {"x.SKIP_TREES": 1})

    assert problems, '`("",)`를 심었는데 못이 안 운다'
    assert "빈 문자열" in problems[0]


def test_그물이_줄면_운다() -> None:
    assert SIGHT.verdict({"x.DOCUMENTS": ()}, {"x.DOCUMENTS": 4})
    assert not SIGHT.verdict({"x.DOCUMENTS": ("가",) * 5}, {"x.DOCUMENTS": 4})


def test_빼는_목록이_늘면_운다() -> None:
    assert SIGHT.verdict({"x.SKIP_FILES": ("가", "나")}, {"x.SKIP_FILES": 1})
    assert not SIGHT.verdict({"x.SKIP_FILES": ()}, {"x.SKIP_FILES": 1})


def test_상수가_사라지면_운다() -> None:
    """**지우는 것이 비우는 것보다 조용하다.** 이름이 없으면 무엇을 봤는지도 모른다."""
    problems = SIGHT.verdict({}, {"x.DOCUMENTS": 4})

    assert problems and "사라졌다" in problems[0]


def test_새_상수는_그냥_통과한다() -> None:
    """못이 안 박힌 것은 막지 않는다. **새 도구마다 빨개지면 사람이 못을 끈다.**"""
    assert not SIGHT.verdict({"x.NEW": ("가",)}, {})


def test_첫_문제에서_안_멈춘다() -> None:
    problems = SIGHT.verdict(
        {"x.DOCUMENTS": (), "x.SKIP_FILES": ("가", "나")},
        {"x.DOCUMENTS": 4, "x.SKIP_FILES": 1, "x.사라진것": 2},
    )

    assert len(problems) == 3, problems


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다() -> None:
    assert SIGHT.verdict(SIGHT.measure(), SIGHT.PINNED) == []


def test_못이_실측과_같다() -> None:
    """**못이 실측과 어긋나면 다음 판에 터진다.** `--update`가 멱등인지 보는 자리다."""
    seen = SIGHT.measure()
    assert {key: len(items) for key, items in seen.items()} == SIGHT.PINNED


def test_모든_관문_도구를_본다() -> None:
    """**못이 보는 도구가 줄면 못도 D-0349를 당한다.**"""
    tools = {key.split(".", 1)[0] for key in SIGHT.measure()}

    assert len(tools) >= 20, tools
    for wanted in (
        "check_issue_mentions",
        "check_egress",
        "deadcheck",
        "check_secrets",
        "check_sight",
    ):
        assert wanted in tools, f"{wanted}를 안 본다"


# ------------------------------------------------------------------ 방향 (D-0349 · fire-lane)


def test_느슨해지는_쪽은_안_쓴다() -> None:
    """**`fire-lane`에서 가져왔다** — `ratchet.py:87`의 `DIRECTIONS`.

    저쪽 머리말이 적는다: ***"느슨해진 래칫은 초록으로 위장한다."*** 커버리지 래칫이
    14인데 실물이 24%인 것을 **나흘간** 아무도 몰랐다.

    첫 판의 `--update`는 실측을 그대로 적었다. 그러면 **상수를 비운 사람이 `--update`
    한 번으로 못을 같이 내릴 수 있고, 그것이 이 못이 막으려던 사고 그 자체다.**
    """
    assert SIGHT.loosening({"x.DOCUMENTS": ()}, {"x.DOCUMENTS": 4})
    assert SIGHT.loosening({"x.SKIP_FILES": ("가", "나")}, {"x.SKIP_FILES": 1})
    assert SIGHT.loosening({}, {"x.사라진것": 2})


def test_조이는_쪽은_쓴다() -> None:
    assert SIGHT.loosening({"x.DOCUMENTS": ("가",) * 9}, {"x.DOCUMENTS": 4}) == []
    assert SIGHT.loosening({"x.SKIP_FILES": ()}, {"x.SKIP_FILES": 1}) == []


def test_지금_저장소는_느슨해지는_쪽이_아니다() -> None:
    assert SIGHT.loosening(SIGHT.measure(), SIGHT.PINNED) == []


# ------------------------------------------------------------------ 면제 역검증 (fire-lane)


def test_쓸모_없어진_면제가_없다() -> None:
    """**`fire-lane`의 `assert bad`를 가져왔다** (`test_layering.py:139`).

    저쪽 규율: *"`EXEMPT`에 있는데 이미 깨끗하다 → 줄을 지워라. **면제가 낡으면 그 자리가
    사각지대가 된다.**"*

    여기서는 **건너뛰는 번호**를 본다. `SKIP_NUMBERS`에 사유를 적고 면제했는데 그 번호가
    나중에 두 표에 들어가면, 면제는 **아무것도 안 하면서 다음 고아를 숨길 자리**로 남는다.
    """
    mentions = _tool("check_issue_mentions")
    design = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    closed = {int(key.removeprefix("O-")) for key in mentions.closed_issues(design)}
    opened = {int(key.removeprefix("O-")) for key in mentions.open_issues(plan)}

    for number in mentions.SKIP_NUMBERS:
        assert number not in closed | opened, (
            f"O-{number}이 이제 표에 있다. `SKIP_NUMBERS`에서 지운다 — "
            "쓸모 없어진 면제는 다음 고아를 숨긴다"
        )
