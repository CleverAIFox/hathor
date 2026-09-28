"""**CLI 계약 검사** — 부류를 막는다 (D-0069).

### 왜 이 파일이 따로 있는가

같은 부류의 결함이 하루에 두 번 나왔다.

1. `chroma(harmonic=...)`가 `cq_chroma`로 안 넘어가 **조용히 무시됐다** (D-0064)
2. `ingest keys --out`에 `type`이 없어 **현재 디렉터리 기준으로 풀렸다** (D-0069).
   `ingest scan`은 저장소 루트 기준이라 쓰는 곳과 읽는 곳이 갈렸다

둘 다 **"인자가 선언돼 있으나 의도대로 걸리지 않는다"**는 한 부류다. 개별 수정은
같은 부류의 다음 사례를 못 막는다 — 실제로 네 시간 만에 재발했다.

`import-linter`의 아키텍처 계약 넷은 한 번도 깨지지 않았다. 규율이 좋아서가 아니라
**기계가 매번 보기 때문이다.** 여기서 같은 것을 CLI 인자에 한다.

### 규칙

**경로처럼 보이는 인자는 `resolve_path`를 거쳐야 한다.** 그러면 어느 디렉터리에서
실행하든 같은 곳을 가리킨다. 새 명령을 추가할 때 잊으면 이 검사가 잡는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from hathor.interfaces.cli.main import build_parser
from hathor.interfaces.cli.tables import REPLAY_DEFAULTS, replay_refusal
from hathor.shared.config.paths import repo_path_hints, resolve_path


def _walk_parsers(parser: argparse.ArgumentParser) -> list[tuple[str, argparse.ArgumentParser]]:
    """서브파서를 전부 펼친다. `("ingest keys", 파서)` 꼴로 낸다."""
    found: list[tuple[str, argparse.ArgumentParser]] = [("", parser)]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                for suffix, deeper in _walk_parsers(sub):
                    found.append((f"{name} {suffix}".strip(), deeper))
    return found


def _path_like_actions() -> list[tuple[str, argparse.Action]]:
    """경로처럼 보이는 인자를 전부 모은다."""
    hits: list[tuple[str, argparse.Action]] = []
    for command, parser in _walk_parsers(build_parser()):
        for action in parser._actions:
            if not action.option_strings or action.dest == "help":
                continue
            name = action.option_strings[-1].lstrip("-").replace("-", "_")
            if any(hint in name for hint in repo_path_hints()):
                hits.append((f"{command} {action.option_strings[-1]}".strip(), action))
    return hits


def _case_id(value: object) -> str:
    """시험 이름은 **라벨만** 쓴다 (D-0238).

    `str(action)`은 `type=<function resolve_path at 0x7f...>`를 물고 온다. 주소는 프로세스마다
    다르므로 **이름이 실행마다 달라진다** — 병렬 실행(`-n`)이 «워커마다 다른 시험을 모았다»며
    죽고, 로그의 이름으로는 같은 시험을 두 번 못 부른다.
    """
    return value if isinstance(value, str) else ""


def test_경로_인자를_실제로_찾는다():
    """검사가 아무것도 안 잡으면 통과해도 뜻이 없다."""
    found = _path_like_actions()
    assert len(found) >= 20, f"경로 인자를 {len(found)}개밖에 못 찾았다. 탐지가 망가졌다"


@pytest.mark.parametrize("label,action", _path_like_actions(), ids=_case_id)
def test_경로_인자는_저장소_루트로_풀린다(label, action):
    """**어느 디렉터리에서 실행하든 같은 곳을 가리켜야 한다** (D-0066 · D-0069).

    `type=resolve_path`가 없으면 현재 디렉터리 기준이 되고, 쓰는 명령과 읽는 명령이
    다른 곳을 보게 된다. 실제로 `ingest scan`이 쓴 것을 `ingest keys`가 못 찾았다.
    """
    if action.dest in {"profile", "features"}:
        # 값이 `이름=경로` 복합이라 argparse `type`을 못 붙인다. **대신 푸는 자리가 있고**
        # 그것을 `test_eval_cli.py::test_features_argument_resolves_against_repo_root`가
        # 지킨다 — 이 건너뜀이 D-0233의 결함을 가렸다.
        pytest.skip("이름만 경로처럼 보이거나 `이름=경로` 복합이다 (D-0233)")
    assert action.type is resolve_path, (
        f"`{label}`에 type=resolve_path가 없다. "
        "경로 인자는 저장소 루트 기준으로 풀려야 한다 (D-0069)"
    )


@pytest.mark.parametrize("label,action", _path_like_actions(), ids=_case_id)
def test_경로_기본값은_문자열이어야_한다(label, action):
    """**argparse는 기본값이 문자열일 때만 `type`을 적용한다** (D-0069).

    `Path("var/ingest")`를 기본값으로 두면 `type=resolve_path`를 붙여도 기본값에는
    안 걸린다. `--out`을 명시했을 때와 생략했을 때가 다른 곳을 가리키게 된다.
    """
    if action.default is None or isinstance(action.default, str):
        return
    pytest.fail(
        f"`{label}`의 기본값이 {type(action.default).__name__}다. "
        "문자열이어야 type이 적용된다 (D-0069)"
    )


def test_쓰는_명령과_읽는_명령이_같은_곳을_본다(monkeypatch, tmp_path):
    """**이것이 실제로 터진 사고다** (D-0069).

    `ingest scan --out var/ingest`가 쓴 것을 `ingest keys --out var/ingest`가 못
    찾았다. 하나는 저장소 루트 기준, 다른 하나는 현재 디렉터리 기준이었다.
    """
    monkeypatch.chdir(tmp_path)
    scan = build_parser().parse_args(["ingest", "scan"])
    keys = build_parser().parse_args(["ingest", "keys"])
    assert Path(scan.out) == Path(keys.out)
    assert Path(scan.out).is_absolute()


def test_현재_디렉터리를_바꿔도_기본값이_같다(monkeypatch, tmp_path):
    first = build_parser().parse_args(["ingest", "keys"]).out
    monkeypatch.chdir(tmp_path)
    assert build_parser().parse_args(["ingest", "keys"]).out == first


# ------------------------------------------------------------------ 도구 (D-0153)

TOOLS = Path(__file__).resolve().parents[3] / "tools"

PATH_ARGUMENTS = ("--out", "--root", "--series", "--priors", "--store")


def test_도구의_경로_인자도_저장소_루트로_풀린다():
    """**D-0069가 CLI에만 걸려 있었다** (D-0153).

    `probe_onsets`가 `cd core`에서 돌자 `core/var/ingest`를 찾았다. 산출물은
    저장소 루트 아래에 있으므로 **현재 디렉터리 기준으로 두면 조용히 빈손이 된다.**

    argparse를 실행 없이 들여다볼 수 없어 **본문에 `ROOT`가 있는지로 본다.**
    거칠지만 이 부류를 잡는다.
    """
    problems = []
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        takes_path = any(f'"{name}"' in text for name in PATH_ARGUMENTS)
        if takes_path and "ROOT" not in text:
            problems.append(path.name)
    assert not problems, f"경로 인자를 받는데 저장소 루트를 안 쓴다: {problems}"


def test_경로_인자_목록이_비어_있지_않다():
    assert PATH_ARGUMENTS


# ------------------------------------------------------------------ 재판정 거부 (D-0191)


def _keys_args(**given: object) -> argparse.Namespace:
    """`ingest keys` 기본값 그대로 파싱하고 준 것만 바꾼다.

    **손으로 기본값을 적지 않는다** — 파서가 정본이고, 여기 베끼면 두 곳이 어긋난다
    (D-0043). 기본값이 바뀌면 이 검사가 따라 움직인다.
    """
    parsed = build_parser().parse_args(["ingest", "keys", "--replay", "x.jsonl"])
    for name, value in given.items():
        setattr(parsed, name, value)
    return parsed


def test_기본값이면_거부하지_않는다():
    """**기본으로 돌리는 재판정은 막히면 안 된다.**"""
    assert replay_refusal(_keys_args()) == ""


def test_재판정이_쓰는_둘은_거부하지_않는다():
    """`--harmonic` · `--profile`은 저장된 크로마에서도 걸린다 (D-0191)."""
    assert replay_refusal(_keys_args(harmonic=0.3)) == ""
    assert replay_refusal(_keys_args(profile="temperley")) == ""


@pytest.mark.parametrize(
    ("name", "value", "flag"),
    [
        ("gamma", 0.5, "--gamma"),
        ("aggregate", "median", "--aggregate"),
        ("window_seconds", 5.0, "--window-seconds"),
        ("chroma", "linear", "--chroma"),
        ("tuning", True, "--tuning"),
        ("separate", True, "--separate"),
        ("halves", True, "--halves"),
        ("series", 1.0, "--series"),
    ],
)
def test_못_쓰는_손잡이를_이름으로_말한다(name, value, flag):
    """**조용히 무시하면 *"효과가 없다"*로 읽힌다** (D-0191).

    `--gamma 0.5`와 `--aggregate median`이 기본값과 소수점까지 같은 표를 냈고,
    그것을 *"이 손잡이는 효과가 없다"*로 읽을 뻔했다.
    """
    refusal = replay_refusal(_keys_args(**{name: value}))
    assert flag in refusal
    assert "--harmonic" in refusal and "--profile" in refusal


def test_여러_개면_전부_말한다():
    """**첫 하나에서 멈추지 않는다.** 한 번에 다 보여야 한 번에 고친다."""
    refusal = replay_refusal(_keys_args(gamma=0.5, tuning=True))
    assert "--gamma" in refusal and "--tuning" in refusal


def test_거부_목록이_파서와_맞다():
    """**기본값을 베껴 적지 않았는가.** 두 곳이 어긋나면 조용히 통과한다 (D-0043)."""
    parsed = build_parser().parse_args(["ingest", "keys", "--replay", "x.jsonl"])
    for flag, name, default in REPLAY_DEFAULTS:
        assert hasattr(parsed, name), f"{flag}가 파서에 없다"
        assert getattr(parsed, name) == default, f"{flag}의 기본값이 어긋난다"


# ------------------------------------------------- 등재와 배선 (D-0204 · D-0273)

REGISTERED = 27
"""등재된 하위 명령의 수. 늘리려면 결정 기록이 필요하다 (D-0118).

**세는 값이 있어야 «전부»가 뜻을 갖는다.** 등재표와 파서를 견주기만 하면 **둘 다 빈**
경우에도 통과한다 — D-0230이 검사 도구에서 확인한 자리다."""


def _parser_commands(parser: argparse.ArgumentParser, prefix: str = "") -> list[str]:
    """파서가 실제로 아는 하위 명령. 묶음은 `묶음 하위` 꼴로 펼친다."""
    found: list[str] = []
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, sub in action.choices.items():
            label = f"{prefix}{name}".strip()
            found.extend(_parser_commands(sub, f"{label} ") or [label])
    return found


def test_등재표와_파서가_같다():
    """**등재와 배선이 한 표를 읽는다** (D-0273).

    D-0204 이래 이 자리를 지킨 검사는 `main.py`의 **글자를 정규식으로 긁어** «배선에 없는
    이름이 정확히 하나여야 한다»고 말했다. 위험을 없앤 것이 아니라 하나로 못 박은 것이고,
    `add_parser`를 함수로 감싼 둘(`eval clap` · `ingest onsets`)은 **그 정규식에 아예 안
    잡혔다** — 그 둘의 배선을 빼먹으면 검사는 초록이었다.

    이제 글자가 아니라 표를 본다.
    """
    from hathor.interfaces.cli.main import entries
    from hathor.interfaces.cli.registry import names

    registered = names(entries())
    assert len(registered) == REGISTERED, f"등재가 {len(registered)}개다"
    assert sorted(_parser_commands(build_parser())) == sorted(registered)


def test_모든_등재에_러너가_있다():
    """**떨어지는 기본이 없다** (D-0273). 표에 있으면 부를 것이 있다."""
    from hathor.interfaces.cli.main import entries
    from hathor.interfaces.cli.registry import Group

    for entry in entries():
        commands = entry.commands if isinstance(entry, Group) else (entry,)
        for command in commands:
            assert callable(command.run), f"{command.name}에 러너가 없다"
            assert command.help.strip(), f"{command.name}에 도움말이 없다"


def test_표에_없는_이름은_죽는다():
    """**양성 대조다** (D-0230). 조용히 다른 명령을 돌리지 않는다.

    D-0204에서 `ingest all`이 배선에 없어 **스캔이 돌았고** `scan-*.jsonl`이 하나 더
    생겼다. 지금은 표가 하나라 그 상태를 만들 수 없으므로 **일부러 만들어** 먹인다.
    """
    from hathor.interfaces.cli.registry import Command, Group, resolve

    table = (Group("ingest", "h", "ingest_command", (Command("scan", "h", lambda _: None, int),)),)
    args = argparse.Namespace(command="ingest", ingest_command="all")
    with pytest.raises(SystemExit, match="ingest all"):
        resolve(table, args)
    with pytest.raises(SystemExit, match="없는것"):
        resolve(table, argparse.Namespace(command="없는것"))


def test_D0204의_그_명령이_제_러너로_간다():
    """`ingest all`이 스캔으로 떨어지지 않는다 (D-0204)."""
    from hathor.interfaces.cli import main
    from hathor.interfaces.cli.registry import resolve

    args = build_parser().parse_args(["ingest", "all"])
    assert resolve(main.entries(), args) is main._run_ingest_all


# ------------------------------- 계산이 표시 계층에 있다 (GR-2.2 · D-0278)

COMPUTING = (
    "cli/ingest_keys.py",
    "cli/ingest_onsets.py",
    "cli/keys_report.py",
    "cli/main.py",
    "cli/tables.py",
)
"""`interfaces`에서 `numpy`를 들이는 파일. **다섯이고 0으로 간다** (D-0278).

### 왜 이것을 세나

GR-2.2가 *"interfaces에 로직 금지"*라고 적혀 있고 `main.py`가 4161줄이 된 것이 그 규약이
검사 없이 잊혔다는 증거였다 (D-0116 · D-0117). 그래서 **길이**에 래칫이 붙었고
(`check_file_size`) **방향**에 계약이 붙었다 (`import-linter`). 그런데 **깊이는 아무도 안
봤다** — 표시 계층이 얼마나 계산하는지다.

사용자가 그것을 지적했다 — *"아키텍처가 완전 개 엉망진창이네. 개발 원칙 철저하게 하자고
했는데 main에다가 다 짱박아 놨었네."* 실측 —

| 계층 | `numpy`를 들이는 파일 |
|---|---|
| `domain` | 13 / 45 |
| `application` | 12 / 21 |
| `infrastructure` | 12 / 27 |
| **`interfaces`** | **5 / 24** |

`interfaces`가 5494줄로 가장 큰 계층이지만 **그것만으로는 로직이라고 못 한다** — 문장 수준
호출의 82%가 `print`·`add_argument`이고 이 저장소는 근거를 문서 문자열에 적는다. **`numpy`는
다르다.** 수를 계산하지 않으면 들일 이유가 없다.

### 왜 래칫인가

다섯을 한 판에 옮기면 계산이 어느 계층으로 가야 하는지를 다섯 번 동시에 판단해야 한다.
**줄어들기만 하는 수**로 두면 한 판에 하나씩 옳게 옮길 수 있고, 늘리려면 결정 기록이
필요하다 (D-0118). `check_file_size`가 예외표를 내리는 것과 같은 규율이다."""


def computing_files() -> list[str]:
    """`interfaces`에서 `numpy`를 들이는 파일. 경로로 낸다."""
    base = TOOLS.parent / "core" / "hathor" / "interfaces"
    return sorted(
        path.relative_to(base).as_posix()
        for path in base.rglob("*.py")
        if "import numpy" in path.read_text(encoding="utf-8")
    )


def test_표시_계층이_계산하는_자리를_센다():
    """**D-0278의 강제자.** 줄면 이 목록을 줄이고, 늘리려면 결정 기록을 쓴다."""
    found = computing_files()
    assert found == list(COMPUTING), f"목록이 어긋난다: {found}"


def test_계산_자리_목록이_비어_있지_않다():
    """**세는 그물이 비면 «0건»이 거짓으로 참이 된다** (D-0230)."""
    assert COMPUTING, "목록이 비었다. 0이 되면 이 시험을 못으로 바꾼다"
