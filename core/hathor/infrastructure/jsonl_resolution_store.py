"""정규 신원 확정 산출물 JSONL 기록.

JsonlScanStore와 대칭이다. 조회에 20분이 걸리므로 결과를 남기지 않으면
후속 단계가 매번 재실행해야 한다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from hathor.application.resolution_summary import ResolutionSummary
    from hathor.application.resolve_identities import ResolutionRecord

from hathor.domain.entities.resolved_identity import ResolutionState

RESOLUTION_SUFFIX = ".resolve.jsonl"
RESOLUTION_SUMMARY_SUFFIX = ".resolve.summary.json"


def resolution_as_record(record: ResolutionRecord) -> dict[str, object]:
    """키 순서를 고정한다. 2대 노트북 산출물이 바이트 단위로 같아야 한다 (D-0009).

    queried_artist·queried_title을 남기는 이유는 실패 분석이다. 무엇으로
    조회했는지가 없으면 원인을 알 수 없다. 실측에서 '효린 -> Hyolyn'
    치환 문제를 찾은 것도 이 정보 덕이었다.
    """
    recording = record.recording
    return {
        "source_key": recording.source_key,
        "state": recording.state.value,
        "identity": recording.identity,
        "recording_mbid": recording.recording_mbid,
        "canonical_title": recording.canonical_title,
        "fallback_key": recording.fallback_key,
        "queried_artist": record.queried_artist,
        "queried_title": record.queried_title,
    }


class JsonlResolutionStore:
    """확정 결과를 JSONL로 기록하고 다시 읽는다.

    스트리밍으로 기록한다. 20분짜리 작업이므로 중간에 끊겨도 그때까지의
    결과가 파일에 남아야 한다.
    """

    def __init__(self, output_root: Path) -> None:
        self._root = output_root

    def write(self, records: Iterable[ResolutionRecord], summary: ResolutionSummary) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        tracks_path = self._root / f"resolve-{stamp}{RESOLUTION_SUFFIX}"
        with tracks_path.open("w", encoding="utf-8") as stream:
            for record in records:
                line = json.dumps(resolution_as_record(record), ensure_ascii=False)
                stream.write(line + "\n")
                stream.flush()

        summary_path = self._root / f"resolve-{stamp}{RESOLUTION_SUMMARY_SUFFIX}"
        payload = {
            "total": summary.total,
            "counts": {state.value: summary.count_of(state) for state in ResolutionState},
            "ratios": {state.value: round(summary.ratio_of(state), 4) for state in ResolutionState},
        }
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return summary_path

    def read_records(self) -> Iterator[dict[str, object]]:
        """최신 산출물을 순차 방출한다. 후속 단계의 입력이다."""
        paths = sorted(self._root.glob(f"*{RESOLUTION_SUFFIX}"))
        if not paths:
            return
        with paths[-1].open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield dict(json.loads(line))
