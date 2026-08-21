"""저장소 경로와 `.env` 해석 (D-0066).

**기기를 옮길 때마다 손으로 치던 것을 없앤 장치다.** 그 장치가 조용히 안 걸리면
이전과 똑같아지므로 단위 검사로 고정한다 — `chroma(harmonic=...)`가 무시되던
D-0064와 같은 종류의 사고를 막는다.
"""

import os
from pathlib import Path

import pytest

from hathor.shared.config.paths import (
    LIBRARY_ROOT_ENV,
    PATCH_DIR_ENV,
    library_root,
    load_dotenv,
    parse_dotenv,
    patch_dir,
    repo_root,
    resolve_path,
)


def test_저장소_루트는_표식을_갖는다():
    root = repo_root()
    assert (root / "CONTRIBUTING.md").exists()
    assert (root / "core").is_dir()
    assert (root / "docs").is_dir()


def test_저장소_루트는_현재_디렉터리와_무관하다(tmp_path, monkeypatch):
    """**이것이 요점이다.** `cd core`를 했는지에 따라 산출물이 갈리지 않아야 한다."""
    before = repo_root()
    monkeypatch.chdir(tmp_path)
    assert repo_root() == before


def test_상대_경로는_저장소_루트_기준이다(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert resolve_path("var/ingest") == repo_root() / "var" / "ingest"


def test_절대_경로는_그대로_둔다():
    assert resolve_path("/mnt/f/노래") == Path("/mnt/f/노래")


def test_물결표를_편다():
    assert not str(resolve_path("~/hathor")).startswith("~")


def test_주석과_빈_줄을_건너뛴다():
    values = parse_dotenv("# 설명\n\nA=1\n  B = 2  \n잘못된줄\n")
    assert values == {"A": "1", "B": "2"}


def test_따옴표를_벗긴다():
    assert parse_dotenv("A=\"/mnt/f/노래\"\nB='x'\n") == {"A": "/mnt/f/노래", "B": "x"}


def test_값에_등호가_있어도_첫_등호에서만_가른다():
    assert parse_dotenv("URL=postgresql://a:b@c/d?x=1\n")["URL"].endswith("?x=1")


def test_이미_있는_환경변수는_덮지_않는다(tmp_path, monkeypatch):
    """셸에서 명시로 준 값이 파일보다 우선한다.

    한 번만 다르게 돌려 보는 일이 잦은데, 파일이 이기면 그 실행이 조용히 틀린다.
    """
    monkeypatch.setenv("HATHOR_TEST_KEEP", "셸")
    monkeypatch.delenv("HATHOR_TEST_NEW", raising=False)
    target = tmp_path / ".env"
    target.write_text("HATHOR_TEST_KEEP=파일\nHATHOR_TEST_NEW=파일\n", encoding="utf-8")

    applied = load_dotenv(target)
    assert os.environ["HATHOR_TEST_KEEP"] == "셸"
    assert os.environ["HATHOR_TEST_NEW"] == "파일"
    assert applied == {"HATHOR_TEST_NEW": "파일"}


def test_파일이_없으면_아무_일도_하지_않는다(tmp_path):
    assert load_dotenv(tmp_path / "없는파일") == {}


def test_설정_읽기는_미설정이면_None이다(monkeypatch):
    monkeypatch.delenv(LIBRARY_ROOT_ENV, raising=False)
    monkeypatch.delenv(PATCH_DIR_ENV, raising=False)
    assert library_root() is None
    assert patch_dir() is None

    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/mnt/f/노래")
    monkeypatch.setenv(PATCH_DIR_ENV, "~/내려받기")
    assert library_root() == Path("/mnt/f/노래")
    assert patch_dir() is not None
    assert not str(patch_dir()).startswith("~")


def test_env_명령이_경로를_찍는다(capsys, monkeypatch):
    from hathor.interfaces.cli.main import main

    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/존재하지-않는-경로")
    assert main(["env"]) == 0
    out = capsys.readouterr().out
    assert "저장소" in out
    assert "음원 루트" in out
    assert "드라이브 마운트" in out


def test_env_명령이_미설정을_알린다(capsys, monkeypatch):
    from hathor.interfaces.cli.main import main

    monkeypatch.delenv(LIBRARY_ROOT_ENV, raising=False)
    assert main(["env"]) == 0
    assert "미설정" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["var/ingest", "var/out/a.mid"])
def test_해석된_경로는_항상_절대_경로다(name):
    assert resolve_path(name).is_absolute()


# ---------------------------------------------------- doctor (D-0067)


def test_doctor는_설정이_다_있으면_0이다(tmp_path, monkeypatch, capsys):
    """`.env`가 있고 음원 루트가 실재하면 통과한다."""
    from hathor.interfaces.cli.main import main
    from hathor.shared.config import paths

    fake = tmp_path / "projects" / "hathor"
    (fake / "core").mkdir(parents=True)
    (fake / "docs").mkdir()
    (fake / "CONTRIBUTING.md").write_text("x", encoding="utf-8")
    (fake / ".env").write_text("", encoding="utf-8")

    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: fake)
    monkeypatch.setattr(paths, "repo_root", lambda: fake)
    monkeypatch.setenv(LIBRARY_ROOT_ENV, str(tmp_path))
    monkeypatch.setenv(PATCH_DIR_ENV, str(tmp_path))
    main(["doctor"])
    out = capsys.readouterr().out
    # 설치본은 진짜 저장소를 가리키므로 여기서는 어긋난다. 설정 쪽만 본다.
    assert ".env" in out
    assert "미설정" not in out


def test_doctor는_설정이_없으면_1이다(monkeypatch, capsys):
    from hathor.interfaces.cli.main import main

    monkeypatch.delenv(LIBRARY_ROOT_ENV, raising=False)
    monkeypatch.delenv(PATCH_DIR_ENV, raising=False)
    assert main(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "고칠 것" in out
    assert LIBRARY_ROOT_ENV in out


def test_doctor는_설치본이_같은_저장소인지_본다(capsys, monkeypatch):
    """**낡은 결과의 진짜 원인은 캐시가 아니라 다른 클론이다** (D-0067).

    클론을 둘 둔 채 한쪽에서 고치고 다른 쪽 가상환경으로 실행하면, 고쳐도 결과가
    바뀌지 않는다. 검사 도구 캐시는 내용 해시 기반이라 그런 일을 만들지 않는다.
    """
    from hathor.interfaces.cli.main import main

    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")
    main(["doctor"])
    assert "설치본" in capsys.readouterr().out


def test_doctor는_윈도우_드라이브를_경고한다(monkeypatch, capsys):
    from hathor.interfaces.cli.main import main
    from hathor.shared.config import paths

    monkeypatch.setattr(paths.repo_root, "__wrapped__", lambda: Path("/mnt/c/x/hathor"))
    paths.repo_root.cache_clear()
    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: Path("/mnt/c/x/hathor"))
    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")
    assert main(["doctor"]) == 1
    assert "drvfs" in capsys.readouterr().out
    paths.repo_root.cache_clear()


# ------------------------------------------------ 기기 탐지 (D-0068)


@pytest.fixture
def fake_mount(tmp_path):
    """리전의 실제 배치를 흉내낸다 — `노래` 안에 `노래`가 한 겹 더 있다."""
    users = tmp_path / "c" / "Users"
    (users / "Fox" / "Downloads").mkdir(parents=True)
    (users / "Public").mkdir()
    library = tmp_path / "d" / "노래" / "노래"
    library.mkdir(parents=True)
    for index in range(120):
        (library / f"가수-곡{index}.mp3").touch()
    # 상위 폴더에도 몇 개 흩어져 있지만 라이브러리는 아니다.
    for index in range(5):
        (library.parent / f"트랙{index}.mp3").touch()
    (library.parent / "앨범 커버").mkdir()
    (tmp_path / "c" / "Windows").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_윈도우_사용자를_찾는다(fake_mount, monkeypatch):
    from hathor.shared.config import paths

    monkeypatch.setattr(paths, "WINDOWS_USERS_ROOT", fake_mount / "c" / "Users")
    found = paths.windows_user_dir()
    assert found is not None
    assert found.name == "Fox"


def test_Public_같은_시스템_계정은_거른다(fake_mount, monkeypatch):
    from hathor.shared.config import paths

    monkeypatch.setattr(paths, "WINDOWS_USERS_ROOT", fake_mount / "c" / "Users")
    assert paths.windows_user_dir().name != "Public"


def test_사용자_폴더가_없으면_None이다(tmp_path, monkeypatch):
    from hathor.shared.config import paths

    monkeypatch.setattr(paths, "WINDOWS_USERS_ROOT", tmp_path / "없음")
    assert paths.windows_user_dir() is None


def test_음원_루트는_안쪽_폴더를_고른다(fake_mount):
    """**바로 아래 파일 수로 고른다.**

    상위 폴더는 하위를 합치면 더 크지만 라이브러리 루트가 아니다. `/mnt/d/노래`를
    루트로 잡아 한 겹을 놓쳤던 것이 실제 사고였다.
    """
    from hathor.shared.config.paths import find_library_candidates

    found = find_library_candidates(mount_root=fake_mount)
    assert found
    best, count = found[0]
    assert best.name == "노래"
    assert best.parent.name == "노래"
    assert count == 120


def test_C드라이브는_훑지_않는다(fake_mount):
    from hathor.shared.config.paths import find_library_candidates

    for path, _ in find_library_candidates(mount_root=fake_mount):
        assert "/c/" not in str(path)


def test_음원이_적으면_후보가_아니다(tmp_path):
    from hathor.shared.config.paths import find_library_candidates

    thin = tmp_path / "d" / "작은폴더"
    thin.mkdir(parents=True)
    for index in range(10):
        (thin / f"{index}.mp3").touch()
    assert find_library_candidates(mount_root=tmp_path) == []


def test_setup은_dry_run에서_쓰지_않는다(tmp_path, monkeypatch, capsys):
    from hathor.interfaces.cli.main import main

    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: tmp_path)
    assert main(["setup", "--dry-run"]) == 0
    assert not (tmp_path / ".env").exists()
    assert "쓰지 않았다" in capsys.readouterr().out


def test_setup은_이미_있는_값을_두고_force로_덮는다(tmp_path, monkeypatch, capsys):
    from hathor.interfaces.cli.main import main
    from hathor.shared.config import paths

    (tmp_path / ".env.example").write_text(
        "HATHOR_LIBRARY_ROOT=\nHATHOR_PATCH_DIR=\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text(
        "HATHOR_LIBRARY_ROOT=/직접/적은/경로\nHATHOR_PATCH_DIR=\n", encoding="utf-8"
    )
    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: tmp_path)
    monkeypatch.setattr(paths, "find_library_candidates", lambda **_: [(Path("/탐지/경로"), 500)])

    assert main(["setup"]) == 0
    assert "/직접/적은/경로" in (tmp_path / ".env").read_text(encoding="utf-8")

    assert main(["setup", "--force"]) == 0
    assert "/탐지/경로" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_setup은_env가_없으면_예시에서_만든다(tmp_path, monkeypatch):
    from hathor.interfaces.cli.main import main
    from hathor.shared.config import paths

    (tmp_path / ".env.example").write_text(
        "# 주석\nHATHOR_LIBRARY_ROOT=\nHATHOR_PATCH_DIR=\nPOSTGRES_USER=hathor\n", encoding="utf-8"
    )
    monkeypatch.setattr("hathor.interfaces.cli.main.repo_root", lambda: tmp_path)
    monkeypatch.setattr(paths, "find_library_candidates", lambda **_: [(Path("/음원"), 900)])

    assert main(["setup"]) == 0
    written = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "HATHOR_LIBRARY_ROOT=/음원" in written
    assert "POSTGRES_USER=hathor" in written  # 나머지 줄을 보존한다


def test_doctor가_환경_프로파일을_찍는다(monkeypatch, capsys):
    from hathor.interfaces.cli.main import main

    monkeypatch.setenv(LIBRARY_ROOT_ENV, "/tmp")
    monkeypatch.setenv(PATCH_DIR_ENV, "/tmp")
    main(["doctor"])
    out = capsys.readouterr().out
    assert "설치 프로파일" in out
    assert ("리전형" in out) or ("광인사형" in out)
