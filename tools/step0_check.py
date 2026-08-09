#!/usr/bin/env python3
"""
HATHOR — STEP 0 환경 점검

하는 일
  1. 시스템 정보 (OS / CPU / RAM / 디스크)
  2. GPU 및 VRAM 확인 → 어떤 모델이 돌아가는지 자동 판정
  3. Python / PyTorch / CUDA 상태
  4. 음원 라이브러리 스캔 (포맷 · 길이 · 가사태그 · ISRC · 결측)

사용법
  python step0_check.py "D:/Music"
  python step0_check.py "/mnt/d/Music"

필요 패키지 (음원 스캔용, 없으면 시스템 점검만 수행)
  pip install mutagen
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".aiff", ".alac"}
REPORT_PATH = Path("hathor_step0_report.json")

# VRAM(GB) 기준 작업별 요구량
VRAM_REQUIREMENTS = [
    ("Demucs 스템 분리 (segment 조절)", 4, "곡당 2~4분. 필수 기능"),
    ("MERT 임베딩 추출 (fp16)", 4, "취향 벡터의 핵심"),
    ("CLAP 임베딩 추출", 3, "자연어 음악 검색"),
    ("faster-whisper large-v3 (int8)", 4, "가사 태그 없는 곡 전사"),
    ("SDXL 앨범 커버 (fp16 + slicing)", 6, "앨범 커버 생성"),
    ("RVC v2 학습 (batch 1~2)", 6, "가창 음색 변환"),
    ("MIDI Transformer 학습 (small)", 6, "멜로디 생성"),
    ("한국어 LLM 8B 추론 (4bit)", 6, "챗봇 · 군집 서술"),
    ("한국어 LLM 8B QLoRA 학습", 10, "작사 특화 (선택)"),
    ("DiffSinger 파인튜닝", 12, "가창 합성 (RunPod 권장)"),
    ("FLUX 이미지 생성", 12, "고품질 커버 (RunPod 권장)"),
]


def hr(title: str = "") -> None:
    print("\n" + "=" * 62)
    if title:
        print(f"  {title}")
        print("=" * 62)


def run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------- 1. 시스템
def check_system() -> dict:
    hr("1. 시스템")
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
    }

    try:
        import psutil  # noqa

        info["ram_gb"] = round(psutil.virtual_memory().total / 1024**3, 1)
    except ImportError:
        info["ram_gb"] = None

    total, used, free = shutil.disk_usage(Path.home())
    info["disk_free_gb"] = round(free / 1024**3, 1)
    info["disk_total_gb"] = round(total / 1024**3, 1)

    print(f"  OS          : {info['os']} ({info['machine']})")
    print(f"  Python      : {info['python']}")
    print(f"  CPU 코어    : {info['cpu_count']}")
    print(f"  RAM         : {info['ram_gb'] or '미확인 (pip install psutil)'} GB")
    print(f"  디스크 여유 : {info['disk_free_gb']} GB / {info['disk_total_gb']} GB")

    if info["python"] < "3.10":
        print("  [경고] Python 3.12 이상을 권장한다.")
    if info["disk_free_gb"] < 100:
        print("  [경고] 여유 공간 100GB 미만. 스템 분리 산출물이 원본의 4배를 차지한다.")
    return info


# ---------------------------------------------------------------- 2. GPU
def check_gpu() -> dict:
    hr("2. GPU / VRAM")
    info: dict = {"available": False, "devices": []}

    out = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
               "--format=csv,noheader,nounits"])
    if not out:
        print("  NVIDIA GPU를 찾지 못했다.")
        print("  → GPU 없이도 인제스트·정규화·EDA·DB 작업은 전부 가능하다.")
        print("  → 모델 관련 작업은 RunPod 등 클라우드 GPU로 처리한다.")
        return info

    info["available"] = True
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        name, mem_mb, driver = parts[0], parts[1], parts[2]
        vram = round(int(mem_mb) / 1024, 1)
        info["devices"].append({"name": name, "vram_gb": vram, "driver": driver})
        print(f"  {name}")
        print(f"    VRAM   : {vram} GB")
        print(f"    드라이버: {driver}")

    if not info["devices"]:
        return info

    vram = max(d["vram_gb"] for d in info["devices"])
    print(f"\n  [VRAM {vram} GB 기준 실행 가능 여부]")
    verdict = {}
    for task, need, note in VRAM_REQUIREMENTS:
        ok = vram >= need
        verdict[task] = {"required_gb": need, "possible": ok}
        mark = "가능" if ok else "불가"
        print(f"    {mark:4} | {task:38} (필요 {need:>2}GB) — {note}")
    info["task_verdict"] = verdict
    info["max_vram_gb"] = vram
    return info


# ---------------------------------------------------------------- 3. 파이썬 환경
def check_python_env() -> dict:
    hr("3. Python 라이브러리")
    info: dict = {}

    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["cuda_version"] = torch.version.cuda
        print(f"  PyTorch     : {torch.__version__}")
        print(f"  CUDA 사용   : {torch.cuda.is_available()}")
        print(f"  CUDA 버전   : {torch.version.cuda}")
        if torch.cuda.is_available():
            print(f"  인식 GPU    : {torch.cuda.get_device_name(0)}")
        else:
            print("  [안내] PyTorch가 GPU를 못 본다. CPU 전용 빌드일 수 있다.")
    except ImportError:
        info["torch"] = None
        print("  PyTorch     : 미설치 (지금은 필요 없다. 나중에 설치한다)")

    for mod, label in [("mutagen", "mutagen (태그 읽기)"),
                       ("numpy", "numpy"),
                       ("psutil", "psutil")]:
        try:
            __import__(mod)
            print(f"  {label:22}: 설치됨")
            info[mod] = True
        except ImportError:
            print(f"  {label:22}: 미설치")
            info[mod] = False

    for tool, label in [("ffmpeg", "ffmpeg (오디오 디코딩)"),
                        ("fpcalc", "fpcalc (Chromaprint 지문)")]:
        found = shutil.which(tool)
        print(f"  {label:22}: {'설치됨' if found else '미설치'}")
        info[tool] = bool(found)

    return info


# ---------------------------------------------------------------- 4. 음원 스캔
def scan_library(root: Path) -> dict:
    hr("4. 음원 라이브러리 스캔")

    try:
        import mutagen
        from mutagen.id3 import ID3
    except ImportError:
        print("  mutagen이 없어 태그를 읽을 수 없다.")
        print("  → pip install mutagen  실행 후 다시 시도한다.")
        return {"error": "mutagen_missing"}

    if not root.exists():
        print(f"  경로를 찾을 수 없다: {root}")
        return {"error": "path_not_found", "path": str(root)}

    print(f"  경로: {root}")
    print("  스캔 중... (곡 수에 따라 1~5분 소요)")

    files = [p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXTS]
    total = len(files)
    if total == 0:
        print("  오디오 파일을 찾지 못했다. 경로를 확인한다.")
        return {"error": "no_audio_files", "path": str(root)}

    fmt = Counter()
    sample_rates = Counter()
    bit_depths = Counter()
    duration_s = 0.0
    size_bytes = 0

    has_lyrics_sync = 0      # SYLT — 시간 동기 가사
    has_lyrics_unsync = 0    # USLT / LYRICS — 텍스트 가사
    has_isrc = 0
    has_title = 0
    has_artist = 0
    has_album = 0
    has_date = 0
    unreadable = 0

    for i, path in enumerate(files, 1):
        if i % 200 == 0:
            print(f"    {i}/{total} …")
        fmt[path.suffix.lower()] += 1
        try:
            size_bytes += path.stat().st_size
        except OSError:
            pass

        try:
            audio = mutagen.File(path)
        except Exception:
            unreadable += 1
            continue
        if audio is None:
            unreadable += 1
            continue

        inf = getattr(audio, "info", None)
        if inf is not None:
            duration_s += float(getattr(inf, "length", 0) or 0)
            sr = getattr(inf, "sample_rate", None)
            if sr:
                sample_rates[sr] += 1
            bd = getattr(inf, "bits_per_sample", None)
            if bd:
                bit_depths[bd] += 1

        tags = getattr(audio, "tags", None)
        if tags is None:
            continue

        keys = set()
        try:
            keys = {str(k).upper() for k in tags.keys()}
        except Exception:
            pass

        # 가사
        if any(k.startswith("SYLT") for k in keys):
            has_lyrics_sync += 1
        elif any(k.startswith("USLT") for k in keys) or "LYRICS" in keys or "\xa9LYR" in keys:
            has_lyrics_unsync += 1
        elif "UNSYNCEDLYRICS" in keys:
            has_lyrics_unsync += 1

        # ISRC
        if any("ISRC" in k for k in keys):
            has_isrc += 1

        def present(*names: str) -> bool:
            for n in names:
                if n in keys:
                    return True
                try:
                    v = tags.get(n)
                    if v:
                        return True
                except Exception:
                    pass
            return False

        if present("TIT2", "TITLE", "\xa9NAM"):
            has_title += 1
        if present("TPE1", "ARTIST", "\xa9ART"):
            has_artist += 1
        if present("TALB", "ALBUM", "\xa9ALB"):
            has_album += 1
        if present("TDRC", "DATE", "\xa9DAY", "YEAR"):
            has_date += 1

    lyrics_total = has_lyrics_sync + has_lyrics_unsync

    def pct(n: int) -> str:
        return f"{n:>5} ({n / total * 100:5.1f}%)"

    print(f"\n  총 파일 수    : {total}")
    print(f"  총 재생 시간  : {duration_s / 3600:.1f} 시간")
    print(f"  총 용량       : {size_bytes / 1024**3:.1f} GB")
    print(f"  읽기 실패     : {unreadable}")

    print("\n  [포맷 분포]")
    for ext, cnt in fmt.most_common():
        print(f"    {ext:<7}: {pct(cnt)}")

    print("\n  [샘플레이트]")
    for sr, cnt in sample_rates.most_common(6):
        print(f"    {sr:>6} Hz: {pct(cnt)}")

    print("\n  [태그 보유율]  ← 인제스트 설계의 핵심 지표")
    print(f"    제목        : {pct(has_title)}")
    print(f"    아티스트    : {pct(has_artist)}")
    print(f"    앨범        : {pct(has_album)}")
    print(f"    발매일      : {pct(has_date)}")
    print(f"    ISRC        : {pct(has_isrc)}   ← 있으면 정규화 신뢰도 1.00")
    print(f"    가사(동기)  : {pct(has_lyrics_sync)}   ← SYLT. 시간정보 포함")
    print(f"    가사(텍스트): {pct(has_lyrics_unsync)}   ← USLT. 정렬만 하면 됨")
    print(f"    가사 합계   : {pct(lyrics_total)}")

    print("\n  [판정]")
    if lyrics_total / total >= 0.9:
        print("    가사: 전사(STT) 불필요. 강제 정렬 문제로 축소된다. 매우 유리하다.")
    elif lyrics_total / total >= 0.5:
        print("    가사: 절반 이상 보유. 나머지만 STT로 보완한다.")
    else:
        print("    가사: 보유율 낮음. Demucs 보컬 분리 후 STT 경로가 주력이 된다.")

    if has_isrc / total >= 0.5:
        print("    ISRC: 보유율 높음. 정규화 난이도가 크게 낮아진다.")
    else:
        print("    ISRC: 보유율 낮음. 지문(Chromaprint) 기반 정규화가 주력이 된다.")

    est_stem_gb = size_bytes / 1024**3 * 4
    print(f"    스템 분리 시 추가 용량 예상: 약 {est_stem_gb:.0f} GB")

    return {
        "path": str(root),
        "total_files": total,
        "duration_hours": round(duration_s / 3600, 2),
        "size_gb": round(size_bytes / 1024**3, 2),
        "unreadable": unreadable,
        "formats": dict(fmt),
        "sample_rates": {str(k): v for k, v in sample_rates.items()},
        "tags": {
            "title": has_title,
            "artist": has_artist,
            "album": has_album,
            "date": has_date,
            "isrc": has_isrc,
            "lyrics_synced": has_lyrics_sync,
            "lyrics_unsynced": has_lyrics_unsync,
            "lyrics_total": lyrics_total,
        },
        "estimated_stem_gb": round(est_stem_gb, 1),
    }


# ---------------------------------------------------------------- main
def main() -> None:
    print("\nHATHOR — STEP 0 환경 점검")
    print(f"실행 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")

    report = {
        "generated_at": datetime.now().isoformat(),
        "system": check_system(),
        "gpu": check_gpu(),
        "python_env": check_python_env(),
    }

    if len(sys.argv) > 1:
        report["library"] = scan_library(Path(sys.argv[1]).expanduser())
    else:
        hr("4. 음원 라이브러리 스캔")
        print("  경로를 지정하지 않아 건너뛴다.")
        print('  사용법: python step0_check.py "D:/Music"')
        report["library"] = {"skipped": True}

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    hr("완료")
    print(f"  결과 파일: {REPORT_PATH.resolve()}")
    print("  이 파일 내용을 그대로 붙여넣으면 다음 단계를 정한다.")


if __name__ == "__main__":
    main()
