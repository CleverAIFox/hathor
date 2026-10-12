"""템포를 어디서 가져오나 (D-0392 · O-46).

`main.py`가 1256줄 못을 넘어 떼어 왔다 (D-0257). `feature_sources.py`와 같은 부류다 —
**입구가 산출물을 찾아 읽는 일**이고, 그래서 `application`이 아니라 여기다
(계약: 애플리케이션은 구현체를 모른다).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from hathor.domain.services.midi_writer import DEFAULT_TEMPO_BPM

if TYPE_CHECKING:
    import argparse


def resolve_tempo(args: argparse.Namespace, source_keys: list[str]) -> tuple[int, str]:
    """템포를 고른다 — O-46의 남은 절반 (D-0392).

    **`--tempo`의 기본값이 `None`인 것이 이 함수의 전제다.** `DEFAULT_TEMPO_BPM`을
    박아 두면 *«사람이 줬다»*와 *«안 줬다»*가 안 갈려 참조곡을 볼 자리가 없다 —
    그것이 이 판 전까지의 상태였다.

    차례는 **사람 → 참조곡 → 코퍼스 중앙**이다. 사람이 `--tempo`를 주면 그대로 쓰고,
    안 주면 참조곡의 **온셋 포락선 산출물**(`keys-*.onsets` · 믹스)에서 뽑고, 그것도
    못 읽으면 `DEFAULT_TEMPO_BPM`으로 떨어진다. **어디서 왔는지는 산출물이 말한다**
    (D-0269).
    """
    from hathor.application.reference_tempo import from_envelopes
    from hathor.infrastructure.onset_store import find_envelope_root, load_envelope
    from hathor.shared.config.paths import repo_root as _root

    if args.tempo is not None:
        return args.tempo, "사람이 줬다"
    root = find_envelope_root(_root())
    if root is None:
        return DEFAULT_TEMPO_BPM, "기본값 — 온셋 산출물이 없다"
    found = [one for key in source_keys if (one := load_envelope(root, key)) is not None]
    if not found:
        print("참조곡이 온셋 저장분에 없다. 코퍼스 중앙 템포를 쓴다.", file=sys.stderr)
        return DEFAULT_TEMPO_BPM, f"기본값 — 참조 {len(source_keys)}곡이 저장분에 없다"
    # **물어본 수를 넘긴다** (D-0396). 위에서 저장분에 없는 곡을 걸러 냈으므로, 안
    # 넘기면 판정이 「2/2」라 적고 **셋을 물어 둘을 읽은 것이 안 보인다** (GR-0.5).
    verdict = from_envelopes(found, asked=len(source_keys))
    if verdict.bpm is None:
        return DEFAULT_TEMPO_BPM, verdict.source
    return verdict.bpm, verdict.source
