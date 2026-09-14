"""반쪽 크로마의 변화 벡터 (D-0098 · D-0099 · D-0190).

**`application/evaluate_time_drift`에서 내려왔다.** 거기 있는 동안
`infrastructure/keys_jsonl_store`가 **함수 안에서 응용 계층을 임포트했다** —
계층이 거꾸로 섰고 `lint-imports` 계약에 그 방향이 없어 안 잡혔다.

여기 있는 둘은 **크로마에만 의존하는 순수 계산**이다. 파일도 모델도 모른다.
판정과 보고는 여전히 응용이 든다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

DEGREE_COUNT = 12
"""도수 칸 수. **반음 열둘이며 밖에서 온 격자다.**"""


@dataclass(frozen=True, slots=True)
class DriftObservation:
    """곡 하나의 두 출처 변화 벡터. **이미 으뜸음으로 회전돼 있다.**"""

    source_key: str
    left: tuple[float, ...]
    right: tuple[float, ...]

    def __post_init__(self) -> None:
        for vector in (self.left, self.right):
            if len(vector) != DEGREE_COUNT:
                raise ValueError(f"변화 벡터는 12차원이어야 한다: {len(vector)}")


def drift_vector(head: Sequence[float], tail: Sequence[float]) -> tuple[float, ...]:
    """`log(tail) - log(head)`. **로그를 쓰는 이유는 크기가 아니라 방향을 보기 위해서다.**

    반쪽마다 전체 세기가 다를 수 있고 그것은 화성이 아니다. 로그 차는 비율을 재므로
    세기의 곱셈 성분이 상수로 빠진다.
    """
    left = np.maximum(np.asarray(head, dtype=np.float64), 1e-12)
    right = np.maximum(np.asarray(tail, dtype=np.float64), 1e-12)
    changed = np.log(right) - np.log(left)
    return tuple(float(value) for value in changed - changed.mean())
