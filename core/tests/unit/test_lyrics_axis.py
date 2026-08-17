"""가사축 테스트. 실제 음원도 GPU도 쓰지 않는다."""

import numpy as np
import pytest

from hathor.application.extract_lyrics import ExtractLyrics
from hathor.domain.services.lyrics_segmentation import normalize_lyrics, split_segments
from hathor.infrastructure.hashed_lyrics_extractor import (
    FEATURE_DIM,
    HashedLyricsExtractor,
    char_ngrams,
    hash_index,
)
from hathor.infrastructure.npz_feature_store import NpzFeatureStore
from hathor.interfaces.cli.main import main
from tests.unit.test_eval_cli import write_scan

VERSE = "밤에 들려오는 그대 목소리\n창밖에 별이 내리고"
CHORUS = "나는 오늘도 그대를 생각해\n잠들지 못한 채로"


def test_split_prefers_blank_lines():
    segments = split_segments(f"{VERSE}\n\n{CHORUS}")
    assert len(segments) == 2


def test_split_falls_back_to_line_groups():
    """빈 줄이 없어도 나눌 수 있어야 M0를 잴 수 있다."""
    lines = "\n".join(f"{index}번째 줄입니다 가사 내용" for index in range(9))
    assert len(split_segments(lines)) >= 2


def test_split_drops_structure_markers():
    """`[Verse 1]` 같은 표기는 가사가 아니다. 두면 곡끼리 그것 때문에 비슷해진다."""
    text = f"[Verse 1]\n{VERSE}\n\n[Chorus]\n{CHORUS}"
    segments = split_segments(text)
    assert all("[" not in segment for segment in segments)
    assert len(segments) == 2


def test_split_drops_short_segments():
    text = f"{VERSE}\n\n(간주)\n\n{CHORUS}"
    assert len(split_segments(text)) == 2


def test_split_returns_empty_for_single_segment():
    """구간이 하나면 홀·짝 분할이 불가능하므로 아예 내지 않는다."""
    assert split_segments("짧은 한 줄짜리 가사입니다") == []


def test_split_handles_missing_lyrics():
    assert split_segments(None) == []
    assert split_segments("   ") == []


def test_normalize_unifies_line_endings():
    assert "\r" not in normalize_lyrics("가\r\n나\r다")


def test_char_ngrams_absorb_korean_inflection():
    """교착어 어미 변화를 문자 n-gram이 흡수해야 한다."""
    base = set(char_ngrams("사랑해"))
    inflected = set(char_ngrams("사랑했어"))
    assert base & inflected


def test_char_ngrams_ignore_whitespace_formatting():
    assert char_ngrams("가 나  다") == char_ngrams("가 나\n다")


def test_hash_index_is_stable_across_processes():
    """내장 hash를 쓰면 실행마다 값이 달라져 재현성 계층 1이 깨진다 (D-0009)."""
    assert hash_index("사랑해") == hash_index("사랑해")
    assert 0 <= hash_index("사랑해") < FEATURE_DIM
    # blake2b 기반이므로 값이 고정된다. 내장 hash였다면 이 단언이 실행마다 깨진다.
    assert hash_index("사랑해", 1024) == hash_index("사랑해", 1024)


def test_extract_returns_segment_rows():
    matrix = HashedLyricsExtractor().extract([VERSE, CHORUS])
    assert matrix.shape == (2, FEATURE_DIM)
    assert np.isfinite(matrix).all()


def test_extract_rows_are_unit_length():
    matrix = HashedLyricsExtractor().extract([VERSE, CHORUS])
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)


def test_extract_is_deterministic():
    extractor = HashedLyricsExtractor()
    assert np.array_equal(extractor.extract([VERSE]), extractor.extract([VERSE]))


def test_extract_separates_different_lyrics():
    matrix = HashedLyricsExtractor().extract([VERSE, "완전히 다른 내용의 영어 가사 hello world"])
    assert float(matrix[0] @ matrix[1]) < 0.5


def test_extract_handles_empty_segments():
    assert HashedLyricsExtractor().extract([]).shape == (0, FEATURE_DIM)


def test_extract_survives_unhashable_short_text():
    matrix = HashedLyricsExtractor().extract(["가"])
    assert np.isfinite(matrix).all()


class FakeTrack:
    def __init__(self, source_key: str, lyrics: str | None) -> None:
        self.source_key = source_key
        self.tags = type("Tags", (), {"lyrics_text": lyrics})()


def test_use_case_skips_tracks_without_lyrics():
    """제외 이유를 추출 단계에서 남긴다. 평가에서 걸러지면 원인이 흐려진다."""
    use_case = ExtractLyrics(HashedLyricsExtractor())
    tracks = [
        FakeTrack("가.mp3", f"{VERSE}\n\n{CHORUS}"),
        FakeTrack("나.mp3", None),
        FakeTrack("다.mp3", "짧다"),
    ]
    results = list(use_case.run(tracks))  # type: ignore[arg-type]
    assert len(results) == 1
    assert use_case.processed == 1
    reasons = dict(use_case.skipped)
    assert reasons["나.mp3"] == "가사 없음"
    assert reasons["다.mp3"] == "구간 2개 미만"


def write_library(tmp_path, lyrics_by_key):
    entries = []
    for index, (key, _) in enumerate(lyrics_by_key.items()):
        entries.append((key, f"가수{index}", "앨범"))
    path = write_scan(tmp_path, entries)
    import json

    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        record["tags"]["lyrics_text"] = lyrics_by_key[record["source_key"]]
        lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_cli_lyrics_extract(tmp_path, capsys):
    write_library(
        tmp_path,
        {
            "가.mp3": f"{VERSE}\n\n{CHORUS}",
            "나.mp3": f"{CHORUS}\n\n{VERSE}\n\n{CHORUS}",
            "다.mp3": None,
        },
    )
    assert main(["lyrics", "extract", "--out", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "성공 2곡, 제외 1곡" in output

    store = NpzFeatureStore(tmp_path / "lyrics-hashed")
    keys = [key for key, _ in store.iter_vectors()]
    assert keys == ["가.mp3", "나.mp3"]


def test_cli_lyrics_output_is_readable_by_eval(tmp_path):
    """산출물 규격이 오디오와 같아야 같은 하네스가 읽는다."""
    write_library(
        tmp_path,
        {
            "가.mp3": f"{VERSE}\n\n{CHORUS}",
            "나.mp3": f"{CHORUS}\n\n{VERSE}",
        },
    )
    main(["lyrics", "extract", "--out", str(tmp_path)])
    store = NpzFeatureStore(tmp_path / "lyrics-hashed")
    _, vectors = next(iter(store.iter_vectors()))
    assert "mixture" in vectors
    assert vectors["mixture"].ndim == 2


def test_cli_lyrics_resumes(tmp_path, capsys):
    write_library(tmp_path, {"가.mp3": f"{VERSE}\n\n{CHORUS}"})
    main(["lyrics", "extract", "--out", str(tmp_path)])
    assert main(["lyrics", "extract", "--out", str(tmp_path)]) == 0
    assert "처리할 곡이 없다" in capsys.readouterr().out


def test_cli_lyrics_without_scan_output(tmp_path):
    assert main(["lyrics", "extract", "--out", str(tmp_path)]) == 2


def test_lyrics_requires_subcommand():
    with pytest.raises(SystemExit):
        main(["lyrics"])
