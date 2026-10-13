"""MusicFM 기반 특징 추출 — 세 번째 취향 축 후보 (O-68 · D-0248 · D-0413).

### 왜 또 하나인가

검색 M1 20.4배(D-0027)와 화성 `layer03`(D-0181)이 `m-a-p/MERT-v1-95M` 위에 서 있고
**그 가중치는 CC-BY-NC-4.0이라 제품에 못 간다** (D-0217). CLAP은 상업 가능하지만
**MERT의 27%**였다 (O-68 닫힘 D-0235). MusicFM은 셋째 후보이고 **같은 하네스로 잰다** —
같은 1004곡 · 같은 분할이라 비교가 이미 선다.

### MERT와 같은 것, 다른 것

| | MERT | MusicFM |
|---|---|---|
| 입력 | 24kHz 모노 | **같다** |
| 청크 | 10초 (D-0018) | **같다** |
| 차원 | 768 | **1024** |
| 은닉 층 | 13 (1+12) | **13 (1+12)** |
| 적재 | `transformers` | **클론한 코드** — pip 패키지가 아니다 |

**전처리를 두 벌로 안 만든다** (D-0043). 입력 규격이 MERT와 **같은 값**이라
`to_feature_waveform` · `split_chunks` · `layer_key`를 그대로 들여온다. CLAP이 제 것을
따로 둔 것은 48kHz라 **값이 달라서**였지 취향이 아니다.

### 마스크가 없다

MERT는 처리기가 패딩을 넣으므로 유효 구간만 평균한다(`_masked_mean`). MusicFM은
**처리기가 없고 파형을 그대로 받는다** — 청크를 하나씩 넣으므로 패딩이 아예 안 생기고,
짧은 마지막 청크는 멜스펙 프레임이 그만큼 적게 난다. **전 프레임 평균이 곧 정확한
평균이다.**

### 층을 한 번에 뽑는다

저자가 준 `get_latent(x, layer_ix=N)`은 **층마다 `get_predictions`를 다시 돈다** — 층
셋이면 forward 세 번이다. 그 안쪽 `get_predictions`가 **은닉 상태 전부**를 내므로 그것을
직접 부른다. D-0025가 MERT에서 *«반복하면 13배 시간이 든다»*로 피한 자리이고 같은 함정이
여기 그대로 있다.

### 설치가 다르다

`setup.py`도 `pyproject.toml`도 없어 **pip로 안 깔린다.** 저자의 README대로 클론해서
경로를 준다. 재현성은 **커밋을 박아** 지킨다 (`MUSICFM_COMMIT`) — 서브모듈은 제품 경로가
정해진 뒤에 단다. **가중치 라이선스가 미명시라 제품 경로인지가 아직 안 정해졌다**
(D-0413 · `check_model_licenses`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from hathor.domain.ports.audio_analysis import FEATURE_SAMPLE_RATE, Embedding
from hathor.infrastructure.mert_feature_extractor import (
    MIXTURE_OUTPUT_KEY,
    layer_key,
    split_chunks,
    to_feature_waveform,
)

if TYPE_CHECKING:
    from hathor.domain.ports.audio_analysis import StereoWaveform

DEFAULT_MODEL = "minzwon/MusicFM"
"""가중치가 사는 곳. **코드는 GitHub(`minzwon/musicfm`)에, 가중치는 여기 있다** —
`check_model_licenses`가 이 이름으로 가중치 라이선스를 센다 (D-0217)."""

DEFAULT_DEVICE = "cuda"

MUSICFM_COMMIT = "b83ebedb401bcef639b26b05c0c8bee1dc2dfe71"
"""잰 코드의 커밋 (2024-02-14). **클론은 버전이 안 박힌다** — 여기 적어 두고 산출물
설명에 싣는다 (D-0009). 저자가 *«2024-02-13 이전 체크포인트는 틀렸다»*라고 적었으므로
**가중치도 그 뒤 판이어야 한다.**"""

MUSICFM_SAMPLE_RATE = FEATURE_SAMPLE_RATE
"""입력 규격. **포트의 값을 그대로 쓴다** — MERT와 같은 24kHz라 새 상수를 안 만든다.
CLAP이 제 값을 따로 둔 것은 48kHz라 **달라서**였다 (D-0043)."""

MUSICFM_DIMENSION = 1024
"""`encoder_dim`. **여기 적어 두고 모델이 다른 값을 내면 죽는다** (D-0233 · CLAP과 같은 규율)."""

MUSICFM_LAYERS = 13
"""`encoder_depth=12`에 입력 임베딩 하나. MERT 95M과 **우연히 같은 수**다."""

DEFAULT_CHECKPOINT = "pretrained_fma.pt"
DEFAULT_STATS = "fma_stats.json"
"""**FMA 판을 기본으로 둔다** (D-0413). MSD 판이 성능은 낫다고 저자가 적었지만, FMA 판은
*«라이선스 분쟁을 피하려고»* 따로 낸 것이다 — D-0217이 ACE-Step의 **학습 데이터 출처
불투명**을 문제 삼은 것과 같은 줄에 선다. 바꾸려면 인자로 준다."""

MODEL_IMPORT = "musicfm.model.musicfm_25hz"
"""저자 코드의 임포트 경로. **클론한 곳의 부모를 `PYTHONPATH`에 넣어야 보인다.**"""


def _home(home: Path | None) -> Path:
    """저자 코드를 클론한 자리. **없으면 무엇을 해야 하는지 말한다.**

    「임포트 실패」만 던지면 사람이 pip를 친다. **이 모델은 pip로 안 깔린다** —
    그 사실을 오류가 직접 적어야 한다 (D-0069의 규율: 조용히 틀린 곳을 가리키지 않는다).
    """
    if home is None:
        raise ValueError(
            "MusicFM 코드 경로가 없다. **pip로 안 깔린다** — "
            "`git clone https://github.com/minzwon/musicfm`하고 그 **부모 폴더**를 준다 "
            f"(잰 커밋 {MUSICFM_COMMIT[:7]} · D-0413)"
        )
    if not (home / "musicfm" / "model" / "musicfm_25hz.py").is_file():
        raise ValueError(
            f"{home}/musicfm/model/musicfm_25hz.py가 없다 — 클론한 곳의 **부모**를 준다"
        )
    return home


class MusicFmFeatureExtractor:
    """모델을 한 번 적재하고 재사용한다.

    `extract_layers`를 두어 `LayeredFeatureExtractor` 포트를 만족시킨다 — MERT·CLAP과
    **같은 유스케이스**(`ExtractLayerFeatures`)를 그대로 쓰기 위해서다.
    """

    def __init__(
        self,
        home: Path | None = None,
        device: str = DEFAULT_DEVICE,
        layers: tuple[int, ...] = (),
        checkpoint: str = DEFAULT_CHECKPOINT,
        stats: str = DEFAULT_STATS,
    ) -> None:
        import sys

        root = _home(home)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from musicfm.model.musicfm_25hz import MusicFM25Hz  # type: ignore[import-not-found]

        data = root / "musicfm" / "data"
        model: Any = MusicFM25Hz(
            is_flash=False,
            stat_path=str(data / stats),
            model_path=str(data / checkpoint),
        )
        self._model: Any = model.to(device).eval()
        self._device = device
        self._layers = tuple(sorted(set(layers)))
        self._checkpoint = checkpoint
        self._stats = stats

    @property
    def layers(self) -> tuple[int, ...]:
        return self._layers

    @property
    def layer_count(self) -> int:
        return MUSICFM_LAYERS

    @property
    def dimension(self) -> int:
        return MUSICFM_DIMENSION

    @property
    def checkpoint(self) -> str:
        """어느 판으로 쟀나. **산출물이 자기를 설명한다** (D-0203)."""
        return self._checkpoint

    def extract(self, waveform: StereoWaveform) -> Embedding:
        """기본 경로. 마지막 층 하나만 낸다 (MERT와 같은 꼴)."""
        return self.extract_layers(waveform)[MIXTURE_OUTPUT_KEY]

    def extract_layers(self, waveform: StereoWaveform) -> dict[str, Embedding]:
        """혼합 임베딩과 고른 층을 함께 낸다. 키는 `mixture`와 `layerNN`이다.

        **`get_predictions`를 한 번만 부른다** — 저자의 `get_latent`은 층마다 다시 돈다.
        """
        import torch

        chunks = split_chunks(to_feature_waveform(waveform))
        wanted = (MIXTURE_OUTPUT_KEY, *(layer_key(index) for index in self._layers))
        if not chunks:
            empty = np.zeros((0, MUSICFM_DIMENSION), dtype=np.float32)
            return dict.fromkeys(wanted, empty)

        collected: dict[str, list[Any]] = {key: [] for key in wanted}
        with torch.no_grad():
            for chunk in chunks:
                values = torch.from_numpy(np.asarray(chunk, dtype=np.float32))
                _logits, hidden = self._model.get_predictions(values[None, :].to(self._device))
                if len(hidden) != MUSICFM_LAYERS:
                    # 체크포인트를 바꾸면 여기서 먼저 죽는다. **조용히 다른 수를 쌓으면
                    # MERT와 나란히 못 놓는데 산출물은 그럴듯하게 쌓인다** (D-0233).
                    raise ValueError(f"은닉 층이 {MUSICFM_LAYERS}개가 아니다: {len(hidden)}")
                collected[MIXTURE_OUTPUT_KEY].append(self._pooled(hidden[-1]))
                for index in self._layers:
                    collected[layer_key(index)].append(self._pooled(hidden[index]))
        return {
            key: np.asarray(torch.stack(values).cpu().numpy(), dtype=np.float32)
            for key, values in collected.items()
        }

    def _pooled(self, hidden: Any) -> Any:
        """청크 하나를 벡터 하나로. **마스크가 필요 없다** — 패딩이 안 생긴다.

        청크를 하나씩 넣으므로 배치 패딩이 없고, 짧은 마지막 청크는 멜스펙 프레임이
        그만큼 적게 난다. **전 프레임 평균이 곧 정확한 평균이다.**
        """
        vector = hidden[0].mean(dim=0)
        if int(vector.shape[0]) != MUSICFM_DIMENSION:
            raise ValueError(f"차원이 {MUSICFM_DIMENSION}이 아니다: {int(vector.shape[0])}")
        return vector


def read_stats(home: Path, stats: str = DEFAULT_STATS) -> dict[str, float]:
    """정규화 통계. **적재 전에 읽어 파일이 있는지 본다** — 모델은 없으면 늦게 죽는다."""
    with (home / "musicfm" / "data" / stats).open(encoding="utf-8") as handle:
        return dict(json.load(handle))
