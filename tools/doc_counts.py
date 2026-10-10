#!/usr/bin/env python3
"""문서가 **세어서 적은 수**와 실물을 견주는 축 (D-0263 · D-0288 · D-0349).

### 왜 세는 자리가 필요한가

<!-- doc_fsck: ok 그때의 값을 인용한다 -->
D-0261이 여섯째 계약을 넣고 **`MASTER`의 «계약 5종» 세 곳을 안 고쳤다.** 경로도 도구도
실재하므로 다른 눈에는 안 걸렸다 — **숫자만 틀렸다.**

경로가 틀리면 명령이 죽어서 알게 되지만, **수가 틀리면 아무 일도 안 일어난다.** 읽는
사람만 틀린 것을 배운다.

### 축이 하나에서 열여섯이 됐다

`fire-lane`이 같은 자리를 `docgen.py`로 풀었다 — 정본이 있는 값마다 **축**을 선언하고,
문서는 그 수를 **들기만 한다.** 그쪽 실측이 이랬다: 전수 절 수가 **하루에 네 번** 손으로
맞춰졌고(1,004 → 1,017 → 1,030 → 1,033 → 1,036), *"손으로 적으면 낡는다"*고 적은 절
자신이 낡아 있었다.

D-0349가 일곱을 더하며 잡은 것:

| 축 | 문서가 적던 것 → 실물 |
|---|---|
| `GR 참조` | 220곳 → **206** (과거 축을 뺀 수 · D-0350) |
| `형식 면제 기록` | 78건 → **79** |
| `deadcheck 프로브` | 「넷」 → **6** (한글 수사라 축이 못 읽었다) |
| `결정 기록 검사` | 이름 열 개 손목록 → **수 하나** |
| `compose 서비스` | 7 → **10** |
| 대장 내역 셋 | 43 · 174 · 30 → **53 · 186 · 32** (합이 255였고 대장은 279) |

### 왜 이 파일로 갈랐나 (D-0349)

`doc_fsck`가 **622줄로 상한(600)을 넘었다.** `fire-lane`의 자기 진단이 그 꼴이다 —
*"세 번째까지는 「검사를 하나 더 만든다」로 대응했다. 그래서 강제자가 마흔아홉이 됐다."*
**도구를 키우는 대신 가른다.** 여기는 *"적은 수 ↔ 실물"*이고 `doc_fsck`는 *"가리키는 것이
실물로 있나"*다 — 다른 질문이다.

### 규율 둘

**정본이 없는 값은 축으로 안 만든다.** «1004곡»·«281판»은 그때의 실측이고 축이 아니다.

**정본이 사라지면 0을 내지 않고 터진다** (`LookupError`). `fire-lane`의 `doc_fsck ⑥`가
적은 그 규율이다 — ***"못 잰 것을 통과로 세지 않는다."*** 조용한 0이 곧 빈 그물이다
(D-0230).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import check_doc_style
from decision_ledger import evidence_base

ROOT = Path(__file__).resolve().parent.parent

GR_TREES = ("docs", "tools", "core/hathor", "core/tests", ".github")
"""`GR-` 참조를 셀 나무. 뿌리 `README.md`는 따로 더한다."""

LEDGER = ("<!-- decision-ledger:begin -->", "<!-- decision-ledger:end -->")
"""결정 대장이 사는 자리. **표식 밖의 `| D-xxxx |` 행은 안 센다** — `MASTER`에는
기록 번호를 드는 표가 대장 말고도 있고, 전부 세면 230과 223처럼 **말없이 갈린다.**"""

BOLD = r"\*{0,2}(\d+)\*{0,2}\s*"
"""수 하나. **굵게를 양쪽 다 받는다** — 이 문서들은 크기를 `**24**`로 적는다.

한쪽만 받다가 `대장 **201**건`을 못 찾았다. 못 찾는 축은 **조용히 통과한다**.

**한글 수사는 못 읽는다** — 「프로브 넷」이 그래서 축 밖에 있었다 (D-0349). 수는
숫자로 적는다."""


def contract_count() -> int:
    """`import-linter` 계약의 실제 수."""
    body = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    return body.count("[[tool.importlinter.contracts]]")


def record_check_count() -> int:
    """`check_decisions.run_checks`가 거느린 검사의 수. **정본은 그 함수 하나다** (D-0223).

    `MASTER`가 *"`make check`가 다음을 본다: 색인 일치 · 번호 중복·결번 · …"*라고 **손으로
    열을 적고 있었다** (D-0349). 재 보니

    | | |
    |---|---|
    | 「색인 일치」 | **D-0189가 색인을 없앴다.** 그런 검사가 없다 |
    | 목록에 없던 실물 검사 | **여섯** — 자료 · 귀속 · 강제자 둘 · 질문 참조 · 떠돌이 기록 |

    **이름을 두 곳에 적으면 한쪽만 고쳐진다** (D-0043). 그래서 문서는 **수만 든다** —
    `fire-lane`이 `docgen.py`로 푼 자리와 같은 꼴이다.
    """
    body = (ROOT / "tools" / "check_decisions.py").read_text(encoding="utf-8")
    if "def run_checks(" not in body:
        raise LookupError("`check_decisions.run_checks`를 못 찾았다. 정본이 사라졌다 (D-0223)")
    inside = body.split("def run_checks(", 1)[1].split("\n    ]", 1)[0]
    return len(re.findall(r"\*check_\w+\(", inside))


def probe_count() -> int:
    """`deadcheck`의 프로브 수. **정본은 `PROBES` 하나다** (D-0223).

    README가 *"프로브 넷"*이라 적고 있었고 실물은 다섯이었다 (D-0349). `probe_empty_net`과
    `probe_dropped_doc`이 들어온 판에 README를 안 고쳤다 — D-0261의 여섯째 계약과 같은
    꼴이다.

    **한글 수사로 적혀 있어서 이 축이 못 봤다.** 세는 자가 `(\\d+)`만 보고 「넷」은
    못 읽는다. 그래서 수는 숫자로 적는다 — `check_doc_style`이 그것을 본다 (D-0349).
    """
    body = (ROOT / "tools" / "deadcheck.py").read_text(encoding="utf-8")
    if "PROBES: dict" not in body:
        raise LookupError("`deadcheck.PROBES`를 못 찾았다. 정본이 사라졌다 (D-0223)")
    inside = body.split("PROBES: dict", 1)[1].split("\n}", 1)[0]
    return len(re.findall(r"(?m)^    \"", inside))


def _ledger() -> list[str]:
    """대장 행의 `자료` 칸. 행 수는 길이다."""
    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    if LEDGER[0] not in body:
        return []
    inside = body.split(LEDGER[0])[1].split(LEDGER[1])[0]
    return [source.strip() for source in re.findall(r"(?m)^\| D-\d{4} \|.*\| ([^|]+) \|$", inside)]


def ledger_rows() -> int:
    """결정 대장의 행 수 — **강제자를 적은 기록의 수**다 (D-0193)."""
    return len(_ledger())


def synthetic_rows() -> int:
    """대장에서 **`자료 합성`으로만 선 판단**의 수 (D-0265). PLAN §3이 이 수를 든다.

    **`(D-xxxx 승격 아님)` 꼬리표가 붙어도 여전히 합성이다** (D-0323). 그 꼬리표는
    「뒤 판이 안 올린다」는 판단이지 **자료가 실물이 됐다는 뜻이 아니다** — 떼고 센다.
    """
    return sum(1 for source in _ledger() if evidence_base(source) == "합성")


def _bucket(source: str) -> str:
    """대장 한 행의 `자료`가 네 부류 중 어디인가 (D-0349).

    **넷이 전수여야 한다** — 하나라도 새면 합이 대장 행 수와 안 맞고, 그러면 내역이
    내역이 아니다. PLAN이 **255**를 적고 실물이 **279**였던 것이 그 꼴이다.
    """
    base = evidence_base(source)
    if base == "합성":
        return "합성"
    if base == "해당 없음":
        return "해당없음"
    return "합성+실물" if base.startswith("합성") else "실물"


def mixed_rows() -> int:
    """합성과 실물을 **둘 다** 든 판단의 수 (D-0349). PLAN이 **43**이라 적고 실물은 53이었다."""
    return sum(1 for source in _ledger() if _bucket(source) == "합성+실물")


def real_rows() -> int:
    """**실물만**으로 선 판단의 수 (D-0349). PLAN이 **174**이고 실물은 186이었다."""
    return sum(1 for source in _ledger() if _bucket(source) == "실물")


def not_applicable_rows() -> int:
    """`해당 없음`의 수 (D-0349). PLAN이 **30**이고 실물은 32였다.

    D-0265가 *"`해당 없음`이 첫 번째 쓰레기통이었다"*며 18건을 되돌린 자리다 —
    **세는 자가 없으면 다시 찬다.**
    """
    return sum(1 for source in _ledger() if _bucket(source) == "해당없음")


def unknown_reproductions() -> int:
    """`재현 불명`으로 남은 기록의 수 (D-0307). PLAN §3의 빚 행이 이 수를 든다.

    **PLAN이 16이라 적고 실물은 11이었다.** 다섯이 어디서 줄었는지 아무도 모른다 — 수가
    틀려도 아무 일이 안 일어나는 자리이기 때문이다 (D-0263의 논거 그대로).

    `재현`은 *"지금 이 수치를 다시 내는 명령"*이라 **현재 사실이고 조사할 수 있다**
    (D-0136). 조사하면 줄어드는 수이므로 **세는 자리가 필요하다.**
    """
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(r"(?m)^재현 불명", body))


def frozen_issues() -> int:
    """「얼림」이 붙은 열린 질문의 수 (D-0349).

    `PLAN` §1이 *"O-54 → O-53 → O-49가 한 줄에 걸려 있고"*라 적어 **셋**으로 읽히는데
    표에는 **여덟**이 「얼림」이다. 셋은 **막는 사슬**이고 여덟은 **얼린 전부**인데
    읽는 사람이 그 둘을 가를 수 없었다 — D-0328이 두 자리가 *"서로를 몰랐다"*고 적은
    그 자리에 **수가 없었다.**
    """
    body = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    inside = body.split("<!-- open-issues:begin -->")[-1].split("<!-- open-issues:end -->")[0]
    return len(re.findall(r"(?m)^\| O-\d+ \| \*\*얼림\*\*", inside))


def open_issues() -> int:
    """열린 질문의 수. **`check_decisions`가 표 자체는 이미 보고, 여기는 산문의 수를 본다.**"""
    body = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    inside = body.split("<!-- open-issues:begin -->")[-1].split("<!-- open-issues:end -->")[0]
    return len(re.findall(r"(?m)^\| O-\d+ \|", inside))


def rule_mentions() -> int:
    """`GR-` 규약 ID를 부르는 자리의 수 — **과거 축은 뺀다** (D-0349 · D-0350).

    <!-- doc_fsck: ok 그때의 값을 인용한다 -->
    `MASTER`가 *"저장소 안에서 220곳이 그 ID를 부른다"*라 적고 있었고 실측은 달랐다.
    번호를 다시 안 매기는 **근거가 그 수**인데, 그 수가 낡으면 근거가 낡는다.

    ### 첫 안은 결정 기록까지 셌고 그것이 틀렸다

    전수가 **356**이고 그중 **153이 결정 기록**이다. 그래서 **기록에 `GR-0.5` 한 번만
    적어도 수가 흔들렸다** — 두 판 연속 356 ↔ 357로 오갔고 매번 `make docs-fix`가 필요했다.
    **매 판 뜨는 경보는 경보가 아니다** (GR-0.8).

    그래서 **살아 있는 문서와 코드만** 센다. 과거 축은 추가만 하므로 **어차피 번호를
    바꿀 때 소급 대상이고**(GR-0.2), 그 비용은 *"기록 153곳이 더 있다"*로 산문이 든다.
    """
    found = 0
    for tree in GR_TREES:
        base = ROOT / tree
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in (".md", ".py", ".toml", ".yml") or "__pycache__" in path.parts:
                continue
            if path == ROOT / "docs" / "DECISIONS.md":
                continue
            found += len(re.findall(r"GR-\d[\d.]*", path.read_text(encoding="utf-8")))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    return found + len(re.findall(r"GR-\d[\d.]*", readme))


def egress_points() -> int:
    """망 접점 허용 목록의 수. **정본은 `check_egress.ALLOWED`다** (D-0223).

    `MASTER` 두 곳과 README 한 곳이 「4곳」을 손으로 적고 있었다. 지금 맞지만 **늘어도
    아무 일이 안 일어난다** — 그리고 이 수는 **보안 주장**이다 (NFR-SEC-007).
    """
    body = (ROOT / "tools" / "check_egress.py").read_text(encoding="utf-8")
    if "ALLOWED" not in body:
        raise LookupError("`check_egress.ALLOWED`를 못 찾았다. 정본이 사라졌다")
    inside = body.split("ALLOWED", 1)[1].split("\n}", 1)[0]
    return len(re.findall(r'(?m)^    "', inside))


def grandfathered_records() -> int:
    """형식 검사가 **안 걸리는** 옛 기록의 수 (D-0349).

    `MASTER`가 **78건**이라 적고 있었고 실측은 **79**다 (`FORMAT_ENFORCED_FROM = 80`
    미만이 79건). 세 곳이 그 수를 들고 있었다 — *"78건이 쌓이는 동안"* ·
    *"78건을 손대는 순간"* · *"78건 시점에"*.

    **이 수는 추가 전용의 크기다.** 틀리면 「얼마를 안 건드리는가」가 틀린다.
    """
    threshold = re.search(
        r"(?m)^FORMAT_ENFORCED_FROM\s*=\s*(\d+)",
        (ROOT / "tools" / "check_decisions.py").read_text(encoding="utf-8"),
    )
    if not threshold:
        raise LookupError("`FORMAT_ENFORCED_FROM`을 못 찾았다. 정본이 사라졌다")
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    numbers = {int(one) for one in re.findall(r"(?m)^## D-(\d{4})\.", body)}
    return len([one for one in numbers if one < int(threshold.group(1))])


def past_rule_mentions() -> int:
    """과거 축이 든 `GR-` 참조의 수 (D-0350).

    **산문이 이 수를 들므로 이 수도 축이다.** 안 세면 `rule_mentions`를 안정시키려고
    옮긴 비용이 **다시 손으로 적힌 수**가 된다 — 같은 병이다.
    """
    body = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(r"GR-\d[\d.]*", body))


def mvp_exemptions() -> int:
    """MVP 경계의 선언된 예외 수 (D-0350).

    **예외가 조용히 자라면 규칙이 꺼진 것과 같다.** 산문이 *"예외가 아홉이고"*라 적으므로
    그 수도 축이다 — 안 세면 **다시 손으로 적힌 수**가 된다.
    """
    body = (ROOT / "tools" / "check_requirements.py").read_text(encoding="utf-8")
    if "MVP_EXEMPT = {" not in body:
        raise LookupError("`check_requirements.MVP_EXEMPT`를 못 찾았다. 정본이 사라졌다")
    inside = body.split("MVP_EXEMPT = {", 1)[1].split("\n}", 1)[0]
    return len(re.findall(r'(?m)^    "REQ-', inside))


def requirement_rows() -> int:
    """요구사항 표의 행 수 (D-0350).

    첫 측정이 **97을 72로 셌다** — 정규식이 빈 비고를 떨어뜨렸다.
    """
    body = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    return len(re.findall(r"(?m)^\|\s*REQ-[A-Z]{2,3}-\d{3}\s*\|", body))


def gate_tools() -> list[str]:
    """`--check`를 받는 관문 도구의 이름 (D-0350). **정본은 `tools/` 실물이다.**

    `MASTER` §11의 「검사 체계」 표가 **손으로 적은 목록**이라 관문을 넷 더해도 안 따라왔다 —
    CI 표가 `codeql`을 스무 판 넘게 빠뜨린 것과 같은 꼴이다.
    """
    found = []
    for path in sorted((ROOT / "tools").glob("check_*.py")):
        # **`add_argument` 꼴로 본다** (D-0350). 느슨하게 `"--check"` 문자열만 찾으면
        # **그 문자열을 쓴 이 함수 자신이 걸린다** — 실제로 그랬다.
        if re.search(r'add_argument\(\s*"--check"', path.read_text(encoding="utf-8")):
            found.append(path.stem)
    return found


def outside_tense_count() -> int:
    """`docs/`에 사는 **시제 밖** 파일 수 (D-0378).

    축 셋 말고도 실측 정본·제출본·자물쇠가 거기 산다. 디렉터리만 보면 여섯이라
    *«문서 체계가 무너졌나»*로 읽힌다 — **문서가 수를 들고 여기가 실물을 센다.**
    """
    return len(check_doc_style.OUTSIDE_TENSE)


def gate_count() -> int:
    return len(gate_tools())


def compose_services() -> list[str]:
    """`docker-compose.yml`의 서비스 이름. **정본은 그 파일이다** (D-0223).

    `doc_fsck`에도 같은 함수가 있다 — **둘 다 `docker-compose.yml`을 읽으므로 정본은
    하나다.** 저쪽은 이름으로 「문서가 적었나」를 보고 여기는 수를 센다. 함수를 공유하면
    `doc_counts` ↔ `doc_fsck` 순환 임포트가 난다.
    """
    body = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    inside = body.split("\nservices:", 1)[-1].split("\nvolumes:", 1)[0]
    return re.findall(r"(?m)^  ([a-z][a-z0-9-]*):$", inside)


def service_count() -> int:
    """서비스 수. `check_compose`가 메모리로 세는 것과 같은 실물을 센다."""
    return len(compose_services())


COUNTED: tuple[tuple[str, re.Pattern[str], Callable[[], int]], ...] = (
    ("import-linter 계약", re.compile(rf"(?:계약|import-linter)\s*{BOLD}종"), contract_count),
    ("deadcheck 프로브", re.compile(rf"프로브\s*{BOLD}종"), probe_count),
    ("결정 기록 검사", re.compile(rf"결정 기록에서\s*{BOLD}종"), record_check_count),
    ("결정 대장", re.compile(rf"대장\s*{BOLD}건\s*중"), ledger_rows),
    ("합성으로만 선 판단", re.compile(rf"합성\s*{BOLD}\s*·"), synthetic_rows),
    ("합성+실물 판단", re.compile(rf"합성\+실물\s*{BOLD}\s*·"), mixed_rows),
    ("실물만 선 판단", re.compile(rf"실물\s*{BOLD}\s*·\s*해당없음"), real_rows),
    ("해당없음 판단", re.compile(rf"해당없음\s*{BOLD}\b"), not_applicable_rows),
    ("열린 질문", re.compile(rf"열린 질문\s*{BOLD}건"), open_issues),
    ("얼린 질문", re.compile(rf"「얼림」이 붙은 행\s*{BOLD}개"), frozen_issues),
    ("compose 서비스", re.compile(rf"서비스\s*{BOLD}개"), service_count),
    ("GR 참조", re.compile(rf"저장소 안에서\s*{BOLD}곳"), rule_mentions),
    ("과거 축 GR 참조", re.compile(rf"기록에\s*{BOLD}곳이 더"), past_rule_mentions),
    ("망 접점", re.compile(rf"허용 목록\s*{BOLD}곳"), egress_points),
    ("MVP 예외", re.compile(rf"예외가\s*{BOLD}이고"), mvp_exemptions),
    ("요구사항 행", re.compile(rf"요구사항\s*{BOLD}행"), requirement_rows),
    ("관문 도구", re.compile(rf"관문 도구\s*{BOLD}개"), gate_count),
    ("docs 시제 밖", re.compile(rf"시제 밖\s*{BOLD}개"), outside_tense_count),
    ("형식 면제 기록", re.compile(rf"형식 면제\s*{BOLD}건"), grandfathered_records),
    ("재현 불명", re.compile(rf"재현 불명\s*{BOLD}건"), unknown_reproductions),
)
"""문서가 **세어서 적은 수**와 실물 (D-0263).

<!-- doc_fsck: ok 그때의 값을 인용한다 -->
D-0261이 여섯째 계약을 넣고 **`MASTER`의 «계약 5종» 세 곳을 안 고쳤다.** 경로도
도구도 실재하므로 이 검사의 다른 눈에는 안 걸렸다 — **숫자만 틀렸다.**

경로가 틀리면 명령이 죽어서 알게 되지만, **수가 틀리면 아무 일도 안 일어난다.**
읽는 사람만 틀린 것을 배운다. 그래서 세는 자리를 여기 둔다.

### 축이 하나에서 넷이 됐다 (D-0288)

`fire-lane`이 같은 자리를 `docgen.py`로 풀었다 — 정본이 있는 값마다 **축**을 선언하고,
문서는 그 수를 **들기만 한다.** 그쪽 실측이 이랬다: 전수 절 수가 **하루에 네 번** 손으로
맞춰졌고(1,004 → 1,017 → 1,030 → 1,033 → 1,036), *"손으로 적으면 낡는다"*고 적은 절
자신이 낡아 있었다.

<!-- doc_fsck: ok 그때의 값을 인용한다 -->
우리도 같은 값을 물었다. **「대장 201건 중」이 실물 223일 때까지 아무도 안 셌다** — 그
줄이 사는 표의 머리말이 *"크기를 재서 적는다. 안 재고 적으면 영원히 다음 세션이다"*다.

**블록 표식(`<!--gen: 축-->`)은 안 쓴다.** 그쪽 수는 제목 줄에 살고 우리 수는 **표 칸
안에** 사는데, 빈 줄이 표를 끊는다(`check_doc_style`). 대신 **라벨 옆의 수**를 읽는다 —
그쪽이 2026-09-02에 「정답이 파일 어딘가에 있나」만 보던 구멍을 메운 방식이다.

**정본이 없는 값은 축으로 안 만든다.** «1004곡»·«281판»은 그때의 실측이고 축이 아니다."""
