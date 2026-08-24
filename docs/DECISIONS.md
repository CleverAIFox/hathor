# 결정 기록 (GR-0.2)

> **문서 4종** (D-0043) — 규약 `CONTRIBUTING.md` · 기획 `docs/DESIGN.md` ·
> 결정 `docs/DECISIONS.md` · 진입 `README.md`. **현재 문서: 결정.**

형식: 배경 / 후보 / 선택 / 근거 / 결과

**본문은 번호대별 조각에 있다** (O-30 · D-0080). 한 파일이 6000줄 또는 100건을
넘으면 `make split`이 다시 나눈다. **전체 색인은 `docs/DESIGN.md` 부록 A**이며
`tools/sync_decision_index.py`가 조각 전부를 긁어 생성한다.

<!-- 이 목록은 tools/split_decisions.py가 생성한다. 손으로 고치지 않는다. -->

| 조각 | 범위 | 건수 |
|---|---|---|
| [`D-0001-0050.md`](decisions/D-0001-0050.md) | D-0001~D-0050 | 50건 |
| [`D-0051-0100.md`](decisions/D-0051-0100.md) | D-0051~D-0100 | 50건 |
| [`D-0101-0150.md`](decisions/D-0101-0150.md) | D-0101~D-0113 | 13건 |

찾기:

```bash
grep -rn "D-0086" docs/decisions/
```
