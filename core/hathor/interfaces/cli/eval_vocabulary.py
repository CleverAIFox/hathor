"""`eval chromatic-origin` · `degree-restriction`.

어휘가 곡을 가르는가 (O-31 · D-0088 · O-33 · D-0090).

**`main.py`에서 내려왔다** (D-0133). D-0127이 `tables.py`를, D-0128이 `doctor`를 뗀 뒤
남은 `eval` 보고를 명령 계열로 나눈다. **판정도 통계도 `application`에 있다** — 이
파일은 출력만 한다 (GR-2.2).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from hathor.domain.services.stem_sets import MIX_SOURCE
from hathor.infrastructure.keys_jsonl_store import (
    find_keys_store,
    load_degree_priors,
    load_key_margins,
)
from hathor.interfaces.cli.tables import parse_key, render_table

if TYPE_CHECKING:
    import argparse


def run_eval_chromatic_origin(args: argparse.Namespace) -> int:
    """반음계 질량이 **치환(조성 오차)인지 첨가(차용화음)인지** 잰다 (O-33 · D-0089).

    사전 벡터만 읽는다. 생성도 음원도 GPU도 필요 없다.
    """
    from hathor.application.evaluate_chromatic_origin import (
        MODAL_MIXTURE,
        SUBSTITUTION_PAIRS,
        EvaluateChromaticOrigin,
        OriginCondition,
        OriginReport,
    )
    from hathor.application.evaluate_harmony_output import ReferencePrior
    from hathor.shared.config.paths import repo_root as _root

    source = args.stem_set
    store = args.priors
    if store is None:
        store = find_keys_store(_root(), source if source != MIX_SOURCE else "other")
    if store is None or not store.exists():
        print("사전 산출물을 찾지 못했다. --priors로 경로를 준다.", file=sys.stderr)
        return 1

    table = load_degree_priors(store, source)
    if len(table) < 3:
        print(f"출처 `{source}`의 사전이 {len(table)}개다.", file=sys.stderr)
        return 1

    key = parse_key(args.key)
    condition = OriginCondition(key_mode=key.mode, seed=args.seed, rotated_share=args.rotated_share)
    harness = EvaluateChromaticOrigin(condition)
    names = sorted(table)
    everything = [ReferencePrior(name, table[name]) for name in names]

    groups: list[tuple[str, list[ReferencePrior]]] = [("전체", everything)]
    if args.margin_split:
        margins = load_key_margins(store)
        ranked = sorted((margins.get(name, 0.0), name) for name in names)
        half = len(ranked) // 2
        groups.append(("추정 확실", [ReferencePrior(n, table[n]) for _, n in ranked[half:]]))
        groups.append(("추정 불확실", [ReferencePrior(n, table[n]) for _, n in ranked[:half]]))

    pairs = ", ".join(f"{chromatic}<-{scale}" for chromatic, scale in SUBSTITUTION_PAIRS[key.mode])
    mixture_cells = ", ".join(str(cell) for cell in MODAL_MIXTURE[key.mode])
    print(
        f"곡 {len(everything)}개 · {key} · 출처 {source}\n사전: {store.name}\n"
        f"치환 짝 (반음계<-온음계): {pairs}\n"
    )
    print(f"단조 차용 삼총사: {mixture_cells} (D-0091)\n")
    columns = (
        ("묶음", "<12"),
        ("곡", ">6"),
        ("치환초과", ">11.4f"),
        ("t", ">8.2f"),
        ("눈금선", ">10.4f"),
        ("뭉침대비", ">11.4f"),
        ("t", ">8.2f"),
        ("온음계질량", ">12.4f"),
    )
    results: list[tuple[str, OriginReport]] = []
    rows: list[tuple[object, ...]] = []
    for name, subset in groups:
        report = harness.run(subset, name)
        results.append((name, report))
        rows.append(
            (
                name,
                report.reference_count,
                report.excess,
                report.t_statistic,
                report.rotated_excess,
                report.mixture_excess,
                report.mixture_t,
                report.scale_mass,
            )
        )
    for line in render_table(columns, rows):
        print(line)
    whole = results[0][1]
    verdict = (
        "**조성 추정 오차가 지배한다**"
        if whole.chromatic_is_substitution
        else "오차로 설명되지 않는다"
    )
    mixture_verdict = (
        "**단조 차용이 있다**" if whole.modal_mixture_present else "삼총사가 안 뭉친다"
    )
    print(
        f"\n치환 판정: {verdict}"
        f"\n뭉침 판정: {mixture_verdict}"
        f"  (대비 {whole.mixture_excess:+.4f} ±{whole.mixture_standard_error:.4f},"
        f" t = {whole.mixture_t:.2f})\n"
    )
    print("--- 읽는 법 ---")
    print("**오차는 치환이고 차용은 첨가다.** 조성 추정이 5도 틀리면 ♭7이 오르면서")
    print("이끔음이 **사라진다.** 진짜 믹솔리디안 차용은 ♭7이 오르되 이끔음이 남는다 —")
    print("곡의 다른 곳에서 V화음을 쓰기 때문이다.")
    print("`초과`는 반음계 칸과 그 짝 온음계 칸의 곡 간 상관에서 조 내 치환 귀무선을 뺀 값이다.")
    print("**음수면 대체, 양수면 첨가다.** 합이 1인 자료라 아무 상관이나 음수로 치우치므로")
    print("귀무선을 빼야 한다.")
    print("**`눈금선`은 실제 곡의 일부를 일부러 잘못 회전시킨 값이다** — 오차가 그만큼")
    print("있으면 값이 어디까지 내려가는지 자료로 보여 준다.")
    print("**검출력이 한쪽만 강하다.** 합성에서 오차는 t=-8로 잡히고 차용은 t=+1.4로 겨우")
    print('보인다. 그러니 **뚜렷한 음수만 강한 결론이고**, 아닌 쪽은 "오차로 설명 안 됨"까지다.')
    print("**`뭉침 대비`가 누설과 차용을 가른다** (D-0091). 단조 차용은 화음 단위로 오므로")
    print("♭3·♭6·♭7이 한 곡에서 **같이** 오른다. 누설은 곡마다 양이 다를 뿐 반음계 다섯 칸을")
    print("**고르게** 올리므로 특정 셋만 뭉치지 않는다. 삼총사 세 쌍에서 나머지 일곱 쌍을 뺀다.")
    print("합성에서 누설만 있을 때 -0.03~0.00이었고 차용이 있으면 +0.50을 넘었다.")
    if args.margin_split:
        print("**`추정 확실`은 보조 시야다.** 차용화음이 많으면 조성 추정도 어려워지므로")
        print("역인과가 있다. 상위 묶음에서도 음수가 아니면 오차로 설명되지 않는다는 쪽이 는다.")
    return 0


def run_eval_degree_restriction(args: argparse.Namespace) -> int:
    """다이어토닉 제한이 버리는 몫을 잰다 (O-31 · D-0083).

    **사전 벡터만 읽는다** — 생성도 음원도 GPU도 필요 없다. 1초 이내다.
    """
    from hathor.application.evaluate_degree_restriction import (
        EvaluateDegreeRestriction,
        chromatic_indices,
        off_scale_indices,
        scale_but_discarded,
    )
    from hathor.application.evaluate_harmony_output import OutputCondition, ReferencePrior
    from hathor.shared.config.paths import repo_root as _root

    source = args.stem_set
    store = args.priors
    if store is None:
        store = find_keys_store(_root(), source if source != MIX_SOURCE else "other")
    if store is None or not store.exists():
        print(
            "사전 산출물을 찾지 못했다. `ingest keys --separate`로 먼저 뽑거나 "
            "--priors로 경로를 준다.",
            file=sys.stderr,
        )
        return 1

    table = load_degree_priors(store, source)
    if len(table) < 2:
        print(f"출처 `{source}`의 사전이 {len(table)}개다.", file=sys.stderr)
        return 1

    condition = OutputCondition(pair_count=args.pairs, key=parse_key(args.key), seed=args.seed)
    references = [ReferencePrior(key, table[key]) for key in sorted(table)]
    report = EvaluateDegreeRestriction(condition).run(references, source)
    observed = report.line("observed")
    off = off_scale_indices(condition.key.mode)
    scale_cells = scale_but_discarded(condition.key.mode)
    chromatic_cells = chromatic_indices(condition.key.mode)

    print(
        f"곡 {len(references)}개 · 쌍 {len(observed.shares)} · {condition.key}"
        f" · 출처 {source}\n사전: {store.name}\n"
        f"버리는 칸 {len(off)}개 (반음 {', '.join(str(value) for value in off)})\n"
        f"  그중 온음계 음 {scale_cells} — **반음계음이 아니다.** 화음 근음에서만 빠졌다\n"
        f"  진짜 반음계 음 {chromatic_cells}\n"
    )
    columns = (
        ("선", "<10"),
        ("비음계몫", ">12.4f"),
        ("표준오차", ">10.4f"),
        ("질량", ">10.4f"),
        ("몫/질량", ">11.4f"),
        ("제한후/전", ">12.4f"),
        ("순위상관", ">10.3f"),
    )
    for line in render_table(
        columns,
        [
            (
                item.name,
                item.mean_share,
                item.standard_error,
                item.mean_mass,
                item.share_per_mass,
                item.survival,
                item.rank_agreement,
            )
            for item in report.lines
        ],
    ):
        print(line)
    print("\n(버리는 칸을 쪼갠다 · D-0085)")
    for line in render_table(
        (("선", "<10"), ("온음계몫", ">12.4f"), ("반음계몫", ">12.4f")),
        [(item.name, item.mean_scale_share, item.mean_chromatic_share) for item in report.lines],
    ):
        print(line)
    verdict = (
        "**버리는 칸이 다이어토닉보다 더 곡 고유하다**"
        if report.off_scale_exceeds_matched
        else "버리는 칸이 다이어토닉보다 **덜하거나 같다**"
    )
    from hathor.application.evaluate_degree_restriction import NULL_REPEATS

    print(
        f"\n등가선 대비 = {report.specificity_gap:+.4f}"
        f" ±{report.specificity_standard_error:.4f} (짝지은 표준오차)"
        f" · 쌍 단위 승률 {report.specificity_win_rate:.1%}\n"
        f"판정: {verdict}\n"
        f"\n[참고] 조 내 치환 대비 = {report.mass_matched_gap:+.4f}"
        f" · 승률 {report.mass_matched_win_rate:.1%}"
        f" · 전체 치환 대비 = {report.gap:+.4f}\n"
        f"       **둘 다 0점이 0이 아니라 단독으로 읽지 않는다** (D-0084 · D-0086).\n"
        f"\n귀무선은 {NULL_REPEATS}회 뽑아 쌍별로 평균했다. 선마다 난수 흐름이 따로다 (D-0087).\n"
    )
    print("--- 읽는 법 ---")
    print("**전변동은 칸별 절댓값의 합이라 다이어토닉과 비음계로 정확히 쪼개진다.** 모형이")
    print("필요 없다. `비음계 몫`은 두 사전의 거리 중 버려지는 칸이 낸 비율이다.")
    print("**칸 수 비율(6/12)은 기준선이 아니다.** 사전 질량이 다이어토닉에 몰려 있으면 몫도")
    print("자연히 낮아진다. 그래서 귀무선이 필요한데, **`shuffled`(12칸 전체 치환)는 질량까지")
    print("바꾼다** — 그것이 D-0083의 결함이었다 (D-0084).")
    print("**`within`도 0점이 0이 아니다** — 온음계 칸에는 코퍼스가 공유하는 조성 모양이 있어")
    print("자리를 뒤섞으면 기여가 크게 늘고, 비음계 칸은 평평해 조금만 는다. 그 비대칭만으로")
    print("부호가 양수가 된다 (D-0086).")
    print("**`matched`가 눈금이다.** 온음계 칸의 곡별 편차를 비음계 칸에 이식해 **두 조가")
    print("똑같이 곡 고유한** 사전을 만든다. 조별 질량과 코퍼스 모양은 그대로다. 실측이")
    print("`matched`보다 **크면** 버리는 칸이 더, **작으면** 덜 곡 고유하다.")
    print("**`순위상관`은 진단이다.** 탐색에서 곡 고유 성분이 없을 때도 0.54였다 — 갈리지 않는")
    print("지표는 판정에 쓰지 않는다 (O-25 (2)).")
    print("**쌍 단위 승률이 60%를 못 넘으면 동전 던지기와 구분되지 않는다** — 쌍 100개에서")
    print("57%의 단측 확률이 0.10이다 (D-0087).")
    return 0
