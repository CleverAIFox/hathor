"""`eval harmony-output` — 출력 차이가 참조곡에서 오는가 (O-29 · D-0082).

**`main.py`에서 내려왔다** (D-0133). D-0127이 `tables.py`를, D-0128이 `doctor`를 뗀 뒤
남은 `eval` 보고를 명령 계열로 나눈다. **판정도 통계도 `application`에 있다** — 이
파일은 출력만 한다 (GR-2.2).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, cast

from hathor.domain.services.stem_sets import MIX_SOURCE
from hathor.infrastructure.keys_jsonl_store import (
    find_keys_store,
    load_degree_priors,
)
from hathor.interfaces.cli.tables import parse_key, render_table

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence


def report_harmonic_sweep(rows: list[dict[str, object]], profile: str) -> int:
    """배음 감산 강도를 **선법으로 나눠** 훑는다 (D-0060 · D-0197).

    D-0060이 전체 지표만 냈고 **코퍼스가 장조 745 · 단조 259라 전체는 장조가
    든다.** 통계는 `application`이 낸다 (GR-2.2) — 여기는 찍기만 한다.
    """
    from hathor.application.sweep_harmonic_modes import sweep_harmonic_modes
    from hathor.domain.value_objects.key import Mode

    saved = [row.get("chroma") for row in rows]
    if any(item is None for item in saved):
        print("저장된 크로마가 없다. 먼저 크로마를 포함해 추출한다.", file=sys.stderr)
        return 1

    chromas = cast("list[Sequence[float]]", saved)
    sweep = sweep_harmonic_modes(chromas, profile=profile)
    print(
        f"곡 {sweep.song_count}개 · 프로파일 {profile}"
        f" · 고정 집합 {sweep.stable_count}곡 ({sweep.stable_share:.1%})\n"
    )

    for text in render_table(
        (
            ("강도", ">6.1f"),
            ("선법", "<8"),
            ("곡", ">6"),
            ("비중", ">8.1%"),
            ("애매", ">8.1%"),
            ("무작위바닥", ">12.1%"),
            ("초과", ">9.1f"),
            ("고정집합", ">10.1%"),
            ("나란한조", ">10.1%"),
            ("이동", ">6"),
        ),
        [
            (
                item.strength,
                "major" if cell.mode is Mode.MAJOR else "minor",
                cell.count,
                cell.share,
                cell.ambiguous,
                cell.floor,
                cell.excess,
                cell.stable_ambiguous,
                cell.relative_in_ambiguous,
                item.moved,
            )
            for item in sweep.rows
            for cell in item.cells
        ],
    ):
        print(text)

    print("\n--- 읽는 법 ---")
    print("**`무작위바닥`이 선법별이다** (D-0197). 전체 바닥 하나를 두 선법에 같이 대면")
    print("판정이 뒤집힌다 — 귀무에서 장조 바닥 35.7% · 단조 바닥 29.4%로 6%p 넘게 다르다.")
    print("**`초과`가 판정이다.** 양수면 그 선법에서 추정이 무작위보다 나쁘다.")
    print("**`고정집합`을 먼저 읽는다.** 강도를 올리면 경계의 곡이 선법을 갈아타고")
    print("(`이동`), 갈아탄 곡은 원래 애매하다 — 귀무에서 넘어온 곡의 93.9%가 애매했다.")
    print("그래서 `애매`는 실력이 아니라 분모 이동으로도 움직인다. **선법이 전 강도에서")
    print("안 바뀐 곡만 본 것이 `고정집합`이며 거기서만 강도끼리 비교가 성립한다.**")
    print("나란한조가 오르면 남은 애매함이 원리적 한계 쪽으로 이동한 것이다.")
    print("**귀무가 코퍼스 구조를 재현하지 않는다** (O-25 다섯째 줄). 디리클레는 선법")
    print("구성이 45/55인데 코퍼스는 74/26이다. 바닥은 하한이지 예측이 아니다.")
    return 0


def run_eval_harmony_output(args: argparse.Namespace) -> int:
    """참조곡을 바꾸면 출력이 얼마나 갈리는지 잰다 (O-29 · D-0078).

    **8마디 한 번을 세는 것으로는 아무것도 판정할 수 없다.** `rng.choices`는
    가중치에 비례하는 것이 아니라 **가중치가 뽑힌 난수를 넘어설 때만** 바뀌는
    문턱이다. 시드 1000개로 늘리고 비교선 일곱을 함께 낸다.

    저장된 크로마만 읽으므로 **음원도 GPU도 필요 없다.**
    """
    from hathor.application.evaluate_harmony_output import (
        EvaluateHarmonyOutput,
        OutputCondition,
        OutputReport,
        ReferencePrior,
        SourceComparison,
        sweep_bar_counts,
    )
    from hathor.engines.compose.harmony_generator import vocabulary_roots
    from hathor.shared.config.paths import repo_root as _root

    target = args.stem_set
    baseline = None if args.against.lower() == "none" else args.against
    store = args.priors
    if store is None:
        store = find_keys_store(_root(), target if target != MIX_SOURCE else "other")
    if store is None or not store.exists():
        print(
            "사전 산출물을 찾지 못했다. `ingest keys --separate`로 먼저 뽑거나 "
            "--priors로 경로를 준다.",
            file=sys.stderr,
        )
        return 1

    tables = {name: load_degree_priors(store, name) for name in {target, baseline} if name}
    for name, table in tables.items():
        if len(table) < 2:
            print(
                f"출처 `{name}`의 사전이 {len(table)}개다. {store.name}에 그 출처가 없다.",
                file=sys.stderr,
            )
            return 1

    # **두 출처가 같은 곡 집합을 써야 짝지은 비교가 된다.** 곡이 다르면 쌍 추첨이
    # 서로 다른 곡을 가리켜 출처 차이인지 쌍 차이인지 갈리지 않는다 (D-0033).
    shared = sorted(set.intersection(*(set(table) for table in tables.values())))
    if len(shared) < 2:
        print(f"두 출처에 공통인 곡이 {len(shared)}개다.", file=sys.stderr)
        return 1

    from hathor.engines.compose.harmony_generator import Vocabulary

    condition = OutputCondition(
        seed_count=args.seeds,
        bar_count=args.bars,
        pair_count=args.pairs,
        key=parse_key(args.key),
        seed=args.seed,
        vocabulary=Vocabulary(args.vocabulary),
    )
    harness = EvaluateHarmonyOutput(condition)

    def references(name: str) -> list[ReferencePrior]:
        return [ReferencePrior(source_key=key, prior=tables[name][key]) for key in shared]

    reports: dict[str, OutputReport] = {
        name: harness.run(references(name), name) for name in tables
    }
    result = reports[target]

    print(
        f"곡 {len(shared)}개 · 쌍 {result.line('paired').pair_count}"
        f" · 시드 {condition.seed_count} · {condition.bar_count}마디"
        f" · {condition.key} · 출처 {target}"
        f"{f' (기준 {baseline})' if baseline else ''}\n"
        f"사전: {store.name}\n"
    )

    for name, report in reports.items():
        print(f"[{name}]")
        for text in render_table(
            (
                ("선", "<10"),
                ("도수거리", ">12.4f"),
                ("표준오차", ">10.4f"),
                ("마디환산", ">11.2f"),
                ("극한", ">10.4f"),
                ("마디불일치", ">13.4f"),
                ("전이초과", ">11.4f"),
                ("t", ">7.2f"),
            ),
            [
                (
                    item.name,
                    item.mean_distance,
                    item.standard_error,
                    item.mean_distance * condition.bar_count,
                    item.mean_limit,
                    item.mean_mismatch,
                    item.order_excess,
                    item.order_t,
                )
                for item in report.lines
            ],
        ):
            print(text)
        verdict = "정보 있음" if report.is_output_conditioned else "정보 없음"
        sound = "건전" if report.is_harness_sound else "**고장**"
        order = "**있음**" if report.line("paired").carries_order else "없음"
        print(f"하네스 {sound} · 어휘 판정: **{verdict}** · 순서 판정: {order}\n")

    if baseline:
        comparison = SourceComparison(baseline=reports[baseline], target=result)
        moved = comparison.gain * condition.bar_count
        print(
            f"짝지은 비교 ({baseline} → {target})\n"
            f"  출력 차이 이득 {comparison.gain:+.4f}  (마디 환산 {moved:+.2f})\n"
            f"  사전 극한 이득 {comparison.limit_gain:+.4f}\n"
            f"  쌍 단위 승률  {comparison.win_rate:.1%}\n"
            f"  전달: **{'그렇다' if comparison.transmits_prior_contrast else '아니다'}**\n"
        )

    if args.compare_vocabulary:
        from dataclasses import replace

        from hathor.application.evaluate_harmony_output import OutputLine

        print("어휘 비교 (같은 쌍·같은 시드) — O-36 · D-0094")
        columns = (
            ("어휘", "<10"),
            ("칸", ">5"),
            ("paired", ">10.4f"),
            ("극한", ">10.4f"),
            ("마디환산", ">11.2f"),
        )
        measured: dict[str, OutputReport] = {}
        rows: list[tuple[object, ...]] = []
        for name in ("base", "control", "mixture"):
            chosen = replace(condition, vocabulary=Vocabulary(name))
            report = EvaluateHarmonyOutput(chosen).run(references(target), name)
            measured[name] = report
            line = report.line("paired")
            rows.append(
                (
                    name,
                    len(vocabulary_roots(condition.key.mode, Vocabulary(name))),
                    line.mean_distance,
                    line.mean_limit,
                    line.mean_distance * condition.bar_count,
                )
            )
        for text in render_table(columns, rows):
            print(text)
        mixture_line = measured["mixture"].line("paired")
        control_line = measured["control"].line("paired")
        gain = mixture_line.mean_distance - control_line.mean_distance
        wins = sum(
            1
            for left, right in zip(mixture_line.distances, control_line.distances, strict=True)
            if left > right
        )
        share = wins / max(len(mixture_line.distances), 1)
        free = control_line.mean_distance - measured["base"].line("paired").mean_distance
        beats = gain > 0 and share > 0.5
        verdict = "차용 어휘가 출력을 더 가른다" if beats else "대조군을 못 넘는다"
        print(
            f"\n칸이 늘어 공짜로 오른 몫 (control - base) = {free:+.4f}\n"
            f"차용이 번 몫 (mixture - control) = {gain:+.4f}"
            f" · 쌍 단위 승률 {share:.1%}\n"
            f"판정: **{verdict}**\n"
        )
        from hathor.application.evaluate_harmony_output import cell_spread
        from hathor.engines.compose.harmony_generator import (
            BORROWED_ROOT_SEMITONES,
            CONTROL_ROOT_SEMITONES,
        )

        mode = condition.key.mode
        picked = references(target)
        print(
            f"칸별 곡 간 로그 표준편차 — 차용 칸 "
            f"{cell_spread(picked, BORROWED_ROOT_SEMITONES[mode]):.4f}"
            f" · 대조 칸 {cell_spread(picked, CONTROL_ROOT_SEMITONES[mode]):.4f}\n"
        )
        print("**D-0093이 잰 것과 여기서 필요한 것이 다른 양이다** (D-0095). 거기서는 세 칸이")
        print("**함께 오르는가**(상관)를 쟀고, 히스토그램 거리를 만드는 것은 **얼마나")
        print("흔들리는가**(분산)다. 위 두 표준편차가 비슷하면 어휘를 넓혀도 이득이 없다.\n")
        if args.bar_sweep:
            counts = tuple(int(token) for token in args.bar_sweep.split(",") if token.strip())
            limit_gain = (
                measured["mixture"].line("paired").mean_limit
                - measured["control"].line("paired").mean_limit
            )
            print(
                "마디 수 훑기 — **8마디 되튐이 어휘 이득을 덮는가** (D-0096)\n"
                f"극한 차이 (mixture - control) = {limit_gain:+.4f}\n"
            )
            sweep_columns = (
                ("마디", ">6"),
                ("mixture", ">10.4f"),
                ("control", ">10.4f"),
                ("차이", ">10.4f"),
                ("극한대비", ">10.1%"),
                ("승률", ">8.1%"),
            )
            sweep_rows: list[tuple[object, ...]] = []
            for bars in counts:
                swept: dict[str, OutputLine] = {}
                for name in ("control", "mixture"):
                    chosen = replace(condition, vocabulary=Vocabulary(name), bar_count=bars)
                    swept[name] = (
                        EvaluateHarmonyOutput(chosen).run(references(target), name).line("paired")
                    )
                step = swept["mixture"].mean_distance - swept["control"].mean_distance
                won = sum(
                    1
                    for left, right in zip(
                        swept["mixture"].distances, swept["control"].distances, strict=True
                    )
                    if left > right
                )
                sweep_rows.append(
                    (
                        bars,
                        swept["mixture"].mean_distance,
                        swept["control"].mean_distance,
                        step,
                        step / limit_gain if limit_gain != 0 else 0.0,
                        won / max(len(swept["mixture"].distances), 1),
                    )
                )
            for text in render_table(sweep_columns, sweep_rows):
                print(text)
            print(
                "\n**8마디에서 안 보인다고 없는 것이 아니다.** 되튐은 마디 수가 늘면 줄고"
                "\n극한 차이는 안 줄므로, 마디를 늘리면 어휘 이득이 드러난다. 합성에서"
                "\n8마디가 극한 차이의 44.7%, 256마디가 101.4%였다 (D-0096)."
                "\n**`승률`이 60%를 못 넘는 줄은 읽지 않는다** — 쌍 100개에서 동전과 구분되지"
                "\n않는다 (D-0095에서 51%를 통과로 읽을 뻔했다).\n"
            )

        print("**`control`을 안 빼면 아무것도 못 읽는다.** 도수를 6에서 9로 늘리는 것만으로")
        print("두 진행이 겹칠 확률이 낮아져 거리가 오른다 — 합성에서 차용이 전혀 없어도")
        print("0.2155에서 0.2696으로 올랐다. `control`은 **뭉치지 않는 세 칸**(♭2·♯4·이끔음)을")
        print("같은 개수로 넣은 선이며, 거기서 오르는 몫은 전부 칸이 늘어서다 (D-0094).\n")

    if args.bar_sweep and not args.compare_vocabulary:
        counts = tuple(int(token) for token in args.bar_sweep.split(",") if token.strip())
        print("마디 수 훑기 (실측이 극한으로 내려가는가)")
        for bars, observed, limit in sweep_bar_counts(references(target), counts, condition):
            print(f"  {bars:>5}마디  {observed:.4f}  (극한 {limit:.4f})")
        print()

    print("--- 읽는 법 ---")
    print("**도수 히스토그램 거리가 지표다.** 마디별 일치율이 아니다 — 같은 어휘를 다른")
    print("순서로 뽑은 것과 다른 어휘를 뽑은 것은 다르다. `마디 환산`은 거리에 마디 수를")
    print("곱한 값이며 지난 세션이 센 `다른 마디 수`와 같은 단위다.")
    print("**`극한`이 상한이다** (O-25 (3)). 사전 가중치 벡터 자체의 거리이며 마디 수를")
    print("늘리면 실측이 거기로 내려간다. 실측이 극한보다 큰 것은 정상이고, 그 초과분은")
    print("**전달된 정보가 아니라 8마디의 되튐이다.** `--bar-sweep`으로 확인한다.")
    print("**`전이초과`는 진단이지 판정이 아니다** (D-0114). **짧은 마디에서 부호가 뒤집힌다** —")
    print("8마디에서 -0.0133이 나온다. 표본 부족이며(4마디는 전이 표본이 3개다) 판정은")
    print("`eval harmony-order`가 self/other로 한다. 그쪽은 4마디에서도 +0.2357이다.")
    print("**`전이초과`가 순서 지표다** (O-32 · D-0102). 도수 히스토그램은 순서에 눈이 없어")
    print("`I V vi IV`와 `IV vi V I`의 거리가 0이다. 전이 행렬은 이웃 관계를 본다.")
    print("귀무선은 **같은 치환을 두 진행에 적용한 것**이다 — 각자 뒤섞으면 시드 짝짓기까지")
    print("깨져 초과가 -0.25로 나온다. **지금은 0이어야 한다** — 순서를 시드가 정하므로")
    print("(D-0062). **이 값이 양수가 되는 날이 O-32가 풀린 날이다.**")
    print("`identical`은 0, `onehot`은 1.0이어야 한다. 아니면 하네스가 고장이므로 나머지")
    print("숫자를 읽지 않는다. `random`은 아무 사전 둘이라 느슨하고, `shuffled`가 뾰족함을")
    print("맞춘 귀무선이다 — 실측이 그보다 작으면 곡들이 화성 어휘를 공유한다는 뜻이다.")
    return 0
