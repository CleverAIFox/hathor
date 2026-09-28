"""저장된 크로마로 조성을 **다시 판정한다** (D-0059 · D-0281).

### 왜 재판정이 따로 있나

디코딩이 곡당 수 초다. 프로파일·배음 실험마다 1004곡을 다시 디코드하면 실험 회전이 느려지고,
그것이 «지표를 만들어두고 보지 않게 되는» 원인이다 (D-0030). 크로마만 있으면 **음원도 GPU도
없는 기기에서** 알고리즘을 바꿔 볼 수 있다.

### 왜 여기 있나

`interfaces/cli/ingest_keys`에 있었다. 저장된 벡터를 정규화하고 다시 판정하는 것은 **계산**이고,
표시 계층이 `numpy`를 들이던 두 자리 중 하나였다 (GR-2.2 · D-0278의 래칫).

**`argparse`를 안 받는다.** 배음 강도와 프로파일만 받는다 — 응용이 CLI의 인자 꼴을 알면
그 순간 계층이 뒤집힌다. 이 저장소는 `domain`·`application`·`infrastructure` 어디에도
`argparse`가 없고(실측 0파일), 그 상태를 지킨다.
"""

from __future__ import annotations

import numpy as np

from hathor.domain.services.key_estimation import estimate_key, subtract_harmonics


def recompute(rows: list[dict[str, object]], *, strength: float, profile: str) -> int:
    """행의 `chroma`로 판정을 다시 쓴다. **다시 판정한 곡 수를 낸다.**

    크로마가 없는 행과 무게가 0인 행은 **그대로 둔다** — 기록된 판정이 남는다. 0으로 나누면
    `numpy`가 조용히 `nan`을 내고 그 `nan`이 분포 보고로 들어간다.
    """
    recomputed = 0
    for row in rows:
        saved = row.get("chroma")
        if saved is None:
            continue
        vector = subtract_harmonics(np.asarray(saved, dtype=np.float64), strength)
        total = float(vector.sum())
        if total <= 0:
            continue
        estimate = estimate_key(np.asarray(vector / total, dtype=np.float32), profile=profile)
        row.update(estimate.as_record())
        row["profile"] = profile
        recomputed += 1
    return recomputed
