#!/usr/bin/env python3
"""이 기기가 엔진 재개 조건을 넘는가 (D-0224).

셀프호스티드 러너(`gpu-smoke.yml`)가 돈다. **장비를 바꾼 날 버튼 하나로 답이 나오게** 하려고
만든다 — G0이 떨어진 이유(bf16 없음 · fp16 NaN · VRAM 부족)를 그대로 잰다.

재개 조건은 여기 적지 않는다. **`docs/PLAN.md` §1에서 읽는다** — 숫자가 두 곳에 있으면
한쪽만 고친 날 이 도구가 거짓말을 한다 (D-0223).

    python3 tools/gpu_smoke.py        # 보고한다. CUDA가 없으면 1, 조건 미달이어도 0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESUME = re.compile(r"재개 조건: NVIDIA · VRAM (\d+)GB 이상")


def required_vram(root: Path = ROOT) -> int:
    """PLAN §1의 재개 조건 VRAM(GB)."""
    found = RESUME.search((root / "docs" / "PLAN.md").read_text(encoding="utf-8"))
    if not found:
        raise LookupError("PLAN.md에서 재개 조건을 못 읽었다 — 문장 모양이 바뀌었다")
    return int(found.group(1))


def verdict(vram_gb: float, bf16: bool, fp16_finite: bool, required: int) -> list[str]:
    """미달 사유. **비었으면 재개 조건을 넘는다.**"""
    short: list[str] = []
    if vram_gb < required:
        short.append(f"VRAM {vram_gb:.1f}GB < {required}GB")
    if not bf16:
        short.append("bf16을 안 받는다 — fp16으로 돌면 G0처럼 NaN이 난다")
    if not fp16_finite:
        short.append("fp16 행렬곱이 유한하지 않다")
    return short


def main() -> int:
    try:
        import torch
    except ImportError:
        print("torch가 없다. `make sync`", file=sys.stderr)
        return 2
    if not torch.cuda.is_available():
        print("CUDA를 못 본다 — 드라이버 · WSL GPU 지원을 먼저 본다", file=sys.stderr)
        return 1
    props = torch.cuda.get_device_properties(0)
    vram = props.total_memory / 2**30
    bf16 = bool(torch.cuda.is_bf16_supported())
    probe = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
    finite = bool(torch.isfinite(probe @ probe).all().item())
    required = required_vram()
    print(f"기기 {props.name} · VRAM {vram:.1f}GB · 연산 능력 {props.major}.{props.minor}")
    print(f"torch {torch.__version__} · CUDA {torch.version.cuda} · bf16 {bf16}")
    short = verdict(vram, bf16, finite, required)
    if short:
        print(f"엔진 재개 조건 미달 (PLAN §1: VRAM {required}GB · bf16):")
        for reason in short:
            print(f"  - {reason}")
    else:
        print("엔진 재개 조건을 넘는다 — PLAN §1의 G0부터 다시 돈다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
