#!/usr/bin/env python3
"""**기획서 본문의 조립** — 정본 마크다운에 그림을 박는다 (D-0368).

### 왜 떼어냈나

D-0368에서 화면을 붙이며 `build_proposal.py`가 616줄이 되어 `code` 상한 600을 넘었다
(D-0117). 이음매는 **조립(마크다운)과 쓰기(docx)**다 — 윗동은 표준 라이브러리만 쓰고
아랫동은 pandoc · python-docx가 있어야 돈다. 그래서 그 선에서 갈랐다.

```text
MASTER Part I~III (정본)
   ├─ 이 파일 → 그림 박은 마크다운 → build_proposal → docs/proposal.docx
   └─ render_proposal ──────────────────────────────→ site/proposal.html
```

**화면은 이것을 안 쓴다.** `render_proposal`은 `proposal_source.source()`를 직접 읽어
칸으로 가른다 — pandoc이 없는 CI에서도 `--check`가 돌아야 하기 때문이다. 둘이 갈릴
자리는 정본 하나뿐이고, 둘 다 `proposal_source`로만 그것을 본다 (D-0219).
"""

from __future__ import annotations

import re
from pathlib import Path

from proposal_source import SourceError, source

# 쪽 안쪽 폭/높이(인치). **그림 크기가 마크다운에 적히므로** 조립 쪽이 안다 —
# `build_proposal`도 표 폭에 쓰고 여기서 가져간다. 두 곳에 적으면 어긋난다 (D-0043).
PAGE_WIDTH_IN = 6.3
PAGE_HEIGHT_IN = 8.3


def _span(lines: list[str], heading: str) -> tuple[int, int]:
    for index, line in enumerate(lines):
        if line.strip() == heading:
            level = len(line) - len(line.lstrip("#"))
            for later in range(index + 1, len(lines)):
                match = re.match(r"^(#+) ", lines[later])
                if match and len(match.group(1)) <= level:
                    return index, later
            return index, len(lines)
    raise SourceError(
        f"그림 자리 `{heading}`이 `MASTER.md`에 없다 — 제목을 바꿨으면 FIGURES도 고친다"
    )


# ------------------------------------------------------------------ pandoc


# (제목 줄, 그림, 캡션, 자리) — 자리: replace = 절의 첫 코드 블록을 바꾼다
#                                     intro = 절의 첫 문단 뒤 · end = 절 끝
FIGURES: list[tuple[str, str, str, str]] = [
    (
        "### 목적 및 핵심가치",
        "concept",
        "서비스 개념도 — 음원은 기기를 떠나지 않고 벡터만 기획으로 간다",
        "end",
    ),
    ("### □ 추진 일정", "gantt", "추진 일정과 단계별 상태", "end"),
    (
        "## □ REQ-HATHOR 요구사항 체계도",
        "requirement_tree",
        "요구사항 체계도 — 12개 영역",
        "replace",
    ),
    ("## □ REQ-HATHOR 요구사항 체계도", "use_cases", "유스케이스 — 사용자 · 개발자", "end"),
    (
        "## □ 세부 기능 요구사항 정의서",
        "requirement_status",
        "요구사항 상태 집계 — 영역별",
        "intro",
    ),
    (
        "### □ 전체 파이프라인",
        "pipeline",
        "전체 파이프라인 — 기기 분석 · 기획 · 렌더 · 관문",
        "replace",
    ),
    # **수를 캡션에 적지 않는다** (D-0361 · GR-0.7). 「5종」이 남아 같은 기획서의
    # 다른 세 자리가 「7종」을 적는 동안 **그림 캡션만 계약 다섯을 말하고 있었다.**
    ("### □ 계층 구조 (GR-2)", "layers", "계층 구조와 import 계약", "end"),
    ("### □ 테이블 명세 (주요) — P4 설계 · 미구현", "erd", "ERD — P4 설계", "intro"),
    ("### □ ID3 프레임 실측 (1004곡 전수)", "id3_frames", "ID3 프레임 보유율 (1004곡 전수)", "end"),
    ("### □ 아티스트 표기 실측", "artist_notation", "아티스트 표기 구성", "end"),
    ("### □ 처리 순서", "ingest_flow", "인제스트 처리 순서", "replace"),
    ("### □ 델타 이벤트", "delta_states", "델타 판정 — 재스캔 이벤트 넷", "end"),
    (
        "### □ MusicBrainz 조회 개선 이력 (D-0019)",
        "musicbrainz",
        "MusicBrainz 곡 조회 성공률 개선",
        "end",
    ),
    ("## 4. 4축 특징 설계", "axes", "4축과 모델 — 스템 분리가 편곡 · 가창의 전제다", "end"),
    ("### □ 취향 신호 3층", "taste_layers", "취향 신호 3층", "end"),
    (
        "### □ 기획과 렌더를 나눈다",
        "plan_render",
        "hathor가 기획하고 엔진이 소리를 입힌다",
        "replace",
    ),
    (
        "### □ 엔진 선정 — 서류 관문 (D-0217)",
        "engine_funnel",
        "엔진 서류 관문 — 일곱에서 둘로",
        "end",
    ),
    (
        "### □ 실측 관문 — 착수 전에 적었다 (D-0217)",
        "engine_gates",
        "엔진 실측 관문 G0 ~ G3",
        "end",
    ),
    (
        "### □ G0 실측 — 기기가 떨어졌다 (D-0218)",
        "g0_runs",
        "G0 실측 — fp16 NaN · fp32 메모리 부족",
        "end",
    ),
    ("### □ 청취 판정 이력", "listening", "청취 판정 이력", "end"),
    ("### □ 청취 판정 이력", "voice_leading", "성부 진행 전후 (D-0137)", "end"),
    ("### □ 음색 누설 관문 (G2)", "leak_gate", "음색 누설 관문 G2", "replace"),
    ("### □ 지표", "retrieval", "검색 평가 — 무작위 대비", "end"),
    ("### □ 레이어 곡선 — 검색축 (D-0027)", "layer_curve", "레이어 곡선 — 검색축", "end"),
    ("### □ 층별 화성 — 화성축 (D-0181)", "harmony_layers", "층별 화성 — 화성축", "end"),
    ("### □ 패치 파이프", "patch_pipe", "패치 파이프", "replace"),
    ("### □ 검사 체계", "gate_parity", "make check · CI · 커밋 훅 대조 (실물에서 읽었다)", "end"),
    ("### □ 문서 체계", "documents", "문서 체계 — 기획서는 MASTER에서 빌드한다", "end"),
]


def _image(path: Path, caption: str) -> list[str]:
    from PIL import Image  # matplotlib이 끌고 온다

    with Image.open(path) as picture:
        width, height = picture.size
    inches = min(PAGE_WIDTH_IN, PAGE_HEIGHT_IN * width / height, width / 150)
    return ["", f"![{caption}]({path.resolve().as_posix()}){{width={inches:.2f}in}}", ""]


def place_figures(body: str, figures: dict[str, Path]) -> str:
    lines = body.splitlines()
    for heading, name, caption, where in FIGURES:
        start, end = _span(lines, heading)
        image = _image(figures[name], caption)
        if where == "replace":
            fence = next((i for i in range(start, end) if lines[i].startswith("```")), None)
            if fence is None:
                raise SourceError(f"`{heading}`에 바꿀 코드 블록이 없다")
            close = next(i for i in range(fence + 1, end) if lines[i].startswith("```"))
            lines[fence : close + 1] = image
        elif where == "intro":
            first = next(i for i in range(start + 1, end) if lines[i].strip())
            blank = next((i for i in range(first, end) if not lines[i].strip()), end)
            lines[blank:blank] = image
        else:
            while end > start and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = image
    return "\n".join(lines) + "\n"


def split_cover(text: str) -> tuple[list[str], str]:
    """표지 문단들과 본문. 마크다운은 문단 안에서 줄을 접으므로 **빈 줄로 문단을 가른다.**"""
    head, _, body = text.partition("# Part I.")
    paragraphs = [
        " ".join(line.strip() for line in block.splitlines())
        for block in re.split(r"\n\s*\n", head)
        if block.strip() and block.strip() != "---"
    ]
    return paragraphs, "# Part I." + body


def clean(markdown: str) -> str:
    markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.S)
    return markdown.replace("\n---\n", "\n")


def drawn(figures_dir: Path) -> dict[str, Path]:
    """그림 전부. **부르는 이름이 다 그려졌는지 그 자리에서 본다.**"""
    import render_charts
    import render_figures

    figures = {**render_figures.render_all(figures_dir), **render_charts.render_all(figures_dir)}
    missing = {name for _, name, _, _ in FIGURES} - set(figures)
    if missing:
        raise SourceError(f"그리지 않은 그림을 부른다: {sorted(missing)}")
    return figures


def body_markdown(figures_dir: Path) -> tuple[list[str], str]:
    """`(표지 문단, 그림이 박힌 본문 마크다운)` — pandoc에 넘길 중간 표현.

    정본을 자르는 일은 `proposal_source.source()` 하나가 하고, 이 함수는 거기에
    그림을 박는 것만 한다. 화면(`render_proposal`)도 같은 `source()`를 보므로
    **둘이 갈릴 자리가 정본 하나뿐이다** (D-0219).
    """
    figures = drawn(figures_dir)
    cover_lines, body = split_cover(source())
    return cover_lines, clean(place_figures(body, figures))
