"""쌍대비교 응답 저장. 추가 전용 JSONL이다.

**응답마다 즉시 쓰고 flush한다.** 세션 끝에 한 번에 쓰면 중간에 끊길 때
사람이 이미 들인 시간이 통째로 날아간다. 재추출은 GPU를 다시 돌리면 되지만
사람의 응답은 되돌릴 방법이 없다. 산출물 중 유일하게 재생성 불가능한 자산이다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from hathor.domain.entities.preference_comparison import PreferenceComparison, Side

TASTE_DIRNAME = "taste"
COMPARISONS_FILENAME = "comparisons.jsonl"


class JsonlPreferenceStore:
    def __init__(self, output_root: Path) -> None:
        self._root = output_root / TASTE_DIRNAME

    @property
    def path(self) -> Path:
        return self._root / COMPARISONS_FILENAME

    def append(self, comparison: PreferenceComparison) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(comparison.as_record(), ensure_ascii=False) + "\n")
            stream.flush()

    def read_all(self) -> Iterator[PreferenceComparison]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                winner = record["winner"]
                yield PreferenceComparison(
                    left=str(record["left"]),
                    right=str(record["right"]),
                    winner=None if winner is None else Side(winner),
                    recorded_at=str(record["recorded_at"]),
                    mode=str(record.get("mode", "random")),
                )

    def counts(self) -> dict[str, int]:
        """모드별 응답 수와 건너뛴 수. 수집이 얼마나 됐는지 한눈에 본다."""
        summary = {"total": 0, "answered": 0, "skipped": 0}
        for comparison in self.read_all():
            summary["total"] += 1
            summary["skipped" if comparison.skipped else "answered"] += 1
            key = f"mode:{comparison.mode}"
            summary[key] = summary.get(key, 0) + 1
        return summary
