import pytest

from hathor.application.orchestrator.generation_pipeline import run_dry
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony
from hathor.engines.compose.structure_generator import generate_structure

STAGES = (Stage.STRUCTURE, Stage.HARMONY)


def test_structure_is_deterministic():
    assert generate_structure(42) == generate_structure(42)


def test_structure_bounds():
    sections = generate_structure(7, section_count=6)
    assert len(sections) == 6
    assert sections[0] == "intro" and sections[-1] == "outro"
    with pytest.raises(ValueError):
        generate_structure(7, section_count=1)


def test_harmony_is_deterministic_and_diatonic():
    key = Key("C", Mode.MAJOR)
    a = generate_harmony(42, key, bar_count=8)
    b = generate_harmony(42, key, bar_count=8)
    assert a == b
    assert all(d in ("I", "ii", "iii", "IV", "V", "vi") for d in a.degrees)
    with pytest.raises(ValueError):
        generate_harmony(42, key, bar_count=0)


def test_harmony_differs_by_seed():
    key = Key("C", Mode.MAJOR)
    assert generate_harmony(1, key, 16) != generate_harmony(2, key, 16)


def test_minor_mode_uses_minor_pool():
    prog = generate_harmony(3, Key("A", Mode.MINOR), bar_count=8)
    assert all(d in ("i", "III", "iv", "v", "VI", "VII") for d in prog.degrees)


def test_pipeline_dry_run_reproducible():
    first = run_dry(GenerationJob(seed=42, stages=STAGES))
    second = run_dry(GenerationJob(seed=42, stages=STAGES))
    first.pop("job"), second.pop("job")
    assert first == second


def test_pipeline_partial_stage():
    out = run_dry(GenerationJob(seed=5, stages=(Stage.HARMONY,)))
    assert "harmony" in out and "structure" not in out
    assert out["status"] == "succeeded"
