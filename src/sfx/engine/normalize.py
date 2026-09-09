"""Loudness normalization and true-peak ceiling."""

from __future__ import annotations

import warnings

import numpy as np
import pyloudnorm as pyln

MIN_MEASURE_S = 0.5


def measure_lufs(x: np.ndarray, sr: int) -> float | None:
    """Integrated loudness. Short sounds are zero-padded to the meter's minimum block."""
    if len(x) == 0 or not np.any(x):
        return None
    need = int(MIN_MEASURE_S * sr)
    y = x if len(x) >= need else np.concatenate([x, np.zeros(need - len(x))])
    meter = pyln.Meter(sr)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = meter.integrated_loudness(y.astype(np.float64))
    if not np.isfinite(val):
        return None
    return float(val)


def peak_db(x: np.ndarray) -> float:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return 20 * np.log10(p) if p > 0 else -np.inf


def limiter(y: np.ndarray, ceiling: float, sr: int, lookahead_ms: float = 1.5, release_ms: float = 60.0) -> np.ndarray:
    """Look-ahead peak limiter. Gain drops instantly ahead of a peak and recovers smoothly."""
    from scipy.ndimage import minimum_filter1d

    n = len(y)
    if n == 0:
        return y
    la = max(int(sr * lookahead_ms / 1000.0), 1)
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(y), 1e-9))
    # each sample's gain must satisfy every peak within the next `la` samples
    need = minimum_filter1d(need, size=la, mode="nearest", origin=-(la // 2))
    rel = np.exp(-1.0 / (release_ms * sr / 1000.0))
    g = np.empty(n)
    cur = 1.0
    for i in range(n):
        v = need[i]
        cur = v if v < cur else cur + (1.0 - rel) * (v - cur)
        g[i] = cur
    return y * g


def normalize(x: np.ndarray, sr: int, target_lufs: float | None, ceiling_dbtp: float) -> tuple[np.ndarray, dict]:
    """Returns (audio, info). info has gain_db, limited_db, lufs, target_miss_db, warnings."""
    y = np.asarray(x, dtype=np.float64)
    y = y - np.mean(y) if len(y) else y
    ceiling = 10 ** (ceiling_dbtp / 20.0)
    info: dict = {"gain_db": 0.0, "limited_db": 0.0, "warnings": []}
    if target_lufs is not None:
        lufs = measure_lufs(y, sr)
        if lufs is not None:
            gain = 10 ** ((target_lufs - lufs) / 20.0)
            # never ask the limiter for more than 3 dB; scale the rest so transients survive
            cap = ceiling * 10 ** (3 / 20)
            peak = float(np.max(np.abs(y))) * gain if len(y) else 0.0
            if peak > cap:
                gain *= cap / peak
            y = y * gain
            info["gain_db"] = round(20 * np.log10(gain), 2)
    # true-peak approximation: 4x oversampled peak
    up = np.interp(np.arange(0, len(y), 0.25), np.arange(len(y)), y) if len(y) > 1 else y
    peak = float(np.max(np.abs(up))) if len(up) else 0.0
    if peak > ceiling and peak > 0:
        info["limited_db"] = round(20 * np.log10(peak / ceiling), 2)
        y = limiter(y, ceiling * 0.98, sr)
        y = np.clip(y, -ceiling, ceiling)
    final = measure_lufs(y, sr)
    info["lufs"] = round(final, 2) if final is not None else None
    if target_lufs is not None and final is not None:
        miss = round(final - target_lufs, 2)
        info["target_miss_db"] = miss
        if miss < -1.5:
            info["warnings"].append(
                f"loudness landed {abs(miss)} dB below target_lufs: the true_peak_dbtp ceiling stopped the gain, "
                "so this sound is effectively peak-normalized. Normal for sounds under about 250 ms; raising "
                "target_lufs will not help. If it matters, lower amp.punch, use linear decay, or lengthen it; "
                "a master compressor helps only partially on short sounds."
            )
    if info["limited_db"] > 3:
        info["warnings"].append(f"peak limiter worked hard ({info['limited_db']} dB); transients may be squashed")
    return y, info
