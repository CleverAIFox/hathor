"""산출물 대장과 실물 대조 (D-0266).

### 왜 이 파일이 생겼나

사용자가 `make ship`의 한 줄을 보고 물었다 — *"교두보에 1090개 이거 맞나? 1004개가
아니라?"* **저장소가 그 질문에 답할 수 없었다.** 선언이 없으면 «맞나»는 물을 수 없는
질문이고, 있는 것을 세는 것과 있어야 할 것과 대조하는 것은 다르다.

파이어레인의 데이터 규율(R2 · R3 · R4)을 산출물에 옮긴 판이다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from hathor.shared.config.paths import repo_root

ROOT = repo_root()


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LEDGER = _tool("check_artifacts")


def test_지금_대장에_결함이_없다() -> None:
    """**D-0266의 강제자.** `make check`와 CI가 매번 보는 것이다."""
    assert LEDGER.check_ledger(LEDGER.load()) == []


def test_모든_계열이_누가_읽는지_적는다() -> None:
    """**R4.** 못 채우면 «미투입 — 언제 쓸지»를 적고 산다.

    *"문제는 모은 데서 안 나오고 안 치운 데서 나온다."* 지금 `clap` 하나가 미투입이고
    그것도 **적혀 있다** — 안 적힌 것과 적고 남긴 것은 다르다.
    """
    for name, entry in sorted(LEDGER.load().items()):
        reads = entry["reads"]
        assert isinstance(reads, list) and reads, name
        assert all(isinstance(one, str) and one.strip() for one in reads), name


def test_재생성_불가는_교두보가_강제된다() -> None:
    """**R2.** `var/`는 전부 `.gitignore`에 있다 (D-0266).

    다시 만들 수 있어서 제외하는 것이며, **못 만드는 것을 제외하면 그 파일은 사실상
    소실된다.** 지금 그 계열은 `taste` 하나다 — 사람이 답한 라벨이다.
    """
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "var/" in ignored, "이 시험의 전제가 깨졌다 — var/가 ignore되지 않는다"

    cannot = {
        name: entry for name, entry in LEDGER.load().items() if entry["regen"] == LEDGER.CANNOT
    }
    assert cannot, "재생성 불가 계열이 하나는 있어야 이 시험이 뜻이 있다 (taste)"
    for name, entry in cannot.items():
        assert entry["store"] is True, f"{name}이 교두보 의무를 안 진다"
        assert isinstance(entry["why"], str) and len(entry["why"]) > 30, name


def test_교두보_의무를_안_지면_잡는다() -> None:
    """**양성 대조.** 이 검사가 무엇을 잡는지 본다 (D-0230)."""
    broken = {
        "손라벨": {
            "what": "사람이 답한 것",
            "made": "core/hathor/infrastructure/jsonl_preference_store.py",
            "regen": LEDGER.CANNOT,
            "why": "사람이 답한 라벨이라 명령으로 다시 만들 수 없다. 다시 물으면 답이 다르다",
            "reads": ["engines/taste"],
            "store": False,
        }
    }
    problems = LEDGER.check_ledger(broken)

    assert [line for line in problems if "소실된다" in line]


def test_만드는_코드가_실재하는지_본다() -> None:
    """**`doc_fsck`와 같은 자리다** — 선언이 없는 파일을 가리키면 잡는다 (D-0189)."""
    fiction = {
        "없는계열": {
            "what": "무엇",
            "made": "core/hathor/infrastructure/없는저장소.py",
            "regen": "명령",
            "reads": ["누군가"],
            "store": True,
        }
    }
    assert [line for line in LEDGER.check_ledger(fiction) if "없는 파일" in line]


def test_칸이_빠지면_잡는다() -> None:
    assert [line for line in LEDGER.check_ledger({"빈계열": {}}) if "`what` 칸이 없다" in line]


def test_대장에_없는_계열을_격리로_판정한다(tmp_path: Path) -> None:
    """**R3. 등록되지 않은 산출물은 없는 산출물이다.**

    새 계열을 내면서 대장을 안 쓰는 길을 막는다 — 천장이 0이다.
    """
    (tmp_path / "scan-20260101T000000Z").mkdir()
    (tmp_path / "낯선계열").mkdir()
    entries: dict[str, dict[str, object]] = {"scan-*": {}, "taste": {}}

    missing, orphan, normal = LEDGER.audit(entries, tmp_path)

    assert normal == 1
    assert missing == ["taste"]
    assert orphan == ["낯선계열"]
    assert LEDGER.QUARANTINE_CEILING == 0


def test_스탬프를_계열로_접는다(tmp_path: Path) -> None:
    """실행마다 이름이 다르다. **접지 않으면 매번 격리 대상이 된다.**"""
    for stamp in ("20260101T000000Z", "20260102T111111Z", "20260103T222222Z"):
        (tmp_path / f"keys-{stamp}.series").mkdir()

    assert LEDGER.folded(tmp_path) == {"keys-*.series"}


def test_못_쟀으면_0건이_아니다() -> None:
    """**파이어레인 `lakecheck`의 규율** — *"프로브가 잴 수 없으면 0건이 아니라 빨간불이다."*

    `var/`가 없는 기기에서 «격리 0건»을 찍으면 그것은 통과가 아니라 **안 본 것이다.**
    """
    source = (ROOT / "tools" / "check_artifacts.py").read_text(encoding="utf-8")
    body = source.split("def main(")[1]

    assert "is_dir()" in body, "루트가 있는지 안 본다"
    assert "산출물이 있는 기기에서 돌린다" in body
