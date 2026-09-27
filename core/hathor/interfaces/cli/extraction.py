"""추출 배치를 돌리는 공용 루프 (D-0250).

**`main.py`에 있었다.** MERT · MFCC · 레이어 경로가 같은 루프를 쓰는데 그 루프가
2900줄짜리 파일 안에 있어 §3의 빚(«`main.py`의 `eval` 보고»)을 키우고 있었다.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hathor.application.extract_features import ExtractFeatures, ExtractLayerFeatures
    from hathor.domain.entities.scanned_track import ScannedTrack
    from hathor.infrastructure.npz_feature_store import NpzFeatureStore


def drive_extraction(
    use_case: ExtractFeatures | ExtractLayerFeatures,
    store: NpzFeatureStore,
    tracks: list[ScannedTrack],
    *,
    seconds_per_track: float,
) -> int:
    """추출을 돌리며 곡 단위로 저장하고 요약을 남긴다.

    MERT 경로와 MFCC 베이스라인 경로가 같은 루프를 쓴다. 진행 출력·실패
    처리·요약 형식이 갈라지면 두 산출물을 나란히 놓고 비교할 수 없다.
    """
    print(f"대상 {len(tracks)}곡, 예상 {len(tracks) * seconds_per_track / 60:.1f}분", flush=True)

    started = time.monotonic()
    for index, features in enumerate(use_case.run(tracks), 1):
        store.write_track(features)
        elapsed = time.monotonic() - started
        print(
            f"  {index:>4}/{len(tracks)} {features.chunk_count:>3}청크 "
            f"{elapsed / index:5.1f}초/곡 {features.source_key}",
            flush=True,
        )

    summary_path = store.write_summary(
        {
            "processed": use_case.processed,
            "failed": len(use_case.failed),
            "failures": [{"source_key": key, "reason": reason} for key, reason in use_case.failed],
        }
    )
    print()
    print(f"성공 {use_case.processed}곡, 실패 {len(use_case.failed)}곡")
    for key, reason in use_case.failed:
        print(f"  실패 {key}: {reason}", file=sys.stderr)
    print(f"요약: {summary_path}")
    return 0
