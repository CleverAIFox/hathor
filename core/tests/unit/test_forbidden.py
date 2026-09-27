"""결정이 금지한 것이 코드에 들어왔는가 (D-0261).

**§3에 «설계 판단 13건에 강제 수단이 없다»가 오래 적혀 있었다.** 그중 D-0003은 문서
표가 *"어기면 가장 나쁜 것"*으로 이름을 부른 둘 중 하나다.

첫 삽에 걸렸다 — `tools/step0_check.py`의 VRAM 계획표에 *"RVC v2 학습 — 가창 음색
변환"*이 앉아 있었다. **D-0003이 구현하지 않는다고 적은 바로 그것**이고, 검사가 없어서
아무도 안 봤다.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from hathor.shared.config.paths import repo_root


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, repo_root() / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FORBID = _tool("check_forbidden")


def test_지금_금지된_것이_없다() -> None:
    """**D-0261의 강제자.** 구멍이 0일 때 박았으므로 0이어야 한다."""
    assert FORBID.survey() == []


def test_음색_복제_이름을_잡는다() -> None:
    """이름을 막는 것이 판단을 막는 것은 아니지만 **판단을 어기는 가장 흔한 길을 막는다.**"""
    patterns = FORBID.FORBIDDEN["음색 복제"][2]

    for line in (
        "from rvc import convert",
        "so-vits-svc",
        "SO_VITS",
        "speaker_encoder = X",
        "speaker-embedding",
        "x-vector",
        "OpenVoice",
        "XTTS 로 합성",
    ):
        assert FORBID.hits(line, patterns), f"못 잡았다: {line}"


def test_비슷한_낱말은_안_잡는다() -> None:
    """`service` 안의 `rvc`까지 잡으면 **사람이 패턴을 지운다.**"""
    patterns = FORBID.FORBIDDEN["음색 복제"][2]

    for line in ("servicer = X", "curvcheck", "speakers = []", "vectorize(x)"):
        assert not FORBID.hits(line, patterns), f"헛잡았다: {line}"


def test_호칭과_복사도_막는다() -> None:
    assert FORBID.hits("model = RandomForest()", FORBID.FORBIDDEN["호칭"][2])
    assert FORBID.hits("랜덤 포레스트로 적합한다", FORBID.FORBIDDEN["호칭"][2])
    assert FORBID.hits("shutil.copy2(a, b)", FORBID.FORBIDDEN["DrvFs 복사"][2])
    assert not FORBID.hits("shutil.copyfile(a, b)", FORBID.FORBIDDEN["DrvFs 복사"][2])


def test_뜻이_있으면_선언하고_넘어간다() -> None:
    """**선언 없는 면제는 없다** (D-0219). 그러나 선언할 길은 있어야 한다."""
    patterns = FORBID.FORBIDDEN["호칭"][2]

    assert FORBID.hits("RandomForest", patterns)
    assert not FORBID.hits(f"RandomForest  {FORBID.ALLOW} 남의 논문을 인용한다", patterns)


def test_표가_사유를_든다() -> None:
    """검사가 빨개졌을 때 **왜 막혔는지를 결정 기록까지 가서 찾아야 하면 패턴을 지운다.**"""
    for name, (decision, reason, patterns) in FORBID.FORBIDDEN.items():
        assert decision.startswith("D-"), name
        assert len(reason) > 40, name
        assert patterns, name


def test_제품_코드와_도구만_본다() -> None:
    """**결정 기록은 금지어를 설명하느라 그 낱말을 쓴다.** 거기까지 보면 자기 자신에 걸린다."""
    assert FORBID.TREES == ("core/hathor", "tools")

    seen = [path for path in FORBID.tracked() if "docs/" in str(path)]
    assert not seen, "문서는 이 검사의 대상이 아니다 — 금지어를 설명하는 자리다"


def test_가창_엔진_계약이_선언돼_있다() -> None:
    """**낱말 금지만으로는 부족하다.** 이름을 안 쓰고도 성문을 뽑을 수 있다 (D-0003).

    `lint-imports`가 실제로 돌려 확인하는 것은 `make check`의 `arch` 단계다. 여기는
    그 계약이 **지워지지 않았는지**를 본다 — 지우면 아무 소리 없이 사라진다.
    """
    project = (repo_root() / "core" / "pyproject.toml").read_text(encoding="utf-8")

    assert "가창 엔진은 라이브러리 오디오를 모른다" in project
    body = project.split('name = "가창 엔진은 라이브러리 오디오를 모른다"', 1)[1]
    head = body.split("[[tool.importlinter.contracts]]", 1)[0]
    for module in ("demucs_separator", "mert_feature_extractor", "audio_stream"):
        assert module in head, f"계약이 {module}을 안 막는다"


def test_가창_엔진이_아직_비어_있다() -> None:
    """**구멍이 0일 때 박는다** (D-0134와 같은 모양). 이 전제가 깨지면 계약을 다시 본다."""
    vocal = repo_root() / "core" / "hathor" / "engines" / "vocal" / "__init__.py"
    body = [
        line
        for line in vocal.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert len(body) < 40, "가창 엔진에 코드가 생겼다 — D-0003의 계약을 다시 읽는다"


def test_도구가_자기_패턴에_안_걸린다() -> None:
    """**금지할 이름을 적어 두는 자리가 바로 그 도구다** (D-0261).

    처음에 이 예외가 없었다. 파일이 커밋되기 전에는 `git ls-files`에 없어 보이지 않다가
    **커밋되자마자 자기 패턴 여덟 줄에 걸렸다** — «구멍이 0일 때 박는다»의 함정이다.
    """
    assert all(path.name != "check_forbidden.py" for path in FORBID.tracked())
    assert FORBID.survey() == []
