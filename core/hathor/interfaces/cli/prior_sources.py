"""생성이 쓸 사전을 고른다. **조건화의 출처를 한자리에서 고른다** (D-0429).

`main`이 1141줄로 못(1116)을 넘겼고, **못을 올리는 대신 쪼갰다** (D-0117). 사전
고르기는 명령 배선과 다른 일이다 — `tempo_source`가 박자를 고르는 것과 같은 자리다.

### 되돌아감에는 까닭이 붙는다

전체 믹스로 물러나는 길이 셋인데 **돌아온 줄은 «전체 믹스» 하나였다.** 어느 길로
왔는지 구별이 안 되면 그 줄은 사람을 틀린 쪽으로 보낸다 (D-0203 · D-0292).

**내가 적은 경로가 없으면 오타다.** `--priors`·`--series`는 `_run_generate_midi`가
`roots.missing_given_path`로 먼저 막으므로, 여기 오는 *«못 찾았다»*는 **우리가 찾다
못 찾은 경우뿐이다** (D-0429 · D-0326).
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from hathor.infrastructure.chroma_series_store import (
    find_series_root,
    load_transition_priors,
)
from hathor.infrastructure.keys_jsonl_store import (
    find_keys_store,
    load_stem_priors,
    load_tonics,
)
from hathor.interfaces.cli.roots import announce_series

if TYPE_CHECKING:  # pragma: no cover - 형만 쓴다
    from hathor.domain.services.key_estimation import KeyEstimate


def _resolve_harmony_prior(
    args: argparse.Namespace, source_keys: list[str], estimates: dict[str, KeyEstimate]
) -> tuple[tuple[float, ...] | None, str]:
    """화성 사전을 고른다. **스템 저장분이 있으면 그것을 쓴다** (D-0074).

    스템 크로마가 전체 믹스보다 세 배 낫다 — 조건화 이득이 K-K 폭 대비 14.1%에서
    44.3%로 올랐다 (D-0063 · D-0074, 200곡). 다만 **생성할 때 Demucs를 돌리지는
    않는다.** 미리 뽑아 둔 것을 조회하고, 없으면 전체 믹스로 물러난다.

    참조곡이 저장분에 하나도 없으면 전체 믹스를 쓴다. **일부만 있으면 그 일부만
    쓴다** — 섞으면 스템과 믹스가 한 사전 안에서 더해져 무엇을 재는지 알 수 없다.
    """
    from hathor.shared.config.paths import repo_root as _root

    if args.stem_set == "mix":
        return _harmony_prior(estimates), "전체 믹스 (--stem-set mix)"

    store = args.priors if args.priors else find_keys_store(_root(), args.stem_set)
    if store is None or not store.exists():
        # **이 자리가 아무 말도 안 했다** (D-0429). 준 경로가 없는 경우는 명령이
        # 먼저 막으므로, 여기 오는 것은 **우리가 찾다 못 찾은 경우뿐이다.**
        print(
            f"{args.stem_set} 스템 저장분을 못 찾았다. 전체 믹스로 물러난다 "
            "— 뽑으려면 hathor ingest keys",
            file=sys.stderr,
        )
        return _harmony_prior(estimates), "전체 믹스 (스템 저장분 없음)"

    table = load_stem_priors(store, args.stem_set)
    picked = [table[key] for key in source_keys if key in table]
    if not picked:
        print(
            f"참조곡이 스템 저장분에 없다. 전체 믹스로 물러난다: {store.name}",
            file=sys.stderr,
        )
        return _harmony_prior(estimates), "전체 믹스 (참조곡이 저장분에 없다)"

    from hathor.domain.services.harmony_prior import merge_degree_priors

    if len(picked) < len(source_keys):
        print(
            f"참조곡 {len(source_keys)}곡 중 {len(picked)}곡만 스템 저장분에 있다.",
            file=sys.stderr,
        )
    merged = merge_degree_priors([(vector, tonic) for vector, tonic in picked])
    return tuple(float(value) for value in merged), f"{args.stem_set} 스템"


def _resolve_transition_prior(
    args: argparse.Namespace, source_keys: list[str]
) -> tuple[tuple[tuple[float, ...], ...] | None, str]:
    """배열 사전을 고른다 (O-32 · D-0110).

    **참조곡이 여럿이면 곡마다 으뜸음으로 돌린 뒤 더한다** (D-0063 · D-0213).
    *"이미 으뜸음 기준"*이라 적고 안 돌려 절대음을 도수로 읽었다. 없으면 `None`이다.
    """
    from hathor.domain.services.transition_prior import averaged
    from hathor.shared.config.paths import repo_root as _root

    if not args.transitions:
        return None, "없음"
    root = args.series if args.series else find_series_root(_root(), args.stem_set)
    if root is None or not root.is_dir():
        print("시계열 산출물을 찾지 못했다. 배열 조건화를 건너뛴다.", file=sys.stderr)
        return None, "없음"

    store = getattr(args, "priors", None) or find_keys_store(_root(), args.stem_set)
    if store is None:
        print("조성 산출물이 없어 회전 기준이 없다. 배열 조건화를 건너뛴다.", file=sys.stderr)
        return None, "없음"
    announce_series(root, args.stem_set)
    table = load_transition_priors(root, args.stem_set, source_keys, tonics=load_tonics(store))
    found = len(table)
    if found == 0:
        print(f"참조곡이 시계열 저장분에 없다: {root.name}", file=sys.stderr)
        return None, "없음"
    if found < len(source_keys):
        print(
            f"참조곡 {len(source_keys)}곡 중 {found}곡만 시계열 저장분에 있다.",
            file=sys.stderr,
        )
    # **합치는 것은 도메인이 한다** (D-0279). 여기 `numpy`가 있었고 GR-2.2가 금지한다.
    blended = averaged(table.values())
    if blended is None:
        print(f"시계열 저장분의 전이 무게가 0이다: {root.name}", file=sys.stderr)
        return None, "없음"
    return blended, f"{root.name} ({found}곡)"


def _harmony_prior(estimates: dict[str, KeyEstimate]) -> tuple[float, ...] | None:
    """참조곡들의 크로마를 도수 사전 하나로 합친다 (O-21 · D-0063).

    **각 곡을 자기 으뜸음으로 회전시킨 뒤 평균한다.** 피치클래스 공간에서 더하면
    서로 다른 조성이 겹쳐 뭉개진다.

    조성을 추정하지 못했으면 `None`이고, 그러면 화성은 이전처럼 시드만 따른다 —
    조건화가 조용히 반쯤 걸리는 것보다 아예 안 걸리는 편이 낫다.
    """
    from hathor.domain.services.harmony_prior import merge_degree_priors
    from hathor.domain.value_objects.key import PITCH_CLASSES

    usable = [
        (estimate.chroma, PITCH_CLASSES.index(estimate.key.tonic))
        for estimate in estimates.values()
        if len(estimate.chroma) == 12
    ]
    if not usable:
        return None
    return tuple(float(value) for value in merge_degree_priors(usable))
