"""외부 조회 결과의 정규화 판정 (D-0019).

조회 자체는 infrastructure의 일이지만 "무엇을 확정으로 볼 것인가"는
정규화 정책이므로 도메인에 둔다. 임계값 조정은 여기서만 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from hathor.domain.entities.resolved_identity import ResolutionState

MIN_ACCEPT_SCORE = 90
MIN_SCORE_GAP = 10
# mp3 인코더가 앞뒤에 무음 프레임을 넣어 1~2초가 흔들린다.
# 실측 최대 오차 1689ms. 5초까지 열면 다른 버전이 섞인다.
MAX_DURATION_GAP_MS = 3000


@dataclass(frozen=True, slots=True)
class LookupVerdict:
    """판정 결과와 그 근거가 된 점수."""

    state: ResolutionState
    top_score: int
    runner_up_score: int


@dataclass(frozen=True, slots=True)
class DurationCandidate:
    """길이 선별에 쓰는 후보 하나. 조회처 형식에 의존하지 않는다."""

    index: int
    length_ms: int | None


def narrow_by_duration(
    candidates: list[DurationCandidate], duration_ms: int
) -> DurationCandidate | None:
    """재생시간이 가장 가까운 후보를 고른다.

    유명한 곡일수록 MB에 스튜디오·라이브·리마스터가 모두 등재돼
    전부 100점을 받는다. 점수로는 갈리지 않지만 길이는 다르다.

    길이가 없는 후보는 비교에서 제외한다. MB 레코딩에 length가
    비어 있는 경우가 실제로 있다.
    """
    best: tuple[int, DurationCandidate] | None = None
    for candidate in candidates:
        if candidate.length_ms is None:
            continue
        gap = abs(candidate.length_ms - duration_ms)
        if gap > MAX_DURATION_GAP_MS:
            continue
        if best is None or gap < best[0]:
            best = (gap, candidate)
    return best[1] if best else None


def judge_scores(top: int, runner_up: int) -> LookupVerdict:
    """1·2순위 점수 격차로 판정한다.

    MB 검색은 부분 일치에도 100점을 주므로 점수 단독으로는 오답을
    거를 수 없다. 실측에서 `미연((여자)아이들)`이 재즈 뮤지션 `미연`에
    100점으로 매칭됐다. 2순위와의 격차가 실질적인 신뢰 지표다.

    격차 10점은 실측으로 정했다. 이 값이 낮으면 오답이 RESOLVED로
    새고, 높으면 정상 매칭이 AMBIGUOUS로 떨어진다 (O-4).
    """
    if top < MIN_ACCEPT_SCORE:
        return LookupVerdict(ResolutionState.UNRESOLVED, top, runner_up)
    if top - runner_up < MIN_SCORE_GAP:
        return LookupVerdict(ResolutionState.AMBIGUOUS, top, runner_up)
    return LookupVerdict(ResolutionState.RESOLVED, top, runner_up)
