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


def test_경로_인자를_실제로_찾는다():
    """검사가 아무것도 안 잡으면 통과해도 뜻이 없다."""
    found = _path_like_actions()
    assert len(found) >= 20, f"경로 인자를 {len(found)}개밖에 못 찾았다. 탐지가 망가졌다"


@pytest.mark.parametrize("label,action", _path_like_actions(), ids=lambda value: str(value))
def test_경로_인자는_저장소_루트로_풀린다(label, action):
    """**어느 디렉터리에서 실행하든 같은 곳을 가리켜야 한다** (D-0066 · D-0069).

    `type=resolve_path`가 없으면 현재 디렉터리 기준이 되고, 쓰는 명령과 읽는 명령이
    다른 곳을 보게 된다. 실제로 `ingest scan`이 쓴 것을 `ingest keys`가 못 찾았다.
    """
    if action.dest in {"profile", "features"}:
        pytest.skip("이름만 경로처럼 보이고 경로가 아니다")
    assert action.type is resolve_path, (
        f"`{label}`에 type=resolve_path가 없다. "
        "경로 인자는 저장소 루트 기준으로 풀려야 한다 (D-0069)"
    )


@pytest.mark.parametrize("label,action", _path_like_actions(), ids=lambda value: str(value))
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
