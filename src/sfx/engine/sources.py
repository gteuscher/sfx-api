"""Signal sources. Every function returns a float64 mono array in roughly [-1, 1]."""

from __future__ import annotations

import numpy as np

from sfx.spec.models import FMSource, NoiseSource, OscSource


def _phase(freq_hz: np.ndarray, sr: int) -> np.ndarray:
    """Cumulative phase in cycles for an instantaneous frequency track."""
    return np.cumsum(freq_hz / sr)


def oscillator(src: OscSource, freq_hz: np.ndarray, sr: int) -> np.ndarray:
    n = len(freq_hz)
    ph = _phase(freq_hz, sr) % 1.0
    if src.wave == "sine":
        return np.sin(2 * np.pi * ph)
    if src.wave == "triangle":
        return 4.0 * np.abs(ph - 0.5) - 1.0
    if src.wave == "saw":
        return 2.0 * ph - 1.0
    # square / pulse with optional duty sweep, DC-free so narrow pulses don't thump
    if src.duty_end is None:
        duty = np.full(n, src.duty)
    else:
        duty = np.linspace(src.duty, src.duty_end, n)
    raw = np.where(ph < duty, 1.0, -1.0) - (2.0 * duty - 1.0)
    return raw / (2.0 * np.maximum(duty, 1.0 - duty))


def _pink(white: np.ndarray) -> np.ndarray:
    # Paul Kellet's economy pink filter
    b0 = b1 = b2 = 0.0
    out = np.empty_like(white)
    for i, w in enumerate(white):
        b0 = 0.99765 * b0 + w * 0.0990460
        b1 = 0.96300 * b1 + w * 0.2965164
        b2 = 0.57000 * b2 + w * 1.0526913
        out[i] = b0 + b1 + b2 + w * 0.1848
    return out / 5.0


def _pink_fast(white: np.ndarray) -> np.ndarray:
    from scipy.signal import lfilter

    # Three one-pole sections in parallel, same coefficients as _pink but vectorized
    out = (
        lfilter([0.0990460], [1, -0.99765], white)
        + lfilter([0.2965164], [1, -0.96300], white)
        + lfilter([1.0526913], [1, -0.57000], white)
        + white * 0.1848
    )
    return out / 5.0


def noise(src: NoiseSource, n: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    white = rng.standard_normal(n) * 0.5
    if src.color == "white":
        return np.clip(white, -1, 1)
    if src.color == "pink":
        return np.clip(_pink_fast(white), -1, 1)
    if src.color == "brown":
        from scipy.signal import lfilter

        brown = lfilter([1.0], [1, -0.995], white)
        brown = lfilter([1.0, -1.0], [1, -0.998], brown)  # remove DC drift
        peak = np.max(np.abs(brown)) or 1.0
        return brown / peak
    # bit noise: random +/-1 held for a period set by the (possibly sweeping) bit rate
    if src.bit_rate_end_hz is None:
        rate = np.full(n, src.bit_rate_hz)
    else:
        rate = np.geomspace(src.bit_rate_hz, src.bit_rate_end_hz, n)
    ticks = np.floor(_phase(rate, sr)).astype(np.int64)
    values = rng.choice([-1.0, 1.0], size=int(ticks[-1]) + 2)
    return values[ticks]


def fm(src: FMSource, freq_hz: np.ndarray, sr: int) -> np.ndarray:
    n = len(freq_hz)
    if src.index_curve == "exp" and src.index > 0 and src.index_end > 0:
        index = np.geomspace(src.index, src.index_end, n)
    elif src.index_curve == "exp" and src.index > 0:
        index = src.index * np.exp(-np.linspace(0, 6, n))
    else:
        index = np.linspace(src.index, src.index_end, n)
    car = 2 * np.pi * _phase(freq_hz * src.carrier_ratio, sr)
    mod = 2 * np.pi * _phase(freq_hz * src.mod_ratio, sr)
    return np.sin(car + index * np.sin(mod))
