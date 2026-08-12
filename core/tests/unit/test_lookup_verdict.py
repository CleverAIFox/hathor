"""정규화 판정 규칙 테스트 (D-0019).

임계값은 실측으로 정했다. 이 테스트가 그 근거를 고정한다.
"""

from hathor.domain.entities.resolved_identity import ResolutionState
from hathor.domain.services.lookup_verdict import judge_scores


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
