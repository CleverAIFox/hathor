"""정규 신원 확정 결과 집계."""

from __future__ import annotations

from dataclasses import dataclass, field

from hathor.domain.entities.resolved_identity import ResolutionState


@dataclass(slots=True)
class ResolutionSummary:
    """상태별 건수를 누적한다.

    RESOLVED 비율은 실측 78.5%가 기준선이다 (D-0019). 크게 벗어나면
    조회 경로나 라이브러리 구성이 달라졌다는 신호다.
    AMBIGUOUS 비율은 미지의 표기 패턴이 유입됐는지 보는 지표다.
    """

    counts: dict[ResolutionState, int] = field(default_factory=dict)

    def observe(self, state: ResolutionState) -> None:
        self.counts[state] = self.counts.get(state, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def count_of(self, state: ResolutionState) -> int:
        return self.counts.get(state, 0)

    def ratio_of(self, state: ResolutionState) -> float:
        """전체 대비 비율. 관측이 없으면 0.0이다."""
        if not self.total:
            return 0.0
        return self.count_of(state) / self.total
