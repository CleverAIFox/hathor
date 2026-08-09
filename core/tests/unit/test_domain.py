import pytest

from hathor.domain.entities.generation_job import GenerationJob, JobStatus, Stage
from hathor.domain.entities.track import Track
from hathor.domain.value_objects.chord_progression import ChordProgression
from hathor.domain.value_objects.key import Key, Mode
from hathor.infrastructure.persistence.in_memory_track_repository import InMemoryTrackRepository


def make_track(**kw):
    base = dict(title="테스트곡", artist="오창준", duration_ms=210_000, source_path="/x.flac")
    base.update(kw)
    return Track(**base)


def test_track_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        make_track(duration_ms=0)


def test_track_rejects_blank_title():
    with pytest.raises(ValueError):
        make_track(title="   ")


def test_track_normalization_depends_on_isrc():
    assert make_track().is_normalized is False
    assert make_track(isrc="KRA382400001").is_normalized is True


def test_key_rejects_unknown_tonic():
    with pytest.raises(ValueError):
        Key(tonic="H", mode=Mode.MAJOR)


def test_key_pitch_class_and_str():
    key = Key(tonic="A", mode=Mode.MINOR)
    assert key.tonic_pitch_class == 9
    assert str(key) == "A minor"


def test_chord_progression_transpose_keeps_degrees():
    src = ChordProgression(key=Key("C", Mode.MAJOR), degrees=("I", "V", "vi", "IV"))
    dst = src.transposed(Key("G", Mode.MAJOR))
    assert dst.degrees == src.degrees
    assert dst.key.tonic == "G"
    assert src.length == 4


def test_chord_progression_rejects_empty():
    with pytest.raises(ValueError):
        ChordProgression(key=Key("C", Mode.MAJOR), degrees=())


def test_job_state_machine():
    job = GenerationJob(seed=42, stages=(Stage.STRUCTURE,))
    with pytest.raises(ValueError):
        job.mark_succeeded()
    job.mark_running()
    with pytest.raises(ValueError):
        job.mark_running()
    job.mark_succeeded()
    assert job.status is JobStatus.SUCCEEDED


def test_job_mark_failed_is_always_allowed():
    job = GenerationJob(seed=1, stages=(Stage.HARMONY,))
    job.mark_failed()
    assert job.status is JobStatus.FAILED


def test_job_validation():
    with pytest.raises(ValueError):
        GenerationJob(seed=1, stages=())
    with pytest.raises(ValueError):
        GenerationJob(seed=-1, stages=(Stage.HARMONY,))


def test_in_memory_repository_roundtrip():
    repo = InMemoryTrackRepository()
    track = make_track()
    repo.add(track)
    assert repo.count_all() == 1
    assert repo.find_by_id(track.track_id) is track
    assert repo.find_by_id(make_track().track_id) is None
