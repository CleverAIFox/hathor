"""저장소 경로와 기기별 설정. **경로를 손으로 치지 않기 위한 것이다** (D-0066).

### 무엇을 없애려는가

두 기기(광인사·리전)를 오가며 개발한다. 저장소 위치, 음원 드라이브, 패치 받는 폴더가
기기마다 다르고, 그것을 **매번 셸에 다시 쳤다.** 실제로 잃은 것들이다.

- `cd core`를 잊어 `git add`가 `core/core/...`를 찾았다
- `export HATHOR_LIBRARY_ROOT`를 셸마다 다시 쳤고 한 번은 `/mnt/d/노래`로 잘못 잡았다
- `.env`에 음원 경로를 적었는데 **CLI가 `.env`를 읽지 않아** 아무 일도 없었다
- 리전 저장소가 어디인지 몰라 `find`를 돌렸다

### 규약

**저장소는 양쪽 기기에서 `~/projects/hathor`다.** 이것은 상대 경로가 아니라 약속이다. 드라이브
문자가 다른 것(리전 `/mnt/f`, 광인사 `/mnt/d`)은 상대 경로로 표현할 수 없으므로
`.env`가 진다 (D-0009).

**기기마다 다른 값은 `.env` 하나에만 적는다.** 셸에 치지 않는다. `.env`는 커밋하지
않는다 (§5.5).

**상대 경로는 저장소 루트 기준으로 푼다.** `var/ingest`는 어느 디렉터리에서 실행하든
같은 곳을 가리킨다. 이전에는 현재 디렉터리 기준이라 `core/`에서 돌리면
`core/var/ingest`에, 루트에서 돌리면 `var/ingest`에 쌓였다.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

DOTENV_NAME = ".env"
REPO_MARKERS = ("CONTRIBUTING.md", "core", "docs")

LIBRARY_ROOT_ENV = "HATHOR_LIBRARY_ROOT"
PATCH_DIR_ENV = "HATHOR_PATCH_DIR"
ARTIFACT_STORE_ENV = "HATHOR_ARTIFACT_STORE"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """저장소 루트. **현재 디렉터리와 무관하다.**

    모듈 파일 위치에서 올라가며 표식을 찾는다. 개발 설치(`uv sync`)에서는 실제
    저장소를 가리킨다. 못 찾으면 현재 디렉터리에서 올라가며 다시 찾는다.
    """
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / marker).exists() for marker in REPO_MARKERS):
            return candidate
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if all((candidate / marker).exists() for marker in REPO_MARKERS):
            return candidate
    raise RuntimeError(f"저장소 루트를 찾지 못했다. 표식: {REPO_MARKERS}")


def parse_dotenv(text: str) -> dict[str, str]:
    """`KEY=VALUE` 줄을 읽는다. 주석과 빈 줄은 건너뛴다.

    의존성을 쓰지 않는다. `pydantic-settings`는 `api` 추가 의존성에만 있어
    `uv sync --dev`만 한 기기에서는 없다 — 그 기기가 광인사다.
    """
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """`.env`를 읽어 환경변수에 넣는다. **이미 있는 값은 덮지 않는다.**

    셸에서 명시로 준 값이 파일보다 우선해야 한다. 한 번만 다르게 돌려 보는 일이
    잦은데, 그때 파일을 고쳤다가 되돌리는 것을 잊으면 다음 실행이 조용히 틀린다.

    파일이 없으면 아무 일도 하지 않는다. `.env`는 커밋하지 않으므로 새 클론에는
    없는 것이 정상이다.
    """
    target = path if path is not None else repo_root() / DOTENV_NAME
    if not target.exists():
        return {}
    values = parse_dotenv(target.read_text(encoding="utf-8"))
    applied = {key: value for key, value in values.items() if key not in os.environ}
    os.environ.update(applied)
    return applied


PATH_ARGUMENT_HINTS = (
    "out",
    "replay",
    "midi",
    "path",
    "root",
    "dir",
    "file",
    "index",
    "store",
    "features",
    "profile",
    # `generate --priors`는 경로인데 이 목록에 없어 검사를 안 받고 있었다. 맞게
    # 짜여 있었으나 **기계가 보고 있지 않았다** — D-0069가 막으려던 부류가 그대로
    # 남아 있던 자리다. 규율이 아니라 검사가 지켜야 한다 (GR-0.9).
    "prior",
)
"""CLI 인자 이름이 이 중 하나를 담으면 **경로로 취급한다** (D-0069).

이름 기반이라 완벽하지 않다. `--profile`처럼 경로가 아닌 것도 걸리므로 검사 쪽에서
예외로 뺀다. **놓치는 것보다 과하게 잡는 편이 낫다** — 놓치면 쓰는 곳과 읽는 곳이
갈리고, 그것이 실제로 터졌다.
"""


def repo_path_hints() -> tuple[str, ...]:
    """경로 인자 판별에 쓰는 이름 조각. 검사에서 쓴다."""
    return PATH_ARGUMENT_HINTS


def resolve_path(value: str | Path) -> Path:
    """상대 경로를 **저장소 루트 기준**으로 푼다. 절대 경로는 그대로 둔다.

    `~`도 편다. 현재 디렉터리는 쓰지 않는다 — `cd core`를 했는지 안 했는지에 따라
    산출물이 다른 곳에 쌓이는 것이 사고의 근원이었다.
    """
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_root() / path


def library_root() -> Path | None:
    """음원 라이브러리 루트. `.env`나 셸에 없으면 `None`이다."""
    value = os.environ.get(LIBRARY_ROOT_ENV)
    return Path(value).expanduser() if value else None


def patch_dir() -> Path | None:
    """패치를 받아 두는 폴더. 보통 윈도우 다운로드다."""
    value = os.environ.get(PATCH_DIR_ENV)
    return Path(value).expanduser() if value else None


def artifact_store() -> Path | None:
    """산출물 교두보. 외장 SSD의 마운트 지점이다 (D-0118).

    **`var/`는 커밋하지 않으므로 기기 간 이동 경로가 여기뿐이다.** 없으면 `None`이고
    그때는 산출물을 다시 뽑는 수밖에 없다.
    """
    value = os.environ.get(ARTIFACT_STORE_ENV)
    return Path(value).expanduser() if value else None


def artifact_store_files() -> int | None:
    """교두보에 있는 산출물 파일 수. **안 붙었으면 `None`이다** (D-0118).

    경로 미설정과 구분하지 않는다 — 부르는 쪽이 `artifact_store()`로 이미 안다.
    """
    root = artifact_store()
    if root is None:
        return None
    ingest = root / "var" / "ingest"
    if not ingest.is_dir():
        return None
    return sum(1 for path in ingest.rglob("*") if path.is_file())


# --------------------------------------------------------------- 기기 탐지 (D-0068)

AUDIO_SUFFIXES = frozenset({".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".wma"})
SKIP_DIR_NAMES = frozenset(
    {
        "$RECYCLE.BIN",
        "System Volume Information",
        "Windows",
        "Program Files",
        "Program Files (x86)",
        "ProgramData",
        "AppData",
        "node_modules",
        ".git",
        "$WinREAgent",
        "Recovery",
    }
)
MIN_LIBRARY_TRACKS = 50
"""음원 폴더로 인정할 최소 파일 수. 앨범 하나 정도는 라이브러리가 아니다."""

WINDOWS_USERS_ROOT = Path("/mnt/c/Users")
SKIP_WINDOWS_USERS = frozenset({"Public", "Default", "Default User", "All Users", "desktop.ini"})


def windows_user_dir() -> Path | None:
    """윈도우 사용자 폴더를 찾는다. **기기마다 이름이 다르다** (광인사 foxlo, 리전 Fox).

    `Downloads`가 있는 것만 후보로 보고, 여럿이면 가장 최근에 쓴 것을 고른다.
    """
    if not WINDOWS_USERS_ROOT.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    try:
        entries = list(WINDOWS_USERS_ROOT.iterdir())
    except OSError:
        return None
    for entry in entries:
        if entry.name in SKIP_WINDOWS_USERS or not entry.is_dir():
            continue
        downloads = entry / "Downloads"
        try:
            if downloads.is_dir():
                candidates.append((downloads.stat().st_mtime, entry))
        except OSError:
            continue
    if not candidates:
        return None
    return max(candidates)[1]


def _count_audio(directory: Path, depth: int, budget: int) -> tuple[int, int]:
    """디렉터리 바로 아래 음원 수와, 하위를 포함한 수를 센다. 예산을 넘기면 멈춘다."""
    import os

    here = 0
    total = 0
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return 0, 0
    for entry in entries:
        if total >= budget:
            break
        try:
            if entry.is_file() and Path(entry.name).suffix.lower() in AUDIO_SUFFIXES:
                here += 1
                total += 1
            elif entry.is_dir() and depth > 0 and entry.name not in SKIP_DIR_NAMES:
                _, below = _count_audio(Path(entry.path), depth - 1, budget - total)
                total += below
        except OSError:
            continue
    return here, total


def find_library_candidates(
    max_depth: int = 4, mount_root: Path | None = None
) -> list[tuple[Path, int]]:
    """마운트된 드라이브에서 음원 폴더 후보를 찾는다. 많은 순으로 낸다.

    **바로 아래에 음원이 가장 많은 폴더**를 고른다. 상위 폴더는 하위를 합쳐 더 큰
    수를 갖지만 그것은 라이브러리 루트가 아니다 — 리전 `/mnt/d/노래`는 안쪽에
    `노래`가 한 겹 더 있었고, 그 한 겹을 놓쳐 실제로 잘못 잡았다.
    """
    import os

    found: dict[Path, int] = {}

    def walk(directory: Path, depth: int) -> None:
        here, _ = _count_audio(directory, 0, MIN_LIBRARY_TRACKS * 40)
        if here >= MIN_LIBRARY_TRACKS:
            found[directory] = here
        if depth <= 0:
            return
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        for entry in entries:
            try:
                if entry.is_dir() and entry.name not in SKIP_DIR_NAMES:
                    walk(Path(entry.path), depth - 1)
            except OSError:
                continue

    mounts = mount_root if mount_root is not None else Path("/mnt")
    if not mounts.is_dir():
        return []
    for drive in sorted(mounts.iterdir()):
        # C는 시스템 드라이브라 건너뛴다. wsl·wslg는 마운트 지점이다.
        if not drive.is_dir() or drive.name in {"c", "wsl", "wslg"}:
            continue
        walk(drive, max_depth)
    return sorted(found.items(), key=lambda item: -item[1])
