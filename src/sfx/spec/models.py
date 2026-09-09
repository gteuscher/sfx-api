"""SoundSpec: the JSON contract an agent writes to describe a sound.

A sound is a stack of layers rendered in parallel, mixed, then mastered.
Each layer has a source, a pitch curve, an amplitude envelope, an optional
filter, and an optional effect chain. Times are milliseconds, frequencies
are hertz, levels are decibels unless stated otherwise.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- sources


class OscSource(_Model):
    """Classic oscillator. Square with duty < 0.5 gives the thin NES pulse sound."""

    type: Literal["osc"] = "osc"
    wave: Literal["sine", "triangle", "saw", "square"] = Field(
        "square", description="Waveform. square is a pulse wave whose width is set by duty."
    )
    duty: float = Field(0.5, ge=0.05, le=0.95, description="Pulse width for square, 0.5 is symmetric.")
    duty_end: float | None = Field(
        None, ge=0.05, le=0.95, description="If set, duty sweeps linearly from duty to duty_end."
    )


class NoiseSource(_Model):
    """Noise. white is bright, pink is balanced, brown is rumbly, bit is chiptune LFSR noise."""

    type: Literal["noise"] = "noise"
    color: Literal["white", "pink", "brown", "bit"] = "white"
    bit_rate_hz: float = Field(
        8000, ge=100, le=48000, description="For bit noise: sample-and-hold rate. Lower is crunchier."
    )
    bit_rate_end_hz: float | None = Field(
        None, ge=100, le=48000, description="If set, bit rate sweeps exponentially to this value."
    )


class FMSource(_Model):
    """Two-operator FM. Good for bells, UI blips, metallic hits, and sci-fi tones."""

    type: Literal["fm"] = "fm"
    carrier_ratio: float = Field(1.0, gt=0, description="Carrier frequency as a multiple of the pitch.")
    mod_ratio: float = Field(2.0, gt=0, description="Modulator frequency as a multiple of the pitch.")
    index: float = Field(2.0, ge=0, le=20, description="Modulation index at note start. Higher is brighter.")
    index_end: float = Field(0.0, ge=0, le=20, description="Modulation index at note end.")
    index_curve: Literal["linear", "exp"] = "exp"


Source = Annotated[Union[OscSource, NoiseSource, FMSource], Field(discriminator="type")]


# --------------------------------------------------------------------------- modulation


class Pitch(_Model):
    """Pitch trajectory. Noise sources ignore start_hz except for bit noise rate (use bit_rate_hz)."""

    start_hz: float = Field(440.0, ge=10, le=20000)
    end_hz: float | None = Field(None, ge=10, le=20000, description="Target pitch. None means no slide.")
    curve: Literal["linear", "exp", "step"] = Field(
        "exp", description="exp glides musically, linear is a plain ramp, step jumps at step_at_ms."
    )
    slide_ms: float | None = Field(
        None, ge=0, description="How long the glide takes. None means the whole layer duration."
    )
    step_at_ms: float = Field(80.0, ge=0, description="For curve=step: when the pitch jumps to end_hz.")
    vibrato_cents: float = Field(0.0, ge=0, le=1200, description="Vibrato depth. 0 disables.")
    vibrato_hz: float = Field(6.0, ge=0.1, le=60)
    arpeggio_semitones: list[float] = Field(
        default_factory=list,
        description="Cycle through these semitone offsets at arpeggio_hz. Empty disables.",
    )
    arpeggio_hz: float = Field(30.0, ge=0.5, le=200)


class Amp(_Model):
    """Amplitude envelope. Layer length is attack + hold + decay + sustain_ms + release."""

    attack_ms: float = Field(2.0, ge=0)
    hold_ms: float = Field(0.0, ge=0, description="Time at full level after the attack.")
    decay_ms: float = Field(150.0, ge=0, description="Time to fall from full level to sustain level.")
    sustain: float = Field(0.0, ge=0, le=1, description="Sustain level, 0 to 1.")
    sustain_ms: float = Field(0.0, ge=0, description="How long to hold the sustain level.")
    release_ms: float = Field(20.0, ge=0)
    punch: float = Field(0.0, ge=0, le=1, description="Extra transient boost at the start, sfxr style.")
    retrigger_hz: float = Field(
        0.0, ge=0, le=200, description="Restart the envelope at this rate for a stuttered repeat. 0 disables."
    )
    curve: Literal["linear", "exp"] = Field("exp", description="Shape of the decay and release.")


class Filter(_Model):
    """Resonant biquad filter with optional cutoff sweep over the layer."""

    type: Literal["lowpass", "highpass", "bandpass"] = "lowpass"
    cutoff_hz: float = Field(8000.0, ge=20, le=20000)
    end_cutoff_hz: float | None = Field(None, ge=20, le=20000, description="If set, cutoff sweeps exponentially.")
    q: float = Field(0.707, ge=0.1, le=20, description="Resonance. 0.707 is flat, 4 or more rings.")


# --------------------------------------------------------------------------- effects


class Bitcrush(_Model):
    type: Literal["bitcrush"] = "bitcrush"
    bits: float = Field(8, ge=1, le=16)
    rate_hz: float | None = Field(None, ge=500, le=48000, description="Sample-rate reduction. None keeps full rate.")


class Distortion(_Model):
    type: Literal["distortion"] = "distortion"
    drive_db: float = Field(12.0, ge=0, le=60, description="Gain into a soft clipper.")


class Clip(_Model):
    type: Literal["clip"] = "clip"
    threshold_db: float = Field(-6.0, le=0, ge=-40, description="Hard clip level.")


class Compressor(_Model):
    type: Literal["compressor"] = "compressor"
    threshold_db: float = Field(-18.0, le=0, ge=-60)
    ratio: float = Field(4.0, ge=1, le=20)
    attack_ms: float = Field(2.0, ge=0.1)
    release_ms: float = Field(80.0, ge=1)


class Delay(_Model):
    type: Literal["delay"] = "delay"
    time_ms: float = Field(120.0, ge=1, le=2000)
    feedback: float = Field(0.3, ge=0, le=0.95)
    wet: float = Field(0.3, ge=0, le=1)


class Reverb(_Model):
    type: Literal["reverb"] = "reverb"
    room: float = Field(0.3, ge=0, le=1, description="Room size. 0.1 is a closet, 0.9 is a hall.")
    damping: float = Field(0.5, ge=0, le=1, description="High-frequency damping of the tail.")
    wet: float = Field(0.2, ge=0, le=1)


class Chorus(_Model):
    type: Literal["chorus"] = "chorus"
    rate_hz: float = Field(1.5, ge=0.05, le=20)
    depth_ms: float = Field(4.0, ge=0.1, le=30)
    wet: float = Field(0.5, ge=0, le=1)


class Gain(_Model):
    type: Literal["gain"] = "gain"
    db: float = Field(0.0, ge=-60, le=24)


class PitchShift(_Model):
    type: Literal["pitch_shift"] = "pitch_shift"
    semitones: float = Field(0.0, ge=-24, le=24)


Effect = Annotated[
    Union[Bitcrush, Distortion, Clip, Compressor, Delay, Reverb, Chorus, Gain, PitchShift],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- layer, master, spec


class Layer(_Model):
    id: str = Field("layer", description="Short label such as transient, body, tail.")
    source: Source = Field(default_factory=OscSource)
    pitch: Pitch = Field(default_factory=Pitch)
    amp: Amp = Field(default_factory=Amp)
    filter: Filter | None = None
    fx: list[Effect] = Field(default_factory=list)
    gain_db: float = Field(0.0, ge=-60, le=12)
    start_ms: float = Field(0.0, ge=0, description="When this layer starts relative to the sound.")

    def duration_ms(self) -> float:
        a = self.amp
        return a.attack_ms + a.hold_ms + a.decay_ms + a.sustain_ms + a.release_ms


class Master(_Model):
    fx: list[Effect] = Field(default_factory=list)
    target_lufs: float | None = Field(
        -18.0, le=0, ge=-40, description="Integrated loudness target. None skips loudness normalization."
    )
    true_peak_dbtp: float = Field(-1.0, le=0, ge=-12, description="Peak ceiling after normalization.")
    tail_ms: float = Field(0.0, ge=0, description="Silence appended so reverb and delay tails can ring out.")


class Variation(_Model):
    """Random jitter applied per variation render. Values are maximum deviations."""

    pitch_cents: float = Field(50.0, ge=0, le=1200)
    timing_ms: float = Field(0.0, ge=0, le=500, description="Random delay applied to layers after the first.")
    gain_db: float = Field(1.0, ge=0, le=12)


class SoundSpec(_Model):
    name: str = Field("sound", description="Used for the output file name. Letters, digits, underscores.")
    seed: int = Field(0, ge=0, description="Seed for noise and variation randomness.")
    sample_rate: Literal[22050, 44100, 48000] = 44100
    layers: list[Layer] = Field(default_factory=lambda: [Layer()], min_length=1)
    master: Master = Field(default_factory=Master)
    variation: Variation = Field(default_factory=Variation)

    def duration_ms(self) -> float:
        end = max(layer.start_ms + layer.duration_ms() for layer in self.layers)
        return end + self.master.tail_ms


def spec_json_schema() -> dict:
    return SoundSpec.model_json_schema()
