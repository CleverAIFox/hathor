"""조성(調性) 값 객체."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PITCH_CLASSES: tuple[str, ...] = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)


class Mode(StrEnum):
    """선법. P0에서는 장·단조만 다룬다."""

    MAJOR = "major"
    MINOR = "minor"


@dataclass(frozen=True, slots=True)
class Key:
    """조성. 으뜸음 피치클래스와 선법으로 식별한다."""

    tonic: str
    mode: Mode

    def __post_init__(self) -> None:
        if self.tonic not in PITCH_CLASSES:
            raise ValueError(f"알 수 없는 으뜸음: {self.tonic}")

    @property
    def tonic_pitch_class(self) -> int:
        return PITCH_CLASSES.index(self.tonic)

    def __str__(self) -> str:
        return f"{self.tonic} {self.mode.value}"
