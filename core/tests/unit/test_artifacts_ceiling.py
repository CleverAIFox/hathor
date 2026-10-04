"""**수만 보는 천장은 결함을 기대값으로 얼린다** (D-0363).

`check_artifacts`의 `임시` · `조사중` 면제는 **수**였다(`TRANSIENT_CEILING = 1`). 이름은
독스트링에만 있었고 **코드가 그것을 안 읽었다** — 세샤트/토트 세션이 코드를 읽고 짚었다.

**`test_artifacts_ledger.py`에서 떼어 왔다** — 그쪽이 726줄로 상한 700을 넘었다 (D-0117).
"""

from __future__ import annotations

from tests.conftest import tool_module

LEDGER = tool_module("check_artifacts")


def test_이름_천장이_네_방향을_다_본다() -> None:
    """**수만 보는 천장은 결함을 기대값으로 얼린다** (D-0363 · 세샤트/토트 세션의 지적).

    `TRANSIENT_CEILING = 1`이던 동안 셋이 안 걸렸다 — ① 좋아져서 0이 되어도 천장 1이
    남아 **영원히 비어 있는 허가증**, ② 다른 계열로 **바뀌어도 수는 1 그대로**,
    ③ 이름이 바뀌어도 조용하다. 저쪽은 `WRONG_CEILING = 214`를 그렇게 박아 두고
    **그 214 중 164가 규칙의 결함**인 것을 몇 주 동안 못 봤다.
    """
    entries = LEDGER.load()
    kept = LEDGER.TRANSIENT_ALLOWED
    one = kept[0]

    assert LEDGER.named_ceiling(entries, LEDGER.TRANSIENT, kept, "T") == [], "그대로인데 운다"

    renamed = {("남의계열" if name == one else name): body for name, body in entries.items()}
    said = LEDGER.named_ceiling(renamed, LEDGER.TRANSIENT, kept, "T")
    assert len(said) == 2, f"이름이 바뀐 것을 못 본다: {said}"

    better = {
        name: ({**body, "state": "있음"} if body.get("state") == LEDGER.TRANSIENT else body)
        for name, body in entries.items()
    }
    assert LEDGER.named_ceiling(better, LEDGER.TRANSIENT, kept, "T"), "좋아진 것을 안 박는다"

    grown = dict(entries)
    extra = next(name for name in grown if name != one)
    grown[extra] = {**grown[extra], "state": LEDGER.TRANSIENT}
    assert LEDGER.named_ceiling(grown, LEDGER.TRANSIENT, kept, "T"), "늘어난 것을 못 본다"
