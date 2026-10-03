#!/usr/bin/env python3
"""문서 **전체**를 보는 레이아웃 검사 (D-0356에서 `check_doc_style`에서 뗐다).

`check_doc_style.py`가 **611줄로 상한 600을 넘었다.** 문서 하나씩 보는 검사(`check_layout`
· `check_bold_density` · `check_records`)는 그쪽에 두고, **저장소 전체를 보는 넷**을 여기로
옮겼다 — `doc_fsck` → `doc_counts`와 같은 쪼개기다 (D-0350).

**`--check`를 안 받는다.** 도서관 모듈이고 입구는 `check_doc_style`이다 (D-0121).
"""

from __future__ import annotations

import check_doc_style as style

# **이름을 값으로 끌어오지 않는다** (D-0356). `from … import ROOT` 꼴로 묶으면 시험이
# `check_doc_style.ROOT`를 임시 폴더로 바꿔도 **여기는 안 따라온다** — 떼어 내자마자
# 시험 여섯이 그 자리에서 빨개졌다. 모듈로 참조하면 부를 때마다 다시 읽는다.


def check_sixth_document() -> list[str]:
    """축 셋 말고 다른 문서가 `docs/`에 생겼는가 (D-0130).

    **한 항목은 한 문서에만 산다.** 넷째 축을 만들면 그 순간 어느 시제인지 모르는
    항목이 생기고, 같은 항목이 두 곳에 살기 시작한다. 새 문서를 만들고 싶으면
    **그것은 셋 중 하나의 절이다.**

    하위 폴더까지 본다. `docs/_patch/` 같은 자리가 두 검사 사이로 빠져나가는 것이
    이 검사가 막는 일이다.
    """
    base = style.ROOT / "docs"
    if not base.is_dir():
        return []
    problems: list[str] = []
    for path in sorted(base.rglob("*.md")):
        parts = path.relative_to(base).parts
        if len(parts) == 1 and parts[0] in style.AXES:
            continue
        if len(parts) > 1 and parts[0] in style.ALLOWED_TREES:
            continue
        name = path.relative_to(style.ROOT).as_posix()
        problems.append(
            f"{name}: 여섯 번째 문서다. 미래(PLAN) · 현재(DESIGN) · 과거(DECISIONS) 중 "
            "어디의 절인지 정해 옮긴다"
        )
    return problems


def check_plan_leftovers() -> list[str]:
    """**끝난 것이 `PLAN.md`에 남아 있는가** (D-0308).

    PLAN은 미래 문서다. 갚은 빚에 취소선을 그어 두고 남기면 **미래 문서가 과거를 이고
    간다** — 실측에서 빚 표 14행 중 **13행이 취소선**이었다. 남은 진짜 빚은 하나였고
    그 하나가 열세 줄에 묻혀 있었다.

    **이 규율은 이미 옆 표에 있었다.** PLAN §2가 *"닫힌 질문은 여기 없다. 닫히면 근거는
    결정 기록으로, 한 줄 색인은 `MASTER.md` 닫힘표로 간다"*라고 적어 두었고, **빚 표만
    그것을 안 따랐다.** 한 층위에 쓴 규칙을 옆 표에 안 쓴 자리다.

    **`MASTER.md`는 안 본다.** 거기 갚음표가 사는 자리이며, 그 표의 행은 취소선 없이
    평서문으로 적는다 — 끝난 것을 끝난 자리에 적는 것은 취소선이 필요 없다.
    """
    body = (style.ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    found = [
        line.strip()
        for line in body.splitlines()
        if line.startswith("| ~~") or line.lstrip().startswith("- ~~")
    ]
    return [
        f"docs/PLAN.md에 끝난 항목이 남아 있다: {line[:60]}. "
        "근거는 결정 기록으로, 한 줄 색인은 `MASTER.md`로 옮기고 여기서 지운다 (D-0308)"
        for line in found
    ]


def check_debt_rows() -> list[str]:
    """빚 표의 **갚는 법 칸이 비어 있는가** (D-0324).

    ### 왜 행 단위여야 했나

    D-0320이 같은 검사를 **부류 단위**로 지었고 **원인이 된 자리를 못 잡았다** — 빚 표가
    한 줄이라 옆 절의 `eval`이 이 절을 덮었다. 표를 **한 줄에 한 기록**으로 바꾸자
    같은 규칙이 정확해졌다. **그물이 안 걸리면 그물을 고치기 전에 자료 모양을 본다.**

    ### 세 판 연속 같은 자리에서 틀렸다

    D-0313이 넷을 「온셋·박」으로 묶었고 둘은 그 명령이 재는 것이 아니었다 (D-0317).
    그 뒤 「화음 사전 4건」이 서로 다른 네 모듈이었고 **둘은 이미 돌 수 있었다** (D-0324).
    **번호를 나열하면 묶임이 주장을 가린다.**
    """
    body = (style.ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    if style.DEBT_TABLE not in body:
        return ["docs/PLAN.md에 빚 표(§3.1)가 없다. 없애려면 결정 기록이 필요하다 (D-0324)"]
    rest = body[body.index(style.DEBT_TABLE) :]
    end = rest.find("\n## ", 1)
    rows = [
        line
        for line in rest[: end if end > 0 else len(rest)].splitlines()
        if line.startswith("| D-")
    ]
    found = [
        f"docs/PLAN.md 빚 행에 갚는 법이 없다: {line.split('|')[1].strip()}. "
        f"명령을 백틱으로 적거나 {style.NO_TOOL[0]}·{style.NO_TOOL[1]}이라고 적는다 (D-0324)"
        for line in rows
        if "`" not in line.rsplit("|", 2)[1] and not any(word in line for word in style.NO_TOOL)
    ]
    # **행이 아니라 표 머리를 본다** (D-0345). *"그물이 비면 «전부 맞다»가 거짓으로
    # 참이 된다"*(D-0230)가 이 자의 근거였고 **옳은 걱정에 틀린 자였다** — 진짜로 다
    # 갚아서 비는 경우를 막는다. 네 행이 하루 만에 0이 되자 이 줄이 걸렸고, 걸린 이유가
    # **빚을 다 갚아서**였다. 같은 가정을 `test_debts.py`도 하고 있었다.
    if style.DEBT_HEADING not in rest:
        found.append("docs/PLAN.md 빚 표의 머리가 없다. 「갚았다」와 「표를 잃었다」가 안 갈린다")
    return found


def check_duplicates() -> list[str]:
    """문서 둘이 **같은 세 줄**을 들고 있는가 (D-0043 · D-0262).

    두 곳에 있으면 한쪽만 고치는 날이 온다. 실제로 그 날이 왔었다.
    """
    seen = {
        path.relative_to(style.ROOT).as_posix(): style.shingles(path.read_text(encoding="utf-8"))
        for path in style.targets()
    }
    problems: list[str] = []
    names = sorted(seen)
    for first in range(len(names)):
        for second in range(first + 1, len(names)):
            here, there = seen[names[first]], seen[names[second]]
            for block in sorted(set(here) & set(there)):
                head = block.splitlines()[0][:60]
                problems.append(
                    f"{names[first]}:{here[block]}와 {names[second]}:{there[block]}이 "
                    f"{style.SHINGLE}줄 겹친다 — «{head}»"
                )
    return problems
