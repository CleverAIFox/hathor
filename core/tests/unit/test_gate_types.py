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
