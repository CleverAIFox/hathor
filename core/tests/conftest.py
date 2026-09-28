"""테스트 픽스처. 실제 음원을 저장소에 커밋하지 않기 위해 합성 mp3를 생성한다."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from hathor.domain.entities.audio_stream import AudioStreamProperties
from hathor.domain.entities.scanned_track import ScannedTrack
from hathor.domain.entities.track_tags import TrackTags

pytest.importorskip("mutagen")

MACHINE_ENV_PREFIX = "HATHOR_"
TOOLS_CACHE = Path(__file__).resolve().parents[2] / "tools" / "__pycache__"


def pytest_configure(config: pytest.Config) -> None:
    """**도구의 낡은 바이트코드를 지운다** (D-0252).

    시험 열다섯 개가 `tools/*.py`를 경로로 로드한다. 그 로드가 `tools/__pycache__`를
    만들고, 파이썬은 `.pyc`의 유효성을 **mtime(초)과 크기**로만 본다 — 같은 초에 같은
    크기로 고치면 낡은 것이 그대로 쓰인다.

    **실측했다.** `SHARE = 0.6`을 `0.0`으로 고치고 되돌렸더니 파일에는 `0.6`이 적혀
    있는데 시험은 `0.0`을 보고 판정했다. «고쳤다»를 시험으로 확인하는 이 저장소의
    방식이 **그 순간 거짓말을 한다.**
    """
    shutil.rmtree(TOOLS_CACHE, ignore_errors=True)
    sys.dont_write_bytecode = True


GPU_GROUP = "gpu"
"""장비를 같이 쓰는 시험을 **한 워커로 모으는** 이름 (D-0290)."""

GPU_REASON = "CUDA"
"""건너뜀 사유에 이 글자가 있으면 그 시험은 **GPU를 잡는다.**

**파일 목록을 손으로 들지 않는다.** 목록은 낡고, 새 GPU 시험이 조용히 밖에 남는다.
이미 선언된 사유를 읽는다 — «transformers 또는 CUDA 없음» · «demucs 또는 CUDA 없음»."""


def gpu_bound(item: pytest.Item) -> bool:
    """이 시험이 GPU를 잡는가. **선언된 건너뜀 사유로 판정한다** (D-0290)."""
    return any(
        GPU_REASON in str(mark.kwargs.get("reason", "")) for mark in item.iter_markers("skipif")
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """GPU를 잡는 시험을 한 무리로 묶는다 (D-0290).

    `--dist loadgroup`이 같은 `xdist_group`을 **한 워커에** 보낸다. 이 기기의 가용 VRAM은
    4.8GB이고(D-0218) MERT·CLAP·Demucs가 **다른 워커에 동시에 실리면** 카드에 모델이 둘
    올라간다. 워커 경계는 시험 수가 바뀔 때마다 움직이므로 **언제 겹칠지는 운이다.**
    """
    for item in items:
        if gpu_bound(item):
            item.add_marker(pytest.mark.xdist_group(GPU_GROUP))


@pytest.fixture(autouse=True)
def isolate_machine_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """**검사는 기기 상태에 의존하지 않는다** (D-0071).

    `.env`가 있는 기기와 없는 기기에서 결과가 갈렸다. 광인사에는 `.env`가 없어
    초록이었고 리전에서는 `make setup`이 만든 `.env`를 CLI가 읽어 두 건이 깨졌다.
    **검사가 잡아야 할 부류를 검사 자신이 저질렀다.**

    모든 검사에서 `HATHOR_*` 환경변수를 지우고 `.env` 적재를 막는다. 기기별 값을
    쓰는 검사는 스스로 `monkeypatch.setenv`로 넣는다 — 이 픽스처가 먼저 돌므로
    덮이지 않는다.

    `load_dotenv` 자체를 검사하는 것은 `paths` 모듈을 직접 부르므로 영향이 없다.
    """
    for key in [name for name in os.environ if name.startswith(MACHINE_ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "hathor.interfaces.cli.main.load_dotenv", lambda *_args, **_kwargs: {}, raising=False
    )
    yield


def scanned_track(
    source_key: str = "a.mp3",
    *,
    title: str | None = "t",
    artist: str | None = "a",
    duration_ms: int = 1000,
) -> ScannedTrack:
    """인제스트의 최소 단위 하나. **정본은 여기 하나다** (D-0264).

    응용 계층의 유스케이스 여섯이 `Iterable[ScannedTrack]`을 받고, 시험은 그것을
    **다섯 군데서 손으로 조립하고 있었다** — 같은 17줄이 다섯 벌이고 다른 것은
    `source_key` · `title` · `artist` · 길이뿐이다.

    그래서 일곱째 시험(`test_extract_onsets`)이 **`source_key`만 가진 가짜 반**을
    새로 만들었다. `ExtractOnsets`가 실제로 읽는 것이 그 칸 하나이므로 돌기는 돈다 —
    그러나 **`ScannedTrack`이라고 적힌 자리에 그것이 아닌 것이 들어갔다.** 형 검사를
    걸자 여덟 건으로 나왔다. 조립이 한 자리면 애초에 생기지 않는 부류다.
    """
    return ScannedTrack(
        source_key=source_key,
        file_size_bytes=1,
        modified_at=datetime.now(UTC),
        stream=AudioStreamProperties(
            sample_rate_hz=44100,
            channels=2,
            duration_ms=duration_ms,
            bitrate_bps=320000,
            codec="mp3",
        ),
        tags=TrackTags(
            title=title,
            artist=artist,
            album=None,
            lyrics_text=None,
            has_album_art=False,
            has_synced_lyrics=False,
        ),
        raw_frame_names=(),
    )


TOOLS = Path(__file__).resolve().parents[2] / "tools"
"""`tools/`. 시험이 도구를 경로로 싣는 자리다."""


def tool_module(name: str) -> ModuleType:
    """`tools/<name>.py`를 싣는다. **정본은 여기 하나다** (D-0272).

    `tools/`는 패키지가 아니라 `python3 tools/x.py`로 도는 스크립트 묶음이다 (D-0256).
    그래서 시험이 경로로 실어야 하고, 그 여덟 줄이 **시험 파일 21벌에 흩어져 있었다** —
    꼴이 열셋으로 갈려 있었다. `ScannedTrack` 조립이 다섯 벌이던 것과 같은 부류다 (D-0264).

    `sys.path`에 `tools/`를 얹는다. **도구가 형제 도구를 임포트한다** —
    `build_proposal`이 `proposal_source`를 부르고, 그것을 세 파일이 각자 해 주고 있었다.

    **이미 실은 것은 다시 싣지 않는다.** 모듈 수준에서 부르는 파일이 여럿이고, 다시
    실으면 그 모듈의 상수가 두 벌이 되어 `monkeypatch`가 한쪽만 고친다.
    """
    root = str(TOOLS)
    if root not in sys.path:
        sys.path.insert(0, root)
    path = TOOLS / f"{name}.py"
    loaded = sys.modules.get(name)
    if loaded is not None and getattr(loaded, "__file__", None) == str(path):
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"{path}를 못 싣는다"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FFMPEG = shutil.which("ffmpeg")
requires_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg 미설치")


def _make_silent_mp3(path: Path, seconds: float = 1.0, sample_rate: int = 44100) -> None:
    """무음 mp3를 생성한다. 태그는 없는 상태로 만들어진다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(FFMPEG),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=stereo",
            "-t",
            str(seconds),
            "-b:a",
            "128k",
            str(path),
        ],
        check=True,
    )


@pytest.fixture
def make_mp3() -> Callable[..., Path]:
    """무음 mp3를 만들고 지정한 ID3 태그를 주입한다.

    D-0010 실측 기준으로 라이브러리에 실재하는 프레임만 다룬다:
    TIT2 / TPE1 / TALB / USLT / APIC.
    """

    def _factory(
        path: Path,
        *,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
        album_art: bool = False,
        seconds: float = 1.0,
        sample_rate: int = 44100,
    ) -> Path:
        from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, USLT

        _make_silent_mp3(path, seconds=seconds, sample_rate=sample_rate)

        if not any([title, artist, album, lyrics, album_art]):
            return path

        tags = ID3()
        if title is not None:
            tags.add(TIT2(encoding=3, text=[title]))
        if artist is not None:
            tags.add(TPE1(encoding=3, text=[artist]))
        if album is not None:
            tags.add(TALB(encoding=3, text=[album]))
        if lyrics is not None:
            tags.add(USLT(encoding=3, lang="kor", desc="", text=lyrics))
        if album_art:
            tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="",
                    data=b"\xff\xd8\xff\xd9",
                )
            )
        tags.save(path)
        return path

    return _factory
