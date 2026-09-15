import pytest

from hathor.application.orchestrator.generation_pipeline import DEFAULT_SECTIONS, run_dry
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony
from hathor.engines.compose.structure_generator import generate_structure

STAGES = (Stage.STRUCTURE, Stage.HARMONY)


def test_structure_is_deterministic():
    assert generate_structure(42, DEFAULT_SECTIONS) == generate_structure(42, DEFAULT_SECTIONS)


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


def test_섹션_수와_마디_수는_다른_것이다():
    """**섹션 수를 마디 수로 넘기고 있었다** (D-0097).

    이름이 `DEFAULT_SECTIONS`인데 `bar_count` 자리에 들어갔고 아무도 안 봤다.
    섹션당 화음 하나인 곡은 없다.
    """
    from hathor.application.orchestrator.generation_pipeline import (
        BARS_PER_SECTION,
        DEFAULT_BARS,
        DEFAULT_SECTIONS,
    )

    assert BARS_PER_SECTION > 1
    assert DEFAULT_BARS == DEFAULT_SECTIONS * BARS_PER_SECTION
    assert DEFAULT_BARS > DEFAULT_SECTIONS


def test_생성이_섹션_수보다_많은_마디를_낸다():
    """**어휘 이득이 8마디에서 안 보인 뿌리다** (D-0096 · D-0097)."""
    from hathor.application.orchestrator.generation_pipeline import (
        DEFAULT_BARS,
        DEFAULT_SECTIONS,
    )
    from hathor.domain.value_objects.key import Key, Mode
    from hathor.engines.compose.harmony_generator import generate_harmony

    key = Key(tonic="C", mode=Mode.MAJOR)
    assert len(generate_harmony(7, key, bar_count=DEFAULT_BARS).degrees) == DEFAULT_BARS
    assert DEFAULT_BARS != DEFAULT_SECTIONS


def test_구간_수가_실제로_전달된다():
    """**`--sections`가 선언만 있고 아무도 안 읽었다** (D-0200).

    `run_dry`가 `generate_structure(job.seed)`로 불러 **엔진의 기본값 8이 조용히
    이겼다.** 손잡이를 돌려도 아무 일이 없는 것은 `chroma(harmonic=...)`가
    무시되던 D-0064와 같은 모양이다.
    """
    job = GenerationJob(seed=42, stages=(Stage.STRUCTURE,))
    assert len(run_dry(job, 4)["structure"]) == 4
    assert len(run_dry(GenerationJob(seed=42, stages=(Stage.STRUCTURE,)))["structure"]) == (
        DEFAULT_SECTIONS
    )


def test_엔진이_기본값을_따로_들지_않는다():
    """**한 이름이 두 값이면 둘 중 하나는 반드시 틀린다** (D-0111의 문장 그대로).

    `generate_structure`가 `section_count: int = 8`을 들고 있었고
    `DEFAULT_SECTIONS`도 8이었다. 같은 기본값이 두 곳에 살면 한쪽만 바뀐다.
    """
    import inspect

    spec = inspect.signature(generate_structure).parameters["section_count"]
    assert spec.default is inspect.Parameter.empty, "기본값은 DEFAULT_SECTIONS 하나만 든다"
