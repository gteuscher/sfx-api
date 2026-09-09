"""WAV writing with TPDF dither to 16-bit."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def write_wav(path: Path, x: np.ndarray, sr: int, dither: bool = True) -> Path:
    y = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
    if dither:
        rng = np.random.default_rng(12345)
        lsb = 1.0 / 32768.0
        y = y + (rng.random(len(y)) - rng.random(len(y))) * lsb
        y = np.clip(y, -1.0, 1.0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), y, sr, subtype="PCM_16")
    return path


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="float64", always_2d=True)
    return data.mean(axis=1), sr
