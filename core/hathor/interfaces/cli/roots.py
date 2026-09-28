"""CLI가 공유하는 기본값과 라이브러리 루트 해결 (D-0260 · D-0273).

**`main.py`에 있었다.** `eval` 계열을 떼어내려 하니 여섯 명령이 전부 이것을 보고 있어
순환이 생겼다 — 떼어낼 것이 남을 것을 보면 못 뗀다. 공유하는 것을 먼저 공유하는 자리로
옮긴다.

D-0273이 `eval` 파서를 러너 옆으로 옮길 때 같은 자리에 또 걸렸다. 파서가 쓰는 기본값
다섯이 `main.py`에 있었고, 옮긴 모듈에서 그것을 부르면 `main.py`를 다시 들여야 해서
**순환이 된다.** 그래서 경로가 아닌 기본값도 여기 둔다 — 이 파일은 «경로»가 아니라
«CLI가 공유하는 것»의 자리다.
"""

from __future__ import annotations

from pathlib import Path

from hathor.infrastructure.track_bundle_store import BUNDLE_DIRNAME
from hathor.shared.config.paths import LIBRARY_ROOT_ENV

DEFAULT_LIBRARY_ROOT_ENV = LIBRARY_ROOT_ENV
"""`--root`를 안 줬을 때 볼 환경변수. **정본은 `paths`에 있다** (D-0199).

처음에 여기 `"HATHOR_LIBRARY_ROOT"`를 손으로 적었다가 `ruff`가 잡았다 — 글자를 두 곳에
두면 한쪽만 고쳐진다. 이 저장소가 되풀이해 맞은 그 부류다."""

DEFAULT_OUTPUT_ROOT = "var/ingest"
"""산출물 기본 위치. **문자열이어야 한다** (D-0069).

argparse는 기본값이 문자열일 때만 `type`을 적용한다. `Path("var/ingest")`로 두면
`type=resolve_path`를 붙여도 기본값에는 안 걸려 현재 디렉터리 기준으로 남는다.
`--out`을 명시했을 때와 안 했을 때가 다른 곳을 가리키게 된다.
"""
DEFAULT_MFCC_DIRNAME = "baseline-mfcc"
"""`eval mfcc`가 **쓰는** 자리."""

DEFAULT_LAYERS_DIRNAME = "mert-layers"
"""`eval layers`가 **쓰는** 자리. **읽는 기본값이 아니다** (D-0274).

D-0203이 산출물을 묶음으로 옮긴 뒤에도 읽는 쪽 넷이 이 이름을 기본값으로 쓰고 있었고,
`--audit`은 이 계열을 **어디에도 없다**고 판정했다 (O-69 닫힘 D-0274). 한 이름이 «쓰는 자리»와 «읽는
기본값» 두 뜻을 겸하고 있었던 것이 원인이다 — D-0263이 `ship.py`의 `GREEN`에서 잡은 것과
같은 부류이고, 그쪽은 한 함수 안이었고 이쪽은 파일 넷에 걸쳐 있었다."""

DEFAULT_FEATURE_DIRNAME = BUNDLE_DIRNAME
"""**읽는 기본값.** `--features`를 안 주면 여는 자리다 (O-69 닫힘 · D-0274).

정본은 `track_bundle_store.BUNDLE_DIRNAME`이다 — 글자를 두 곳에 두면 한쪽만 고쳐진다.
`open_feature_source`가 모양을 보고 읽는 쪽을 고르므로(D-0233) 여기 묶음을 걸어도 옛
인덱스 저장소를 `--features`로 주는 길은 그대로 산다."""

DEFAULT_LAYERS = "0,1,2,6"
"""D-0026 실측 후 기본값. layer00이 최선이었고 1·2는 미탐색이다 (O-9).

**이 문서 문자열은 `main.py`에서 아무것도 설명하지 못하고 있었다** (D-0273). 두 상수
아래가 아니라 그 뒤 `_DETERMINISM_PROBE` 뒤에 둘이 나란히 떠 있었다 — 파이썬에서 그것은
그냥 버려지는 문자열이고 `deadcheck`도 그 부류를 안 본다. 내용으로 짝을 다시 지었다:
«어느 레이어를 뽑나»는 이쪽이고 «무엇으로 검색하나»는 아래다."""

DEFAULT_SEARCH_KEY = "layer00"
"""D-0027 정본 뷰."""

DEFAULT_OUTPUT_SEEDS = 1000
DEFAULT_OUTPUT_BARS = 8
DEFAULT_OUTPUT_PAIRS = 100
"""O-29 표본. **8마디 하나는 표본이 아니다** (D-0078).

100쌍 곱하기 1000시드가 CPU로 약 16초다. D-0078에 "수 초"라고 적었으나 실측은 그보다
느리다 — 음원도 GPU도 안 쓰는 것은 맞다.
"""


def resolve_root(raw: Path | None) -> Path:
    """라이브러리 루트를 결정한다.

    노트북마다 드라이브 문자가 다르므로(리전 /mnt/f, 광인사 /mnt/d)
    경로를 코드에 하드코딩하지 않고 환경변수로 외부화한다(D-0009).
    """
    if raw is not None:
        return raw
    from os import environ

    value = environ.get(DEFAULT_LIBRARY_ROOT_ENV)
    if not value:
        raise SystemExit(f"--root를 지정하거나 {DEFAULT_LIBRARY_ROOT_ENV} 환경변수를 설정해야 한다")
    return Path(value)
