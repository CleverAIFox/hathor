#!/usr/bin/env python3
"""기획서의 구조도를 정본에서 그린다 — graphviz (D-0221).

### 손으로 그리지 않는다

그림이 문서와 따로 살면 한쪽만 고쳐진다. 요구사항 체계도는 `MASTER.md`의 체계도 블록에서,
ERD는 테이블 명세 표에서, 검사 관문 대조는 Makefile · CI · 훅에서 **읽어서** 그린다. 읽을
수 없는 모양이면 `SourceError`로 멈춘다 — 옛 그림을 조용히 내지 않는다.

개념도(서비스 흐름 · 계층 · 관문 흐름)는 구조가 설계 자체라 코드에 적는다. 그 구조가 바뀌면
결정 기록이 먼저 바뀐다.

    python3 tools/render_figures.py --out var/proposal/figures
"""

# 그림 글자에 곱셈표 · 빼기표 같은 조판 기호를 쓴다. 코드가 아니라 사람이 읽는 라벨이다.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from proposal_source import ROOT, SourceError, code_block, plain, section, source, tables

NAVY = "#1F4E79"
INK = "#2F3B4A"
BLUE = "#DCE8F5"
GREEN = "#DFF0E3"
AMBER = "#FCEBD2"
ROSE = "#F8DCDC"
GRAY = "#ECEEF1"
FONTS = ("Noto Sans CJK KR", "Malgun Gothic", "NanumGothic", "Apple SD Gothic Neo")


def korean_font() -> str:
    """설치된 한글 글꼴. 없으면 멈춘다 — 네모 칸이 찍힌 그림을 내지 않는다."""
    listed = subprocess.run(["fc-list", ":lang=ko", "family"], capture_output=True, text=True)
    for name in FONTS:
        if name in listed.stdout:
            return name
    raise SourceError("한글 글꼴이 없다. `sudo apt install fonts-noto-cjk`")


def _head(font: str, rankdir: str = "LR", extra: str = "") -> str:
    return (
        f'graph [rankdir={rankdir}, fontname="{font}", fontsize=11, nodesep=0.35, ranksep=0.45, '
        f'bgcolor="white", pad=0.2 {extra}];\n'
        f'node [shape=box, style="rounded,filled", fontname="{font}", fontsize=11, '
        f'color="{NAVY}", fillcolor="{BLUE}", fontcolor="{INK}", penwidth=1.1, '
        f'margin="0.18,0.08"];\n'
        f'edge [fontname="{font}", fontsize=9, color="#5B6B7F", fontcolor="#5B6B7F", '
        f"arrowsize=0.7];\n"
    )


def _q(text: str) -> str:
    return '"' + text.replace('"', r"\"") + '"'


def render(
    out: Path, name: str, body: str, font: str, rankdir: str = "LR", extra: str = ""
) -> Path:
    target = out / f"{name}.png"
    graph = "digraph G {\n" + _head(font, rankdir, extra) + body + "\n}\n"
    subprocess.run(
        ["dot", "-Tpng", "-Gdpi=220", "-o", str(target)], input=graph, text=True, check=True
    )
    return target


# ------------------------------------------------------------------ Part I


def concept(out: Path, font: str) -> Path:
    body = f"""
subgraph cluster_edge {{ label="사용자 기기 — 음원이 떠나지 않는다"; style="rounded,dashed";
  color="{NAVY}"; fontcolor="{NAVY}";
  lib [label="음원 라이브러리\\n(원본 위치 참조)", fillcolor="{GRAY}"];
  ana [label="분석\\n스템 · 4축 특징"];
  taste [label="취향 표현\\n임베딩 · 사전"];
  lib -> ana -> taste; }}
subgraph cluster_srv {{ label="생성"; style="rounded"; color="#7A8BA0"; fontcolor="#5B6B7F";
  plan [label="기획 — hathor\\n구조 · 화성 · 배열 · 가락", fillcolor="{GREEN}"];
  render [label="렌더 — 오디오 엔진\\n가사 · 가창 · 믹스", fillcolor="{AMBER}"];
  gate [label="관문\\n음색 누설 · 조건 도달", fillcolor="{ROSE}"];
  plan -> render -> gate; }}
song [label="내 취향의 곡\\n오디오 · MIDI", shape=box, fillcolor="{NAVY}", fontcolor="white"];
taste -> plan [label="벡터만", color="{NAVY}", fontcolor="{NAVY}", penwidth=1.6];
seed [label="시드곡 1~5", fillcolor="{GRAY}"]; seed -> plan;
gate -> song;
"""
    return render(out, "concept", body, font, "TB")


# ------------------------------------------------------------------ Part II


def requirement_tree(out: Path, font: str) -> Path:
    block = code_block("## □ REQ-HATHOR 요구사항 체계도")
    rows = re.findall(r"[├└]─ (REQ-[A-Z]+)\s+(.+?)\s{2,}(.+)", block)
    if len(rows) < 10:
        raise SourceError("요구사항 체계도에서 그룹을 못 읽었다")
    lines = [f'root [label="HATHOR", fillcolor="{NAVY}", fontcolor="white"];']
    for code, name, detail in rows:
        node = code.replace("-", "_")
        label = f"{code}\\n{name}\\n{detail.strip().replace(' · ', ', ')}"
        lines.append(f"{node} [label={_q(label)}, fontsize=9]; root -> {node};")
    return render(out, "requirement_tree", "\n".join(lines), font, "LR", ", ranksep=0.6")


def use_cases(out: Path, font: str) -> Path:
    body = f"""
node [shape=ellipse, fillcolor="{BLUE}"];
user [shape=box, label="사용자", fillcolor="{GRAY}"];
dev [shape=box, label="개발자 · 운영", fillcolor="{GRAY}"];
subgraph cluster_sys {{ label="HATHOR"; style="rounded"; color="{NAVY}"; fontcolor="{NAVY}";
  u1 [label="라이브러리 스캔 · 분석"]; u2 [label="취향 프로파일 조회"];
  u3 [label="시드곡 고르기 (1~5곡)"]; u4 [label="곡 생성"];
  u5 [label="오디오 · MIDI 받기"]; u6 [label="쌍대비교 응답"];
  u7 [label="관문 판정 조회", fillcolor="{ROSE}"]; u8 [label="파이프라인 재실행 · 산출 이력"];
  u9 [label="평가 리포트", fillcolor="{GREEN}"];
  u4 -> u3 [label="«include»", style=dashed]; u4 -> u7 [label="«include»", style=dashed]; }}
user -> u1; user -> u2; user -> u4; user -> u5; user -> u6;
dev -> u8; dev -> u9; dev -> u7;
"""
    return render(out, "use_cases", body, font, "LR")


# ------------------------------------------------------------------ Part III


def pipeline(out: Path, font: str) -> Path:
    body = f"""
subgraph cluster_edge {{ label="사용자 기기 (로컬 에이전트)"; style="rounded,dashed";
  color="{NAVY}";
  fontcolor="{NAVY}";
  lib [label="음원 라이브러리", fillcolor="{GRAY}"];
  ing [label="[1] 인제스트\\n스캔 · 태그 · 아티스트 파싱 · MusicBrainz"];
  sep [label="[2] 스템 분리\\nhtdemucs — 보컬 · 드럼 · 베이스 · 기타"];
  ax1 [label="음악축\\n조성 · 크로마 · 온셋 · MERT"]; ax2 [label="편곡축\\n스템별 MERT"];
  ax3 [label="가사축\\nBGE-M3"]; ax4 [label="가창축\\n(미착수)", fillcolor="{GRAY}"];
  tv [label="[4] 취향 표현\\n축별 임베딩 · 화성 사전"];
  lib -> ing -> sep; sep -> ax1; sep -> ax2; ing -> ax3; sep -> ax4;
  ax1 -> tv; ax2 -> tv; ax3 -> tv; ax4 -> tv; }}
subgraph cluster_srv {{ label="생성"; style="rounded"; color="#7A8BA0"; fontcolor="#5B6B7F";
  plan [label="[5] 기획 — hathor\\n구조 → 화성 → 배열 → 가락 → 베이스 → 반주", fillcolor="{GREEN}"];
  eng [label="[5'] 렌더 — ACE-Step 1.5\\n가사 · 가창 · 편곡 · 믹스", fillcolor="{AMBER}"];
  gate [label="[6] 관문\\nG2 음색 누설 · G3 조건 도달", fillcolor="{ROSE}"];
  res [label="[7] 산출\\n오디오 · 스템 · MIDI", fillcolor="{NAVY}", fontcolor="white"];
  plan -> eng [label="SMF"]; eng -> gate -> res; }}
tv -> plan [label="벡터 · 임베딩만\\n오디오 바이트는 넘지 않는다", color="{NAVY}",
  fontcolor="{NAVY}",
  penwidth=1.8];
"""
    return render(out, "pipeline", body, font, "TB")


def layers(out: Path, font: str) -> Path:
    red = 'style=dashed, color="#C0392B", fontcolor="#C0392B", constraint=false'
    body = f"""
iface [label="interfaces\\nCLI · REST · 워커 — 로직 없음", fillcolor="{GRAY}"];
infra [label="infrastructure\\n포트 구현 — 파일 · 모델 · 외부 API", fillcolor="{GRAY}"];
app [label="application\\n유스케이스 · 오케스트레이션"];
eng [label="engines\\n무거운 AI 연산", fillcolor="{AMBER}"];
dom [label="domain\\n엔티티 · 값객체 · 포트 — 외부를 모른다", fillcolor="{GREEN}"];
{{rank=same; iface; infra;}} {{rank=same; app; eng;}}
iface -> app; infra -> app; infra -> dom; app -> dom; eng -> dom;
app -> infra [label="② 금지", {red}];
dom -> app [label="① 금지", {red}];
eng -> app [label="③ 엔진 간 · 역방향 금지", {red}];
subgraph cluster_five {{ label="⑤ 송신부는 오디오를 모른다 (D-0134)"; style="rounded,dashed";
  color="#C0392B"; fontcolor="#C0392B";
  send [label="송신부\\n망을 타는 모듈", fillcolor="{ROSE}"];
  audio [label="디코더 · 분리기 · 추출기 · 파형 타입", fillcolor="{ROSE}"];
  send -> audio [label="import 금지", style=dashed, color="#C0392B", fontcolor="#C0392B"]; }}
dom -> send [style=invis];
"""
    return render(out, "layers", body, font, "TB")


def erd(out: Path, font: str) -> Path:
    text = section(source(), "### □ 테이블 명세 (주요) — P4 설계 · 미구현")
    names = re.findall(r"^\*\*`(\w+)`\*\*", text, re.M)
    found = tables(text)
    if len(names) < 5 or len(found) < len(names):
        raise SourceError("테이블 명세에서 표 이름과 표를 못 맞췄다")
    nodes = []
    for name, table in zip(names, found, strict=False):
        fields = []
        for row in table.rows:
            column = plain(row[0]).replace("~", "")
            kind = plain(row[1]) if len(row) > 1 else ""
            mark = " PK" if "PK" in kind else (" FK" if "FK" in kind else "")
            fields.append(f"{column}{mark}")
        label = "{" + name + "|" + "\\l".join(fields) + "\\l}"
        nodes.append(
            f'{name} [shape=record, style="filled", fillcolor="{BLUE}", label={_q(label)}];'
        )
    links = """
tracks -> track_sources [label="1:N", arrowhead=crow];
tracks -> track_features [label="1:N (축마다)", arrowhead=crow];
tracks -> pairwise_comparisons [label="left · right", arrowhead=crow];
artists -> tracks [label="N:M (track_artists)", arrowhead=crow, dir=both, arrowtail=crow];
taste_vectors -> pairwise_comparisons [label="source=pairwise", style=dashed];
"""
    known = set(names)
    edges = [line for line in links.strip().splitlines() if line.split(" ->")[0] in known]
    return render(out, "erd", "\n".join(nodes + edges), font, "TB")


def ingest_flow(out: Path, font: str) -> Path:
    block = code_block("### □ 처리 순서")
    steps = [
        re.sub(r"\s{2,}D-\d{4}.*$", "", line.strip().lstrip("→ ").strip())
        for line in block.splitlines()
    ]
    steps = [step for step in steps if step]
    refs = [" ".join(re.findall(r"D-\d{4}", line)) for line in block.splitlines() if line.strip()]
    lines = []
    for index, (step, ref) in enumerate(zip(steps, refs, strict=False)):
        label = step + (f"\\n{ref}" if ref else "")
        fill = GREEN if "저장" in step else (ROSE if "실패" in step else BLUE)
        lines.append(f's{index} [label={_q(label)}, fillcolor="{fill}"];')
        if index:
            lines.append(f"s{index - 1} -> s{index};")
    return render(out, "ingest_flow", "\n".join(lines), font, "TB")


def delta_states(out: Path, font: str) -> Path:
    body = f"""
node [shape=box, style="rounded,filled"];
prev [label="이전 스냅샷", fillcolor="{GRAY}"]; scan [label="재스캔", fillcolor="{GRAY}"];
d [label="DISCOVERED\\n전체 분석", fillcolor="{GREEN}"];
m [label="MODIFIED\\nmtime · size 변경 → 재분석", fillcolor="{AMBER}"];
u [label="UNCHANGED\\n건너뜀 · 결과 재사용"];
r [label="REMOVED\\n소실 처리 — 실패가 아니다", fillcolor="{ROSE}"];
guard [label="소실 50% 초과?\\n외장 볼륨 미연결 의심 → 경고 · 자동 삭제 안 함", shape=note,
  fillcolor="white"];
prev -> scan; scan -> d [label="이전에 없음"]; scan -> m [label="바뀜"];
scan -> u [label="같음"]; scan -> r [label="안 보임"]; r -> guard [style=dashed];
"""
    return render(out, "delta_states", body, font, "LR")


def axes(out: Path, font: str) -> Path:
    body = f"""
song [label="원곡 (mp3)", fillcolor="{GRAY}"]; tag [label="USLT 가사 태그", fillcolor="{GRAY}"];
dem [label="htdemucs\\n44.1kHz", fillcolor="{AMBER}"];
v [label="보컬"]; d [label="드럼"]; b [label="베이스"]; o [label="기타"];
mert [label="MERT-v1-95M · 24kHz\\n13층 × 5소스\\n(비상업 — O-68 · D-0235)", fillcolor="{ROSE}"];
chroma [label="크로마 · 조성 · 온셋 · 템포"]; bge [label="BGE-M3\\n(MIT)", fillcolor="{GREEN}"];
m [label="음악축", fillcolor="{NAVY}", fontcolor="white"];
a [label="편곡축", fillcolor="{NAVY}", fontcolor="white"];
l [label="가사축", fillcolor="{NAVY}", fontcolor="white"];
s [label="가창축", fillcolor="{GRAY}"];
song -> dem; dem -> v; dem -> d; dem -> b; dem -> o;
song -> mert; v -> mert; d -> mert; b -> mert; o -> mert;
song -> chroma; o -> chroma [label="드럼 제외 (D-0074)", style=dashed];
chroma -> m; mert -> m; mert -> a; tag -> bge -> l; v -> s [style=dashed, label="미착수"];
"""
    return render(out, "axes", body, font, "LR")


def taste_layers(out: Path, font: str) -> Path:
    body = f"""
l1 [label="1. 라이브러리 — 전역 사전확률\\n보유 곡 전체 · 재스캔 시 갱신", fillcolor="{GRAY}"];
l2 [label="2. 쌍대비교 — 상대 순위\\nA vs B · 온보딩 · 재학습"];
l3 [label="3. 시드곡 — 지역 조건\\n생성마다", fillcolor="{GREEN}"];
g [label="생성 조건", fillcolor="{NAVY}", fontcolor="white"];
l1 -> g [label="시드가 비운 곳을 메운다"]; l2 -> g [label="무게 (미착수 · D-0210)", style=dashed];
l3 -> g [label="우선"];
"""
    return render(out, "taste_layers", body, font, "LR")


def plan_render(out: Path, font: str) -> Path:
    block = code_block("### □ 기획과 렌더를 나눈다")
    steps = re.findall(r"^(\d)\. (\S+(?: · \S+)*)\s{2,}(.+?)\s{2,}(D-\d{4}.*)$", block, re.M)
    if len(steps) < 6:
        raise SourceError("기획 · 렌더 블록에서 단계를 못 읽었다")
    plan, rend = [], []
    for number, name, what, ref in steps:
        label = f"{number}. {name}\\n{what.strip()}\\n{ref.strip()}"
        target = plan if int(number) <= 6 else rend
        target.append(f"p{number} [label={_q(label)}];")
    chain = " -> ".join(f"p{number}" for number, *_ in steps if int(number) <= 6)
    body = f"""
seed [label="참조곡 1~5 + 라이브러리 사전", fillcolor="{GRAY}"];
subgraph cluster_plan {{ label="기획 — hathor · 결정적 · 구현됨"; style="rounded"; color="#3C8D5A";
  fontcolor="#3C8D5A"; node [fillcolor="{GREEN}"]; {" ".join(plan)} {chain}; }}
smf [label="SMF\\n직접 인코딩 (D-0052)", shape=note, fillcolor="white"];
subgraph cluster_render {{ label="렌더 — 오디오 엔진 · 장비 대기"; style="rounded,dashed";
  color="#B9770E"; fontcolor="#B9770E"; node [fillcolor="{AMBER}"]; {" ".join(rend)} }}
gate [label="관문\\nG2 음색 누설 · G3 조건 도달", fillcolor="{ROSE}"];
seed -> p1; p6 -> smf -> p7 -> gate;
"""
    return render(out, "plan_render", body, font, "TB", ", ranksep=0.35")


def engine_gates(out: Path, font: str) -> Path:
    body = f"""
start [label="후보 엔진", fillcolor="{GRAY}"];
g0 [label="G0 설치 · 메모리\\n3분 곡 하나", fillcolor="{ROSE}"];
g1 [label="G1 한국어\\n귀 · 이진"]; g2 [label="G2 음색 누설\\n귀무 먼저"];
g3 [label="G3 조건 도달\\nMERT · CLAP"]; ok [label="채택", fillcolor="{GREEN}"];
x0 [label="1660 Ti — 기기 탈락\\nfp16 NaN · fp32 메모리 부족\\n(D-0218)", shape=note,
  fillcolor="{ROSE}"];
x2 [label="참조 오디오 모드 금지\\n(모델 탈락 아님)", shape=note, fillcolor="white"];
x3 [label="조건 자리가 없는 것과 같다", shape=note, fillcolor="white"];
start -> g0 -> g1 -> g2 -> g3 -> ok;
g0 -> x0 [style=dashed, color="#C0392B"]; g2 -> x2 [style=dashed]; g3 -> x3 [style=dashed];
wait [label="VRAM 16GB 이상 · bf16 장비에서 재개", shape=note, fillcolor="{AMBER}"];
x0 -> wait [style=dotted];
"""
    return render(out, "engine_gates", body, font, "TB")


def leak_gate(out: Path, font: str) -> Path:
    body = f"""
null [label="귀무 — 참조 없이 생성\\nself − other ≈ 0 이어야 한다", fillcolor="{GRAY}"];
ref [label="가수가 다른 참조곡 20곡"]; gen [label="곡마다 참조 오디오로 생성", fillcolor="{AMBER}"];
sep [label="출력 보컬 분리"]; emb [label="화자 임베딩\\n자기 참조 − 다른 19명 (곡 단위 짝)"];
dec [label="유의하게 크다?", shape=diamond, fillcolor="white"];
ban [label="참조 오디오 모드를 제품에서 금지", fillcolor="{ROSE}"];
ok [label="모드 허용", fillcolor="{GREEN}"];
null -> emb [style=dashed, label="먼저"]; ref -> gen -> sep -> emb -> dec;
dec -> ban [label="예"]; dec -> ok [label="아니오"];
"""
    return render(out, "leak_gate", body, font, "TB")


def patch_pipe(out: Path, font: str) -> Path:
    body = f"""
dl [label="윈도 다운로드 폴더\\nHATHOR_PATCH_DIR (.env)", fillcolor="{GRAY}"];
apply [label="make apply\\n최신 패치 · 멱등 · 깨끗한 트리"];
same [label="선언한 파일 = 바뀐 파일?", shape=diamond, fillcolor="white"];
commit [label="커밋\\n메시지 = # hathor-commit:"]; check [label="make check\\n검사 전부"];
push [label="git push → CI 3잡", fillcolor="{GREEN}"];
stop [label="멈춘다 — 다른 작업이 섞였다", fillcolor="{ROSE}"];
dl -> apply -> same; same -> commit [label="같다"]; same -> stop [label="다르다"];
commit -> check -> push;
"""
    return render(out, "patch_pipe", body, font, "TB")


def _parity() -> tuple[set[str], set[str], set[str]]:
    path = ROOT / "core" / "tests" / "unit" / "test_ci_parity.py"
    spec = importlib.util.spec_from_file_location("ci_parity", path)
    if spec is None or spec.loader is None:
        raise SourceError("관문 대조 모듈을 못 읽었다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    makefile, workflow, hook = module._repo()
    table = module.recipes(makefile)
    local = set().union(*(module.tokens(table.get(t, "")) for t in module.check_deps(makefile)))
    return local, module.tokens(workflow), module.tokens(hook)


def gate_parity(out: Path, font: str) -> Path:
    local, ci, hook = _parity()
    both = sorted(local & ci)
    nl = "\\n"
    common = _q("공통" + nl + nl.join(both))
    only = _q("CI 전용 (선언)" + nl + nl.join(sorted(ci - local)))
    slow = _q("훅 제외 — 느리다" + nl + nl.join(sorted(local - hook)))
    lines = [
        f'mk [label="make check\\n{len(local)}종", fillcolor="{BLUE}"];',
        f'ci [label="CI\\n{len(ci)}종", fillcolor="{BLUE}"];',
        f'hk [label="커밋 훅\\n{len(hook)}종 — 빠른 것만", fillcolor="{BLUE}"];',
        f'common [label={common}, shape=note, fillcolor="{GREEN}", fontsize=9];',
        f'only [label={only}, shape=note, fillcolor="{AMBER}", fontsize=9];',
        f'slow [label={slow}, shape=note, fillcolor="{GRAY}", fontsize=9];',
        "mk -> common; ci -> common; ci -> only; hk -> common; mk -> slow [style=dashed];",
    ]
    return render(out, "gate_parity", "\n".join(lines), font, "LR")


def documents(out: Path, font: str) -> Path:
    body = f"""
plan [label="PLAN\\n미래 — 다음 작업 · 열린 질문 · 빚"];
master [label="MASTER\\n현재 — 기획 · 요구사항 · 설계 · 규약", fillcolor="{GREEN}"];
dec [label="DECISIONS\\n과거 — 추가 전용 · 강제자 · 재현", fillcolor="{GRAY}"];
readme [label="README\\n진입", fillcolor="{GRAY}"];
prop [label="proposal.docx\\n밖에 내는 판 · 시제 밖", fillcolor="{AMBER}"];
tests [label="강제자 — 시험 · 검사", shape=note, fillcolor="white"];
plan -> master [label="도래"]; master -> dec [label="회고"]; readme -> master [style=dashed];
master -> prop [label="Part I ~ III 빌드\\n지문 대조"]; dec -> tests [label="결정마다"];
"""
    return render(out, "documents", body, font, "TB")


FIGURES: dict[str, Callable[[Path, str], Path]] = {
    "concept": concept,
    "requirement_tree": requirement_tree,
    "use_cases": use_cases,
    "pipeline": pipeline,
    "layers": layers,
    "erd": erd,
    "ingest_flow": ingest_flow,
    "delta_states": delta_states,
    "axes": axes,
    "taste_layers": taste_layers,
    "plan_render": plan_render,
    "engine_gates": engine_gates,
    "leak_gate": leak_gate,
    "patch_pipe": patch_pipe,
    "gate_parity": gate_parity,
    "documents": documents,
}


def render_all(out: Path) -> dict[str, Path]:
    if shutil.which("dot") is None:
        raise SourceError("graphviz가 없다. `sudo apt install graphviz`")
    out.mkdir(parents=True, exist_ok=True)
    font = korean_font()
    return {name: draw(out, font) for name, draw in FIGURES.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 구조도 (D-0221)")
    parser.add_argument("--out", type=Path, default=ROOT / "var" / "proposal" / "figures")
    args = parser.parse_args()
    made = render_all(args.out)
    print(f"구조도 {len(made)}장 · {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
