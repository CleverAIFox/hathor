"""생성 파이프라인 총괄. 엔진 간 직접 호출을 막고 여기서만 조합한다 (GR-2.2)."""

from __future__ import annotations

from typing import Any

from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony
from hathor.engines.compose.structure_generator import generate_structure

DEFAULT_KEY = Key(tonic="C", mode=Mode.MAJOR)


def run_dry(job: GenerationJob, key: Key = DEFAULT_KEY) -> dict[str, Any]:
    """모델 없이 결정적 산출물만 만든다. CI 재현성 검증이 이 경로를 쓴다."""
    job.mark_running()
    result: dict[str, Any] = {
        "job": {"seed": job.seed, "stages": [s.value for s in job.stages]},
        "key": str(key),
    }
    try:
        if Stage.STRUCTURE in job.stages:
            result["structure"] = generate_structure(job.seed)
        if Stage.HARMONY in job.stages:
            result["harmony"] = list(generate_harmony(job.seed, key).degrees)
    except Exception:
        job.mark_failed()
        raise
    job.mark_succeeded()
    result["status"] = job.status.value
    return result
