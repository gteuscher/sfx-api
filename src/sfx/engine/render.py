"""Render a SoundSpec to a mono float array."""

from __future__ import annotations

import copy

import numpy as np

from sfx.engine.envelopes import amp_envelope, pitch_track
from sfx.engine.filters import apply_filter
from sfx.engine.fx import apply_effects
from sfx.engine.normalize import normalize
from sfx.engine.sfxr import render_sfxr_at
from sfx.engine.sources import fm, noise, oscillator
from sfx.spec.models import FMSource, Layer, NoiseSource, OscSource, Pitch, SfxrSource, SoundSpec


def _ms(ms: float, sr: int) -> int:
    return int(round(ms * sr / 1000.0))


def render_layer(layer: Layer, sr: int, rng: np.random.Generator) -> np.ndarray:
    src = layer.source
    if isinstance(src, SfxrSource):
        sig = render_sfxr_at(src, sr, rng)
        if layer.filter is not None:
            sig = apply_filter(sig, layer.filter, sr)
        if layer.fx:
            sig = apply_effects(sig, layer.fx, sr)
        return sig * 10 ** (layer.gain_db / 20.0)
    env = amp_envelope(layer.amp, sr)
    n = len(env)
    freq = pitch_track(layer.pitch or Pitch(), n, sr)
    if isinstance(src, OscSource):
        sig = oscillator(src, freq, sr)
    elif isinstance(src, NoiseSource):
        sig = noise(src, n, sr, rng)
    elif isinstance(src, FMSource):
        sig = fm(src, freq, sr)
    else:  # pragma: no cover
        raise ValueError(f"unknown source {src!r}")
    sig = sig * env
    if layer.filter is not None:
        sig = apply_filter(sig, layer.filter, sr)
    if layer.fx:
        sig = apply_effects(sig, layer.fx, sr)
    return sig * 10 ** (layer.gain_db / 20.0)


def render_info(spec: SoundSpec) -> tuple[np.ndarray, dict]:
    """Render and return (audio, normalization info with warnings)."""
    sr = spec.sample_rate
    rng = np.random.default_rng(spec.seed)
    total = _ms(spec.duration_ms(), sr)
    # leave room for layers whose effects lengthen them (delay, pitch shift)
    mix = np.zeros(total, dtype=np.float64)
    for layer in spec.layers:
        sig = render_layer(layer, sr, rng)
        start = _ms(layer.start_ms, sr)
        end = start + len(sig)
        if end > len(mix):
            mix = np.concatenate([mix, np.zeros(end - len(mix))])
        mix[start:end] += sig
    if spec.master.fx:
        mix = apply_effects(mix, spec.master.fx, sr)
    mix, info = normalize(mix, sr, spec.master.target_lufs, spec.master.true_peak_dbtp)
    return mix.astype(np.float32), info


def render(spec: SoundSpec) -> np.ndarray:
    return render_info(spec)[0]


def vary(spec: SoundSpec, rng: np.random.Generator) -> SoundSpec:
    """Return a jittered copy of the spec according to spec.variation."""
    v = spec.variation
    new = copy.deepcopy(spec)
    new.seed = int(rng.integers(0, 2**31 - 1))
    cents = rng.uniform(-v.pitch_cents, v.pitch_cents)
    ratio = 2 ** (cents / 1200.0)
    for i, layer in enumerate(new.layers):
        p = layer.pitch
        if p is not None:
            p.start_hz = float(np.clip(p.start_hz * ratio, 10, 20000))
            if p.end_hz is not None:
                p.end_hz = float(np.clip(p.end_hz * ratio, 10, 20000))
        layer.gain_db = float(np.clip(layer.gain_db + rng.uniform(-v.gain_db, v.gain_db), -60, 12))
        if layer.filter is not None and v.filter_cents > 0:
            fr = 2 ** (rng.uniform(-v.filter_cents, v.filter_cents) / 1200.0)
            layer.filter.cutoff_hz = float(np.clip(layer.filter.cutoff_hz * fr, 20, 20000))
            if layer.filter.end_cutoff_hz is not None:
                layer.filter.end_cutoff_hz = float(np.clip(layer.filter.end_cutoff_hz * fr, 20, 20000))
        if i > 0 and v.timing_ms > 0:
            layer.start_ms = float(max(layer.start_ms + rng.uniform(0, v.timing_ms), 0))
    return new


def render_variations(spec: SoundSpec, count: int) -> list[tuple[SoundSpec, np.ndarray]]:
    rng = np.random.default_rng(spec.seed + 1)
    out = []
    for _ in range(count):
        s = vary(spec, rng)
        out.append((s, render(s)))
    return out
