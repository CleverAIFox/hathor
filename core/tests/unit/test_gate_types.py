"""관문 도구도 타입 검사를 받는가 (D-0263).

### 왜 이것이 필요했나

D-0257이 «관문 도구»라는 층에 처음 이름을 붙이면서 **«`mypy`는 `hathor`만 본다 —
`tools/`는 타입 검사 밖이다»**라고 적었다. 적어 두기만 했다.

검사 코드 타입 오류 66건을 갚으려고 `MYPYPATH`에 `tools`를 얹어 본 순간 **`tools/`
안에서 오류가 쏟아졌다.** 그대로 `mypy ../tools --strict`를 돌리니 **41파일에 42건**이고
그중 넷이 **`ship.py`의 `GREEN`과 정확히 같은 부류**였다 — 한 함수에서 이름 하나가
뜻 둘이다.

| 자리 | 앞 | 뒤 |
|---|---|---|
| `sync_artifacts.verify` | `mark` = 봉인 근거(크기 · 시각 · 해시) | `mark` = 화면에 찍는 글자 |
| `probe_chord_rhythm.self_test` | `got` = `list[float]` | `got` = `float \\| None` |
| `probe_latent.by_key` | `name` = 찾는 임베딩 이름 | `name` = 벡터 파일 이름 |
| `probe_latent.report` | `found` = `RetrievalScore` | `found` = `list[float]` |

넷 다 실행 시점에는 안 터진다. 고리가 차례로 돌아서다. **`ship.py`의 그것도 안 터졌고,
여덟 판 동안 머리글에 튜플을 찍었을 뿐이다.**

### 여기가 무엇을 보는가

**강제자는 `mypy` 자신이다** — `make type`과 CI가 돌린다. 이 파일은 둘이다.

1. 그 줄이 **세 관문에 다 있는가.** 지우면 아무 소리 없이 사라진다 (D-0219).
2. `mypy`가 정말 그 부류를 잡는가 — **양성 대조**다. 「검사가 죽었는지 세는 것과
   검사가 무엇을 잡는지 보는 것은 다르다」(D-0230).
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "core"

TOOLS_CHECK = re.compile(r"mypy\s+\.\./tools\s+--strict")
"""관문에 선 그 줄. **`tools`를 `--strict`로 본다**는 것까지 봐야 한다."""


def test_makefile이_관문_도구를_검사한다() -> None:
    """`make type`이 셋을 다 본다 — 제품 · 관문 도구 · 검사 코드."""
    body = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = body.split("\ntype:", 1)[1].split("\narch:", 1)[0]

    assert "mypy hathor --strict" in target, "제품 코드 검사가 없다"
    assert TOOLS_CHECK.search(target), "관문 도구 검사가 없다 (D-0263)"
    assert "check_test_types.py" in target, "검사 코드 래칫이 없다"


def test_ci도_관문_도구를_검사한다() -> None:
    """**로컬과 CI가 어긋나면 그중 하나가 거짓말이다** (D-0219 · D-0254)."""
    body = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert TOOLS_CHECK.search(body), "CI에 관문 도구 타입 검사가 없다 (D-0263)"


def test_캐시를_따로_쓴다() -> None:
    """**깃발이 다른 실행이 캐시를 나눠 쓰면 둘 다 영원히 차갑다** (D-0241).

    `hathor` · `tests` · `tools`가 각자 캐시를 갖는다. 셋이 같은 자리를 쓰면 서로의
    모듈을 무효화한다 — 실측으로 따뜻한 재실행이 100초에서 25초가 된 그 일이다.

    `tests`의 자리는 `Makefile`이 아니라 `check_test_types.CACHE`다 — **깃발을 쥔 쪽이
    캐시도 쥔다.** 그래서 두 자리를 다 읽는다.
    """
    body = (ROOT / "Makefile").read_text(encoding="utf-8")
    body += (ROOT / "tools" / "check_test_types.py").read_text(encoding="utf-8")
    caches = set(re.findall(r"[\"'\s](\.mypy_cache\w+)", body))

    assert len(caches) >= 3, f"캐시를 나눠 쓴다: {sorted(caches)}"
    assert ".mypy_cache_tools" in caches

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for cache in caches:
        assert f"{cache}/" in ignored, f"{cache}가 .gitignore에 없다"


def test_이름_하나에_뜻_둘을_잡는다(tmp_path: Path) -> None:
    """**양성 대조다** (D-0263). `ship.py`를 망친 그 꼴을 그대로 먹인다.

    이 시험이 통과한다는 것은 «`mypy`를 걸었다»가 아니라 «걸어 둔 `mypy`가 그것을
    잡는다»는 뜻이다. D-0230이 검사 도구에 대해 확인한 것과 같은 자리다.
    """
    target = tmp_path / "shadow.py"
    target.write_text(
        'GREEN = "\\033[92m"\nGREEN = ("success", "skipped", "neutral")\n', encoding="utf-8"
    )

    done = subprocess.run(
        (sys.executable, "-m", "mypy", str(target), "--strict", "--cache-dir", str(tmp_path / "c")),
        cwd=CORE,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 1, done.stdout + done.stderr
    assert "[assignment]" in done.stdout, done.stdout


# ----------------------------------- 가짜가 제 포트를 닮았는가 (D-0271)

PORT_METHODS = frozenset(
    {
        "decode",
        "separate",
        "extract",
        "extract_layers",
        "layers",
        "track",
        "scan",
        "resolve_artist",
        "resolve_recording",
    }
)
"""포트가 요구하는 메서드 이름 (`hathor/domain/ports/`). 가짜가 이 이름을 쓰면 포트를
대신하는 것이다.

**전수를 손으로 적는다.** 포트에서 뽑아 쓰면 이름이 바뀔 때 그물이 조용히 따라가고
«0건»이 거짓으로 참이 된다. 아래 시험이 실물 포트와 대조해 **적어 둔 이름이 실재하는지**를
본다 — 첫 판에 `read_tracks`를 넣었다가 그 시험에 걸렸다(그것은 저장소 메서드다)."""

UNTYPED_FAKES = 0
"""주석이 빈 포트 가짜의 수. **0이다** (D-0271).

`--allow-untyped-defs`가 `-> None` 1111개를 면제하는데 **그 면제가 가짜의 서명까지
면제했다.** 주석이 없으면 인자와 반환이 `Any`이고 `Any`는 **어떤 규약에도 구조적으로
맞는다** — `ExtractOnsets(decoder: AudioDecoder)`에 아무 반을 넣어도 조용했다.

19개 중 16개가 그 상태였다. 늘리려면 결정 기록이 필요하다 (D-0118)."""


def port_fakes() -> list[str]:
    """포트를 흉내내면서 **주석이 빈** 가짜. 이름·자리와 함께 낸다."""
    found: list[str] = []
    for path in sorted((CORE / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef) or member.name not in PORT_METHODS:
                    continue
                args = member.args.args[1:] + member.args.kwonlyargs
                if any(arg.annotation is None for arg in args) or member.returns is None:
                    where = path.relative_to(CORE).as_posix()
                    found.append(f"{where}:{member.lineno} {node.name}.{member.name}")
    return found


def test_포트_가짜가_주석을_갖는다() -> None:
    """**D-0271의 강제자.** 주석이 있으면 `mypy`가 호출 자리에서 규약과 대조한다.

    사용자가 물었다 — *"죄다 구라에 가짜에 Mock에."* 가짜 자체는 제약의 결과다(오디오는
    기기를 못 떠나고 GPU가 없다 · D-0015 · D-0021). 문제는 **그 가짜가 실물 포트를 닮았는지
    아무도 안 본 것**이었다.
    """
    assert port_fakes() == [], "주석이 빈 포트 가짜가 있다"


def test_가짜가_실제로_세어진다() -> None:
    """**세는 그물이 비었으면 «0건»이 거짓으로 참이 된다** (D-0230).

    포트 메서드 이름이 바뀌면 이 그물이 조용히 빈다 — 그래서 **실물 포트와 대조한다.**
    """
    ports = (CORE / "hathor" / "domain" / "ports").rglob("*.py")
    declared = {
        member.name
        for path in ports
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ClassDef)
        for member in node.body
        if isinstance(member, ast.FunctionDef) and not member.name.startswith("_")
    }

    assert declared >= PORT_METHODS, f"포트에 없는 이름을 센다: {PORT_METHODS - declared}"
    assert UNTYPED_FAKES == 0


# --------------------------------- 도구를 싣는 자리는 하나다 (D-0272)

LOADERS = 1
"""`spec_from_file_location`을 쓰는 시험 파일의 수. **1이다 — `conftest.py`** (D-0272).

`tools/`는 패키지가 아니라 스크립트 묶음이라(D-0256) 시험이 경로로 실어야 하고, 그 여덟
줄이 **21벌에 흩어져 꼴이 열셋으로 갈려 있었다.** 셋은 `sys.path`를 손으로 얹고 나머지는
안 얹었다 — 같은 일을 다르게 하는 것이 스물한 벌이었다.

`ScannedTrack` 조립이 다섯 벌이던 것과 같은 부류다 (D-0264). 늘리려면 결정 기록이 필요하다."""


SELF = Path(__file__).name
"""**자기 자신은 안 본다** (D-0261과 같은 자리).

세려는 낱말을 적어 두는 자리가 바로 이 파일이다. `check_forbidden`이 커밋되자마자 자기
패턴 여덟 줄에 걸린 것과 같고, 이 시험도 첫 실행에 자기를 잡았다."""


def loader_files() -> list[str]:
    """도구를 손으로 싣는 시험 파일. **이 파일은 뺀다** — 세는 낱말이 여기 적혀 있다."""
    return sorted(
        path.relative_to(CORE).as_posix()
        for path in (CORE / "tests").rglob("*.py")
        if path.name != SELF and "spec_from_file_location" in path.read_text(encoding="utf-8")
    )


def test_도구를_싣는_자리가_하나다() -> None:
    """**D-0272의 강제자.** 스물한 벌이 한 벌이 됐다."""
    found = loader_files()

    assert len(found) == LOADERS, f"싣는 자리가 {len(found)}곳이다: {found}"
    assert found == ["tests/conftest.py"]


def test_같은_도구를_두_번_싣지_않는다() -> None:
    """**다시 실으면 그 모듈의 상수가 두 벌이 된다** (D-0272).

    `monkeypatch.setattr(CHECKER, "ROOT", tmp_path)`가 한쪽만 고치고, 검사는 안 고쳐진
    쪽을 본다. 옛 로더들은 부를 때마다 다시 실었고 **모듈 수준에서 한 번만 불러서**
    우연히 안 터졌다.
    """
    from tests.conftest import tool_module

    first = tool_module("check_egress")
    assert tool_module("check_egress") is first
