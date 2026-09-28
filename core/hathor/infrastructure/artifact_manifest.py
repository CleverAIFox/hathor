"""산출물이 **자기를 설명하는** 한 장 (D-0203 · D-0294 · D-0295).

### 왜 따로 나왔나

`NpzFeatureStore.write_manifest`가 이 일을 하고 있었다. 그런데 manifest가 필요한 산출물이
npz만이 아니다 — 온셋 포락선 878MB와 크로마 시계열 37MB는 **다른 저장소**라 그 메서드에
닿지 못했고, 그래서 위생 출력에서 «정체 불명»으로 남았다.

**저장소마다 같은 코드를 또 쓰지 않는다** (D-0272 — *"같은 일을 하는 코드는 벌 수보다
꼴 가짓수가 위험하다"*). 쓰는 자리를 하나로 두고 저장소들이 불러 쓴다.

### 무엇이 들어가나

`revision`은 **만든 커밋**이다. *"코드가 바뀌면 산출물도 다른 것이다."*
그 한 칸이 「재현 불명」을 막는 최소 장치이고, 파이어레인 `shardseal`의 `seal.code`에
해당한다 — 우리는 봉인 넷을 들지 않고 **이 하나만** 든다 (D-0294).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

SUFFIX = ".manifest.json"
"""`var_fsck`가 찾는 이름. **`tools/var_fsck.MANIFEST_SUFFIX`와 같은 값이다.**"""


def write(root: Path, name: str, manifest: dict[str, object]) -> Path:
    """`<root>/<name>.manifest.json`을 쓴다. **덮어쓴다** — 저장소 하나에 한 장이다.

    같은 배치가 같은 설정으로 전 곡을 뽑으므로 곡마다 쓸 것이 아니다. 실행별 기록은
    `write_summary`가 따로 남긴다.
    """
    from hathor.infrastructure.track_bundle_store import repo_revision

    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}{SUFFIX}"
    written = {
        **manifest,
        "revision": repo_revision(),
        "written_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(
        json.dumps(written, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
