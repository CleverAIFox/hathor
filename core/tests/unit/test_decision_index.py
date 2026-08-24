"""결정 기록 검사 도구를 **검사한다** (D-0080).

### 왜 이 파일이 따로 있는가

`sync_decision_index.py`는 D-0042 이후 `make check`가 매번 부르는 도구인데
**그 도구 자신은 한 번도 검사받지 않았다.** 그리고 색인만 보느라 `D-0076`이
사라진 것을 78건이 쌓이는 동안 못 봤다.

**검사마다 일부러 결함을 만들어 빨갛게 뜨는지 본다** (GR-0.9). 아무것도 못 잡는
검사는 늘 통과하는 하네스와 같고, D-0071이 정확히 그 자리에서 나왔다.

### 왜 `core/tests`에 있는가

도구는 `tools/`에 있고 테스트 하네스는 `core/`에 있다. 하네스를 하나 더 만드는
것보다 `sys.path`를 한 줄 늘리는 편이 싸다 — **검사가 안 도는 것보다 자리가
어색한 것이 낫다.**
"""

from __future__ import annotations

import sys

import pytest

from hathor.shared.config.paths import repo_root

sys.path.insert(0, str(repo_root() / "tools"))

import sync_decision_index as tool

HEAD = "# 결정 기록\n\n"


def record(number: int, body: str = "- **배경**: 무엇이 있었다.\n") -> str:
    return f"\n---\n\n## D-{number:04d}. 제목 {number}\n\n{body}\n"


def decisions(*numbers: int) -> str:
    return HEAD + "".join(record(number) for number in numbers)


def design(active: list[str], closed: list[str]) -> str:
    def table(rows: list[str]) -> str:
        return "| # | 항목 | 상태 |\n|---|---|---|\n" + "\n".join(rows) + "\n"

    return (
        f"{tool.OPEN_BEGIN}\n\n{table(active)}\n{tool.OPEN_END}\n\n"
        f"{tool.CLOSED_BEGIN}\n\n{table(closed)}\n{tool.CLOSED_END}\n"
    )


CLEAN_DESIGN = design(["| O-1 | 열림 | 상태 |", "| O-2 | 열림 | 상태 |"], ["| O-3 | 닫힘 | 결말 |"])


# --------------------------------------------------------------- 긁기


def test_기록을_표제_단위로_자른다():
    found = tool.scan_records(decisions(1, 2, 3))
    assert [item.number for item in found] == [1, 2, 3]
    assert found[0].title == "제목 1"
    assert "무엇이 있었다" in found[0].body


def test_기록이_없으면_색인_생성이_거부한다():
    with pytest.raises(SystemExit):
        tool.build_index("표제가 없는 글")


def test_색인은_제목을_그대로_옮긴다():
    """**요약하지 않는다.** 요약하는 순간 두 번째 진실 공급원이 된다 (D-0042)."""
    index = tool.build_index(decisions(1, 2))
    assert "| D-0001 | 제목 1 |" in index
    assert "| D-0002 | 제목 2 |" in index


# --------------------------------------------------------------- 번호


def test_깨끗한_기록에는_번호_문제가_없다():
    assert tool.check_numbering(tool.scan_records(decisions(1, 2, 3))) == []


def test_결번을_잡는다():
    """**D-0076이 이 검사에 걸렸을 것이다.**"""
    problems = tool.check_numbering(tool.scan_records(decisions(1, 3)))
    assert any("D-0002가 비어 있다" in problem for problem in problems)


def test_번호_중복을_잡는다():
    problems = tool.check_numbering(tool.scan_records(decisions(1, 1)))
    assert any("중복" in problem for problem in problems)


def test_기록이_없으면_번호_검사가_조용하다():
    assert tool.check_numbering([]) == []


# --------------------------------------------------------------- 참조


def test_깨끗한_참조에는_문제가_없다():
    text = decisions(1) + record(2, "- **배경**: D-0001을 잇는다.\n")
    assert tool.check_references(tool.scan_records(text)) == []


def test_없는_번호를_가리키면_잡는다():
    """**이것이 D-0076을 그 자리에서 잡았을 검사다.**"""
    text = decisions(1) + record(2, "- **배경**: D-0076에서 넣은 것을 고쳤다.\n")
    problems = tool.check_references(tool.scan_records(text))
    assert problems == ["D-0002가 없는 기록을 가리킨다: D-0076"]


def test_같은_번호를_여러_번_가리켜도_한_번만_알린다():
    text = decisions(1) + record(2, "- **배경**: D-0099와 D-0099.\n")
    assert len(tool.check_references(tool.scan_records(text))) == 1


# --------------------------------------------------------------- 절과 짝

FULL = "- **배경**: 무엇.\n- **결과**:\n  - 무엇을 했다.\n"


def _new(body: str) -> list[tool.Record]:
    text = decisions(*range(1, tool.FORMAT_ENFORCED_FROM)) + record(tool.FORMAT_ENFORCED_FROM, body)
    return tool.scan_records(text)


def test_필수_절이_다_있으면_통과한다():
    assert tool.check_sections(_new(FULL)) == []


@pytest.mark.parametrize("name", tool.REQUIRED_SECTIONS)
def test_필수_절이_없으면_잡는다(name):
    body = "".join(line + "\n" for line in FULL.splitlines() if f"**{name}**" not in line)
    assert any(name in problem for problem in tool.check_sections(_new(body)))


@pytest.mark.parametrize("kept,missing", [("후보", "선택"), ("선택", "후보")])
def test_후보와_선택은_양방향_짝이다(kept, missing):
    """**한쪽만 보던 것이 D-0080의 누락이다** (D-0081)."""
    problems = tool.check_sections(_new(FULL + f"- **{kept}**: 무엇.\n"))
    assert any(missing in problem for problem in problems)


def test_후보와_선택이_짝이면_통과한다():
    assert tool.check_sections(_new(FULL + "- **후보**: 둘.\n- **선택**: 앞의 것.\n")) == []


def test_옛_기록은_내용_검사를_받지_않는다():
    """**내용은 소급하지 않는다.** 채우면 그때 하지 않은 판단을 지어내는 것이다."""
    text = decisions(*range(1, tool.FORMAT_ENFORCED_FROM - 1)) + record(
        tool.FORMAT_ENFORCED_FROM - 1, "- **후보**: 둘.\n"
    )
    assert tool.check_sections(tool.scan_records(text)) == []


def test_결번_표시는_내용_검사에서_뺀다():
    """**결번은 결정이 아니라 구멍의 표시다.** 배경·결과를 요구하면 지어내게 된다."""
    text = decisions(*range(1, tool.FORMAT_ENFORCED_FROM)) + (
        f"\n---\n\n## D-{tool.FORMAT_ENFORCED_FROM:04d}. {tool.BLANK_RECORD} 유실됐다\n\n"
        "- **선택**: 결번임을 적는다.\n"
    )
    assert tool.check_sections(tool.scan_records(text)) == []


# --------------------------------------------------------------- 표기


def _layout(body: str) -> list[str]:
    return tool.check_layout([("DECISIONS", HEAD + record(1) + body)])


def test_표제_앞뒤가_규약대로면_통과한다():
    assert _layout("\n---\n\n## D-0002. 제목\n\n- **배경**: 무엇.\n") == []


def test_표제_앞에_구분선이_없으면_잡는다():
    """**49대 31로 섞여 있었다** (D-0081)."""
    assert any("`---`" in problem for problem in _layout("\n## D-0002. 제목\n\n본문\n"))


def test_표제_뒤에_빈_줄이_없으면_잡는다():
    problems = _layout("\n---\n\n## D-0002. 제목\n본문\n")
    assert any("빈 줄이 없다" in problem for problem in problems)


def test_줄이_너무_길면_잡는다():
    text = {"문서": "가" * (tool.LINE_LIMIT + 1)}
    assert any("넘는다" in problem for problem in tool.check_text_style(text))


def test_짧은_줄은_통과한다():
    assert tool.check_text_style({"문서": "가" * tool.LINE_LIMIT}) == []


def test_펜스에_언어_태그가_없으면_잡는다():
    problems = tool.check_text_style({"문서": "```\ncd core\n```\n"})
    assert any("언어 태그가 없다" in problem for problem in problems)


def test_닫는_펜스에_태그가_붙으면_잡는다():
    """**내가 실제로 저지른 결함이다** (D-0081)."""
    problems = tool.check_text_style({"문서": "```bash\ncd core\n```text\n"})
    assert any("닫는 펜스" in problem for problem in problems)


def test_펜스_짝이_안_맞으면_잡는다():
    problems = tool.check_text_style({"문서": "```bash\ncd core\n"})
    assert any("짝이 맞지 않는다" in problem for problem in problems)


def test_펜스_안의_긴_줄은_봐준다():
    """코드는 접을 수 없다. 접으면 붙여넣기가 깨진다."""
    text = {"문서": "```bash\n" + "x" * (tool.LINE_LIMIT + 20) + "\n```\n"}
    assert tool.check_text_style(text) == []


def test_표_열_수가_다르면_잡는다():
    text = {"문서": "| 가 | 나 |\n|---|---|\n| 하나 | 둘 | 셋 |\n"}
    assert any("열 수" in problem for problem in tool.check_text_style(text))


def test_이스케이프된_파이프는_열로_세지_않는다():
    """**처음에 세다가 멀쩡한 표를 결함으로 보고했다** (D-0081)."""
    text = {"문서": "| 지표 | 정의 |\n|---|---|\n| a | `\\|nA - nB\\|` |\n"}
    assert tool.check_text_style(text) == []


# --------------------------------------------------------------- 갱신 배지


def _superseding(badge: bool) -> str:
    body = "- **배경**: 무엇.\n"
    if badge:
        body = "> **갱신됨 — D-0002.** 아래 수치는 낡았다.\n\n" + body
    return HEAD + record(1, body) + record(2, "- **갱신**: D-0001 — 기준이 바뀐다.\n")


def test_배지가_있으면_통과한다():
    assert tool.check_supersession(tool.scan_records(_superseding(badge=True))) == []


def test_배지가_없으면_잡는다():
    """**낡은 수치는 기록 맨 뒤가 아니라 맨 앞에서 알려야 한다** (O-28)."""
    problems = tool.check_supersession(tool.scan_records(_superseding(badge=False)))
    assert any("배지가 없다" in problem for problem in problems)


def test_없는_기록을_갱신한다고_적으면_잡는다():
    text = decisions(1) + record(2, "- **갱신**: D-0099 — 없는 것.\n")
    problems = tool.check_supersession(tool.scan_records(text))
    assert any("없는 기록을 갱신한다고" in problem for problem in problems)


# --------------------------------------------------------------- 미해결표


def test_깨끗한_미해결표에는_문제가_없다():
    assert tool.check_open_issues(CLEAN_DESIGN) == []


def test_표식이_없으면_잡는다():
    assert tool.check_open_issues("표가 없는 문서") != []


def test_활성표_중복을_잡는다():
    text = design(["| O-1 | 하나 | 상태 |", "| O-1 | 또 하나 | 상태 |"], ["| O-3 | 닫힘 | 결말 |"])
    assert any("두 번 있다" in problem for problem in tool.check_open_issues(text))


def test_정렬이_깨지면_잡는다():
    text = design(["| O-9 | 하나 | 상태 |", "| O-2 | 둘 | 상태 |"], ["| O-3 | 닫힘 | 결말 |"])
    assert any("번호 순이 아니다" in problem for problem in tool.check_open_issues(text))


def test_활성과_닫힘에_같은_ID가_있으면_잡는다():
    text = design(["| O-1 | 하나 | 상태 |"], ["| O-1 | 닫힘 | 결말 |"])
    assert any("동시에 있다" in problem for problem in tool.check_open_issues(text))


@pytest.mark.parametrize("mark", ["~~취소선~~", "**해결.**", "**닫힘 (D-0074)**"])
def test_활성표에_닫힘_표시가_남으면_잡는다(mark):
    """실제로 O-12·O-18·O-23·O-27이 그렇게 남아 있었다."""
    text = design([f"| O-1 | {mark} | 상태 |"], ["| O-3 | 닫힘 | 결말 |"])
    assert any("닫힘 표시" in problem for problem in tool.check_open_issues(text))


# --------------------------------------------------------------- 분할 (O-30)


def test_상한_안이면_통과한다():
    assert tool.check_split([("D-0001-0050", decisions(1, 2))]) == []


def test_건수가_상한을_넘으면_잡는다():
    """**O-30이 정한 조건이 발동하는 자리다.** 문서에만 적혀 있어 아무도 안 봤다."""
    many = HEAD + "".join(record(n) for n in range(1, tool.SPLIT_RECORD_LIMIT + 2))
    assert any("건으로 상한" in problem for problem in tool.check_split([("한장", many)]))


def test_줄_수가_상한을_넘으면_잡는다():
    long = HEAD + record(1, "- **배경**: 가.\n" * (tool.SPLIT_LINE_LIMIT + 10))
    assert any("줄로 상한" in problem for problem in tool.check_split([("한장", long)]))


def test_조각_이름의_범위_밖이면_잡는다():
    """**이름이 범위다.** 안 맞으면 `grep` 없이 파일을 고를 수 없다."""
    problems = tool.check_split([("D-0001-0050", decisions(51))])
    assert any("범위 밖" in problem for problem in problems)


def test_같은_번호가_두_조각에_있으면_잡는다():
    problems = tool.check_split([("D-0001-0050", decisions(1)), ("D-0051-0100", decisions(1, 51))])
    assert any("다른 조각에도" in problem for problem in problems)


def test_조각을_이으면_머리말이_본문에_안_섞인다():
    """안 떼면 앞 조각 마지막 기록의 본문에 다음 조각 머리말이 딸려 들어간다."""
    merged = tool.merge_parts([("가", decisions(1)), ("나", "# 다른 머리말\n" + record(2))])
    assert [r.number for r in tool.scan_records(merged)] == [1, 2]
    assert "다른 머리말" not in tool.scan_records(merged)[0].body


def test_이어진_결번은_한_줄로_묶는다():
    """오타 하나로 낱개 887줄이 쏟아지면 **읽을 수 없어 안 잡은 것과 같다.**"""
    problems = tool.check_numbering(tool.scan_records(decisions(1, 900)))
    assert len(problems) == 1
    assert "898건" in problems[0]


# --------------------------------------------------------------- 전체


def test_문제를_모아_낸다():
    """**첫 문제에서 멈추지 않는다** — 고치러 여러 번 오게 하면 안 돌리게 된다."""
    text = decisions(1, 3) + record(4, "- **배경**: D-0099.\n")
    problems = tool.run_checks(
        [("DECISIONS", text)], design(["| O-2 | 하나 | 상태 |", "| O-1 | 둘 | 상태 |"], [])
    )
    assert len(problems) >= 3


def test_실제_저장소가_전_검사를_통과한다():
    """**이것이 `make check`가 매번 보는 것이다.**"""
    assert tool.run_checks(tool.load_parts(), tool.DESIGN.read_text(encoding="utf-8")) == []


def test_실제_저장소의_색인이_일치한다():
    design_text = tool.DESIGN.read_text(encoding="utf-8")
    index = tool.build_index(tool.merge_parts(tool.load_parts()))
    assert tool.BLOCK.sub(lambda _: index, design_text, count=1) == design_text
