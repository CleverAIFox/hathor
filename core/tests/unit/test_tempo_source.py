"""입구가 템포를 어디서 가져오나 (D-0396 · D-0392 · O-46).

**가르는 법은 섰고 그 길은 안 밟혀 있었다.** `reference_tempo`는 100%인데
`tempo_source`는 **21줄 중 16줄이 안 돌았다**(실측 24% · D-0395의 `make check` 로그).
D-0395가 *«말이 배선과 달랐다»*를 고친 판인데, **그 배선 자체가 시험을 안 받고 있었다.**

차례는 **사람 → 참조곡 → 코퍼스 중앙**이고 갈림길이 넷이다. 넷 다 **`tempo_from`에
다른 말을 적는다** — 그 말이 산출물에 실리므로 들어 보고 되물을 수 있다 (D-0269).
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import numpy as np
import pytest

from hathor.domain.services.midi_writer import DEFAULT_TEMPO_BPM
from hathor.infrastructure.onset_store import write_envelope
from hathor.interfaces.cli.tempo_source import resolve_tempo

if TYPE_CHECKING:
    from pathlib import Path

HOP = 0.05
"""그의 산출물과 같은 홉 (`keys-0.05s.onsets`)."""


def _args(tempo: int | None) -> argparse.Namespace:
    return argparse.Namespace(tempo=tempo)


def _pulse(bpm: float, seconds: float = 20.0) -> np.ndarray:
    """그 빠르기로 또박또박 치는 포락선. **합성이라 정답을 안다.**"""
    frames = int(seconds / HOP)
    envelope = np.zeros(frames, dtype=np.float64)
    envelope[:: max(1, round(60.0 / bpm / HOP))] = 1.0
    return envelope


def _store(root: Path, songs: dict[str, float]) -> None:
    """`var/ingest/keys-<홉>s.onsets`에 포락선을 깐다. **`find_envelope_root`가 보는 꼴.**"""
    folder = root / "var" / "ingest" / f"keys-{HOP:g}s.onsets"
    for key, bpm in songs.items():
        write_envelope(folder, key, _pulse(bpm), hop_seconds=HOP)


def _looks_at(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """저장소 루트를 픽스처로 돌린다. **함수 안에서 임포트하므로 원본을 갈아야 한다.**"""
    monkeypatch.setattr("hathor.shared.config.paths.repo_root", lambda: root)


def test_사람이_주면_그대로_쓴다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**참조곡이 있어도 안 본다.** 손으로 박은 값이 가장 세다."""
    _store(tmp_path, {"가.mp3": 96.0})
    _looks_at(tmp_path, monkeypatch)

    assert resolve_tempo(_args(108), ["가.mp3"]) == (108, "사람이 줬다")


def test_산출물이_없으면_코퍼스_중앙으로_떨어진다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**0이나 예외가 아니다.** 안 뽑아 본 기기에서도 생성은 돌아야 한다."""
    _looks_at(tmp_path, monkeypatch)

    found, said = resolve_tempo(_args(None), ["가.mp3"])

    assert found == DEFAULT_TEMPO_BPM
    assert said == "기본값 — 온셋 산출물이 없다"


def test_참조곡이_저장분에_없으면_수를_적어_말한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**«없다»가 아니라 «몇 곡이 없다»다** (GR-0.5). 폴더는 있고 그 곡이 없는 경우다."""
    _store(tmp_path, {"있는곡.mp3": 120.0})
    _looks_at(tmp_path, monkeypatch)

    found, said = resolve_tempo(_args(None), ["없는곡1.mp3", "없는곡2.mp3"])

    assert found == DEFAULT_TEMPO_BPM
    assert said == "기본값 — 참조 2곡이 저장분에 없다"
    assert "코퍼스 중앙 템포를 쓴다" in capsys.readouterr().err


def test_참조곡에서_뽑으면_몇_곡_중앙인지_적는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**120과 128의 중앙은 124다.** 둘 다 접는 선 위라 접기가 안 끼어든다."""
    _store(tmp_path, {"가.mp3": 120.0, "나.mp3": 128.0})
    _looks_at(tmp_path, monkeypatch)

    found, said = resolve_tempo(_args(None), ["가.mp3", "나.mp3"])

    assert 118 <= found <= 130
    assert said == "참조 2/2곡 중앙"


def test_저장분에_있는_곡만_센다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**물어본 수와 읽은 수가 다르면 그 차이를 적는다.** 셋을 묻고 둘을 읽었다."""
    _store(tmp_path, {"가.mp3": 120.0, "나.mp3": 128.0})
    _looks_at(tmp_path, monkeypatch)

    _, said = resolve_tempo(_args(None), ["가.mp3", "나.mp3", "없는곡.mp3"])

    assert said == "참조 2/3곡 중앙"


def test_박을_못_읽으면_판정의_말을_그대로_싣는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**평평한 포락선에는 박이 없다.** 이때 `tempo_from`은 판정이 쓴 말이다."""
    folder = tmp_path / "var" / "ingest" / f"keys-{HOP:g}s.onsets"
    write_envelope(folder, "조용한곡.mp3", np.zeros(400, dtype=np.float64), hop_seconds=HOP)
    _looks_at(tmp_path, monkeypatch)

    found, said = resolve_tempo(_args(None), ["조용한곡.mp3"])

    assert found == DEFAULT_TEMPO_BPM
    assert said == "기본값 — 참조 1곡에서 박을 못 읽었다"


def test_네_말이_서로_다르다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**같은 말이 두 길에서 나오면 산출물을 보고 길을 못 가른다** (D-0269).

    D-0392가 말을 네 가지로 적었고 **그 넷이 정말 다른지는 아무도 안 봤다.**
    """
    _store(tmp_path, {"가.mp3": 120.0})
    _looks_at(tmp_path, monkeypatch)
    said = [
        resolve_tempo(_args(108), ["가.mp3"])[1],
        resolve_tempo(_args(None), ["가.mp3"])[1],
        resolve_tempo(_args(None), ["없는곡.mp3"])[1],
        resolve_tempo(_args(None), [])[1],
    ]

    assert len(set(said)) == len(said)
