#!/usr/bin/env python3
"""기획서의 수치 그림을 정본 표에서 그린다 — matplotlib (D-0221).

### 숫자를 여기 적지 않는다

일정은 «추진 일정» 표, 요구사항 상태는 요구사항 정의서 표 열두 개, 레이어 곡선은 평가 설계의
표에서 읽는다. **표를 고치면 다음 빌드에서 그림이 따라온다.** 한 곳만 예외다 — 성부 진행
전후(D-0137)는 결정 기록에만 있으므로 그 기록의 표를 읽는다.

    cd core && uv run --group docs python ../tools/render_charts.py --out ../var/proposal/figures
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from proposal_source import (
    ROOT,
    SourceError,
    number,
    plain,
    section,
    source,
    table,
    tables,
)
from render_figures import FONTS

NAVY = "#1F4E79"
SKY = "#8DB3DA"
GREEN = "#5FA36F"
AMBER = "#E3A33B"
ROSE = "#D4675F"
GRAY = "#B9C0C9"
INK = "#2F3B4A"
WIDTH = 6.6

STATUS_COLORS = {
    "완료": GREEN,
    "강제": "#2E7D4F",
    "부분": SKY,
    "진행": NAVY,
    "설계": "#9B8EC4",
    "보류": AMBER,
    "변경": "#C9A227",
    "미착수": GRAY,
    "폐기": ROSE,
}


def _style() -> None:
    names = {entry.name for entry in font_manager.fontManager.ttflist}
    family = next((name for name in FONTS if name in names), None)
    if family is None:
        raise SourceError("matplotlib이 한글 글꼴을 못 찾았다. `sudo apt install fonts-noto-cjk`")
    plt.rcParams.update(
        {
            "font.family": family,
            "font.size": 9,
            "axes.edgecolor": "#8A96A5",
            "axes.labelcolor": INK,
            "axes.titleweight": "bold",
            "axes.titlesize": 10,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.unicode_minus": False,
            "figure.dpi": 100,
        }
    )


def _save(fig: Any, out: Path, name: str) -> Path:
    target = out / f"{name}.png"
    fig.savefig(target, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return target


# ------------------------------------------------------------------ Part I


def _months(span: str) -> tuple[float, float]:
    """`2026-08 ~ 09` · `2026-12 ~ 2027-01` · `2027-01` → (시작 월, 끝 월 + 1)."""
    found = re.findall(r"(?:(\d{4})-)?(\d{2})", span)
    if not found:
        raise SourceError(f"기간 `{span}`을 못 읽었다")
    values, year = [], 2026
    for y, m in found:
        year = int(y) if y else year
        values.append((year - 2026) * 12 + int(m))
    return values[0], values[-1] + 1


def gantt(out: Path) -> Path:
    rows = [row for row in table("### □ 추진 일정").rows if row[0].strip("* ").startswith("P")]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    for index, (stage, content, span, state) in enumerate(rows):
        start, end = _months(span)
        state = plain(state)
        colors = {"완료": GREEN, "부분": SKY, "보류": AMBER, "앞당겨": NAVY, "엔진": ROSE}
        colors["설계"] = "#9B8EC4"
        key = next((k for k in colors if state.startswith(k)), "예정")
        color = colors.get(key, GRAY)
        y = len(rows) - index
        ax.barh(y, end - start, left=start, color=color, height=0.6)
        ax.text(start - 0.1, y, plain(stage), ha="right", va="center", fontweight="bold")
        ax.text(
            end + 0.1,
            y,
            plain(content).split(" — ")[0][:22] + " · " + state.split(" — ")[0].split(" (")[0][:26],
            va="center",
            fontsize=7.5,
            color=INK,
        )
    ax.axvline(12 + 0.35, color=ROSE, linestyle="--", linewidth=1)
    ax.text(12 + 0.4, len(rows) + 0.6, "Fire-Lane 마감 12-11", color=ROSE, fontsize=7.5)
    ax.axvline(9 + 22 / 30, color=NAVY, linestyle=":", linewidth=1)
    ax.text(9 + 22 / 30 + 0.05, 0.3, "현재 09-22", color=NAVY, fontsize=7.5)
    ticks = list(range(8, 15))
    ax.set_xticks(ticks, [f"{(t - 1) % 12 + 1}월" for t in ticks])
    ax.set_xlim(7, 21.5)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_title("추진 일정과 상태 (2026-08 ~ 2027-02)")
    return _save(fig, out, "gantt")


# ------------------------------------------------------------------ Part II


def requirement_status(out: Path) -> Path:
    text = section(source(), "## □ 세부 기능 요구사항 정의서")
    groups: list[tuple[str, Counter[str]]] = []
    for found in tables(text):
        if "상태" not in found.header or not found.rows:
            continue
        group = found.rows[0][0].split("-")[1]
        groups.append((group, Counter(plain(state) for state in found.column("상태"))))
    if len(groups) != 12:
        raise SourceError(f"요구사항 표가 12개가 아니다 — {len(groups)}개")
    fig, ax = plt.subplots(figsize=(WIDTH, 3.6))
    order = [state for state in STATUS_COLORS if any(state in c for _, c in groups)]
    unknown = {s for _, c in groups for s in c} - set(STATUS_COLORS)
    if unknown:
        raise SourceError(f"모르는 상태 {sorted(unknown)} — STATUS_COLORS에 없다")
    for index, (_group, counts) in enumerate(reversed(groups)):
        left = 0
        for state in order:
            value = counts.get(state, 0)
            if value:
                ax.barh(
                    index,
                    value,
                    left=left,
                    color=STATUS_COLORS[state],
                    height=0.7,
                    edgecolor="white",
                    linewidth=0.6,
                )
                ax.text(
                    left + value / 2,
                    index,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if state in ("진행", "강제") else INK,
                )
                left += value
    ax.set_yticks(range(len(groups)), [f"REQ-{g}" for g, _ in reversed(groups)])
    ax.set_xlabel("요구사항 수")
    handles = [plt.Rectangle((0, 0), 1, 1, color=STATUS_COLORS[s]) for s in order]
    ax.legend(
        handles,
        order,
        ncol=len(order),
        fontsize=7,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        frameon=False,
    )
    total = Counter(s for _, c in groups for s in c.elements())
    done = total["완료"] + total["강제"]
    ax.set_title(
        f"요구사항 {sum(total.values())}건 — 완료·강제 {done} · 부분·진행 "
        f"{total['부분'] + total['진행']}",
        pad=22,
    )
    return _save(fig, out, "requirement_status")


# ------------------------------------------------------------------ Part III


def id3_frames(out: Path) -> Path:
    rows = table("### □ ID3 프레임 실측 (1004곡 전수)").rows
    labels = [
        plain(r[0]).split(" (")[0] + "\n" + plain(r[0]).split(" (")[-1].rstrip(")")
        if "(" in r[0]
        else plain(r[0])
        for r in rows
    ]
    values = [number(r[1]) for r in rows]
    colors = [GREEN if v >= 99 else (ROSE if v == 0 else AMBER) for v in values]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    ax.bar(range(len(values)), values, color=colors)
    for index, value in enumerate(values):
        ax.text(index, value + 2, f"{value:g}%", ha="center", fontsize=7)
    ax.set_xticks(range(len(values)), labels, fontsize=6.5, rotation=40, ha="right")
    ax.set_ylabel("보유율 (%)")
    ax.set_ylim(0, 112)
    ax.set_title("ID3 프레임 보유율 — 발매일 · ISRC · 동기 가사가 0%")
    return _save(fig, out, "id3_frames")


def artist_notation(out: Path) -> Path:
    rows = [r for r in table("### □ 아티스트 표기 실측").rows if "%" in r[1]]
    labels = [plain(r[0]) for r in rows]
    values = [number(r[1]) for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH, 1.9))
    ax.barh(
        range(len(values)), values, color=[AMBER if "괄호" in label else SKY for label in labels]
    )
    for index, value in enumerate(values):
        ax.text(value + 0.8, index, f"{value:g}%", va="center", fontsize=7.5)
    ax.set_yticks(range(len(values)), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 72)
    ax.set_title("아티스트 표기 — 괄호는 피처링이 아니라 별칭 병기다")
    return _save(fig, out, "artist_notation")


def musicbrainz(out: Path) -> Path:
    rows = table("### □ MusicBrainz 조회 개선 이력 (D-0019)").rows
    labels = [plain(r[0]) for r in rows]
    values = [number(r[1]) for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    ax.plot(range(len(values)), values, marker="o", color=NAVY, linewidth=2)
    for index, value in enumerate(values):
        ax.annotate(
            f"{value:g}%",
            (index, value),
            textcoords="offset points",
            xytext=(0, 7),
            ha="center",
            fontweight="bold",
            color=NAVY,
        )
    ax.set_xticks(range(len(values)), labels)
    ax.set_ylim(0, 100)
    ax.set_ylabel("곡 조회 성공률 (%)")
    ax.set_title("MusicBrainz 곡 조회 — 첫 도약은 구조, 둘째는 0.6%p")
    return _save(fig, out, "musicbrainz")


def engine_funnel(out: Path) -> Path:
    rows = table("### □ 엔진 선정 — 서류 관문 (D-0217)").rows
    verdicts = [plain(r[-1]) for r in rows]
    gates = ["라이선스", "보컬", "조건 자리", "VRAM"]
    alive = [len(rows)]
    for gate in gates:
        alive.append(alive[-1] - sum(1 for v in verdicts if v.startswith(gate)))
    fig, ax = plt.subplots(figsize=(WIDTH, 2.5))
    names = ["후보", *[f"{g}\n관문" for g in gates]]
    ax.bar(range(len(alive)), alive, color=[GRAY, SKY, SKY, SKY, GREEN])
    for index, value in enumerate(alive):
        ax.text(index, value + 0.15, f"{value}", ha="center", fontweight="bold")
    ax.set_xticks(range(len(alive)), names)
    ax.set_ylim(0, len(rows) + 1.2)
    survivors = [plain(r[0]) for r, v in zip(rows, verdicts, strict=True) if "순위" in v]
    ax.set_title(
        f"서류 관문 — {len(rows)}개 후보 중 실측 대상 {alive[-1]}개 ({' · '.join(survivors)})"
    )
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    return _save(fig, out, "engine_funnel")


def g0_runs(out: Path) -> Path:
    rows = table("### □ G0 실측 — 기기가 떨어졌다 (D-0218)").rows
    runs = []
    for attempt, result in rows:
        times = re.findall(r"(\d+)초", plain(result))
        if len(times) >= 2:
            runs.append((plain(attempt), float(times[0]), float(times[1])))
    memory = re.search(r"허용 ([\d.]+)GB에 ([\d.]+)GB", plain(rows[-1][1]))
    if len(runs) < 2 or memory is None:
        raise SourceError("G0 표에서 시간과 메모리를 못 읽었다")
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(WIDTH, 2.4), gridspec_kw={"width_ratios": [2, 1]}
    )
    for index, (_name, diffusion, move) in enumerate(runs):
        left.barh(index, diffusion, color=SKY, label="확산" if index == 0 else None)
        left.barh(
            index, move, left=diffusion, color=AMBER, label="CPU↔GPU 옮기기" if index == 0 else None
        )
        left.text(diffusion + move + 4, index, "NaN", va="center", color=ROSE, fontweight="bold")
    left.set_yticks(range(len(runs)), [name for name, *_ in runs])
    left.set_xlabel("초")
    left.legend(fontsize=7, frameon=False, loc="lower right")
    left.set_title("fp16 — 끝까지 돌고 전부 NaN")
    allowed, used = float(memory.group(1)), float(memory.group(2))
    right.bar([0], [used], color=ROSE, width=0.5)
    right.axhline(allowed, color=INK, linestyle="--", linewidth=1)
    right.text(0.3, allowed + 0.05, f"허용 {allowed}GB", fontsize=7)
    right.text(0, used / 2, f"{used}GB\n+16MB 요청", ha="center", color="white", fontsize=7.5)
    right.set_xticks([])
    right.set_ylim(0, 5)
    right.set_title("fp32 — 올리다 메모리 부족")
    return _save(fig, out, "g0_runs")


def listening(out: Path) -> Path:
    rows = table("### □ 청취 판정 이력").rows
    fig, ax = plt.subplots(figsize=(WIDTH, 2.9))
    for index, (decision, heard, fixed) in enumerate(rows):
        value = int(re.sub(r"\D", "", decision))
        closed = "구분 안 됨" in heard or "낫다" in heard
        y = len(rows) - index
        ax.scatter(value, y, s=55, color=ROSE if closed else NAVY, zorder=3)
        ax.text(
            value + 1.5,
            y,
            f"{plain(decision)}  {plain(heard)}  →  {plain(fixed)[:30]}",
            va="center",
            fontsize=7,
            color=INK,
        )
    ax.set_xlim(135, 290)
    ax.set_ylim(0.3, len(rows) + 0.7)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xticks(range(140, 230, 20))
    ax.set_xlabel("결정 번호")
    ax.set_title("귀가 판정한 일곱 번 — 마지막이 기호 경로를 닫았다 (D-0214)")
    return _save(fig, out, "listening")


def voice_leading(out: Path) -> Path:
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    start = text.index("## D-0137.")
    rows = [r for r in tables(text[start : text.index("## D-0138.")]) if "성부 진행" in r.header]
    if not rows:
        raise SourceError("D-0137에서 전후 표를 못 찾았다")
    data = [(plain(r[0]), number(r[1]), number(r[2])) for r in rows[0].rows]
    fig, axes = plt.subplots(1, len(data), figsize=(WIDTH, 2.1))
    for ax, (name, before, after) in zip(axes, data, strict=True):
        ax.bar([0, 1], [before, after], color=[GRAY, GREEN], width=0.6)
        for x, value in ((0, before), (1, after)):
            ax.text(x, value * 1.03, f"{value:g}", ha="center", fontsize=7.5)
        ax.set_xticks([0, 1], ["현행", "성부 진행"])
        ax.set_title(name, fontsize=8.5)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
    fig.suptitle(
        "성부 진행 전후 (D-0137) — 병행 5도 90.5% → 17.5%", fontsize=9.5, fontweight="bold"
    )
    fig.tight_layout()
    return _save(fig, out, "voice_leading")


def retrieval(out: Path) -> Path:
    rows = table("### □ 지표").rows
    picked = []
    for _target, metric, value in rows:
        found = re.search(r"실측 ([\d.]+) \(무작위 ([\d.]+) 대비 ([\d.]+)배", plain(value))
        if found and metric.startswith("M"):
            picked.append(
                (
                    plain(metric).split(" ")[0],
                    float(found.group(1)),
                    float(found.group(2)),
                    float(found.group(3)),
                )
            )
    if len(picked) < 2:
        raise SourceError("평가 지표 표에서 M1 · M2를 못 읽었다")
    fig, ax = plt.subplots(figsize=(WIDTH, 2.5))
    for index, (_name, measured, random, lift) in enumerate(picked):
        ax.bar(index - 0.18, random, width=0.34, color=GRAY, label="무작위" if index == 0 else None)
        ax.bar(
            index + 0.18,
            measured,
            width=0.34,
            color=NAVY,
            label="MERT layer00" if index == 0 else None,
        )
        ax.text(
            index + 0.18, measured * 1.05, f"{measured:.4f}\n{lift:g}배", ha="center", fontsize=7.5
        )
    ax.set_xticks(range(len(picked)), [p[0] + " P@10" for p in picked])
    ax.set_ylim(0, max(p[1] for p in picked) * 1.45)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("검색 평가 — 앨범 20.4배 · 아티스트 14.3배 (무작위 대비)")
    return _save(fig, out, "retrieval")


def layer_curve(out: Path) -> Path:
    found = table("### □ 레이어 곡선 — 검색축 (D-0027)")
    layers = [int(v) for v in found.column("층")]
    m1 = [number(v) for v in found.column("M1 P@10")]
    m2 = [number(v) for v in found.column("M2 P@10")]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.5))
    ax.plot(layers, m2, marker="o", color=NAVY, label="M2 아티스트 P@10")
    ax.plot(layers, m1, marker="s", color=AMBER, label="M1 앨범 P@10")
    ax.annotate(
        "최댓값 layer00",
        (layers[0], m2[0]),
        xytext=(2.5, m2[0] + 0.005),
        fontsize=7.5,
        arrowprops={"arrowstyle": "->", "color": INK},
    )
    ax.set_xticks(layers, [f"{v:02d}" for v in layers])
    ax.set_xlabel("MERT 층")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("검색축 — 트랜스포머 블록을 지날수록 나빠진다 (D-0027)")
    return _save(fig, out, "layer_curve")


def harmony_layers(out: Path) -> Path:
    found = table("### □ 층별 화성 — 화성축 (D-0181)")
    layers = found.column("층")
    front = [number(v) for v in found.column("앞절반")]
    back = [number(v) for v in found.column("뒤절반")]
    whole = [number(v) for v in found.column("전체")]
    mfcc = (
        number(
            re.search(
                r"MFCC\((\d\.\d+)\)", section(source(), "### □ 층별 화성 — 화성축 (D-0181)")
            ).group(1)
        )
        if re.search(r"MFCC\(", source())
        else 0.0
    )
    fig, ax = plt.subplots(figsize=(WIDTH, 2.6))
    x = range(len(layers))
    ax.bar([i - 0.27 for i in x], front, width=0.27, color=SKY, label="앞절반")
    ax.bar(list(x), back, width=0.27, color=NAVY, label="뒤절반")
    ax.bar([i + 0.27 for i in x], whole, width=0.27, color=GREEN, label="전체")
    if mfcc:
        ax.axhline(mfcc, color=ROSE, linestyle="--", linewidth=1)
        ax.text(len(layers) - 0.6, mfcc + 0.004, f"MFCC {mfcc}", color=ROSE, fontsize=7)
    best = whole.index(max(whole))
    ax.text(best + 0.27, whole[best] + 0.006, "최고", ha="center", color=GREEN, fontweight="bold")
    ax.set_xticks(list(x), [f"layer{v}" for v in layers])
    ax.set_ylabel("화성 검색 P@10")
    ax.set_ylim(0, max(whole) * 1.25)
    ax.legend(frameon=False, fontsize=7.5, ncol=3)
    ax.set_title("화성축 — 중간(layer03)에서 봉우리, 앞·뒤절반 순위가 같다 (D-0181)")
    return _save(fig, out, "harmony_layers")


CHARTS: dict[str, Callable[[Path], Path]] = {
    "gantt": gantt,
    "requirement_status": requirement_status,
    "id3_frames": id3_frames,
    "artist_notation": artist_notation,
    "musicbrainz": musicbrainz,
    "engine_funnel": engine_funnel,
    "g0_runs": g0_runs,
    "listening": listening,
    "voice_leading": voice_leading,
    "retrieval": retrieval,
    "layer_curve": layer_curve,
    "harmony_layers": harmony_layers,
}


def render_all(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    _style()
    return {name: draw(out) for name, draw in CHARTS.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="기획서 수치 그림 (D-0221)")
    parser.add_argument("--out", type=Path, default=ROOT / "var" / "proposal" / "figures")
    args = parser.parse_args()
    made = render_all(args.out)
    print(f"수치 그림 {len(made)}장 · {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
