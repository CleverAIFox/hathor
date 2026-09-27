"""평가 명령이 찍은 것을 산출물로도 남긴다 (D-0250).

### 왜

`eval harmony-output` · `harmony-order` · `degree-restriction` · `chromatic-origin`은
**표를 화면에 찍고 아무것도 남기지 않았다.** 그 수치들은 터미널 스크롤에만 있었고,
창을 닫으면 사라졌다. 결정 기록 74건이 «재현 불명»인 진짜 이유가 이것이다 —
**명령을 잊은 것이 아니라 결과가 사라졌다.**

`JsonEvaluationStore`를 쓰는 둘(`retrieval` · `fusion`)만 살아남았다.

### 명령도 같이 적는다

수치만 있으면 «무슨 조건이었나»가 또 없다. 첫 줄에 **그 산출물을 낸 명령**을 적는다.
홈 경로는 `~`로 줄인다 — 산출물이 사람 이름을 들고 다닐 이유가 없다.

### 찍기를 막지 않는다

사람이 보는 것이 먼저이고 남기는 것은 덤이다. **쓰기가 실패해도 명령은 성공한다** —
읽기 전용 경로나 꽉 찬 디스크에서 평가가 죽으면 바꿔치기가 손해다.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from hathor.infrastructure.json_evaluation_store import EVAL_DIRNAME, safe_label

LOG_SUFFIX = ".eval.log"


def command(argv: Sequence[str] | None = None) -> str:
    """이 산출물을 낸 명령. **집 경로를 `~`로 줄인다.**"""
    raw = list(sys.argv if argv is None else argv)
    if not raw:
        return ""
    raw[0] = Path(raw[0]).name
    home = str(Path.home())
    if home in ("", "/"):
        return " ".join(raw)
    return " ".join(part.replace(home, "~") for part in raw)


class _Tee(io.TextIOBase):
    """화면과 버퍼에 같이 쓴다."""

    def __init__(self, live: IO[str], keep: io.StringIO) -> None:
        super().__init__()
        self._live = live
        self._keep = keep

    def write(self, text: str) -> int:
        self._keep.write(text)
        return self._live.write(text)

    def flush(self) -> None:
        self._live.flush()


def save(root: Path, label: str, body: str) -> Path | None:
    """찍힌 것을 `<root>/eval/<시각>-<라벨>.eval.log`로 남긴다. 실패하면 `None`."""
    if not body.strip():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / EVAL_DIRNAME / f"{stamp}-{safe_label(label)}{LOG_SUFFIX}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"$ {command()}\n\n{body}", encoding="utf-8")
    except OSError:
        return None
    return path


@contextmanager
def recorded(root: Path, label: str) -> Iterator[None]:
    """찍으면서 남긴다. **예외로 끝나도 찍힌 것까지는 남는다** — 중간에 죽은 실측도 단서다.

    남긴 자리는 **`stderr`로 알린다.** 파일 이름에 시각이 들어가므로 `stdout`에 찍으면
    같은 시드로 두 번 돌린 출력이 달라진다 — D-0009가 «내용에는 시각을 넣지 않는다»고
    적은 그 자리이고, `test_시드가_같으면_같은_수를_낸다`가 실제로 빨개졌다.
    """
    keep = io.StringIO()
    try:
        with redirect_stdout(_Tee(sys.stdout, keep)):
            yield
    finally:
        path = save(root, label, keep.getvalue())
        if path is not None:
            print(f"기록: {path}", file=sys.stderr)
