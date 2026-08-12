"""정규화 판정 규칙 테스트 (D-0019).

임계값은 실측으로 정했다. 이 테스트가 그 근거를 고정한다.
"""

from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.domain.services.lookup_verdict import (
    DurationCandidate,
    judge_scores,
    narrow_by_duration,
)


def test_격차가_크면_resolved():
    # 실측: BIGBANG 100 vs 노르웨이 밴드 BigBang 71
    assert judge_scores(100, 71).state is ResolutionState.RESOLVED


def test_격차가_좁으면_ambiguous():
    # 실측: Dan + Shay 100 vs Justin Bieber 99
    assert judge_scores(100, 99).state is ResolutionState.AMBIGUOUS


def test_동점이면_ambiguous():
    # 실측: 이준 100 vs 이준 100 (동명이인)
    assert judge_scores(100, 100).state is ResolutionState.AMBIGUOUS


def test_점수가_낮으면_격차와_무관하게_unresolved():
    assert judge_scores(62, 0).state is ResolutionState.UNRESOLVED


def test_경계값_격차_10은_resolved():
    assert judge_scores(100, 90).state is ResolutionState.RESOLVED


def test_경계값_격차_9는_ambiguous():
    assert judge_scores(100, 91).state is ResolutionState.AMBIGUOUS


def test_판정_근거_점수가_보존된다():
    verdict = judge_scores(100, 71)
    assert (verdict.top_score, verdict.runner_up_score) == (100, 71)


def test_길이가_가장_가까운_후보를_고른다():
    # 실측: Adele - Hello 파일 295709ms, MB 후보에 295493ms
    candidates = [
        DurationCandidate(0, 367000),
        DurationCandidate(1, 295493),
        DurationCandidate(2, 397000),
    ]
    picked = narrow_by_duration(candidates, 295709)
    assert picked is not None
    assert picked.index == 1


def test_길이가_없는_후보는_건너뛴다():
    # MB 레코딩에 length가 비어 있는 경우가 실제로 있다
    candidates = [DurationCandidate(0, None), DurationCandidate(1, 185507)]
    picked = narrow_by_duration(candidates, 185812)
    assert picked is not None
    assert picked.index == 1


def test_임계값_밖이면_고르지_않는다():
    # 68초 차이는 다른 버전이다
    assert narrow_by_duration([DurationCandidate(0, 367000)], 295709) is None


def test_경계값_3초는_고른다():
    assert narrow_by_duration([DurationCandidate(0, 303000)], 300000) is not None


def test_경계값_3001ms는_고르지_않는다():
    assert narrow_by_duration([DurationCandidate(0, 303001)], 300000) is None


def test_후보가_전부_길이가_없으면_고르지_않는다():
    assert narrow_by_duration([DurationCandidate(0, None)], 300000) is None
