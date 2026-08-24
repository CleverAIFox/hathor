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
"""섹션 수. `generate_structure`가 이만큼의 구간 이름을 낸다."""

BARS_PER_SECTION = 8
"""섹션 하나가 몇 마디인가 (D-0097).

**대중가요의 관례이지 측정값이 아니다.** 8마디 또는 16마디가 표준이고 짧은 쪽을
골랐다. 근거가 생기면 새 번호로 바꾼다.
"""

DEFAULT_BARS = DEFAULT_SECTIONS * BARS_PER_SECTION
"""화성 진행의 마디 수 = 64.

### 여기 결함이 있었다 (D-0097)

예전에는 `bar_count=DEFAULT_SECTIONS`였다. **섹션 수를 마디 수로 넘기고 있었다** —
섹션당 화음 하나라는 뜻이고, 그런 곡은 없다.

이름이 `DEFAULT_SECTIONS`인데 `bar_count` 자리에 들어간 것이 신호였고 아무도 안 봤다.
**D-0078이 "8마디 출력"을 세며 판정을 미룬 그 8이 마디 수가 아니라 섹션 수였다.**

그리고 그것이 O-36에서 어휘 이득이 안 보인 뿌리다. 8마디에서는 되튐이 이득을
6.1배로 덮어 극한 차이의 **30.3%**만 오고, 64마디에서는 **77.9%**가 온다 (D-0096).
"""


def render(
    job: GenerationJob,
    references: Sequence[StructurePattern],
    *,
    key: Key = DEFAULT_KEY,
    tempo_bpm: int = DEFAULT_TEMPO_BPM,
    harmony_prior: Sequence[float] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """참조곡 구조를 조건으로 MIDI 바이트를 만든다 (D-0052).

    **처음으로 소리가 나는 경로다.** 지금까지 산출물은 지표 JSON과 검색 CLI뿐이었다.

    `harmony_prior`를 주면 화성 **어휘**도 참조곡을 따른다 (O-21 · D-0063).
    주지 않으면 이전과 같다 — 구조만 조건화되고 화성은 시드가 정한다.

    구조 → 화성 → 배치 → SMF. 시드가 같고 참조가 같으면 바이트가 같다.
    가락도 리듬도 없고 3화음을 마디마다 울릴 뿐이나, **관통이 서면 그 뒤로는
    각 단계를 갈아 끼우기만 하면 된다** (GR-6.2).
    """
    pattern = generate_pattern(job.seed, references)
    progression = generate_harmony(job.seed, key, bar_count=DEFAULT_BARS, prior=harmony_prior)
    notes = arrange(pattern, progression)
    data = render_smf(notes, tempo_bpm=tempo_bpm)
    summary: dict[str, Any] = {
        "seed": job.seed,
        "key": str(key),
        "tempo_bpm": tempo_bpm,
        "structure": pattern.as_text(),
        "harmony": list(progression.degrees),
        "harmony_conditioned": harmony_prior is not None,
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
