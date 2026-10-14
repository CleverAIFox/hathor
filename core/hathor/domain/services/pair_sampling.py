"""비교 문항으로 쓸 곡 쌍을 뽑는다. 순수 함수이며 파일도 모델도 모른다.

**평가용 쌍은 무작위여야 한다.** D-0012는 적응적 선택(불확실성이 높은 쌍 우선)으로
학습 효율을 올린다고 정했는데, 같은 방식으로 평가 쌍까지 뽑으면 시험 분포가
모델에 의존하게 된다. 자기가 헷갈리는 문제만 골라 풀고 채점하는 것과 같다.
따라서 **무작위 쌍을 먼저 고정 평가 집합으로 확보한 뒤** 적응적 수집을 시작한다.
이 모듈은 그 무작위 단계를 담당한다.

무작위 쌍은 대부분 서로 매우 다른 곡이 걸려 문항 하나당 정보량이 적다. 그것이
결함이 아니라 **평가 집합이 가져야 할 자연 분포**다. 학습 효율은 적응적 단계에서 얻는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

type Pair = tuple[str, str]


def canonical(left: str, right: str) -> Pair:
    """순서를 없앤 쌍 키. (A,B)와 (B,A)를 같은 문항으로 본다."""
    return (left, right) if left <= right else (right, left)


def sample_pairs(
    keys: Sequence[str],
    count: int,
    *,
    seed: int,
    exclude: Iterable[Pair] = (),
) -> list[Pair]:
    """중복 없는 쌍을 무작위로 뽑는다. 같은 시드면 같은 결과가 나온다.

    이미 답한 쌍(`exclude`)은 다시 내지 않는다. 세션을 나눠 수집해도
    같은 문항이 반복되지 않아야 하며, 반복되면 같은 응답이 여러 번 세어져
    그 쌍의 가중치만 커진다.

    가능한 쌍을 전부 만들지 않는다. 1004곡이면 50만 쌍이라 목록을 만드는 것
    자체가 낭비다. 거절 표본으로 뽑되 시도 상한을 둬 무한 루프를 막는다.
    """
    if count <= 0:
        raise ValueError("count는 1 이상이어야 한다")
    if len(keys) < 2:
        raise ValueError("곡이 둘 이상이어야 쌍을 만들 수 있다")

    seen = {canonical(*pair) for pair in exclude}
    generator = np.random.default_rng(seed)
    picked: list[Pair] = []
    # 곡 수에 비례한 시도 상한. 남은 쌍이 거의 없을 때 조용히 도는 것을 막는다.
    attempts = 0
    limit = max(count * 50, 1000)
    while len(picked) < count and attempts < limit:
        attempts += 1
        first, second = generator.choice(len(keys), size=2, replace=False)
        pair = canonical(keys[int(first)], keys[int(second)])
        if pair in seen:
            continue
        seen.add(pair)
        picked.append(pair)
    return picked


def presentation_order(pair: Pair, *, seed: int) -> Pair:
    """화면에 보여줄 좌우 순서를 섞는다.

    사람은 먼저 제시된 쪽을 고르는 경향이 있다. 저장은 정규 순서로 하되
    제시만 뒤집으면 그 편향이 라벨에 실리지 않는다. 시드를 받아 재현 가능하게 둔다.
    """
    generator = np.random.default_rng(seed)
    return (pair[1], pair[0]) if bool(generator.integers(2)) else pair


REPEAT_SHARE = 0.1
"""새 문항 대비 **되묻는 몫**.

10%면 200문항에 20번이고, 그 20번으로 본 일치율의 95% 구간이 대략 ±20%p다 —
천장을 소수점까지 재자는 것이 아니라 **«80%대인가 60%대인가»**를 가리자는 것이다.
더 키우면 새 라벨이 줄고, 새 라벨이 모형을 만든다.
"""

REPEAT_MODE = "repeat"
"""되물은 문항의 `mode`. **새 라벨과 섞이면 같은 쌍이 두 번 세어진다** (D-0012)."""


def with_repeats(
    fresh: Sequence[Pair],
    answered: Sequence[Pair],
    *,
    seed: int,
    share: float = REPEAT_SHARE,
) -> list[tuple[Pair, bool]]:
    """새 문항 사이에 **이미 답한 쌍**을 섞는다. 되묻기에는 표시가 붙는다.

    ### 왜 되묻나

    되묻지 않으면 나중에 나올 정확도가 *«모형이 나쁘다»*인지 *«판정자가 흔들린다»*인지
    **못 가린다.** 합성 실측에서 판정자 잡음이 천장을 90%로 눌렀다 — 천장을 모르면
    70%가 좋은 수인지 나쁜 수인지 말할 수 없다.

    **나중에 못 메운다.** 답한 쌍은 다시 안 나오므로(`exclude`), 되묻기 없이 200번을
    누르면 그 200쌍의 천장은 **영원히 못 잰다.**

    ### 지난 세션 것만 되묻는다

    `answered`는 세션 시작에 읽은 것이므로 **방금 답한 문항은 안 들어온다.** 방금
    답한 것을 다시 물으면 일관성이 아니라 **기억**을 재게 된다.

    섞는다 — 되묻기가 끝에 몰리면 사람이 알아채고 그때부터 답이 달라진다.
    """
    if not 0.0 <= share < 1.0:
        raise ValueError(f"되묻는 몫은 [0, 1)이어야 한다: {share}")

    wanted = min(round(len(fresh) * share), len(answered))
    generator = np.random.default_rng(seed)
    chosen = (
        [
            tuple(answered[int(index)])
            for index in generator.choice(len(answered), wanted, replace=False)
        ]
        if wanted
        else []
    )
    asked: list[tuple[Pair, bool]] = [(pair, False) for pair in fresh]
    asked += [(canonical(*pair), True) for pair in chosen]
    return [asked[int(index)] for index in generator.permutation(len(asked))]
