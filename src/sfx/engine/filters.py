"""Time-varying resonant biquad filters (RBJ cookbook), processed in short blocks."""

from __future__ import annotations

import numpy as np
from scipy.signal import sosfilt, sosfilt_zi

from sfx.spec.models import Filter

BLOCK = 64


def _coeffs(kind: str, fc: float, q: float, sr: int) -> np.ndarray:
    fc = min(max(fc, 20.0), sr * 0.45)
    w0 = 2 * np.pi * fc / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == "lowpass":
        b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
    elif kind == "highpass":
        b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
    else:  # bandpass, constant peak gain
        b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * cw, 1 - alpha
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


def apply_filter(x: np.ndarray, flt: Filter, sr: int) -> np.ndarray:
    n = len(x)
    if n == 0:
        return x
    if flt.end_cutoff_hz is None:
        return sosfilt(_coeffs(flt.type, flt.cutoff_hz, flt.q, sr), x)

    cutoffs = np.geomspace(flt.cutoff_hz, flt.end_cutoff_hz, max(n // BLOCK, 1) + 1)
    out = np.empty_like(x)
    sos = _coeffs(flt.type, cutoffs[0], flt.q, sr)
    zi = sosfilt_zi(sos) * 0.0
    for i, start in enumerate(range(0, n, BLOCK)):
        sos = _coeffs(flt.type, cutoffs[min(i, len(cutoffs) - 1)], flt.q, sr)
        seg = x[start : start + BLOCK]
        out[start : start + BLOCK], zi = sosfilt(sos, seg, zi=zi)
    return out
