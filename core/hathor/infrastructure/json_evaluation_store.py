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
        self.describe()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self._root / f"{stamp}-{safe_label(label)}{REPORT_SUFFIX}"
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return path

    def describe(self) -> Path:
        """이 폴더가 무엇인지 적는다 (D-0295).

        **다른 계열과 다르다** — 여기는 특징이 아니라 **평가 리포트와 실행 기록**이고,
        결정 기록의 `재현` 절이 가리키는 자리다 (D-0250). 층도 차원도 없지만 «정체 불명»은
        아니어야 한다. 실행마다 덮어써도 내용이 같으므로 값이 싸다.
        """
        from hathor.infrastructure import artifact_manifest

        return artifact_manifest.write(
            self._root,
            EVAL_DIRNAME,
            {
                "what": "평가 리포트와 실행 기록 — 결정 기록의 «재현»이 가리키는 자리 (D-0250)",
                "dtype": "json",
                "layers": [],
                "stems": [],
            },
        )
