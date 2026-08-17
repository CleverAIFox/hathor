"""쌍대비교 응답 하나. 사용자가 만든 유일한 취향 라벨이다.

코퍼스는 전량 양성 사례이며 음성 사례가 0건이다(C-7). 절대 라벨을 물으면
"좋아하는 곡만 1004개 있는데 얼마나 좋아하냐"가 되어 눈금이 서지 않는다.
쌍대비교는 **상대 순위**만 물으므로 외부 데이터 없이 라벨을 만든다(D-0012).

`winner`가 None이면 건너뛴 문항이다. 지우지 않고 남긴다. 어떤 쌍을 판단하지
못했는지가 정보이며, 지우면 그 쌍이 다시 출제된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Side(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class PreferenceComparison:
    """정규 순서로 저장한다. 화면 제시 순서와 무관하게 같은 쌍은 같은 키다."""

    left: str
    right: str
    winner: Side | None
    recorded_at: str
    mode: str = "random"
    """`random`은 고정 평가 집합용, `adaptive`는 학습용이다. 섞이면 안 된다."""

    def __post_init__(self) -> None:
        if self.left == self.right:
            raise ValueError("같은 곡끼리 비교할 수 없다")
        if self.left > self.right:
            raise ValueError("정규 순서(left <= right)로 저장해야 한다")

    @property
    def skipped(self) -> bool:
        return self.winner is None

    @property
    def preferred(self) -> str | None:
        if self.winner is None:
            return None
        return self.left if self.winner is Side.LEFT else self.right

    def as_record(self) -> dict[str, object]:
        return {
            "left": self.left,
            "right": self.right,
            "winner": None if self.winner is None else self.winner.value,
            "recorded_at": self.recorded_at,
            "mode": self.mode,
        }
