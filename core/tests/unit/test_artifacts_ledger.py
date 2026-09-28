"""산출물 대장과 실물 대조 (D-0266).

### 왜 이 파일이 생겼나

사용자가 `make ship`의 한 줄을 보고 물었다 — *"교두보에 1090개 이거 맞나? 1004개가
아니라?"* **저장소가 그 질문에 답할 수 없었다.** 선언이 없으면 «맞나»는 물을 수 없는
질문이고, 있는 것을 세는 것과 있어야 할 것과 대조하는 것은 다르다.

파이어레인의 데이터 규율(R2 · R3 · R4)을 산출물에 옮긴 판이다.
"""

from __future__ import annotations

from pathlib import Path

from hathor.shared.config.paths import repo_root
from tests.conftest import tool_module as _tool

ROOT = repo_root()


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
            "state": "있음",
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
            "state": "있음",
        }
    }
    assert [line for line in LEDGER.check_ledger(fiction) if "없는 파일" in line]


def test_칸이_빠지면_잡는다() -> None:
    assert [line for line in LEDGER.check_ledger({"빈계열": {}}) if "`what` 칸이 없다" in line]


def test_대장에_없는_계열을_격리로_판정한다(tmp_path: Path) -> None:
    """**R3. 등록되지 않은 산출물은 없는 산출물이다.**

    새 계열을 내면서 대장을 안 쓰는 길을 막는다 — 천장이 0이다.
    """
    (tmp_path / "묶음-20260101T000000Z.jsonl").touch()
    (tmp_path / "낯선계열").mkdir()
    entries: dict[str, dict[str, object]] = {
        "묶음-*.jsonl": {"state": "있음"},
        "없는것": {"state": "있음"},
    }

    seen = LEDGER.audit(entries, tmp_path)

    assert seen.normal == 1
    assert seen.missing == ["없는것"]
    assert seen.orphan == ["낯선계열"]
    assert LEDGER.QUARANTINE_CEILING == 0


def test_스탬프를_계열로_접는다(tmp_path: Path) -> None:
    """실행마다 이름이 다르다. **접지 않으면 매번 격리 대상이 된다.**"""
    for stamp in ("20260101T000000Z", "20260102T111111Z", "20260103T222222Z"):
        (tmp_path / f"keys-{stamp}.series").mkdir()

    seen = LEDGER.folded(tmp_path)

    assert set(seen) == {"keys-*.series"}
    assert seen["keys-*.series"].endswith(".series"), "**재려면 실물 이름이 필요하다** (D-0269)"


def test_못_쟀으면_0건이_아니다() -> None:
    """**파이어레인 `lakecheck`의 규율** — *"프로브가 잴 수 없으면 0건이 아니라 빨간불이다."*

    `var/`가 없는 기기에서 «격리 0건»을 찍으면 그것은 통과가 아니라 **안 본 것이다.**
    """
    source = (ROOT / "tools" / "check_artifacts.py").read_text(encoding="utf-8")
    body = source.split("def main(")[1]

    assert "is_dir()" in body, "루트가 있는지 안 본다"
    assert "산출물이 있는 기기에서 돌린다" in body


# ------------------------------------------------- 첫 실행이 잡은 것 (D-0266 정정)


def test_계열_이름이_실물_그대로다() -> None:
    """**첫 판의 대장이 어간만 적었다** (D-0266).

    `scan-*`이라고 적었더니 실물은 `scan-*.jsonl`·`scan-*.failures.jsonl`·
    `scan-*.summary.json` 셋이었고, **같은 것이 «결손»과 «격리 대상»으로 동시에 떴다.**
    이름을 지어서 적으면 안 된다 — 저장 코드가 붙이는 접미사를 그대로 쓴다.
    """
    names = set(LEDGER.load())
    store = ROOT / "core" / "hathor" / "infrastructure"

    suffixes = {
        "scan": ("jsonl", "failures.jsonl", "summary.json"),
        "resolve": ("resolve.jsonl", "resolve.summary.json"),
    }
    for stem, tails in suffixes.items():
        assert f"{stem}-*" not in names, f"{stem}-*는 어간이다. 접미사까지 적는다"
        for tail in tails:
            assert f"{stem}-*.{tail}" in names, f"{stem}-*.{tail}이 대장에 없다"

    source = (store / "jsonl_scan_store.py").read_text(encoding="utf-8")
    for tail in ('SUMMARY_SUFFIX = ".summary.json"', 'FAILURES_SUFFIX = ".failures.jsonl"'):
        assert tail in source, "저장 코드의 접미사가 바뀌었다 — 대장을 다시 본다"


def test_양쪽을_본다(tmp_path: Path) -> None:
    """**로컬은 부분 사본이어도 된다** (D-0266).

    `make artifacts-pull`의 기본이 `keys,eval`뿐이다. 한쪽만 보면 **정상을 결손으로
    찍고**, 그런 검사는 사람이 끈다 (D-0126 · D-0129).
    """
    local, store = tmp_path / "여기", tmp_path / "교두보"
    local.mkdir()
    store.mkdir()
    (store / "mert-layers").mkdir()
    entries: dict[str, dict[str, object]] = {"mert-layers": {"state": "있음"}}

    assert LEDGER.audit(entries, local).missing == ["mert-layers"], "한쪽만 보면 결손이다"
    assert LEDGER.audit(entries, local, store).missing == [], "양쪽을 보면 정상이다"


def test_미생성은_결손이_아니다(tmp_path: Path) -> None:
    """`taste`는 취향 라벨이고 **아직 하나도 안 모았다** (D-0028)."""
    entries: dict[str, dict[str, object]] = {"taste": {"state": "미생성"}}

    seen = LEDGER.audit(entries, tmp_path)

    assert seen.missing == []
    assert seen.orphan == []
    assert seen.stale == []


def test_미생성인데_실물이_있으면_선언이_낡았다(tmp_path: Path) -> None:
    """**파이어레인 `lakecheck` L1이다** — *"reserved인데 파일이 있나."*

    라벨을 모으기 시작하면 백업 의무가 살아난다. 선언이 안 따라오면 여기가 운다.
    """
    (tmp_path / "taste").mkdir()
    entries: dict[str, dict[str, object]] = {"taste": {"state": "미생성"}}

    seen = LEDGER.audit(entries, tmp_path)

    assert seen.stale == ["taste"], "낡은 선언은 격리와 다른 자리에 든다 (D-0268)"
    assert seen.orphan == [], "**이미 선언된 것을 또 등재하라고 하면 키가 겹친다**"


def test_폐기는_왜_지웠는지를_든다() -> None:
    """**만드는 도구를 일부러 없앤 것과 잃어버린 것은 다르다** (D-0266).

    D-0216이 `probe_listenbrainz.py`를 지우면서 산출물 세 줄은 남겼다. 그 세 줄이
    D-0216의 «자료» 칸이 가리키는 실물이며 (D-0265) 지우면 판정의 근거가 사라진다.
    """
    retired = {
        name: entry for name, entry in LEDGER.load().items() if entry["regen"] == LEDGER.RETIRED
    }
    assert retired, "폐기 계열이 하나는 있어야 이 시험이 뜻이 있다"
    for name, entry in retired.items():
        assert entry["state"] == LEDGER.RETIRED, name
        assert isinstance(entry["why"], str) and "D-02" in entry["why"], f"{name}이 근거를 안 든다"

    broken = {"버린것": {**next(iter(retired.values())), "why": ""}}
    assert [line for line in LEDGER.check_ledger(broken) if "왜 지웠는지" in line]


def test_교두보_경로_파서가_하나다() -> None:
    """**`.env`를 읽는 파서가 둘이면 갈린다** (D-0199). 정본은 `sync_artifacts`다."""
    source = (ROOT / "tools" / "check_artifacts.py").read_text(encoding="utf-8")

    assert "sync_artifacts.store_root()" in source
    assert "HATHOR_ARTIFACT_STORE" not in source, "환경변수를 직접 읽으면 파서가 둘이 된다"


# ------------------------------------------- 추론을 못 하게 만든다 (D-0268)


def test_미등재_계열의_정체를_재_준다(tmp_path: Path) -> None:
    """**이름만으로는 옛 잔재와 어제 만든 것을 못 가른다** (D-0268).

    작성자가 세 판 연속으로 정체를 추론했고 세 번 다 틀렸다. 추론을 못 하게 하려면
    **추론할 필요가 없게** 만들어야 한다 — 파일 수 · 크기 · 최근 시각을 같이 찍는다.
    """
    (tmp_path / "낯선것").mkdir()
    (tmp_path / "낯선것" / "a.npz").write_bytes(b"x" * 2048)

    detail = LEDGER.measure(tmp_path, "낯선것")

    assert "파일 1개" in detail
    assert "최근 20" in detail


def test_빈_것과_있는_것을_가른다(tmp_path: Path) -> None:
    """`taste`가 **빈 폴더인지 라벨이 든 폴더인지**가 백업 의무를 가른다."""
    (tmp_path / "빈폴더").mkdir()

    assert LEDGER.measure(tmp_path, "빈폴더") == "빈 것"


def test_등재_자리를_찍어_준다() -> None:
    """붙여 넣을 수 있는 TOML이어야 한다 — 손으로 다시 치면 또 틀린다."""
    import tomllib

    block = LEDGER.skeleton("낯선것", "파일 3개 · 1.0MB · 최근 2026-09-27")
    parsed = tomllib.loads(block)["series"]["낯선것"]

    assert set(parsed) >= set(LEDGER.REQUIRED)
    assert parsed["what"].startswith(LEDGER.TODO)


def test_TODO가_남으면_거부한다() -> None:
    """**붙여 넣고 잊을 수 없다** (D-0268). 그 길이 열려 있으면 대장은 이름만 남는다."""
    import tomllib

    pasted = tomllib.loads(LEDGER.skeleton("낯선것", "파일 3개"))["series"]
    problems = LEDGER.check_ledger(pasted)

    assert [line for line in problems if LEDGER.TODO in line]


# ------------------------------------- 모른다고 세는 자리 (D-0269)


def test_접힌_이름으로는_못_잰다(tmp_path: Path) -> None:
    """**접힌 이름은 경로가 아니다** (D-0269).

    `keys-*.keys.jsonl.mix-other`의 `*`는 리터럴이고 그런 파일은 없다. 첫 판은 접힌
    이름을 그대로 `measure()`에 넘겨 **스탬프가 있는 계열마다 «못 쟀다»를 찍었다** —
    스탬프 없는 계열만 우연히 통했다.
    """
    (tmp_path / "keys-20260101T000000Z.keys.jsonl.mix-other").write_bytes(b"x" * 16)

    seen = LEDGER.folded(tmp_path)

    assert seen == {"keys-*.keys.jsonl.mix-other": "keys-20260101T000000Z.keys.jsonl.mix-other"}
    assert LEDGER.measure(tmp_path, seen["keys-*.keys.jsonl.mix-other"]) != "못 쟀다"


def test_조사중은_결손이_아니고_천장이_있다() -> None:
    """**모른다고 세는 것이 추론을 하나 더 얹는 것보다 낫다** (D-0269).

    작성자가 이 대장에서 네 판 연속 정체를 추론하고 네 번 다 틀렸다. 그래서 «모른다»에
    자리를 주되 **천장을 둔다** — `해당 없음`이 첫 번째 쓰레기통이 된 것을 봤다 (D-0265).
    """
    studying = [
        name for name, entry in LEDGER.load().items() if entry.get("state") == LEDGER.UNDER_STUDY
    ]

    assert len(studying) <= LEDGER.UNDER_STUDY_CEILING
    assert LEDGER.UNDER_STUDY_CEILING == 1, "늘리려면 결정 기록이 필요하다 (D-0118)"


def test_조사중은_무엇을_확인했는지_적는다() -> None:
    """**그것이 없으면 «조사중»은 «안 봤다»의 다른 이름이다** (D-0269)."""
    for name, entry in LEDGER.load().items():
        if entry.get("state") != LEDGER.UNDER_STUDY:
            continue
        assert entry["regen"] == LEDGER.UNKNOWN, name
        assert "남은 것" in str(entry["why"]), f"{name}이 다음 손이 볼 자리를 안 적는다"


def test_조사중인데_사유가_없으면_잡는다() -> None:
    """**양성 대조.** 이 검사가 무엇을 잡는지 본다 (D-0230)."""
    base = {
        "what": "무엇",
        "made": "core/hathor/infrastructure/keys_jsonl_store.py",
        "regen": LEDGER.UNKNOWN,
        "reads": ["미투입 — 정체가 풀리면"],
        "store": True,
        "state": LEDGER.UNDER_STUDY,
    }
    assert [line for line in LEDGER.check_ledger({"x": base}) if "무엇을 확인했는지" in line]
    with_why = {"x": {**base, "why": "확인했다"}}
    assert [line for line in LEDGER.check_ledger(with_why) if "남은 것" in line]


def test_ship이_대장_판정을_수로_찍는다() -> None:
    """**가리키기만 하면 안 본다** (D-0269).

    작성자가 대장을 네 판 연속 틀린 채 내보냈고 **넷 다 `--audit` 한 번이면 그 자리에서
    드러났다.** 막지는 않는다 — 숫자를 눈앞에 두는 것이 요점이다.
    """
    source = (ROOT / "tools" / "ship.py").read_text(encoding="utf-8")

    assert "check_artifacts.py" in source
    assert "--audit" in source


# ------------------------------- `reads`가 실재하는 명령인가 (O-69 닫힘 · D-0274)


def _commands() -> tuple[set[str], set[str]]:
    """(등재된 하위 명령 전부, 최상단 이름). **정본은 `entries()`다** (D-0273)."""
    from hathor.interfaces.cli.main import entries
    from hathor.interfaces.cli.registry import names

    registered = set(names(entries()))
    return registered, {one.split(" ")[0] for one in registered}


def reads_that_lie() -> list[str]:
    """`reads`가 든 «명령»인데 등재표에 없는 것. 계열 이름과 함께 낸다."""
    registered, tops = _commands()
    found: list[str] = []
    for series, entry in sorted(LEDGER.load().items()):
        for raw in entry["reads"]:
            words = [one for one in str(raw).split() if not one.startswith("-")]
            if not words or words[0] not in tops:
                continue  # 도구 경로 · 결정 번호 · 「미투입」은 명령이 아니다
            if not any(" ".join(words[:depth]) in registered for depth in (2, 1)):
                found.append(f"{series}: {raw}")
    return found


def test_읽는_이가_실재하는_명령이다() -> None:
    """**대장이 없는 명령을 읽는 이로 들고 있었다** (D-0274).

    넷이었다.

    | 계열 | 적혀 있던 것 | 실제 |
    |---|---|---|
    | `keys-*.keys.jsonl` | `eval priors` · `eval order` | 그런 명령이 없다 — **모듈 이름이다** |
    | `keys-*.series` | `eval order` | `eval harmony-order` |
    | `keys-*.onsets` | `eval priors --onsets` | **그런 깃발이 없다** — `probe_onsets.py`가 읽는다 |

    `eval_priors.py` · `eval_order.py`는 **파일 이름**이고 그 안에 `eval harmony-prior` ·
    `eval time-drift` · `eval harmony-order`가 들어 있다. 대장을 쓴 것이 작성자이므로
    **작성자가 모듈 이름을 명령으로 적은 것**이다.

    **D-0273이 등재표를 만들어서 이제 대조할 수 있다.** 그 전에는 명령 이름이 `build_parser`
    599줄에 흩어져 있어 «실재하는가»를 물을 자리가 없었다.

    **이 검사의 한계를 적어 둔다** — 있는 명령을 틀리게 적은 것은 못 잡는다. `keys-*.series`가
    `eval time-drift`를 들고 있었고 그 명령은 실재하지만 **그 산출물을 안 읽는다** —
    `eval_priors.py`에 「series」가 한 번도 안 나온다. 그것은 눈으로 찾았다.
    """
    assert reads_that_lie() == []


def test_그물이_거짓말을_잡는가() -> None:
    """**양성 대조** (D-0230). 없는 명령을 심어 먹인다."""
    registered, _tops = _commands()
    assert "eval harmony-order" in registered
    assert "eval order" not in registered, "«eval order»가 생겼으면 위 시험의 근거가 바뀐다"


def test_읽는_기본값이_산_계열을_가리킨다() -> None:
    """**O-69가 바로 이것이었다** (D-0274).

    `--features`를 안 준 네 자리가 `mert-layers`를 열었고 그 계열은 **어디에도 없다.**
    대장이 생긴 뒤에도 아무도 «코드의 기본값이 대장에서 산 계열인가»를 안 물었다.

    이제 묻는다. 기본값이 가리키는 이름은 **대장에 있고 `state`가 «있음»이어야 한다.**
    """
    from hathor.interfaces.cli.roots import DEFAULT_FEATURE_DIRNAME

    entries = LEDGER.load()
    assert DEFAULT_FEATURE_DIRNAME in entries, f"기본값 {DEFAULT_FEATURE_DIRNAME}이 대장에 없다"
    assert entries[DEFAULT_FEATURE_DIRNAME]["state"] == "있음"


READER_STORES = 0
"""`args.features`를 받아 저장소를 **직접** 여는 읽는 자리. **0이다** (D-0274).

읽는 쪽은 `open_feature_source`를 거쳐야 한다 — 그것이 모양을 보고 인덱스냐 묶음이냐를
고른다 (D-0233). 넷 중 하나만 거치고 있었고, 그래서 `search`·`eval fusion`·`taste compare`는
**`--features`로 묶음을 줘도 못 읽었다.** 쓰는 쪽(`eval layers` · `eval mfcc` · `eval clap` ·
`lyrics extract`)은 인덱스와 배치 잠금이 필요하므로 직접 연다."""


def reader_stores() -> list[str]:
    """`--features`를 읽으면서 저장소를 직접 여는 **읽는** 자리. 파일:줄로 낸다.

    **쓰는 쪽은 배치 잠금을 든다** — `NpzFeatureStore.batch_lock()`이다 (D-0022). 그것이
    파일 이름보다 나은 판별이다. `lyrics extract`는 `main.py` 안의 쓰는 쪽이라 이름으로
    가르면 못 가른다 — 첫 판에 그렇게 짰다가 이 시험에 걸렸다.
    """
    import ast

    found: list[str] = []
    base = ROOT / "core" / "hathor"
    for path in sorted(base.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "args.features" not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.unparse(node)
            if "batch_lock" in body:
                continue  # 쓰는 쪽이다
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                name = ast.unparse(inner.func)
                if name not in ("NpzFeatureStore", "BundleFeatureSource"):
                    continue
                if "args.features" in ast.unparse(inner):
                    where = path.relative_to(base).as_posix()
                    found.append(f"{where}:{inner.lineno} {node.name}")
    return found


def test_읽는_쪽은_모양을_보고_고른다() -> None:
    """**D-0274의 강제자.** 읽는 쪽 넷이 이제 다 `open_feature_source`를 지난다."""
    assert reader_stores() == [], f"직접 여는 자리: {reader_stores()}"
