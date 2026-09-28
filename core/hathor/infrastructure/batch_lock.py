"""배치 잠금 — 같은 산출물 디렉터리에서 하나만 돌게 한다 (D-0278).

### 왜 이 파일이 생겼나

**잠금이 둘이었고 근거가 서로를 반박했다.**

| | 옛 `BatchLock` (D-0077) | `NpzFeatureStore.batch_lock` (D-0022) |
|---|---|---|
| 기법 | PID 파일 + 생존 확인 | `flock` |
| 죽은 잠금 | PID가 없으면 가져간다 | 커널이 fd 수명에 묶어 자동 해제 |
| 적어 둔 근거 | «손으로 지우면 결국 지운다» | «**PID 파일이면 죽은 잠금이 다음을 막는다**» |

둘 다 «죽은 잠금이 사람을 괴롭히면 안 된다»를 말하는데 **한쪽은 그것을 이유로 PID 파일을
고르고 다른 쪽은 같은 이유로 PID 파일을 버렸다.** 한쪽이 틀렸다 — `flock`이 맞다. PID는
재활용되므로 `os.kill(pid, 0)`은 «그 PID가 살아 있다»만 알려 주고 «그것이 그 배치다»는 못
알려 준다. 그리고 읽고 나서 쓰는 사이에 남이 끼어들 수 있다.

### 왜 여기 있나 (GR-2.2)

PID 파일 쪽은 `interfaces/cli/main.py`에 살았다. **파일 잠금은 인프라다** — 표시도 파싱도
아니고 커널 호출이다. `interfaces`에 로직을 두지 않는다는 규약이 적혀 있는데 잠금이 거기
있었던 것이고, D-0277이 `_run_ingest_keys` 352줄을 쪼개면서 그것이 드러났다.

### 잠금 파일은 남는다 — 그래서 대장에 등재한다

`flock`은 fd에 붙는 잠금이므로 **파일을 지우지 않는다.** 지우면 «잠금이 풀렸다»와 «파일이
없다»가 섞이고, 무엇보다 **지워서 검사를 피하는 것**이 된다 — R3(등록되지 않은 산출물은
없는 산출물이다)이 금지하는 자리이고 사실상 격리와 이름만 다르다. 그래서 `artifacts.toml`에
`state = "임시"`로 등재했다 (D-0278).
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

LOCK_SUFFIX = ".lock"
"""잠금 파일의 꼬리. **정본은 여기 하나다** — 대장의 계열 이름이 이것과 맞아야 한다."""


class BatchAlreadyRunningError(RuntimeError):
    """같은 산출물 디렉터리에서 배치가 이미 돌고 있다 (O-7(D-0022))."""


def lock_path(root: Path, name: str) -> Path:
    """`<root>/.<name>.lock`. 이름을 짓는 자리도 하나다."""
    return root / f".{name}{LOCK_SUFFIX}"


@contextmanager
def batch_lock(root: Path, name: str) -> Iterator[None]:
    """이 디렉터리에서 `name` 배치를 하나만 돌게 한다.

    **`flock`이다** (O-7 · D-0022). 이 배치는 절전·발열·마운트 해제로 네 번 죽었고 그때마다
    정리 코드가 돌지 않았다. 커널이 fd 수명에 묶어 관리하므로 프로세스가 어떻게 죽든 자동으로
    풀린다 — 유령 잠금이 없으니 사람이 잠금을 지우는 습관을 들일 일도 없다.

    **PID 파일보다 엄격하다.** 같은 프로세스가 두 번 열어도 막힌다 — `flock`은 열린 파일
    기술자에 붙기 때문이다. 배치는 실행마다 한 번만 잡으므로 제품 동작에는 차이가 없고,
    막는 쪽으로 틀리는 것이 맞는 방향이다.

    파일 내용은 **사람이 읽기 위한 것이고 잠금 판정에는 쓰지 않는다.**
    """
    root.mkdir(parents=True, exist_ok=True)
    handle = lock_path(root, name).open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.seek(0)
            holder = handle.read().strip() or "(미상)"
            raise BatchAlreadyRunningError(
                f"배치가 이미 실행 중이다: {lock_path(root, name)} — {holder}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        handle.write(f"pid={os.getpid()} started={stamp}\n")
        handle.flush()
        yield
    finally:
        handle.close()  # 닫으면 잠금이 풀린다
