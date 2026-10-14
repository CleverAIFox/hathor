"""쌍대비교 응답 하나. 사용자가 만든 유일한 취향 라벨이다.

코퍼스는 전량 양성 사례이며 음성 사례가 0건이다(C-7). 절대 라벨을 물으면
"좋아하는 곡만 1004개 있는데 얼마나 좋아하냐"가 되어 눈금이 서지 않는다.
쌍대비교는 **상대 순위**만 물으므로 외부 데이터 없이 라벨을 만든다(D-0012).

`winner`가 None이면 건너뛴 문항이다. 지우지 않고 남긴다. 어떤 쌍을 판단하지
못했는지가 정보이며, 지우면 그 쌍이 다시 출제된다.
"""

from __future__ import annotations

from collections.abc import Iterable
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
    """`random`은 고정 평가 집합용, `adaptive`는 학습용, `repeat`은 **되물은 것**이다.

    섞이면 같은 쌍이 두 번 세어져 그 쌍의 가중치만 커진다 (D-0012).
    """

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


def agreement(comparisons: Iterable[PreferenceComparison]) -> tuple[int, int]:
    """`(두 번 이상 물은 쌍, 그중 답이 같았던 쌍)`.

    **판정자의 천장이다.** 같은 쌍을 다시 물었을 때 같은 답이 나오는 비율이
    어떤 모형도 못 넘는 선이다 — 사람이 60%로 흔들리면 모형의 70%는 과적합이고,
    사람이 90%면 70%는 아직 모자란 것이다. **천장 없이는 수치를 못 읽는다.**

    건너뛴 문항은 세지 않는다. 판단을 안 한 것은 일관성의 증거가 아니다.

    세 번 이상 물은 쌍은 **언제나 첫 답과 견준다.** 연달아 견주는 방식(A·B·A를
    «둘 다 틀림»으로 보는 것)도 성립하지만, **학습 집합에 들어가는 라벨이 첫 답이다** —
    모형이 맞혀야 하는 것이 그것이므로 천장도 그것을 기준으로 선다.
    """
    said: dict[tuple[str, str], str] = {}
    asked = matched = 0
    for comparison in comparisons:
        if comparison.preferred is None:
            continue
        key = (comparison.left, comparison.right)
        before = said.get(key)
        if before is None:
            said[key] = comparison.preferred
            continue
        asked += 1
        matched += int(before == comparison.preferred)
    return asked, matched
