"""화성 진행 값 객체."""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.value_objects.key import Key


@dataclass(frozen=True, slots=True)
class ChordProgression:
    """로마숫자 도수 표기 화성 진행. 조성과 함께 의미를 가진다."""

    key: Key
    degrees: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.degrees:
            raise ValueError("화성 진행은 최소 1개 화음이 필요하다")

    @property
    def length(self) -> int:
        return len(self.degrees)

    def transposed(self, key: Key) -> ChordProgression:
        """도수 표기이므로 조성만 교체하면 이조가 끝난다."""
        return ChordProgression(key=key, degrees=self.degrees)
