#!/usr/bin/env python3
"""`layer00`이 화성을 담는가 (O-49 · D-0179).

**학습을 안 한다.** *조성이 같은 곡끼리가 다른 곡끼리보다 임베딩이 가까운가*를 묻고,
`retrieval_metrics`가 유사도 행렬과 마스크만 받으므로 M0/M1/M2와 같은 장치로 잰다.

**판정하지 않는다.** 하한(무작위) · 대조(MFCC) · 상한(크로마) 옆에 MERT를 나란히
찍을 뿐이며 무엇을 할지는 결정 기록으로 정한다 (D-0058).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from hathor.domain.services.embedding_pooling import PoolMode, pool  # noqa: E402
from hathor.domain.services.retrieval_metrics import (  # noqa: E402 — sys.path 조작 뒤라야 한다
    cosine_similarity,
    expected_random_precision,
    score_retrieval,
)
from hathor.infrastructure.keys_jsonl_store import iter_rows  # noqa: E402
from hathor.infrastructure.npz_feature_store import NpzFeatureStore  # noqa: E402


def _resolve(value: str) -> Path:
    """상대 경로는 **저장소 루트 기준**이다 (D-0069 · D-0153).

    `cd core`에서 돌리면 `core/var/ingest`를 찾게 되고 **조용히 빈손이 된다.**
    """
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


AMBIGUOUS = "(애매)"
"""조성 추정이 흔들린 표기 (D-0054). **이미 있는 구분이며 새 문턱이 아니다.**"""

PERMUTATIONS = 200
"""라벨 뒤섞기 횟수. **귀무를 먼저 돌린다** (O-25 (4))."""


def artist_of(source_key: str) -> str:
    """파일 이름 앞부분. **같은 아티스트를 후보에서 빼려고 쓴다.**

    같은 조성이 같은 아티스트일 수 있고, 그러면 조성이 아니라 음색을 재게 된다 —
    D-0099가 *"겹치면 잡음도 함께 움직인다"*고 적은 부류다. **제외이지 문턱이 아니다.**
    """
    return Path(source_key).stem.split("-", 1)[0].strip().casefold()


def chroma_of(out: Path) -> dict[str, np.ndarray]:
    """`source_key` → 곡 전체 크로마 12차원. **상한이다.**

    **조성 라벨이 바로 이것에서 나왔다** (D-0054). 그래서 높게 나오는 것이 당연하고,
    그 당연함이 상한의 뜻이다 — **이보다 잘할 수 없다.** 순환이므로 *성능*으로
    읽으면 안 되고 **자 눈금으로만 읽는다.**
    """
    for path in sorted(out.glob("*.keys.jsonl"), reverse=True):
        found: dict[str, np.ndarray] = {}
        for row in iter_rows(path):
            key, vector = row.get("source_key"), row.get("chroma")
            if isinstance(key, str) and isinstance(vector, list) and len(vector) == 12:
                found[key] = np.asarray(vector, dtype=np.float32)
        if found:
            return found
    return {}


def labels_of(out: Path) -> tuple[dict[str, str], Path | None]:
    """`source_key` → 조성 문자열과 읽은 파일. 없으면 `({}, None)`.

    **스템 조합을 안 고른다.** 조성은 `key` 한 칸이며 스템 사전과 무관하다 —
    `find_keys_store`는 스템 사전을 찾는 함수라 여기 쓰면 엉뚱한 곳을 뒤진다.
    """
    for path in sorted(out.glob("*.keys.jsonl"), reverse=True):
        found: dict[str, str] = {}
        for row in iter_rows(path):
            key, name = row.get("source_key"), row.get("key")
            if isinstance(key, str) and isinstance(name, str):
                found[key] = name
        if found:
            return found, path
    return {}, None


def _fold(embedding: np.ndarray) -> np.ndarray:
    """`(청크, 차원)`을 곡 벡터 하나로 접는다.

    **정본은 `embedding_pooling.pool`이고 검색 하네스와 같은 설정을 쓴다** —
    `mean` · `chunk_l2` 없음이 CLI 기본값이다. D-0027이 *"풀링·정규화에 남은 여지가
    없다"*로 닫았으므로 **여기서 새로 고르지 않는다.**

    이미 1차원이면 그대로 둔다. 배치마다 청크 수가 달라 **안 접으면 곡마다 모양이
    다르고 쌓이지 않는다.**
    """
    stacked = np.asarray(embedding, dtype=np.float32)
    if stacked.ndim == 1:
        return stacked
    return np.asarray(pool(stacked, PoolMode.MEAN), dtype=np.float32)


def stores_under(out: Path) -> list[Path]:
    """특징 저장소 폴더 전부. **한 자리에 다 있지 않다.**

    `mert-layers` · `mert-layers-low` · `baseline-mfcc`처럼 배치마다 폴더가
    갈린다. **어디 있는지 묻지 않고 색인이 있는 곳을 센다** (D-0100).

    **`NpzFeatureStore`가 스스로 `features`를 붙인다.** 색인은
    `<폴더>/features/index.features.jsonl`이므로 여기서 내는 것은 그 **할아버지**다.
    """
    found = {path.parent.parent for path in out.glob("*/features/index.features.jsonl")}
    if (out / "features" / "index.features.jsonl").exists():
        found.add(out)
    return sorted(found)


def vectors_of(out: Path, wanted: str) -> tuple[dict[str, np.ndarray], Path | None]:
    """`source_key` → 그 이름의 임베딩과 찾은 폴더. **없는 곡은 조용히 빠진다.**

    `폴더:이름`으로 폴더를 못 박을 수 있다. **`mixture`는 모든 폴더에 있으므로**
    이름만 주면 사전 순으로 먼저 오는 폴더를 집는다 — 가사 임베딩이 걸릴 수 있다.
    **우연히 맞는 것은 맞은 것이 아니다.**
    """
    home, _, name = wanted.rpartition(":")
    wanted = name
    for folder in stores_under(out):
        if home and folder.name != home:
            continue
        store = NpzFeatureStore(folder)
        found: dict[str, np.ndarray] = {}
        for record in store.read_records():
            key, name = record.get("source_key"), record.get("vector_file")
            if not isinstance(key, str) or not isinstance(name, str):
                continue
            try:
                views = store.read_vectors(name)
            except (OSError, ValueError, KeyError):
                continue
            if wanted in views:
                found[key] = _fold(views[wanted])
        if found:
            return found, folder
    return {}, None


def names_in(out: Path) -> dict[str, list[str]]:
    """폴더마다 어떤 임베딩 이름이 있는지. **못 찾았을 때 다음 수를 준다.**"""
    found: dict[str, list[str]] = {}
    for folder in stores_under(out):
        store = NpzFeatureStore(folder)
        for record in store.read_records():
            name = record.get("vector_file")
            if not isinstance(name, str):
                continue
            try:
                found[folder.name] = sorted(store.read_vectors(name))
            except (OSError, ValueError, KeyError):
                continue
            break
    return found


def masks(keys: list[str], labels: dict[str, str]) -> tuple[np.ndarray, np.ndarray]:
    """`(정답, 제외)`. 정답은 같은 조성, 제외는 **자기 자신과 같은 아티스트**다."""
    names = np.asarray([labels[key] for key in keys])
    artists = np.asarray([artist_of(key) for key in keys])
    relevant = names[:, None] == names[None, :]
    excluded = artists[:, None] == artists[None, :]
    np.fill_diagonal(excluded, True)
    return relevant & ~excluded, excluded


def report(
    name: str,
    matrix: np.ndarray,
    keys: list[str],
    labels: dict[str, str],
    k: int,
    songs: int | None = None,
) -> None:
    """한 줄. **곡 수를 함께 찍는다** — 표본이 다르면 나란히 못 놓는다."""
    relevant, excluded = masks(keys, labels)
    similarity = cosine_similarity(matrix, matrix)
    found = score_retrieval(similarity, relevant, excluded, k)
    tail = "" if songs is None else f" · {songs}곡"
    print(f"  {name:<14} P@{k} {found.precision_at_k:.4f} · MAP@{k} {found.map_at_k:.4f}{tail}")


def shuffled_floor(
    matrix: np.ndarray, keys: list[str], labels: dict[str, str], k: int, seed: int
) -> tuple[float, float]:
    """라벨을 뒤섞은 P@k의 95% 구간.

    **임베딩은 그대로 두고 조성만 섞는다** — 분포는 유지되고 짝만 죽는다.
    """
    rng = np.random.default_rng(seed)
    names = [labels[key] for key in keys]
    similarity = cosine_similarity(matrix, matrix)
    drawn: list[float] = []
    for _ in range(PERMUTATIONS):
        shaken = dict(zip(keys, rng.permutation(names), strict=True))
        relevant, excluded = masks(keys, shaken)
        drawn.append(score_retrieval(similarity, relevant, excluded, k).precision_at_k)
    return float(np.quantile(drawn, 0.025)), float(np.quantile(drawn, 0.975))


def halves(keys: list[str], seed: int) -> tuple[list[str], list[str]]:
    """곡을 둘로 가른다. **같은 시드면 같은 갈림이다.**

    **고르는 데 쓴 자료로 판정하지 않는다** (D-0012와 같은 자리). 여섯 층을 같은
    1004곡에서 보고 최고를 고르면 그 고름이 그 자료에 맞춰진 것이고, 절반에서 고른
    뒤 나머지 절반에서 확인해야 고름과 판정이 갈린다.

    **아티스트로 가르지 않는다** — 곡으로 갈라도 같은 아티스트는 어차피 후보에서
    빠지므로(D-0180) 한쪽에 몰려도 정답이 새지 않는다.
    """
    order = np.random.default_rng(seed).permutation(len(keys))
    cut = len(keys) // 2
    return (
        sorted(keys[int(index)] for index in order[:cut]),
        sorted(keys[int(index)] for index in order[cut:]),
    )


def _spearman(left: np.ndarray, right: np.ndarray) -> float:
    """순위상관. **`probe_onsets`에도 같은 것이 있다** — 두 번째이므로 아직 안 묶는다
    (GR-5 #6). 세 번째가 생기면 도메인으로 올린다."""
    if len(left) < 3:
        return 0.0
    ranks = [np.argsort(np.argsort(value)).astype(np.float64) for value in (left, right)]
    first, second = (value - value.mean() for value in ranks)
    scale = float(np.sqrt((first**2).sum() * (second**2).sum()))
    return float((first * second).sum() / scale) if scale > 0.0 else 0.0


def spread(counted: Counter[str]) -> float:
    """**유효 종수.** `1 / Σp²`이며 고른 값이 없다.

    24종이 균등하면 24, 한 종에 몰리면 1이다. **쏠림을 한 수로 말한다** —
    무작위 하한이 `1/종수`보다 높으면 그만큼 몰려 있다는 뜻이고, 그 하한을
    이 수로 설명할 수 있는지 보려고 낸다.
    """
    total = sum(counted.values())
    return 1.0 / sum((count / total) ** 2 for count in counted.values())


def by_mode(name: str, keys: list[str], labels: dict[str, str], matrix: np.ndarray, k: int) -> None:
    """장단으로 묶어 잰다. **같은 자를 여러 임베딩에 댄다.**

    `layer03`만 보면 단조가 낮은 것이 **라벨 오염인지 임베딩 한계인지 못 가른다.**
    크로마는 조성 라벨이 나온 바로 그 자료이므로, **크로마도 단조에서 낮으면
    라벨 쪽이 고장난 것이다** (D-0054의 나란한조).
    """
    relevant, excluded = masks(keys, labels)
    similarity = cosine_similarity(matrix, matrix)
    line = [f"  {name:<14}"]
    for mode in ("major", "minor"):
        picked = np.asarray([labels[key].endswith(mode) for key in keys])
        if not picked.any():
            continue
        found = score_retrieval(similarity[picked], relevant[picked], excluded[picked], k)
        line.append(f"{mode} {found.precision_at_k:.4f}")
    print(" · ".join(line))


def eda(keys: list[str], labels: dict[str, str], matrix: np.ndarray, k: int) -> None:
    """코퍼스가 어떻게 생겼는지 (O-49).

    **판정하지 않는다.** 34%가 작은 것이 임베딩 탓인지 코퍼스 탓인지 자 탓인지
    못 가른 채로 논하고 있었다 — 분포를 안 보고 수치를 읽은 것이다.
    """
    counted = Counter(labels[key] for key in keys)
    artists = Counter(artist_of(key) for key in keys)
    print(f"\n조성 {len(counted)}종 · 유효 {spread(counted):.1f}종")
    print(
        f"  균등이면 무작위 하한이 {1 / len(counted):.4f}, 유효 종수로는 {1 / spread(counted):.4f}"
    )
    ranked = counted.most_common()
    print("  많은 쪽 " + " · ".join(f"{name} {count}" for name, count in ranked[:4]))
    print("  적은 쪽 " + " · ".join(f"{name} {count}" for name, count in ranked[-4:]))
    print(f"\n아티스트 {len(artists)}명 · 유효 {spread(artists):.1f}명")
    print("  많은 쪽 " + " · ".join(f"{name} {count}" for name, count in artists.most_common(4)))

    print("\n조성마다 따로 잰다 — **곡 수를 따라가면 곡 수를 재는 것이다**")
    relevant, excluded = masks(keys, labels)
    similarity = cosine_similarity(matrix, matrix)
    rows: list[tuple[str, int, float]] = []
    for name, count in ranked:
        picked = np.asarray([labels[key] == name for key in keys])
        found = score_retrieval(similarity[picked], relevant[picked], excluded[picked], k)
        rows.append((name, count, found.precision_at_k))
    order = sorted(rows, key=lambda row: -row[2])
    shown = order if len(order) <= 10 else [*order[:5], ("...", 0, -1.0), *order[-5:]]
    for name, count, score in shown:
        if score < 0.0:
            print("  ...")
            continue
        print(f"  {name:<14} {count:>4}곡  P@{k} {score:.4f}")
    sizes = np.asarray([float(count) for _, count, _ in rows])
    scores = np.asarray([score for _, _, score in rows])
    print(f"  곡 수와 점수의 순위상관 {_spearman(sizes, scores):+.3f}")

    modes: dict[str, list[float]] = {}
    for name, _, score in rows:
        modes.setdefault(name.rsplit(" ", 1)[-1], []).append(score)
    print("\n으뜸음 말고 **장단**으로 묶으면")
    for mode, found in sorted(modes.items()):
        songs = sum(count for name, count, _ in rows if name.endswith(mode))
        print(
            f"  {mode:<8} {len(found):>2}종 {songs:>4}곡  P@{k} 중앙 {float(np.median(found)):.4f}"
        )
    print("  **D-0054의 나란한조 혼동이 여기 있을 수 있다** — 오염된 쪽은 못 맞힌다")


def capped(keys: list[str], labels: dict[str, str]) -> list[str]:
    """조성마다 **중앙값 개수**까지만 남긴 부표본.

    **중앙값은 자료가 정한다** — 고른 값이 아니다. 쏠린 조성이 점수를 끌고 있는지
    보려고 자른다. 순서는 정렬된 채로 잘라 **시드가 필요 없다.**
    """
    counted = Counter(labels[key] for key in keys)
    limit = int(np.median(list(counted.values())))
    taken: Counter[str] = Counter()
    found: list[str] = []
    for key in keys:
        name = labels[key]
        if taken[name] < limit:
            taken[name] += 1
            found.append(key)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=_resolve, default=ROOT / "var" / "ingest", help="산출물 루트")
    parser.add_argument(
        "--keys", default="mert-layers:layer00", help="볼 임베딩. `폴더:이름`으로 못 박는다"
    )
    parser.add_argument(
        "--against", default="baseline-mfcc:mixture", help="대조 임베딩. `폴더:이름`"
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--clear", action="store_true", help="`(애매)` 조성을 뺀다")
    parser.add_argument("--split", action="store_true", help="곡을 반으로 갈라 양쪽에서 잰다")
    parser.add_argument("--eda", action="store_true", help="코퍼스가 어떻게 생겼는지 본다")
    args = parser.parse_args()

    labels, source = labels_of(args.out)
    if not labels:
        seen = sorted(path.name for path in args.out.glob("*.jsonl"))
        print(f"{args.out}에 `*.keys.jsonl`이 없다. 있는 것: {seen or '없음'}", file=sys.stderr)
        return 1
    if args.clear:
        labels = {key: name for key, name in labels.items() if AMBIGUOUS not in name}

    mine, home = vectors_of(args.out, args.keys)
    if not mine:
        print(f"`{args.keys}` 임베딩이 없다. 있는 것:", file=sys.stderr)
        for folder, names in sorted(names_in(args.out).items()):
            print(f"  {folder}: {' · '.join(names)}", file=sys.stderr)
        return 1

    keys = sorted(set(mine) & set(labels))
    if len(keys) < args.k * 2:
        print(f"견줄 곡이 {len(keys)}곡뿐이다.", file=sys.stderr)
        return 1

    relevant, excluded = masks(keys, labels)
    counted = Counter(labels[key] for key in keys)
    ambiguous = sum(count for name, count in counted.items() if AMBIGUOUS in name)
    print(f"\n{source.name if source else '?'} · {home.name if home else '?'} · {len(keys)}곡")
    print(f"  조성 {len(counted)}종 · `{AMBIGUOUS}` {ambiguous}곡")
    print(f"  아티스트 제외 뒤 남는 후보 중앙 {int(np.median((~excluded).sum(axis=1)))}")
    floor = expected_random_precision(relevant, excluded)
    print(f"  **해석 하한** 무작위 순위의 기대 P@k {floor:.4f}")

    print("\n조성이 같은 곡을 찾는다 — 높을수록 화성을 담는다")
    shown = args.keys.rpartition(":")[2]
    report(shown, np.stack([mine[key] for key in keys]), keys, labels, args.k, len(keys))

    if args.eda:
        eda(keys, labels, np.stack([mine[key] for key in keys]), args.k)
        part = capped(keys, labels)
        stacked = np.stack([mine[key] for key in part])
        print("\n조성마다 중앙값 개수까지만 남기고 다시 잰다")
        cut_relevant, cut_excluded = masks(part, labels)
        counted = Counter(labels[key] for key in part)
        print(f"  조성 유효 {spread(counted):.1f}종 (전체는 위에 있다)")
        floor = expected_random_precision(cut_relevant, cut_excluded)
        print(f"  **이 부표본의 해석 하한** {floor:.4f}")
        report(f"{shown} (고르게)", stacked, part, labels, args.k, len(part))

        print("\n같은 자를 여럿에 댄다 — **크로마도 단조가 낮으면 라벨이 고장난 것이다**")
        whole = np.stack([mine[key] for key in keys])
        by_mode(shown, keys, labels, whole, args.k)
        chroma_all = chroma_of(args.out)
        picked = [key for key in keys if key in chroma_all]
        if picked:
            by_mode("크로마", picked, labels, np.stack([chroma_all[key] for key in picked]), args.k)
        noise = np.random.default_rng(args.seed).normal(0.0, 1.0, whole.shape).astype(np.float32)
        by_mode("무작위", keys, labels, noise, args.k)

        chroma = chroma_of(args.out)
        top = [key for key in part if key in chroma]
        if len(top) >= args.k * 2:
            report(
                "크로마 (고르게)",
                np.stack([chroma[key] for key in top]),
                top,
                labels,
                args.k,
                len(top),
            )

    if args.split:
        for side, part in zip(("앞", "뒤"), halves(keys, args.seed), strict=True):
            stacked = np.stack([mine[key] for key in part])
            report(f"{shown} ({side}절반)", stacked, part, labels, args.k, len(part))

    other, _ = vectors_of(args.out, args.against)
    shared = [key for key in keys if key in other]
    if len(shared) >= args.k * 2:
        stacked = np.stack([other[key] for key in shared])
        label = f"{args.against.rpartition(':')[2]} (대조)"
        report(label, stacked, shared, labels, args.k, len(shared))
    else:
        print(f"  {args.against:<14} 겹치는 곡이 {len(shared)}뿐이라 못 견준다")

    chroma = chroma_of(args.out)
    top = [key for key in keys if key in chroma]
    if len(top) >= args.k * 2:
        stacked = np.stack([chroma[key] for key in top])
        report("크로마 (상한)", stacked, top, labels, args.k, len(top))
    else:
        print(f"  {'크로마 (상한)':<14} 겹치는 곡이 {len(top)}뿐이라 못 견준다")

    rng = np.random.default_rng(args.seed)
    shape = (len(keys), int(next(iter(mine.values())).shape[-1]))
    floor_matrix = rng.normal(0.0, 1.0, shape).astype(np.float32)
    report("무작위 (하한)", floor_matrix, keys, labels, args.k, len(keys))

    low, high = shuffled_floor(
        np.stack([mine[key] for key in keys]), keys, labels, args.k, args.seed
    )
    print(f"\n라벨 뒤섞기 · {args.keys}의 P@{args.k} 95% 구간 [{low:.4f}, {high:.4f}]")
    print("  **구간 안이면 아무 말도 못 한다.** 구간 밖이어도 세기를 함께 본다 (D-0173)")
    print("\n**크로마 상한은 순환이다** — 조성 라벨이 거기서 나왔다. 자 눈금으로만 읽는다")
    print("**대조가 붙어야 갈린다** — 음향 유사도만으로도 같은 라벨이 모일 수 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
