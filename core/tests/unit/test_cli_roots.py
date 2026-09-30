"""CLI가 공유하는 해결자 (D-0326).

**같은 다섯 줄이 네 번 복사돼 있었다** — `--priors`를 풀고 못 찾으면 찍는 블록이다.
넷 다 *"찾지 못했다. --priors로 경로를 준다"*만 냈고, **이미 준 사람에게 주라고 했다.**

`test_harmony_output_cli.py`가 700줄 상한에 닿아 여기로 왔다 (D-0117).
"""

from __future__ import annotations

from pathlib import Path

import pytest

Capture = pytest.CaptureFixture[str]


def test_상대_경로는_저장소_루트_기준이다(tmp_path: Path, capsys: Capture) -> None:
    """**`cd core`에서 `../var/...`를 주면 저장소 밖을 가리킨다** (D-0326).

    `resolve_path`가 상대 경로를 저장소 루트로 푸는 것은 D-0069가 정한 계약이다 —
    바꾸지 않고 **못 찾았을 때 푼 경로를 찍는다.**
    """
    from hathor.interfaces.cli.roots import resolve_priors
    from hathor.shared.config.paths import repo_root, resolve_path

    assert resolve_path("var/ingest/x.jsonl") == repo_root() / "var" / "ingest" / "x.jsonl"
    assert resolve_priors(tmp_path / "없다.jsonl", "other") is None
    said = capsys.readouterr().err
    assert str(tmp_path / "없다.jsonl") in said
    assert str(repo_root()) in said, "지금 루트가 어디인지 적어야 스스로 고칠 수 있다"


def test_준_경로가_있으면_그대로_쓴다(tmp_path: Path) -> None:
    """**있으면 아무 말도 안 한다.** 거짓 경보는 진짜 경보를 죽인다."""
    from hathor.interfaces.cli.roots import resolve_priors

    path = tmp_path / "있다.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    assert resolve_priors(path, "other") == path


def test_넷이_같은_자리를_쓴다() -> None:
    """**같은 블록이 네 번 복사돼 있었다** (D-0326).

    넷이면 한 곳만 고쳐지는 날이 온다 — D-0317 · D-0323 · D-0325가 겪은 자리다.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "hathor" / "interfaces" / "cli"
    users = [
        name
        for name in ("eval_vocabulary.py", "eval_output.py", "eval_priors.py")
        if "resolve_priors(" in (root / name).read_text(encoding="utf-8")
    ]
    assert len(users) == 3, f"resolve_priors를 안 쓰는 자리가 있다: {users}"
    for name in users:
        body = (root / name).read_text(encoding="utf-8")
        assert "사전 산출물을 찾지 못했다" not in body, f"{name}에 옛 블록이 남았다"


def test_믹스_바꿔치기는_부르는_쪽이_고른다() -> None:
    """**셋은 바꾸고 하나는 안 바꾼다** (D-0326).

    `mix`로 판정하는 셋은 사전을 `other`에서 찾는다. `eval time-drift`는 **안 바꾼다** —
    거기서 `--left mix`는 믹스 관측이고, 바꾸면 다른 것을 잰다. 넷을 한 함수로 모으며
    기본값으로 숨겼다면 그 하나가 조용히 달라졌을 자리다.
    """
    from pathlib import Path

    from hathor.infrastructure.keys_jsonl_store import priors_stem_set

    assert priors_stem_set("mix") == "other"
    assert priors_stem_set("bass") == "bass"

    root = Path(__file__).resolve().parents[2] / "hathor" / "interfaces" / "cli"
    drift = (root / "eval_priors.py").read_text(encoding="utf-8")
    assert "resolve_priors(args.priors, args.left)" in drift, "time-drift가 바꿔치기를 얻었다"
    for name in ("eval_vocabulary.py", "eval_output.py"):
        body = (root / name).read_text(encoding="utf-8")
        assert "priors_stem_set(" in body, f"{name}이 바꿔치기를 잃었다"
