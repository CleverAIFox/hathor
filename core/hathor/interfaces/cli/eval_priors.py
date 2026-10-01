"""`eval harmony-prior` · `eval time-drift` · `eval fusion` · `eval chord-quality` (D-0260).

**`main.py`에 있었다.** 셋 다 이미 뽑아 둔 산출물을 읽어 판정만 하는 보고다 —
오디오를 다시 안 열고, 그래서 GPU 없이 돈다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hathor.application.evaluate_fusion import EvaluateFusion
from hathor.domain.services.harmony_prior import HalfChroma
from hathor.domain.services.key_estimation import KEY_MARGIN_FLOOR
from hathor.domain.services.seed_search import FusionMode
from hathor.domain.services.stem_sets import STEM_SETS, stems_overlap
from hathor.infrastructure.json_evaluation_store import JsonEvaluationStore
from hathor.infrastructure.keys_jsonl_store import load_drift_observations
from hathor.interfaces.cli.eval_onsets import ONSETS
from hathor.interfaces.cli.eval_quality import CHORD_QUALITY
from hathor.interfaces.cli.eval_retrieval import load_search_tracks
from hathor.interfaces.cli.eval_window import WINDOW_LENGTH
from hathor.interfaces.cli.registry import Command
from hathor.interfaces.cli.roots import (
    DEFAULT_FEATURE_DIRNAME,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SEARCH_KEY,
    resolve_priors,
)
from hathor.interfaces.cli.tables import render_table
from hathor.shared.config.paths import resolve_path


def run_eval_fusion(args: argparse.Namespace) -> int:
    """시드 결합 규칙을 같은 쌍으로 비교한다 (M4, D-0033).

    한 사례를 눈으로 보고 규칙을 고르면 다른 조합에서 더 나빠져도 알 수 없다.
    """

    keys = tuple(token.strip() for token in args.keys.split(",") if token.strip())
    if not keys:
        print("--keys에 임베딩 키를 최소 하나 지정해야 한다", file=sys.stderr)
        return 2
    try:
        tracks = load_search_tracks(args, keys)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    use_case = EvaluateFusion(
        keys,
        centered=not args.raw,
        k=args.k,
        pairs=args.pairs,
        seed=args.seed,
        penalty=args.penalty,
    )
    try:
        report = use_case.run(tracks, list(FusionMode))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"곡 {report.tracks}개 / 시드 쌍 {report.scores[0].pairs}개 / 상위 {report.k}")
    print("  규칙        시드아티스트비율  아티스트불균형  코사인불균형  평균유사도")
    for score in report.scores:
        cosine = (
            "     —"
            if score.cosine_imbalance != score.cosine_imbalance
            else (f"{score.cosine_imbalance:>13.4f}")
        )
        similarity = (
            "     —"
            if score.mean_similarity != score.mean_similarity
            else (f"{score.mean_similarity:>12.4f}")
        )
        print(
            f"  {score.mode:<11} {score.coverage:>13.4f} {score.artist_imbalance:>15.4f}"
            f" {cosine} {similarity}"
        )
    print()
    print("불균형은 낮을수록, 시드아티스트비율은 높을수록 좋다.")
    print("균형만 좋고 비율이 낮으면 두 시드 모두에서 먼 밋밋한 곡을 고른 것이다.")
    print("random은 하한, oracle은 코퍼스 구성상 도달 가능한 상한이다.")
    path = JsonEvaluationStore(args.out).write(report.as_record(), f"fusion-k{args.k}")
    print(f"리포트: {path}")
    return 0


def load_halves(path: Path, stem_set: str | None) -> list[HalfChroma]:
    """keys.jsonl에서 반쪽 크로마를 읽는다 (D-0337).

    **`run_eval_harmony_prior` 안에 있었다.** 두 산출물을 맞대려면 두 번 읽어야 하고,
    그 자리에서 복사하면 **같은 블록이 둘**이 된다 — 이 저장소가 되풀이해 맞은 부류다
    (D-0317 · D-0323 · D-0326).
    """

    from hathor.domain.value_objects.key import PITCH_CLASSES

    with path.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]

    found: list[HalfChroma] = []
    for row in rows:
        key_text = row.get("key_head")
        if stem_set:
            # **조성은 전체 믹스에서 추정한 것을 그대로 쓴다** (D-0073). 스템에서
            # 다시 추정하면 조합마다 회전 기준이 달라져 비교가 성립하지 않는다.
            bundle = row.get("stems") or {}
            picked = bundle.get(stem_set)
            if picked is None:
                continue
            head, tail = picked.get("head"), picked.get("tail")
        else:
            head, tail = row.get("chroma_head"), row.get("chroma_tail")
        if head is None or tail is None or key_text is None:
            continue
        tonic = str(key_text).rsplit(" ", 1)[0]
        found.append(
            HalfChroma(
                source_key=str(row.get("source_key", "")),
                tonic_pitch_class=PITCH_CLASSES.index(tonic),
                margin=float(row.get("margin_head", 0.0)),
                head=tuple(float(value) for value in head),
                tail=tuple(float(value) for value in tail),
            )
        )
    return found


def _compare_aggregation(args: argparse.Namespace, observations: list[HalfChroma]) -> int:
    """두 집계의 달성 가능 폭을 짝지어 맞댄다 (D-0064 · D-0337).

    **눈으로 빼지 않는다.** 폭을 한 수로 찍어 두 번 돌려 빼면 오차가 없다 — D-0327이
    그 부류로 오경보율 50%짜리 판정을 돌렸다.
    """
    from hathor.application.compare_aggregation import compare
    from hathor.application.compare_output import PAIRED_T_FLOOR
    from hathor.domain.services.harmony_prior import PriorCondition

    other = load_halves(args.against, args.stem_set)
    condition = PriorCondition(
        harmonic=args.harmonic,
        smoothing=args.smoothing,
        margin_floor=args.margin_floor,
        confident_only=args.confident_only,
    )
    # **`--replay`가 앞, `--against`가 뒤다.** 어느 쪽이 중앙값인지는 사람이 안다 —
    # 행에 `aggregate`가 적혀 있고(D-0073) 그것을 화면이 든다.
    found = compare(observations, other, condition)
    if not found.songs:
        print("짝지을 곡이 없다. 두 산출물이 같은 코퍼스인지 본다", file=sys.stderr)
        return 1

    gap = found.paired_gap
    print(f"짝지은 곡 {len(found.songs)}개 · {args.replay.name} 대 {args.against.name}")
    print(f"  달성 가능 폭  앞 {found.median_width:.4f} · 뒤 {found.mean_width:.4f}")
    print(f"  차이 {gap.gain:+.4f} ± {gap.standard_error:.4f} · t = {gap.t:+.2f}", end="")
    print(f" (문턱 {PAIRED_T_FLOOR:.1f})")
    print(f"  쌍 단위 승률 {gap.win_rate:.1%} — **진단이다** (D-0327)")
    print(f"판정: **{'앞이 더 넓다' if found.widens else '앞이 뒤를 못 넘는다'}**\n")
    print("**폭은 클수록 좋다** — `uniform`과 `oracle` 사이가 넓다는 것은 곡 고유")
    print("정보가 들어갈 자리가 넓다는 뜻이다. D-0064는 그 폭이 **0.0187에서 오르는가**를")
    print("물었고, 중앙값이 창별 잡음을 깎으면서 **신호도 깎으면 진다** (D-0337).")
    return 0


def run_eval_harmony_prior(args: argparse.Namespace) -> int:
    """화성 도수 사전이 참조곡 고유 정보를 담는지 판정한다 (O-21 · D-0062).

    **생성물을 채점하지 않는다.** "생성된 진행이 참조곡 크로마와 맞는가"는 조건화가
    질 수 없는 지표이며, 코퍼스 전역 베이스라인이 정의상 진다. 곡을 앞뒤로 갈라
    뒷반쪽을 홀드아웃으로 두면 네 선이 전부 질 수 있다.

    저장된 반쪽 크로마만 읽으므로 **음원도 GPU도 필요 없다** — 광인사에서 돈다.
    """

    from hathor.domain.services.harmony_prior import (
        PriorCondition,
        compare_priors,
    )

    observations = load_halves(args.replay, args.stem_set)

    if args.against is not None:
        return _compare_aggregation(args, observations)

    if len(observations) < 2:
        hint = (
            f"`ingest keys --halves --separate`로 먼저 추출하고 --stem-set은 "
            f"{sorted(STEM_SETS)} 중에서 고른다."
            if args.stem_set
            else "`ingest keys --halves`로 먼저 추출한다."
        )
        print(f"반쪽 크로마가 있는 곡이 {len(observations)}개다. {hint}", file=sys.stderr)
        return 1

    condition = PriorCondition(
        harmonic=args.harmonic,
        smoothing=args.smoothing,
        margin_floor=args.margin_floor,
        confident_only=args.confident_only,
        seed=args.seed,
        blend_steps=args.blend_steps,
    )
    result = compare_priors(observations, condition)

    print(
        f"곡 {result.song_count}개 · 스템 {args.stem_set or '전체 믹스'}"
        f" · 배음 {condition.harmonic:g} · 평활 {condition.smoothing:g}"
        f" · 애매 {result.ambiguous_count}곡(격차<{condition.margin_floor:g})"
        f"{' · 애매 제외' if condition.confident_only else ''}\n"
    )

    header = f"{'선':<10}{'중앙값 CE':>12}{'코퍼스 대비':>14}{'포착 비율':>12}{'곡 단위 승률':>14}"
    print(header)
    print("-" * 64)
    lines = (
        ("uniform", result.uniform_score, None),
        ("corpus", result.corpus_score, None),
        ("other", result.other_score, result.other_win_rate),
        ("self", result.self_score, result.self_win_rate),
        ("oracle", result.oracle_score, None),
    )
    for name, score, win_rate in lines:
        gap = score - result.corpus_score
        share = "-" if win_rate is None else f"{win_rate:.1%}"
        captured = result.captured_share(score)
        print(f"{name:<10}{score:>12.4f}{gap:>+14.4f}{captured:>12.1%}{share:>14}")
    print(f"\n달성 가능 폭 (uniform → oracle): {result.uniform_score - result.oracle_score:.4f}")

    print("\nλ 곡선 (자기 반쪽 혼합 비율 → 중앙값 CE)")
    for weight, score in zip(result.lambdas, result.self_curve, strict=True):
        marker = "  ←" if weight == result.best_lambda else ""
        print(f"  {weight:>4.2f}  {score:.4f}{marker}")

    verdict = "정보 있음" if result.is_conditioning_informative else "정보 없음"
    ratio = result.null_gain / result.self_gain if result.self_gain > 0 else float("inf")
    print(f"\nλ*      = {result.best_lambda:.2f}  낙폭 {result.self_gain:.4f}")
    print(
        f"귀무 λ* = {result.null_lambda:.2f}  낙폭 {result.null_gain:.4f}  (자기선의 {ratio:.1%})"
    )
    print(f"판정: **{verdict}**")

    print("\n--- 읽는 법 ---")
    print("λ*가 판정이다. 0이면 참조곡이 코퍼스 평균에 보탤 것이 없고 O-21(D-0082)의 크로마")
    print("접근을 기각한다. 0보다 크면 그 값이 곧 생성기의 혼합 계수다.")
    print("**귀무 λ*가 0이 아닌 것 자체는 이상이 아니다** (D-0065). 곡끼리 독립인 합성")
    print("자료에서도 0.1이 나온다. 볼 것은 위치가 아니라 낙폭이며, 자기선의 낙폭에 비해")
    print("작아야 한다. 비율이 크면 자기선의 이득도 곡 고유성이 아닐 수 있다.")
    print("`uniform`은 천장이 아니다. 구조가 없으면 균등이 최적이라 코퍼스가 진다.")
    print("**포착 비율이 크기다** (D-0063). 격차의 절대값은 크로마가 평평하면 어차피 작다.")
    print("`oracle`은 뒷반쪽으로 뒷반쪽을 맞힌 값이며 어떤 선도 이보다 낮을 수 없다.")
    print("중앙값이라 절대값의 부호는 뜻이 없다. 같은 곡 집합 안의 선끼리만 비교한다.")
    return 0


def run_eval_time_drift(args: argparse.Namespace) -> int:
    """곡마다 다른 시간 변화가 실재하는지 잰다 (O-32 게이트 · D-0098).

    **이 게이트가 통과해야 전량 재추출을 한다.** 스템 캐시가 없어 Demucs를 처음부터
    다시 도는 작업이며, 게이트 없이 그것을 하는 것은 D-0058 계열의 형태다.
    """
    from hathor.application.evaluate_time_drift import GATE_T, EvaluateTimeDrift

    if stems_overlap(args.left, args.right):
        print(
            f"`{args.left}`과 `{args.right}`이 오디오를 공유한다. "
            "**겹치는 두 관측은 잡음도 함께 움직여 상관이 부풀려진다** (D-0099).",
            file=sys.stderr,
        )
        return 2

    store = resolve_priors(args.priors, args.left)
    if store is None:
        return 1

    observations = load_drift_observations(store, args.left, args.right)
    if len(observations) < 10:
        print(
            f"반쪽 크로마가 두 출처에 다 있는 곡이 {len(observations)}개다. "
            f"`ingest keys --halves --separate --limit 200`으로 표본을 먼저 뽑는다. "
            f"`{args.left}`과 `{args.right}`이 둘 다 있어야 한다.",
            file=sys.stderr,
        )
        return 1

    report = EvaluateTimeDrift(seed=args.seed).run(observations, args.left)
    print(f"곡 {report.song_count}개 · 출처 {args.left} 대 {args.right}\n사전: {store.name}\n")
    for text in render_table(
        (
            ("실측", ">10.4f"),
            ("귀무", ">10.4f"),
            ("초과", ">10.4f"),
            ("표준오차", ">10.4f"),
            ("t", ">8.2f"),
            ("칸비율", ">9.0%"),
        ),
        [
            (
                report.observed,
                report.null,
                report.excess,
                report.standard_error,
                report.t_statistic,
                report.cell_share,
            )
        ],
    ):
        print(text)
    passed = report.time_drift_is_song_specific
    print(
        f"\n판정: **{'곡마다 다른 시간 변화가 있다' if passed else '게이트를 못 넘는다'}**"
        f"  (문턱 t > {GATE_T:g} · 칸 과반)\n"
    )
    print("--- 읽는 법 ---")
    print("**두 독립 관측이 같은 방향을 가리키는가**를 본다. 전체 믹스와 스템은 같은 곡의")
    print("두 관측이고, 크로마 추정 잡음은 두 출처에서 갈리지만 **진짜 시간 변화는 둘 다에**")
    print("나타난다. 귀무선은 **곡 짝을 뒤섞은 것**이라 잡음 구조와 코퍼스 공통 변화를")
    print("그대로 갖고 있다 — **초과분만 곡 고유한 시간 변화다.**")
    print("**문턱이 t > 3으로 높다.** 이 게이트가 통과하면 전량 재추출과 시계열 파이프라인을")
    print("승인한다 — **승인 문턱은 관측 문턱보다 높아야 한다** (D-0095에서 51%를 통과로")
    print("읽을 뻔한 뒤 정한 규율이다).")
    print("**두 관측이 겹치면 안 된다** (D-0099). `mix`와 `other`는 오디오를 공유해 잡음도")
    print("함께 움직이고 상관이 부풀려진다 — 실측 0.5572가 그 겹침만으로 설명 가능했다.")
    print("기본값 `other` 대 `bass`는 서로 다른 악기이고 오디오가 겹치지 않는다.")
    print("**그래도 못 가르는 것**: 뒷반쪽이 그냥 더 시끄러운 식의 곡별 인공물은 두 스템에")
    print("함께 나타날 수 있고 그것은 화성이 아니다.")
    return 0


# ------------------------------------------ 명령 등재 (D-0273)


def _build_fusion(parser: argparse.ArgumentParser) -> None:
    """`hathor eval fusion` 인자."""
    parser.add_argument("--out", type=resolve_path, default=DEFAULT_OUTPUT_ROOT, help="산출물 위치")
    parser.add_argument(
        "--features",
        type=resolve_path,
        default=None,
        help=f"특징 산출물 루트 (미지정 시 --out/{DEFAULT_FEATURE_DIRNAME})",
    )
    parser.add_argument("--keys", default=DEFAULT_SEARCH_KEY, help="쓸 임베딩 키")
    parser.add_argument("-k", type=int, default=10, help="상위 k개")
    parser.add_argument("--pairs", type=int, default=200, help="시드 쌍 표본 수")
    parser.add_argument("--seed", type=int, default=20260817, help="쌍 추출 시드")
    parser.add_argument("--penalty", type=float, default=1.0, help="penalized 모드의 편차 계수")
    parser.add_argument("--raw", action="store_true", help="중심화를 끈다")


def _build_harmony_prior(parser: argparse.ArgumentParser) -> None:
    """`hathor eval harmony-prior` 인자."""
    parser.add_argument(
        "--replay",
        type=resolve_path,
        required=True,
        help="`ingest keys --halves`가 만든 keys.jsonl. 음원도 GPU도 필요 없다",
    )
    parser.add_argument(
        "--stem-set",
        default=None,
        help="스템 조합 이름 (예: other, other+bass). --separate로 뽑은 것만 쓸 수 있다",
    )
    parser.add_argument(
        "--against",
        type=resolve_path,
        default=None,
        help="다른 집계로 뽑은 keys.jsonl. 달성 가능 폭을 **짝지어** 맞댄다 (D-0064 · D-0337)",
    )
    parser.add_argument(
        "--harmonic", type=float, default=0.0, help="배음 감산 강도. 네 선 전부에 적용된다"
    )
    parser.add_argument("--smoothing", type=float, default=0.01, help="예측 분포 평활 비율")
    parser.add_argument(
        "--margin-floor", type=float, default=KEY_MARGIN_FLOOR, help="조성 추정 애매 기준"
    )
    parser.add_argument(
        "--confident-only", action="store_true", help="격차가 하한 미만인 곡을 뺀다"
    )
    parser.add_argument("--seed", type=int, default=20260819, help="귀무선 짝짓기 시드")
    parser.add_argument("--blend-steps", type=int, default=11, help="λ 격자 수")


def _build_time_drift(parser: argparse.ArgumentParser) -> None:
    """`hathor eval time-drift` 인자."""
    parser.add_argument(
        "--priors",
        type=resolve_path,
        default=None,
        help="`ingest keys --halves --separate`가 만든 keys.jsonl",
    )
    parser.add_argument(
        "--left", default="other", help="첫째 관측. **둘째와 겹치면 안 된다** (D-0099)"
    )
    parser.add_argument("--right", default="bass", help="둘째 관측. mix면 전체 믹스 크로마")
    parser.add_argument("--seed", type=int, default=20260822, help="귀무선·부트스트랩 시드")


COMMANDS: tuple[Command, ...] = (
    Command("fusion", "시드 결합 규칙 비교 (M4)", _build_fusion, run_eval_fusion),
    Command(
        "harmony-prior",
        "화성 도수 사전의 정보량 판정 (O-21 · D-0062)",
        _build_harmony_prior,
        run_eval_harmony_prior,
    ),
    Command(
        "time-drift",
        "곡마다 다른 시간 변화가 실재하는가 (O-32 게이트 · D-0098)",
        _build_time_drift,
        run_eval_time_drift,
    ),
    CHORD_QUALITY,
    ONSETS,
    WINDOW_LENGTH,
)
"""`eval` 표에 실리는 것 (D-0273). **등재와 배선이 한 줄에 선다.**"""
