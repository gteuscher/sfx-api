"""Cheap descriptors so an agent can reason about what it rendered."""

from __future__ import annotations

import numpy as np

from sfx.engine.normalize import measure_lufs, peak_db


def analyze(x: np.ndarray, sr: int) -> dict:
    n = len(x)
    if n == 0:
        return {"duration_ms": 0.0}
    ax = np.abs(x)
    peak = float(ax.max())
    rms = float(np.sqrt(np.mean(x**2)))
    # attack: time to reach 90% of peak using a 1 ms smoothed envelope
    k = max(int(sr / 1000), 1)
    env = np.convolve(ax, np.ones(k) / k, mode="same")
    attack_idx = int(np.argmax(env >= 0.9 * env.max())) if env.max() > 0 else 0
    # decay: time from peak to below -40 dB of peak
    thresh = env.max() * 10 ** (-40 / 20)
    after = np.where(env[attack_idx:] < thresh)[0]
    decay_idx = int(after[0]) if len(after) else n - attack_idx
    # spectral centroid over the whole clip
    spec = np.abs(np.fft.rfft(x * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    centroid = float((spec * freqs).sum() / spec.sum()) if spec.sum() > 0 else 0.0
    # rough dominant pitch from the first 100 ms
    head = x[: min(n, int(sr * 0.1))]
    hs = np.abs(np.fft.rfft(head * np.hanning(len(head))))
    hf = np.fft.rfftfreq(len(head), 1 / sr)
    hs[hf < 20] = 0.0
    dominant = float(hf[np.argmax(hs)]) if len(hs) else 0.0
    lufs = measure_lufs(x, sr)
    return {
        "duration_ms": round(n / sr * 1000, 1),
        "peak_dbfs": round(peak_db(x), 2) if peak > 0 else None,
        "rms_dbfs": round(20 * np.log10(rms), 2) if rms > 0 else None,
        "lufs": round(lufs, 2) if lufs is not None else None,
        "attack_ms": round(attack_idx / sr * 1000, 1),
        "decay_to_minus40db_ms": round(decay_idx / sr * 1000, 1),
        "spectral_centroid_hz": round(centroid, 1),
        "dominant_hz_first_100ms": round(dominant, 1),
    }
