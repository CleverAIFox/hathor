"""비밀정보 검사의 단위 검사 (D-0128).

**도구 자신을 검사한다** (D-0080). 이 검사는 **오탐이 곧 죽음**이다 — 첫 판에서
`TOKEN`을 넣었더니 파서 코드의 `TOKEN_AND`·`value_token`이 1600곳 잡혔고, 그 상태로
켰으면 다음 세션에 꺼졌을 것이다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "tools" / "check_secrets.py"
    spec = importlib.util.spec_from_file_location("check_secrets", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_secrets"] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _module()


def _scan(tmp_path, monkeypatch, name: str, text: str) -> list[str]:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    return CHECKER.check([name])


# ------------------------------------------------------------------ 잡는다


def test_값이_박힌_키를_잡는다(tmp_path, monkeypatch):
    problems = _scan(tmp_path, monkeypatch, "deploy.yml", "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7\n")
    assert len(problems) == 1
    assert "AWS_SECRET_ACCESS_KEY" in problems[0]


def test_env가_추적되면_잡는다(tmp_path, monkeypatch):
    """**`.gitignore`는 `git add -f`를 못 막는다.** 추적 목록을 직접 본다."""
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    problems = CHECKER.check([".env"])
    assert problems and "추적되고 있다" in problems[0]


def test_줄_번호를_적는다(tmp_path, monkeypatch):
    problems = _scan(tmp_path, monkeypatch, "a.yml", "\n\nDB_PASSWORD=진짜값\n")
    assert ":3:" in problems[0]


# ------------------------------------------------------------------ 안 잡는다


def test_예시_파일은_통과한다(tmp_path, monkeypatch):
    """**예시는 공유되라고 있다.** `change-me-min-8-chars`를 앞자리로 본다."""
    text = "MINIO_ROOT_PASSWORD=change-me-min-8-chars\nPOSTGRES_PASSWORD=change-me\n"
    assert _scan(tmp_path, monkeypatch, ".env.example", text) == []


def test_변수_참조는_대입이_아니다(tmp_path, monkeypatch):
    """`docker-compose.yml`이 쓰는 꼴. 안 빼면 셋이 오탐이다."""
    text = "      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-hathor}\n"
    assert _scan(tmp_path, monkeypatch, "docker-compose.yml", text) == []


def test_토큰_낱말은_안_본다(tmp_path, monkeypatch):
    """**오탐이 많은 검사는 꺼진다.** 실측 1600곳이었다."""
    text = "TOKEN_AND = '*'\nvalue_token = next(stream)\n"
    assert _scan(tmp_path, monkeypatch, "parser.py", text) == []


def test_소문자_이름은_안_본다(tmp_path, monkeypatch):
    """지역 변수는 비밀정보가 아니다. 환경 변수 꼴만 본다."""
    assert _scan(tmp_path, monkeypatch, "a.py", "api_key = compute()\n") == []


def test_패치_파일은_건너뛴다(tmp_path, monkeypatch):
    """패치는 다른 파일의 사본이며 **원본 쪽에서 이미 본다.**"""
    assert _scan(tmp_path, monkeypatch, "x.patch", "+DB_PASSWORD=진짜값\n") == []


# ------------------------------------------------------------------ 저장소


def test_저장소가_통과한다():
    """**지금 초록이 아니면 이 검사를 켤 수 없다.**"""
    names = CHECKER.tracked()
    assert names, "git 추적 목록을 못 읽었다"
    assert CHECKER.check(names) == []


def test_추적_목록을_실제로_읽는다():
    assert len(CHECKER.tracked()) > 50


@pytest.mark.parametrize("name", [".env"])
def test_금지_목록이_비어_있지_않다(name):
    assert name in CHECKER.FORBIDDEN
