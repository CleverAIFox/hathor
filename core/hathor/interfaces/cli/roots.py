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

from hathor.application.evaluate_harmony_output import DEFAULT_PAIR_COUNT
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
DEFAULT_OUTPUT_PAIRS = DEFAULT_PAIR_COUNT
"""O-29 표본. **8마디 하나는 표본이 아니다** (D-0078).

**같은 수가 두 곳에 있었다** (D-0453). 여기와 `evaluate_harmony_output`이 각각 100을
들었고, 쌍 수를 올릴 때 한 곳만 고치면 **화면과 기본값이 갈린다** — 시드가 여덟 곳에
박혀 판정을 뒤집은 것과 같은 부류다 (D-0043 · D-0450).
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


def missing_given_path(given: Path, flag: str) -> None:
    """**준 경로에 파일이 없다**고 적는다. 그 문구는 여기 하나다 (D-0043 · D-0429).

    D-0326이 `--priors`에 이 메시지를 달았고, **`generate`는 그 길을 안 탔다.**
    같은 것을 또 만들 뻔했다 — 새 `argparse` 타입을 하나 짜 놓고 보니 D-0326의
    시험이 빨개졌다. **이미 푼 문제를 103판 뒤에 다시 풀고 있었다.**
    """
    import sys

    from hathor.shared.config.paths import repo_root

    print(
        f"{flag}로 준 경로에 파일이 없다: {given}\n"
        "  **상대 경로는 저장소 루트 기준이다** (cwd 아님) —"
        f" 지금 루트는 {repo_root()}이다.",
        file=sys.stderr,
    )


def announce_series(chosen: Path, stem_set: str) -> None:
    """고른 시계열 폴더와 곡 수를 적는다. **더 큰 후보가 있으면 그것도 말한다** (D-0435).

    40곡짜리가 1004곡짜리를 가렸는데 화면에는 *«곡 40»*만 떴다. **그 수가 적다는 것을
    말해 주는 자가 없었다** — 사람이 1004를 기대하고 40을 읽으면 못 알아챈다 (D-0325).

    **고르는 규칙은 안 바꾼다** (`series_candidates` 참고). 여기서 하는 일은 적는 것뿐이다.
    """
    import sys

    from hathor.infrastructure.chroma_series_store import series_candidates
    from hathor.shared.config.paths import repo_root

    songs = len(list(chosen.glob(f"*-{stem_set}.npz")))
    print(f"시계열 {chosen.name} · {stem_set} {songs}곡")
    for path, count in series_candidates(repo_root(), stem_set):
        if count <= songs or path == chosen:
            continue
        where = path.relative_to(repo_root()) if path.is_relative_to(repo_root()) else path
        print(
            f"  **더 큰 폴더가 있다**: {path.name} · {count}곡 — 쓰려면 --series {where}",
            file=sys.stderr,
        )


def resolve_priors(given: Path | None, stem_set: str) -> Path | None:
    """`--priors`를 풀고 **못 찾으면 왜 못 찾았는지 적는다** (D-0326).

    ### 같은 블록이 넷이었다

    `eval harmony-prior` · `eval time-drift` · `eval chromatic-origin` ·
    `eval harmony-output`이 **네 번 복사된 다섯 줄**을 들고 있었고, 넷 다 «찾지 못했다»만
    찍었다. 하나로 모은다 — 넷이면 한 곳만 고쳐지는 날이 온다 (D-0317 · D-0323 · D-0325).

    ### 준 경로가 없으면 **푼 경로**를 찍는다

    `resolve_path`는 상대 경로를 **저장소 루트 기준**으로 푼다 (cwd 아님). `cd core`에서
    `--priors ../var/ingest/...`를 주면 **저장소 밖**을 가리키고, 예전 메시지는 *"--priors로
    경로를 준다"*였다 — **이미 준 사람에게 주라고 했다.**

    실제로 그렇게 났다 (D-0326). 화면에 푼 절대 경로가 있었으면 한눈에 보였다.
    """
    import sys

    from hathor.infrastructure.keys_jsonl_store import find_keys_store
    from hathor.shared.config.paths import repo_root

    if given is not None:
        if given.exists():
            return given
        missing_given_path(given, "--priors")
        return None
    found = find_keys_store(repo_root(), stem_set)
    if found is None:
        print(
            "사전 산출물이 없다. `ingest keys --separate`로 먼저 뽑거나 --priors로 경로를 준다.",
            file=sys.stderr,
        )
    return found
