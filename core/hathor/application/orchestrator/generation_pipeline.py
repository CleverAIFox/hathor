"""생성 파이프라인 총괄. 엔진 간 직접 호출을 막고 여기서만 조합한다 (GR-2.2)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from hathor.application.arrangement import arrange, duration_seconds, total_bars
from hathor.domain.entities.generation_job import GenerationJob, Stage
from hathor.domain.services.midi_writer import DEFAULT_TEMPO_BPM, render_smf
from hathor.domain.services.song_structure import StructurePattern, generate_pattern
from hathor.domain.value_objects.key import Key, Mode
from hathor.engines.compose.harmony_generator import generate_harmony
from hathor.engines.compose.structure_generator import generate_structure

DEFAULT_KEY = Key(tonic="C", mode=Mode.MAJOR)
DEFAULT_SECTIONS = 8


def render(
    job: GenerationJob,
    references: Sequence[StructurePattern],
    *,
    key: Key = DEFAULT_KEY,
    tempo_bpm: int = DEFAULT_TEMPO_BPM,
) -> tuple[bytes, dict[str, Any]]:
    """참조곡 구조를 조건으로 MIDI 바이트를 만든다 (D-0052).

    **처음으로 소리가 나는 경로다.** 지금까지 산출물은 지표 JSON과 검색 CLI뿐이었다.

    구조 → 화성 → 배치 → SMF. 시드가 같고 참조가 같으면 바이트가 같다.
    가락도 리듬도 없고 3화음을 마디마다 울릴 뿐이나, **관통이 서면 그 뒤로는
    각 단계를 갈아 끼우기만 하면 된다** (GR-6.2).
    """
    pattern = generate_pattern(job.seed, references)
    progression = generate_harmony(job.seed, key, bar_count=DEFAULT_SECTIONS)
    notes = arrange(pattern, progression)
    data = render_smf(notes, tempo_bpm=tempo_bpm)
    summary: dict[str, Any] = {
        "seed": job.seed,
        "key": str(key),
        "tempo_bpm": tempo_bpm,
        "structure": pattern.as_text(),
        "harmony": list(progression.degrees),
        "bars": total_bars(pattern),
        "notes": len(notes),
        "duration_seconds": round(duration_seconds(pattern, tempo_bpm), 2),
        "bytes": len(data),
    }
    return data, summary


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
