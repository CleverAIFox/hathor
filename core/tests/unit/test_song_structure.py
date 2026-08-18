"""곡 구조 추출·생성 테스트. 순수 함수라 모델도 파일도 쓰지 않는다."""

import pytest

from hathor.domain.services.song_structure import (
    REPEATED,
    UNIQUE,
    StructurePattern,
    char_ngrams,
    extract_pattern,
    generate_pattern,
    jaccard,
    summarize,
)

CHORUS = "사랑해 사랑해 그대여 오늘도"
VERSES = (
    "오늘도 너를 생각하며 걷는다",
    "아침이 밝아오면 다시 시작해",
    "바람이 불어와도 멈추지 않아",
    "저녁이 내려앉는 골목을 지나",
)


def alternating() -> list[str]:
    """절·후렴이 교대하는 곡. 한국 대중가요에서 흔한 구조다."""
    result: list[str] = []
    for verse in VERSES[:3]:
        result.extend([verse, CHORUS])
    return result


# --- 지문과 유사도 ---


def test_ngrams_fold_whitespace():
    """띄어쓰기는 신호가 아니다. D-0037이 공백 제거 M0 변화 -0.001로 확인했다."""
    assert char_ngrams("보고 싶어") == char_ngrams("보고싶어")


def test_ngrams_handle_text_shorter_than_window():
    assert char_ngrams("가", size=3) == frozenset({"가"})
    assert char_ngrams("", size=3) == frozenset()


def test_jaccard_bounds():
    left = char_ngrams("사랑해 그대여")
    assert jaccard(left, left) == pytest.approx(1.0)
    assert jaccard(left, char_ngrams("전혀 다른 문장 입력")) < 0.2
    assert jaccard(left, frozenset()) == 0.0


# --- 추출 ---


def test_alternating_song_gives_alternating_pattern():
    """가장 중요한 계약. 후렴이 반복이면 R, 절은 U여야 한다."""
    pattern = extract_pattern(alternating())
    assert pattern.as_text() == "URURUR"
    assert pattern.repeat_ratio == pytest.approx(0.5)
    assert pattern.repeat_group_sizes() == (3,)


def test_song_without_repeats_is_all_unique():
    pattern = extract_pattern(list(VERSES))
    assert pattern.as_text() == UNIQUE * 4
    assert pattern.repeat_ratio == 0.0
    assert pattern.repeat_group_sizes() == ()


def test_identical_segments_form_one_group():
    pattern = extract_pattern([CHORUS] * 5)
    assert pattern.as_text() == REPEATED * 5
    assert pattern.repeat_group_sizes() == (5,)


def test_two_distinct_choruses_form_two_groups():
    """후렴이 둘인 곡. 그룹이 하나로 뭉치면 구조를 잘못 읽는다."""
    other = "밤이 깊어가면 별들이 쏟아져"
    segments = [VERSES[0], CHORUS, VERSES[1], other, VERSES[2], CHORUS, other]
    pattern = extract_pattern(segments)
    assert pattern.repeat_group_sizes() == (2, 2)


def test_threshold_controls_merging():
    """임계값은 근거로 정해진 값이 아니다. 영향을 명시적으로 고정한다."""
    segments = [CHORUS, CHORUS + " 언제나"]
    assert extract_pattern(segments, threshold=0.4).as_text() == "RR"
    assert extract_pattern(segments, threshold=0.99).as_text() == "UU"


def test_extract_rejects_single_segment():
    with pytest.raises(ValueError):
        extract_pattern([CHORUS])


# --- 생성 ---


def test_generation_is_deterministic():
    """시드가 같으면 같은 구조여야 한다 (NFR-M6)."""
    reference = extract_pattern(alternating())
    first = generate_pattern(7, [reference])
    assert first.as_text() == generate_pattern(7, [reference]).as_text()


def test_generation_follows_reference_length():
    reference = extract_pattern(alternating())
    assert generate_pattern(1, [reference]).length == reference.length


def test_generation_averages_multiple_references():
    """축별 시드 퓨전(D-0011). 참조가 여럿이면 평균을 따른다."""
    short = extract_pattern(list(VERSES))
    long_song = extract_pattern(alternating() + list(VERSES))
    merged = generate_pattern(3, [short, long_song])
    assert short.length < merged.length < long_song.length


def test_generation_respects_explicit_length():
    reference = extract_pattern(alternating())
    assert generate_pattern(5, [reference], length=12).length == 12


def test_generation_always_has_both_labels():
    """전부 반복이거나 전부 고유인 구조는 곡이 아니다."""
    reference = extract_pattern(alternating())
    for seed in range(30):
        pattern = generate_pattern(seed, [reference], length=8)
        assert REPEATED in pattern.labels
        assert UNIQUE in pattern.labels


def test_repeats_are_spread_not_clustered():
    """반복이 한쪽에 몰리면 홀짝 분할이 곡 지문을 통째로 한쪽에 준다.

    D-0040이 가사축 M0에서 실측한 상황이다. 생성 단계에서 그것을 만들지 않는다.
    """
    reference = extract_pattern(alternating())
    for seed in range(30):
        labels = generate_pattern(seed, [reference], length=12).labels
        first_half = sum(1 for label in labels[:6] if label == REPEATED)
        second_half = sum(1 for label in labels[6:] if label == REPEATED)
        assert abs(first_half - second_half) <= 2, f"seed={seed} 몰림: {labels}"


def test_generation_rejects_empty_references():
    with pytest.raises(ValueError):
        generate_pattern(1, [])


# --- 통계 ---


def test_summarize_reports_distribution():
    patterns = [extract_pattern(alternating()), extract_pattern(list(VERSES))]
    stats = summarize(patterns)
    assert stats.count == 2
    assert stats.mean_length == pytest.approx(5.0)
    assert stats.mean_repeat_ratio == pytest.approx(0.25)
    assert dict(stats.length_histogram) == {4: 1, 6: 1}


def test_summarize_rejects_empty():
    with pytest.raises(ValueError):
        summarize([])


def test_pattern_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        StructurePattern(labels=("R", "U"), groups=(0,))
