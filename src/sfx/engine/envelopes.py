"""Amplitude envelopes and pitch trajectories."""

from __future__ import annotations

import numpy as np

from sfx.spec.models import Amp, Pitch


def _ms(ms: float, sr: int) -> int:
    return int(round(ms * sr / 1000.0))


def _segment(start: float, end: float, n: int, curve: str) -> np.ndarray:
    if n <= 0:
        return np.zeros(0)
    if curve == "exp" and start > end:
        # exponential fall that actually reaches `end`
        floor = max(end, 1e-4)
        seg = start * np.exp(np.linspace(0, np.log(floor / start), n)) if start > 0 else np.zeros(n)
        if end <= 0:
            seg = seg - floor
            seg = np.clip(seg, 0, None)
        return seg
    return np.linspace(start, end, n, endpoint=False)


def amp_envelope(amp: Amp, sr: int) -> np.ndarray:
    """Envelope in [0, 1+punch]. Length matches the layer duration exactly."""
    n_a, n_h, n_d, n_s, n_r = (
        _ms(amp.attack_ms, sr),
        _ms(amp.hold_ms, sr),
        _ms(amp.decay_ms, sr),
        _ms(amp.sustain_ms, sr),
        _ms(amp.release_ms, sr),
    )
    parts = [
        np.linspace(0.0, 1.0, n_a, endpoint=False),
        np.ones(n_h),
        _segment(1.0, amp.sustain, n_d, amp.curve),
        np.full(n_s, amp.sustain),
        _segment(amp.sustain, 0.0, n_r, amp.curve),
    ]
    env = np.concatenate(parts) if parts else np.zeros(0)
    if len(env) == 0:
        env = np.zeros(1)

    if amp.punch > 0:
        tau = max(n_d, n_h + n_a, 1) / 4.0
        t = np.arange(len(env))
        boost = 1.0 + amp.punch * np.exp(-np.clip(t - n_a, 0, None) / tau)
        env = env * boost

    if amp.retrigger_hz > 0:
        period = max(int(sr / amp.retrigger_hz), 1)
        # restart the attack+decay shape every period, keep the overall envelope as a ceiling
        one = np.concatenate(
            [np.linspace(0.0, 1.0, max(n_a, 1), endpoint=False), _segment(1.0, 0.0, max(period - n_a, 1), amp.curve)]
        )
        reps = int(np.ceil(len(env) / len(one)))
        gate = np.tile(one, reps)[: len(env)]
        env = env * gate
    return env


def pitch_track(pitch: Pitch, n: int, sr: int) -> np.ndarray:
    """Instantaneous frequency per sample."""
    f0 = pitch.start_hz
    if pitch.end_hz is None or n == 0:
        f = np.full(n, f0)
    else:
        f1 = pitch.end_hz
        n_slide = n if pitch.slide_ms is None else min(_ms(pitch.slide_ms, sr), n)
        if pitch.curve == "step":
            k = min(_ms(pitch.step_at_ms, sr), n)
            f = np.concatenate([np.full(k, f0), np.full(n - k, f1)])
        elif pitch.curve == "linear":
            f = np.concatenate([np.linspace(f0, f1, n_slide), np.full(n - n_slide, f1)])
        else:
            f = np.concatenate([np.geomspace(f0, f1, n_slide) if n_slide > 0 else [], np.full(n - n_slide, f1)])
    t = np.arange(n) / sr
    if pitch.vibrato_cents > 0:
        f = f * 2 ** (pitch.vibrato_cents / 1200.0 * np.sin(2 * np.pi * pitch.vibrato_hz * t))
    if pitch.arpeggio_semitones:
        steps = np.asarray(pitch.arpeggio_semitones, dtype=float)
        idx = (np.floor(t * pitch.arpeggio_hz).astype(int)) % len(steps)
        f = f * 2 ** (steps[idx] / 12.0)
    return np.asarray(f, dtype=float)
