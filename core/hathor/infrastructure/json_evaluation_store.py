"""평가 리포트 기록. 실행마다 새 파일을 남기고 덮어쓰지 않는다.

지표는 조건을 바꿔가며 여러 번 재는 것이 목적이다. 덮어쓰면 "혼합 단독이
0.41이었고 스템 concat이 0.44였다"는 비교 자체가 불가능해진다. 파일명에
라벨과 시각을 넣고 내용에는 시각을 넣지 않는다(D-0009).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIRNAME = "eval"
REPORT_SUFFIX = ".eval.json"
SAFE_LABEL = re.compile(r"[^0-9A-Za-z._-]+")


def safe_label(label: str) -> str:
    """파일명에 쓸 수 있는 형태로 줄인다. 빈 문자열이면 기본값을 쓴다."""
    cleaned = SAFE_LABEL.sub("-", label).strip("-")
    return cleaned or "unnamed"


class JsonEvaluationStore:
    def __init__(self, output_root: Path) -> None:
        self._root = output_root / EVAL_DIRNAME

    @property
    def root(self) -> Path:
        return self._root

    def write(self, record: dict[str, object], label: str) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self._root / f"{stamp}-{safe_label(label)}{REPORT_SUFFIX}"
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return path
