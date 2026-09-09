"""Descriptors so an agent can reason about what it rendered.

Definitions (all times in ms, levels in dB):
- onset_ms: first sample louder than -40 dB below the peak.
- attack_ms: onset to the first envelope maximum that reaches at least half the peak.
- decay_ms: from that first maximum until the envelope drops below -40 dB of peak and stays
  there for 20 ms. For sustained or retriggered sounds this runs to the end of activity.
- active_ms: onset to the last sample above -40 dB. The audible length.
- tail_silence_ms: silence after the last active sample.
- pitch_hz_start / pitch_hz_end: autocorrelation pitch of the first and last 40 ms of activity.
  None when there is no clear periodicity (noise-dominated).
- onsets_ms: times where the envelope rises above 30 percent of peak after dipping below 10
  percent, up to 16 entries. Verifies multi-note and stuttered sounds.
- spectral_centroid_hz: magnitude-weighted mean frequency. White noise pulls this high.
- band_db: energy share of low (<250 Hz), mid (250-2000), high (>2000) in dB relative to total.
"""

from __future__ import annotations

import numpy as np

from sfx.engine.normalize import measure_lufs, peak_db

FLOOR_DB = -40.0


def _envelope(x: np.ndarray, sr: int) -> np.ndarray:
    k = max(int(sr / 1000), 1)
    return np.convolve(np.abs(x), np.ones(k) / k, mode="same")


def _pitch(seg: np.ndarray, sr: int) -> float | None:
    n = len(seg)
    if n < 64 or not np.any(seg):
        return None
    seg = seg - seg.mean()
    seg = seg * np.hanning(n)
    ac = np.correlate(seg, seg, mode="full")[n - 1 :]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]
    lo, hi = int(sr / 4000), min(int(sr / 40), n - 1)
    if hi <= lo:
        return None
    # first dip then the best peak after it
    i = lo
    while i < hi and ac[i] > 0:
        i += 1
    if i >= hi:
        return None
    lag = i + int(np.argmax(ac[i:hi]))
    if ac[lag] < 0.35:
        return None
    return float(sr / lag)


def analyze(x: np.ndarray, sr: int) -> dict:
    n = len(x)
    if n == 0:
        return {"duration_ms": 0.0}
    ms = 1000.0 / sr
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x**2)))
    env = _envelope(x, sr)
    emax = float(env.max()) if peak > 0 else 0.0
    floor = emax * 10 ** (FLOOR_DB / 20)

    active = np.where(env >= floor)[0] if emax > 0 else np.array([], dtype=int)
    onset = int(active[0]) if len(active) else 0
    last = int(active[-1]) if len(active) else 0

    # first local maximum >= half peak, on a 2 ms decimated envelope to ignore ripple
    step = max(int(sr / 500), 1)
    dec = env[onset::step]
    first_peak = onset
    if len(dec) > 2:
        for i in range(1, len(dec) - 1):
            if dec[i] >= 0.5 * emax and dec[i] >= dec[i - 1] and dec[i] >= dec[i + 1]:
                first_peak = onset + i * step
                break
        else:
            first_peak = onset + int(np.argmax(dec)) * step

    hold = max(int(0.02 * sr), 1)
    below = env[first_peak:] < floor
    decay_end = last
    if below.any():
        run = np.convolve(below.astype(float), np.ones(hold), mode="valid") >= hold
        idx = np.where(run)[0]
        if len(idx):
            decay_end = first_peak + int(idx[0])

    # onsets: rises above 30% after a dip below 10%, on the 2 ms decimated envelope
    dec_all = env[::step]
    onsets: list[float] = []
    armed = True
    for i, v in enumerate(dec_all):
        if armed and v >= 0.3 * emax:
            onsets.append(round(i * step * ms, 1))
            armed = False
        elif not armed and v < 0.1 * emax:
            armed = True
        if len(onsets) >= 16:
            break

    w = int(0.04 * sr)
    head = x[onset : onset + w]
    tail = x[max(last - w, onset) : last + 1]

    spec = np.abs(np.fft.rfft(x * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    total = float((spec**2).sum()) or 1.0
    centroid = float((spec * freqs).sum() / spec.sum()) if spec.sum() > 0 else 0.0

    def band(lo, hi):
        e = float((spec[(freqs >= lo) & (freqs < hi)] ** 2).sum())
        return round(10 * np.log10(e / total), 1) if e > 0 else None

    lufs = measure_lufs(x, sr)
    return {
        "duration_ms": round(n * ms, 1),
        "active_ms": round((last - onset + 1) * ms, 1),
        "onset_ms": round(onset * ms, 1),
        "attack_ms": round((first_peak - onset) * ms, 1),
        "decay_ms": round((decay_end - first_peak) * ms, 1),
        "tail_silence_ms": round((n - 1 - last) * ms, 1),
        "onsets_ms": onsets,
        "peak_dbfs": round(peak_db(x), 2) if peak > 0 else None,
        "rms_dbfs": round(20 * np.log10(rms), 2) if rms > 0 else None,
        "lufs": round(lufs, 2) if lufs is not None else None,
        "pitch_hz_start": (lambda p: round(p, 1) if p else None)(_pitch(head, sr)),
        "pitch_hz_end": (lambda p: round(p, 1) if p else None)(_pitch(tail, sr)),
        "spectral_centroid_hz": round(centroid, 1),
        "band_db": {"low": band(0, 250), "mid": band(250, 2000), "high": band(2000, sr / 2)},
    }
