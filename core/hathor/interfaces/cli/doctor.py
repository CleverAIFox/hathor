"""`doctor` — **기록된 규약과 지금 이 기기가 맞는지** 검사한다 (D-0067 · D-0128).

**`main.py`에서 내려왔다** (D-0128). D-0127이 `tables.py`를 내리자 나머지가 딸려
내려올 수 있게 됐고, `doctor`는 명령 중 가장 크면서 **다른 명령과 하나도 안 겹친다.**

### 훅을 본다 (D-0128)

`CONTRIBUTING` §5.5가 *"코드에 비밀정보 금지. `.env` + 환경 변수"*라 적었고 기기에는
`~/.githooks/{pre-commit,credential-check}`가 걸려 있다. **그런데 그 훅이 이 기기에
실제로 걸려 있는지 아무도 안 봤다** — 저장소 어디에도 `core.hooksPath`라는 글자가
없었다. **적혀 있고 안 돌면 없는 것이다** (GR-0.8).

경고만 하고 막지 않는다. 다른 훅 배치를 쓸 정당한 이유가 있을 수 있다.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hathor.domain.services.stem_sets import DEFAULT_STEM_SET
from hathor.infrastructure.keys_jsonl_store import find_keys_store
from hathor.infrastructure.track_bundle_store import BUNDLE_DIRNAME, TrackBundleStore
from hathor.shared.config.paths import (
    ARTIFACT_STORE_ENV,
    LIBRARY_ROOT_ENV,
    artifact_store,
    artifact_store_files,
    repo_root,
)

if TYPE_CHECKING:
    import argparse

CONVENTIONAL_REPO_SUFFIX = Path("projects/hathor")
"""저장소가 있어야 하는 자리 (D-0004)."""

HOOKS = ("pre-commit", "credential-check")
"""기기에 걸려 있어야 하는 훅. **`credential-check`가 `.env`와 푸시 사이에 선다.**"""


def _git(root: Path, *arguments: str) -> str | None:
    """git 한 줄. 실패하면 `None`이다."""
    import subprocess

    try:
        done = subprocess.run(
            ("git", *arguments), cwd=root, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _describe_keys(path: Path) -> str:
    """조성 산출물 한 줄 요약 (D-0073).

    **첫 행의 조건만 읽는다.** 한 파일은 한 번의 실행이므로 조건이 같다. 전량을
    읽으면 곡 수가 정확해지지만 `doctor`가 느려지고, 그러면 안 돌리게 된다.
    """
    import json

    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                break
            else:
                return "(비어 있다)"
    except (OSError, ValueError):
        return "(읽을 수 없다)"

    if "aggregate" not in row:
        return "(조건 미기록 — D-0073 이전 산출물)"
    marks = [str(row.get("aggregate"))]
    if row.get("window_seconds"):
        marks.append(f"{row['window_seconds']:g}초 창")
    if row.get("separated"):
        marks.append("분리")
    if row.get("halves"):
        marks.append("반쪽")
    if row.get("limit"):
        marks.append(f"{row['limit']}곡")
    if row.get("profile"):
        marks.append(str(row["profile"]))
    return " · ".join(marks)


def run_doctor(args: argparse.Namespace) -> int:
    """**기록된 규약과 지금 이 기기가 맞는지 검사한다** (D-0067).

    결정 기록이 예순 건을 넘었다. 아무도 매번 다시 읽지 않는다. D-0004가
    저장소 위치를 정해 두었는데 **그 사실을 모른 채 두 기기 모두 다른 곳에 클론했고,
    한 번은 윈도우 드라이브였다.** 규칙이 없어서가 아니라 확인하는 것이 없어서다.

    경고만 하고 막지 않는다. 다른 위치에 클론할 정당한 이유가 있을 수 있다.
    """
    import os
    import shutil

    from hathor.shared.config.paths import PATCH_DIR_ENV

    root = repo_root()
    problems: list[str] = []
    notes: list[str] = []

    def check(ok: bool, label: str, detail: str, hint: str = "") -> None:
        mark = "OK  " if ok else "!!  "
        print(f"{mark}{label:<14}{detail}")
        if not ok:
            (problems if hint else notes).append(f"{label}: {hint or detail}")
            if hint:
                print(f"    → {hint}")

    print("== 위치 규약 (D-0004) ==")
    on_windows_drive = str(root).startswith("/mnt/") and not str(root).startswith("/mnt/wsl")
    check(
        not on_windows_drive,
        "저장소",
        str(root),
        "윈도우 드라이브다. drvfs는 파일 입출력이 10~20배 느리다. ext4로 옮긴다"
        if on_windows_drive
        else "",
    )
    conventional = root.parts[-2:] == CONVENTIONAL_REPO_SUFFIX.parts
    check(
        conventional,
        "위치 규약",
        "규약대로다" if conventional else f"규약은 ~/{CONVENTIONAL_REPO_SUFFIX}다",
    )

    print("\n== 설치본 (D-0067) ==")
    import hathor

    installed = Path(hathor.__file__).resolve().parent.parent.parent
    same = installed == root
    check(
        same,
        "설치본",
        str(installed),
        "**다른 저장소를 실행하고 있다.** 고쳐도 결과가 안 바뀐다. `rm -rf core/.venv && make sync`"
        if not same
        else "",
    )

    print("\n== 설정 (D-0066) ==")
    dotenv = root / ".env"
    check(
        dotenv.exists(),
        ".env",
        str(dotenv),
        ".env.example을 복사한다" if not dotenv.exists() else "",
    )
    library = os.environ.get(LIBRARY_ROOT_ENV)
    if not library:
        check(False, "음원 루트", "미설정", f".env에 {LIBRARY_ROOT_ENV}를 적는다")
    else:
        exists = Path(library).exists()
        check(
            exists,
            "음원 루트",
            library,
            "경로가 없다. 드라이브 마운트를 확인한다" if not exists else "",
        )
    patches = os.environ.get(PATCH_DIR_ENV)
    check(
        bool(patches),
        "패치 폴더",
        patches or "미설정",
        f".env에 {PATCH_DIR_ENV}를 적는다" if not patches else "",
    )

    print("\n== 훅 (D-0128) ==")
    hooks_path = _git(root, "config", "--get", "core.hooksPath")
    check(
        bool(hooks_path),
        "hooksPath",
        hooks_path or "미설정",
        "훅이 안 걸려 있다. `git config --global core.hooksPath ~/.githooks`"
        if not hooks_path
        else "",
    )
    if hooks_path:
        folder = Path(hooks_path).expanduser()
        for name in HOOKS:
            hook = folder / name
            usable = hook.is_file() and os.access(hook, os.X_OK)
            check(
                usable,
                name,
                str(hook) if hook.exists() else "없다",
                "파일이 없거나 실행권한이 없다. 훅은 조용히 건너뛰어진다" if not usable else "",
            )

    print("\n== git ==")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git(root, "rev-parse", "--short", "HEAD")
    dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
    ahead = _git(root, "rev-list", "--count", "--left-right", "@{upstream}...HEAD")
    print(f"    브랜치        {branch or '?'} @ {head or '?'}")
    check(dirty == "", "작업 트리", "깨끗하다" if dirty == "" else "커밋되지 않은 변경이 있다")
    if ahead:
        behind, forward = [*ahead.split(), "0", "0"][:2]
        synced = behind == "0" and forward == "0"
        check(synced, "원격", "동기화됨" if synced else f"뒤 {behind} · 앞 {forward}")

    print("\n== 산출물 ==")
    ingest = root / "var" / "ingest"
    keys = sorted(ingest.glob("*.keys.jsonl")) if ingest.exists() else []
    scans = sorted(ingest.glob("scan-*.jsonl")) if ingest.exists() else []
    print(f"    {ingest}")
    print(f"    스캔 {len(scans)}건 · 조성 {len(keys)}건")
    for path in keys[-6:]:
        print(f"      {path.name}  {_describe_keys(path)}")
    store = find_keys_store(root, DEFAULT_STEM_SET)
    if store is None:
        print(f"    !! {DEFAULT_STEM_SET} 스템 사전이 없다. 생성이 전체 믹스로 물러난다 (D-0074)")
        # **가진 것부터 본다** (D-0211). 묶음에 크로마가 이미 있는데 교두보에서 밀기로
        # 한 것을 되돌리게 하거나 GPU 1시간 40분을 시키고 있었다.
        bundles = TrackBundleStore(ingest / BUNDLE_DIRNAME).counts()["done"]
        if bundles:
            print(
                f"       묶음 {bundles}곡이 있다: ingest keys --from-bundles  (음원·GPU 없이 수 분)"
            )
        else:
            print("       묶음이 없다: 리전에서 ingest all  (GPU · 약 13시간)")
    else:
        print(f"    {DEFAULT_STEM_SET} 스템 사전  {store.name}")
    store_root = artifact_store()
    if store_root is None:
        print(f"    !! 교두보 {ARTIFACT_STORE_ENV} 미설정. .env에 적는다 (D-0118)")
    else:
        found = artifact_store_files()
        state = f"{found}개" if found is not None else "!! 안 붙었다"
        print(f"    교두보  {store_root}  {state}")
    stale = root / "core" / "var"
    if stale.exists():
        check(False, "산출물 위치", str(stale), "루트로 옮긴다: mv core/var var (D-0066)")

    print("\n== 환경 프로파일 (D-0068) ==")
    import importlib.util

    def has(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    heavy = {"torch": has("torch"), "demucs": has("demucs"), "transformers": has("transformers")}
    profile = "리전형(--all-extras)" if heavy["torch"] else "광인사형(--dev)"
    print(f"    설치 프로파일  {profile}")
    for name, present in heavy.items():
        print(f"      {name:<14}{'있음' if present else '없음'}")
    cuda = None
    if heavy["torch"]:
        try:
            import torch

            cuda = torch.cuda.is_available()
        except Exception:
            cuda = None
    print(f"      CUDA          {'있음' if cuda else '없음' if cuda is False else '확인 불가'}")
    if not heavy["torch"]:
        notes.append("torch가 없어 ML 검사가 건너뛰어진다")
        print("    !! ML 검사가 건너뛰어진다. **여기서 초록이어도 리전에서 깨질 수 있다**")

    print("\n== 캐시 ==")
    total = 0
    for name in (".ruff_cache", ".mypy_cache", ".pytest_cache", ".import_linter_cache"):
        target = root / "core" / name
        if target.exists():
            size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
            total += size
    print(f"    {total / 1024 / 1024:.1f}MB   전부 내용 해시 기반이라 낡은 결과를 내지 않는다")
    print("    지우려면 make clean-all (var/과 .venv/는 남는다)")
    if shutil.which("git") is None:
        notes.append("git이 없다")

    print()
    if problems:
        print(f"\033[31m고칠 것 {len(problems)}건\033[0m")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("\033[32m규약과 맞다.\033[0m")
    return 0
