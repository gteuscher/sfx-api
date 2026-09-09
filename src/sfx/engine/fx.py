"""Effects. NumPy implementations are always available; pedalboard is used when installed
for reverb, chorus, compressor, and pitch shift because it sounds better.

Set SFX_NO_PEDALBOARD=1 to force the NumPy path.
"""

from __future__ import annotations

import os

import numpy as np
from scipy.signal import lfilter

from sfx.spec.models import (
    Bitcrush,
    Chorus,
    Clip,
    Compressor,
    Delay,
    Distortion,
    Gain,
    PitchShift,
    Reverb,
)

try:  # optional
    import pedalboard as _pb  # type: ignore

    HAVE_PEDALBOARD = os.environ.get("SFX_NO_PEDALBOARD") != "1"
except Exception:  # pragma: no cover
    _pb = None
    HAVE_PEDALBOARD = False


def _db(db: float) -> float:
    return 10 ** (db / 20.0)


# --------------------------------------------------------------------------- numpy effects


def bitcrush(x: np.ndarray, e: Bitcrush, sr: int) -> np.ndarray:
    levels = 2 ** e.bits
    y = np.round(x * (levels / 2)) / (levels / 2)
    if e.rate_hz and e.rate_hz < sr:
        hold = max(int(sr / e.rate_hz), 1)
        idx = (np.arange(len(y)) // hold) * hold
        y = y[np.minimum(idx, len(y) - 1)]
    return y


def distortion(x: np.ndarray, e: Distortion, sr: int) -> np.ndarray:
    drive = _db(e.drive_db)
    return np.tanh(x * drive) / np.tanh(min(drive, 20.0)) * 0.9


def clip(x: np.ndarray, e: Clip, sr: int) -> np.ndarray:
    t = _db(e.threshold_db)
    return np.clip(x, -t, t) / t * 0.9


def compressor(x: np.ndarray, e: Compressor, sr: int) -> np.ndarray:
    att = np.exp(-1.0 / (e.attack_ms * sr / 1000.0))
    rel = np.exp(-1.0 / (e.release_ms * sr / 1000.0))
    env = np.empty_like(x)
    level = 0.0
    ax = np.abs(x)
    for i, a in enumerate(ax):
        coef = att if a > level else rel
        level = coef * level + (1 - coef) * a
        env[i] = level
    env_db = 20 * np.log10(np.maximum(env, 1e-6))
    over = np.maximum(env_db - e.threshold_db, 0.0)
    gain_db = -over * (1 - 1 / e.ratio)
    makeup = -e.threshold_db * (1 - 1 / e.ratio) * 0.5
    return x * _db(gain_db + makeup)


def delay(x: np.ndarray, e: Delay, sr: int) -> np.ndarray:
    d = max(int(e.time_ms * sr / 1000.0), 1)
    y = np.copy(x)
    buf = np.zeros(len(x) + d)
    buf[: len(x)] = x
    # feedback comb, computed iteratively over delay-sized chunks
    for start in range(d, len(buf), d):
        end = min(start + d, len(buf))
        buf[start:end] += e.feedback * buf[start - d : start - d + (end - start)]
    wet = buf[: len(x)]
    return (1 - e.wet) * y + e.wet * wet


def reverb(x: np.ndarray, e: Reverb, sr: int) -> np.ndarray:
    # Schroeder: four combs in parallel, two allpasses in series
    comb_ms = np.array([29.7, 37.1, 41.1, 43.7]) * (0.5 + e.room * 1.5)
    fb = 0.7 + 0.28 * e.room
    damp = e.damping
    wet = np.zeros_like(x)
    for ms in comb_ms:
        d = max(int(ms * sr / 1000.0), 1)
        # comb with one-pole lowpass in the feedback path
        b = [1.0]
        a = np.zeros(d + 2)
        a[0] = 1.0
        a[d] = -fb * (1 - damp)
        a[d + 1] = -fb * damp
        wet += lfilter(b, a, x)
    wet /= len(comb_ms)
    for ms in (5.0, 1.7):
        d = max(int(ms * sr / 1000.0), 1)
        g = 0.5
        b = np.zeros(d + 1)
        b[0], b[d] = -g, 1.0
        a = np.zeros(d + 1)
        a[0], a[d] = 1.0, -g
        wet = lfilter(b, a, wet)
    return (1 - e.wet) * x + e.wet * wet


def chorus(x: np.ndarray, e: Chorus, sr: int) -> np.ndarray:
    n = len(x)
    t = np.arange(n) / sr
    depth = e.depth_ms * sr / 1000.0
    delay_s = depth * (1.0 + np.sin(2 * np.pi * e.rate_hz * t)) + 1.0
    pos = np.arange(n) - delay_s
    pos = np.clip(pos, 0, n - 1)
    wet = np.interp(pos, np.arange(n), x)
    return (1 - e.wet) * x + e.wet * wet


def gain(x: np.ndarray, e: Gain, sr: int) -> np.ndarray:
    return x * _db(e.db)


def pitch_shift(x: np.ndarray, e: PitchShift, sr: int) -> np.ndarray:
    # Resample-based shift (changes duration). pedalboard path preserves duration.
    ratio = 2 ** (e.semitones / 12.0)
    n = len(x)
    pos = np.arange(0, n, ratio)
    pos = pos[pos < n - 1]
    return np.interp(pos, np.arange(n), x)


_NUMPY = {
    "bitcrush": bitcrush,
    "distortion": distortion,
    "clip": clip,
    "compressor": compressor,
    "delay": delay,
    "reverb": reverb,
    "chorus": chorus,
    "gain": gain,
    "pitch_shift": pitch_shift,
}


# --------------------------------------------------------------------------- pedalboard


def _pedalboard_plugin(e):
    if isinstance(e, Reverb):
        return _pb.Reverb(room_size=e.room, damping=e.damping, wet_level=e.wet, dry_level=1 - e.wet, width=0.0)
    if isinstance(e, Chorus):
        return _pb.Chorus(rate_hz=e.rate_hz, depth=min(e.depth_ms / 10.0, 1.0), mix=e.wet)
    if isinstance(e, Compressor):
        return _pb.Compressor(
            threshold_db=e.threshold_db, ratio=e.ratio, attack_ms=e.attack_ms, release_ms=e.release_ms
        )
    if isinstance(e, PitchShift):
        return _pb.PitchShift(semitones=e.semitones)
    return None


def apply_effects(x: np.ndarray, effects, sr: int) -> np.ndarray:
    y = np.asarray(x, dtype=np.float64)
    for e in effects:
        plugin = _pedalboard_plugin(e) if HAVE_PEDALBOARD else None
        if plugin is not None:
            y = plugin(y.astype(np.float32), sr).astype(np.float64)
        else:
            y = _NUMPY[e.type](y, e, sr)
    return y
