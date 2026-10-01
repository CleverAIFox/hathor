"""산출물 경로가 **곡 이름을 한 글자도 안 쓴다** (D-0331).

### CodeQL 0건이 이것을 말한 것이 아니다

D-0329가 코드 스캐닝을 켜면서 *"여기 실제로 닿는 부류는 경로 탈출이다 — 코퍼스 파일
이름과 ID3 태그가 외부 입력이고 그것으로 만든 경로에 산출물을 쓴다"*고 적었다.
첫 실행은 **0건**이었다.

**0은 「없다」가 아니라 「그 질의가 이 모양을 안 본다」일 수 있다.** CodeQL의 파이썬
질의는 웹 요청·명령줄을 오염원으로 보고, `Path.glob`이 낸 파일 이름은 기본 오염원이
아니다. **예측은 확인된 것이 아니라 아직 안 재어진 것이다** (GR-0.5).

### 진짜 방어는 해시 경로이고, 보안 때문에 생긴 것이 아니다

네 저장소가 전부 `hash(source_key)`로 이름을 짓는다. 독스트링이 드는 이유는 **정규화 ·
길이 제한 · 충돌**이다 (D-0043 · D-0105) — **경로 탈출을 든 자리가 하나도 없다.**

그래서 내일 누가 *"사람이 읽게 제목을 넣자"*고 바꾸면 **아무도 안 막는다.**
`SECURITY.md`는 경로 탈출을 보고 대상으로 들고 있는데 **무엇이 그것을 막는지는 안 적혀
있었다.** 여기서 못을 박는다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hathor.infrastructure.chroma_series_store import series_path
from hathor.infrastructure.npz_feature_store import vector_filename
from hathor.infrastructure.onset_store import envelope_path
from hathor.infrastructure.track_bundle_store import bundle_name

HEX_NAME = re.compile(r"^[0-9a-f]+(-[a-z]+)?(\.npz)?$")

HOSTILE = (
    "../../../etc/passwd",
    "..\\..\\windows\\system32",
    "곡/../../../../tmp/evil",
    "/etc/shadow",
    "a\nb/../c",
    "....//....//x",
    "~/.ssh/id_rsa",
)
"""**곡 파일 이름은 개발자가 안 쓴 문자열이다.** 코퍼스는 내려받은 것이고 태그는 남이
적었다. 여기 있는 것이 실제로 코퍼스에 있다는 뜻은 아니다 — **있어도 되는가**를 묻는다.
"""


@pytest.mark.parametrize("hostile", HOSTILE)
def test_곡_이름이_경로를_못_만든다(hostile: str, tmp_path: Path) -> None:
    """네 저장소 전부. **하나라도 빠지면 그 하나가 구멍이다.**"""
    root = tmp_path / "var"
    root.mkdir()

    made = [
        series_path(root, hostile, "other"),
        envelope_path(root, hostile),
        root / vector_filename(hostile),
        root / f"{bundle_name(hostile)}.npz",
    ]
    for path in made:
        assert HEX_NAME.match(path.name), f"이름에 곡 문자열이 샌다: {path.name}"
        assert path.resolve().parent == root.resolve(), f"뿌리 밖을 가리킨다: {path}"


def test_다른_곡은_다른_이름이고_같은_곡은_같다() -> None:
    """**새니타이즈가 아니라 해시여야 하는 이유다.**

    위험한 글자를 지우는 식이면 `a/b`와 `a_b`가 **같은 이름으로 충돌**한다. 해시는
    서로 다른 키를 서로 다른 이름으로 보낸다 — 그것이 `vector_filename`의 독스트링이
    이미 든 근거이고, 여기서는 그 근거를 **시험으로** 든다.
    """
    assert bundle_name("가/나") != bundle_name("가_나")
    assert bundle_name("같은 곡") == bundle_name("같은 곡")
    assert vector_filename("가/나") != vector_filename("가_나")


def test_네_저장소를_여기서_전부_든다() -> None:
    """**새 저장소가 생기면 이 시험이 그것을 모른다** (D-0230의 빈 그물).

    산출물을 쓰는 자리가 늘면 여기 한 줄을 더해야 한다. 그 사실을 세어서 못 박는다 —
    `hashlib`를 쓰는 인프라 모듈 수가 늘면 빨개진다.
    """
    root = Path(__file__).resolve().parents[2] / "hathor" / "infrastructure"
    hashing = sorted(
        path.name for path in root.glob("*.py") if "hashlib" in path.read_text(encoding="utf-8")
    )
    assert hashing == [
        "chroma_series_store.py",
        "hashed_lyrics_extractor.py",
        "npz_feature_store.py",
        "onset_store.py",
        "track_bundle_store.py",
    ], f"해시로 이름을 짓는 자리가 달라졌다: {hashing}. 위 시험에 더한다 (D-0331)"
