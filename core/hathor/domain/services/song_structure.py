"""곡 구조를 가사 구간의 반복 패턴에서 뽑고, 그것을 조건으로 새 구조를 만든다.

순수 함수다. 모델도 파일도 쓰지 않는다.

### 왜 반복 패턴인가

D-0038이 실측한 것: **곡을 특정하는 것은 반복 문구다.** 반복 감쇠를 걸었더니
M0가 0.8704에서 0.3848로 무너졌다. 즉 **어느 구간이 반복되는지는 가사 데이터에
이미 강하게 들어 있다.**

구조 생성에 필요한 것이 정확히 그것이다. 후렴은 반복되고 절은 반복되지 않는다.
새 모델도 새 데이터도 없이 **이미 뽑아 둔 1003곡, 곡당 13.6구간에서 얻어진다.**

### 라벨을 붙이지 않는다

구간을 `verse` / `chorus`로 부르지 않고 **`R`(반복) / `U`(고유)** 로만 표기한다.
반복 구간이 실제 후렴이라는 보장이 없기 때문이다 — 미검증 가정으로 이미 등재돼
있다. 이름을 붙이는 순간 검증하지 않은 것을 검증된 것처럼 쓰게 된다.

`intro` / `outro`도 붙이지 않는다. 가사 구간에는 전주·후주가 없다.

### 값싼 것부터 (GR-6.1)

문자 n-gram 자카드로 구간 쌍을 비교한다. MFCC가 MERT를 이겼고 해시 n-gram이
BGE-M3에 크게 뒤지지 않았다. **이 코퍼스에서 값싼 기준선이 두 번 값을 했다.**
신경망 표현은 이 기준선을 넘지 못할 때 꺼낸다.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

NGRAM_SIZE = 3
"""자카드 비교용 문자 n-gram 크기. 조사·어미 차이를 흡수하는 최소 단위다."""

REPEAT_THRESHOLD = 0.5
"""두 구간을 같은 반복 그룹으로 볼 자카드 하한.

0.5는 근거 없이 정한 값이 아니라 **정하지 못한 값이다.** 코퍼스 분포를 보고
조정해야 하며 그 전까지 인용 시 함께 적는다 (실측 필요).
"""

MIN_SEGMENTS = 2

REPEATED = "R"
UNIQUE = "U"


def char_ngrams(text: str, size: int = NGRAM_SIZE) -> frozenset[str]:
    """공백을 접어 문자 n-gram 집합을 만든다.

    공백 접기는 D-0037에서 실측으로 확인된 것을 따른다 — 제거해도 M0 변화가
    -0.001이었다. 즉 띄어쓰기는 신호가 아니며, 여기서 접으면 표기 흔들림에
    덜 민감해진다.
    """
    folded = "".join(text.split())
    if len(folded) < size:
        return frozenset({folded}) if folded else frozenset()
    return frozenset(folded[index : index + size] for index in range(len(folded) - size + 1))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0


@dataclass(frozen=True, slots=True)
class StructurePattern:
    """한 곡의 구조. 구간 순서대로 `R`/`U`를 늘어놓은 것이다.

    `groups`는 구간 인덱스를 반복 그룹 번호로 보낸다. 같은 번호는 서로 비슷한
    구간이며, **그룹 크기가 1이면 고유 구간**이다.
    """

    labels: tuple[str, ...]
    groups: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.groups):
            raise ValueError("labels와 groups의 길이가 같아야 한다")

    @property
    def length(self) -> int:
        return len(self.labels)

    @property
    def repeat_ratio(self) -> float:
        """반복 구간이 차지하는 비율. 후렴 비중의 대리 지표다."""
        if not self.labels:
            return 0.0
        return sum(1 for label in self.labels if label == REPEATED) / len(self.labels)

    def as_text(self) -> str:
        return "".join(self.labels)

    def as_record(self) -> dict[str, object]:
        return {
            "pattern": self.as_text(),
            "length": self.length,
            "repeat_ratio": round(self.repeat_ratio, 4),
            "repeat_groups": len(self.repeat_group_sizes()),
        }

    def repeat_group_sizes(self) -> tuple[int, ...]:
        """반복 그룹별 크기를 큰 순으로. 고유 구간은 빼고 센다."""
        counts: dict[int, int] = {}
        for group in self.groups:
            counts[group] = counts.get(group, 0) + 1
        return tuple(sorted((size for size in counts.values() if size >= 2), reverse=True))


def extract_pattern(
    segments: Sequence[str], *, threshold: float = REPEAT_THRESHOLD
) -> StructurePattern:
    """가사 구간들에서 반복 구조를 뽑는다.

    구간 쌍의 자카드가 `threshold` 이상이면 같은 그룹으로 묶는다. 묶기는
    **가장 앞선 구간을 대표로 삼는 단순 병합**이다. 군집 알고리즘을 쓰지 않는
    이유는 구간이 곡당 10여 개뿐이고, 알고리즘을 넣으면 그 선택이 결과에
    섞이기 때문이다 (형태소 분석기를 배제한 것과 같은 이유).
    """
    if len(segments) < MIN_SEGMENTS:
        raise ValueError(f"구간이 {MIN_SEGMENTS}개 이상이어야 한다: {len(segments)}")

    fingerprints = [char_ngrams(segment) for segment in segments]
    groups: list[int] = []
    for index, fingerprint in enumerate(fingerprints):
        assigned = index
        for earlier in range(index):
            if groups[earlier] != earlier:
                continue  # 대표가 아닌 구간과는 비교하지 않는다
            if jaccard(fingerprint, fingerprints[earlier]) >= threshold:
                assigned = earlier
                break
        groups.append(assigned)

    sizes: dict[int, int] = {}
    for group in groups:
        sizes[group] = sizes.get(group, 0) + 1
    labels = tuple(REPEATED if sizes[group] >= 2 else UNIQUE for group in groups)
    return StructurePattern(labels=labels, groups=tuple(groups))


@dataclass(frozen=True, slots=True)
class PatternStats:
    """코퍼스 구조 분포. **베이스라인 없이 수치를 인용하지 않는다**를 위한 것이다.

    생성한 구조가 그럴듯한지는 절대 기준이 없다. 그러나 **코퍼스 분포 안에
    드는지**는 잴 수 있고, 무작위 구조와 비교할 수 있다.
    """

    count: int
    mean_length: float
    mean_repeat_ratio: float
    length_histogram: tuple[tuple[int, int], ...]
    ratio_histogram: tuple[tuple[float, int], ...]

    def as_record(self) -> dict[str, object]:
        return {
            "songs": self.count,
            "mean_length": round(self.mean_length, 3),
            "mean_repeat_ratio": round(self.mean_repeat_ratio, 4),
            "length_histogram": [list(item) for item in self.length_histogram],
            "ratio_histogram": [[round(edge, 2), n] for edge, n in self.ratio_histogram],
        }


def summarize(patterns: Sequence[StructurePattern]) -> PatternStats:
    """코퍼스 패턴들의 분포를 낸다. 비율은 0.1 단위로 묶는다."""
    if not patterns:
        raise ValueError("패턴이 하나 이상 필요하다")

    lengths: dict[int, int] = {}
    ratios: dict[float, int] = {}
    for pattern in patterns:
        lengths[pattern.length] = lengths.get(pattern.length, 0) + 1
        bucket = round(min(0.9, pattern.repeat_ratio // 0.1 * 0.1), 1)
        ratios[bucket] = ratios.get(bucket, 0) + 1

    return PatternStats(
        count=len(patterns),
        mean_length=sum(p.length for p in patterns) / len(patterns),
        mean_repeat_ratio=sum(p.repeat_ratio for p in patterns) / len(patterns),
        length_histogram=tuple(sorted(lengths.items())),
        ratio_histogram=tuple(sorted(ratios.items())),
    )


def generate_pattern(
    seed: int,
    references: Sequence[StructurePattern],
    *,
    length: int | None = None,
) -> StructurePattern:
    """참조곡들의 구조를 조건으로 새 구조를 만든다 (D-0011 시드 퓨전).

    형용사 체크박스가 아니라 **실제 곡의 구조를 조건으로 쓴다.** 참조가
    하나면 길이와 반복 비율이 그 곡을 따르고, 여럿이면 평균을 따른다.

    반복 구간은 **고르게 흩어 놓는다.** 실제 곡에서 후렴이 한쪽에 몰리는 일은
    드물고, 몰리면 홀짝 분할이 곡 지문을 통째로 한쪽에 주게 된다 — D-0040이
    가사축 M0에서 실측한 바로 그 상황이다.

    시드가 같으면 항상 같은 결과다 (NFR-M6).
    """
    if not references:
        raise ValueError("참조 구조가 하나 이상 필요하다")

    target_length = (
        length
        if length is not None
        else round(sum(reference.length for reference in references) / len(references))
    )
    target_length = max(MIN_SEGMENTS, target_length)
    target_ratio = sum(reference.repeat_ratio for reference in references) / len(references)
    repeat_count = min(target_length - 1, max(1, round(target_length * target_ratio)))

    rng = random.Random(seed)
    # 반복 구간을 균등 간격에 놓고 시드로 흔든다. 무작위 배치는 몰림을 만든다.
    step = target_length / repeat_count
    positions = sorted(
        {
            min(target_length - 1, int(index * step) + rng.randint(0, max(0, int(step) - 1)))
            for index in range(repeat_count)
        }
    )

    labels = [UNIQUE] * target_length
    for position in positions:
        labels[position] = REPEATED
    groups = [positions[0] if label == REPEATED else index for index, label in enumerate(labels)]
    return StructurePattern(labels=tuple(labels), groups=tuple(groups))
