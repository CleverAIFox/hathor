"""CLI가 공유하는 경로 기본값과 라이브러리 루트 해결 (D-0260).

**`main.py`에 있었다.** `eval` 계열을 떼어내려 하니 여섯 명령이 전부 이것을 보고 있어
순환이 생겼다 — 떼어낼 것이 남을 것을 보면 못 뗀다. 공유하는 것을 먼저 공유하는 자리로
옮긴다.
"""

from __future__ import annotations

from pathlib import Path

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
DEFAULT_LAYERS_DIRNAME = "mert-layers"


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
