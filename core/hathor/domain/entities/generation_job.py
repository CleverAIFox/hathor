"""생성 잡 엔티티."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Stage(StrEnum):
    """파이프라인 단계. 부분 재생성의 단위이기도 하다."""

    STRUCTURE = "structure"
    HARMONY = "harmony"
    MELODY = "melody"
    LYRICS = "lyrics"
    ARRANGE = "arrange"
    VOCAL = "vocal"
    SCORE = "score"
    ARTWORK = "artwork"


@dataclass(slots=True)
class GenerationJob:
    """생성 요청 1건. 시드는 반드시 확정 저장한다 (GR-6.5)."""

    seed: int
    stages: tuple[Stage, ...]
    job_id: UUID = field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("최소 1개 단계가 필요하다")
        if self.seed < 0:
            raise ValueError("시드는 음수일 수 없다")

    def mark_running(self) -> None:
        if self.status is not JobStatus.PENDING:
            raise ValueError(f"{self.status}에서 running으로 전이할 수 없다")
        self.status = JobStatus.RUNNING

    def mark_succeeded(self) -> None:
        if self.status is not JobStatus.RUNNING:
            raise ValueError(f"{self.status}에서 succeeded로 전이할 수 없다")
        self.status = JobStatus.SUCCEEDED

    def mark_failed(self) -> None:
        self.status = JobStatus.FAILED
