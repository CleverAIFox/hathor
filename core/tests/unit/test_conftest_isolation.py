"""**검사는 기기 상태에 의존하지 않는다** (D-0071 → D-0364).

격리가 `HATHOR_*` **접두사**였다. 손으로 고른 목록이고 정본(`.env.example`)과 갈려
있었다 — 선언 키 18개 중 셋만 지우고 열다섯은 쉘에서 그대로 들어왔다.

세샤트/토트 세션이 짚었다. 저쪽은 접두사 없는 변수 하나로 **41건이 깨졌고**, 그
변수를 쉘에 꽂으라 한 것이 **저장소 자신의 문서**였다.

**여기 유병률은 0으로 쟀다** — 열다섯과 원격 주소 둘을 전부 꽂고 2361건이 초록이었다.
그래서 이 시험이 막는 것은 병이 아니라 **갈림**이다 (D-0043).
"""

from __future__ import annotations

import os
import re

import pytest

from tests import conftest


def test_정본이_선언한_키를_전부_지운다() -> None:
    """**목록을 안 적는다** (GR-0.7). 정본이 선언한 것은 빠짐없이 덮인다."""
    declared = conftest.declared_env()

    assert len(declared) >= 15, f"`.env.example`에서 {len(declared)}개를 읽었다 — 그물이 비었다"
    assert "REDIS_URL" in declared, "접두사 밖의 키를 못 읽는다"
    assert "HATHOR_ARTIFACT_STORE" in declared


@pytest.mark.parametrize("key", ["REDIS_URL", "AMQP_URL", "S3_ENDPOINT_URL"])
def test_접두사_밖의_키도_픽스처가_지운다(key: str) -> None:
    """`isolate_machine_env`는 **autouse**다 — 이 시험이 도는 동안 이미 지워져 있다."""
    assert key not in os.environ, f"{key}가 살아 있다 — 격리가 접두사로 돌아갔다"


def test_정본을_못_읽으면_빈_집합이다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**없는 것을 0이라 말하지 않는다**는 여기선 반대다 — 못 읽으면 접두사만 남는다.

    `.env.example`이 없는 기기(배포 이미지)에서 **터지지 않아야** 한다. 그 경우를
    조용히 넘기는 것이 맞고, 선언 키를 **읽었다고** 적지 않는다.
    """
    monkeypatch.setattr(conftest, "ENV_EXAMPLE", conftest.ENV_EXAMPLE.parent / "없다.example")

    assert conftest.declared_env() == frozenset()
    assert re is not None
