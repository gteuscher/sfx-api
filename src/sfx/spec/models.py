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
    """Two-operator FM. Good for bells, UI blips, metallic hits, and sci-fi tones.
    index 1 to 3 is mellow and electric-piano like, 4 to 8 is bright and bell like,
    10 to 20 is clangorous metal and noise. Inharmonic mod_ratio (1.41, 2.76, 3.7, 5.3)
    gives metal and glass; integer ratios give musical tones."""

    type: Literal["fm"] = "fm"
    carrier_ratio: float = Field(
        1.0, gt=0, description="Carrier frequency as a multiple of the pitch. 2 sounds an octave up, 0.5 an octave down."
    )
    mod_ratio: float = Field(2.0, gt=0, description="Modulator frequency as a multiple of the pitch.")
    index: float = Field(2.0, ge=0, le=20, description="Modulation index at note start. Higher is brighter.")
    index_end: float = Field(
        0.0, ge=0, le=20, description="Modulation index at note end. 0 leaves a pure sine tail; 1 to 2 keeps a metallic ring."
    )
    index_curve: Literal["linear", "exp"] = "exp"


class SfxrSource(_Model):
    """A complete sfxr / jsfxr sound as one source. Field names and ranges match jsfxr, so
    existing sfxr presets paste straight in. When a layer uses this source, the layer's own
    pitch and amp settings are ignored: sfxr has its own envelope and pitch model. Layer
    filter, fx, gain, and start_ms still apply."""

    type: Literal["sfxr"] = "sfxr"
    wave: Literal["square", "saw", "sine", "noise"] = "square"
    p_env_attack: float = Field(0.0, ge=0, le=1)
    p_env_sustain: float = Field(0.3, ge=0, le=1)
    p_env_punch: float = Field(0.0, ge=0, le=1)
    p_env_decay: float = Field(0.4, ge=0, le=1)
    p_base_freq: float = Field(0.3, ge=0, le=1, description="0.3 is about 440 Hz, 0.5 about 1200 Hz.")
    p_freq_limit: float = Field(0.0, ge=0, le=1, description="Stop when pitch falls below this. 0 disables.")
    p_freq_ramp: float = Field(0.0, ge=-1, le=1, description="Pitch slide. Negative falls.")
    p_freq_dramp: float = Field(0.0, ge=-1, le=1, description="Change of slide over time.")
    p_vib_strength: float = Field(0.0, ge=0, le=1)
    p_vib_speed: float = Field(0.0, ge=0, le=1)
    p_arp_mod: float = Field(0.0, ge=-1, le=1, description="Pitch jump after arp_speed. Positive jumps up.")
    p_arp_speed: float = Field(0.0, ge=0, le=1, description="When the jump happens. 1 disables.")
    p_duty: float = Field(0.0, ge=0, le=1, description="Square only. 0 is 50 percent, 1 is a needle.")
    p_duty_ramp: float = Field(0.0, ge=-1, le=1)
    p_repeat_speed: float = Field(0.0, ge=0, le=1, description="Retrigger rate. 0 disables.")
    p_pha_offset: float = Field(0.0, ge=-1, le=1, description="Phaser / flanger offset.")
    p_pha_ramp: float = Field(0.0, ge=-1, le=1)
    p_lpf_freq: float = Field(1.0, ge=0, le=1, description="1 bypasses the low-pass filter.")
    p_lpf_ramp: float = Field(0.0, ge=-1, le=1)
    p_lpf_resonance: float = Field(0.0, ge=0, le=1)
    p_hpf_freq: float = Field(0.0, ge=0, le=1)
    p_hpf_ramp: float = Field(0.0, ge=-1, le=1)
    sound_vol: float = Field(0.5, ge=0, le=1)


Source = Annotated[Union[OscSource, NoiseSource, FMSource, SfxrSource], Field(discriminator="type")]


# --------------------------------------------------------------------------- modulation


class Pitch(_Model):
    """Pitch trajectory for osc and fm sources. Noise sources ignore it entirely (bit noise
    has its own bit_rate_hz), so omit pitch on noise layers. Slides run over slide_ms then hold
    end_hz; slide_ms null means the layer's full envelope length; slide_ms longer than the layer
    is clipped, the layer is never extended. With curve step only step_at_ms matters. Vibrato and
    arpeggio multiply on top of the slide. arpeggio_semitones loops through the list for the
    whole layer, one entry per 1/arpeggio_hz seconds, starting at the first entry."""

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
    """Amplitude envelope. Layer length is attack + hold + decay + sustain_ms + release, except
    that release is skipped when sustain is 0 (decay already reaches silence). With curve exp,
    decay_ms is the time to -60 dB (silence) and the level passes -40 dB at two thirds of it, so
    the audible length is a little shorter than decay_ms; use linear for a fuller decay.
    retrigger_hz restarts a gate every 1/retrigger_hz seconds: the gate rises over
    attack_ms then falls to silence over the rest of that period (so the gate's own decay is the
    period minus attack, not decay_ms). The gate multiplies the overall envelope, so a stutter
    still fades with decay_ms and ends with the layer; hold and sustain shape only the overall
    envelope. Pitch slides, filter sweeps, oscillator phase
    and noise continue uninterrupted across retriggers; only amplitude restarts."""

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
    """Resonant biquad filter with optional cutoff sweep across the layer's full envelope length
    (exponential from cutoff_hz to end_cutoff_hz, reaching end_cutoff_hz at the last sample). Gain at cutoff is 0 dB, so a narrow bandpass (q above 2) on
    noise passes little energy: raise the layer's gain_db by 6 to 12 dB to compensate."""

    type: Literal["lowpass", "highpass", "bandpass"] = "lowpass"
    cutoff_hz: float = Field(8000.0, ge=20, le=20000)
    end_cutoff_hz: float | None = Field(None, ge=20, le=20000, description="If set, cutoff sweeps exponentially.")
    q: float = Field(0.707, ge=0.1, le=20, description="Resonance. 0.707 is flat, 4 or more rings.")


# --------------------------------------------------------------------------- effects


class Bitcrush(_Model):
    """Lower bits for more grit (4 is harsh, 8 is classic, 12 is subtle); lower rate_hz for
    aliasing crunch. There is no drive parameter; to soften it, raise bits."""

    type: Literal["bitcrush"] = "bitcrush"
    bits: float = Field(8, ge=1, le=16)
    rate_hz: float | None = Field(None, ge=500, le=48000, description="Sample-rate reduction. None keeps full rate.")


class Distortion(_Model):
    """Soft clip (tanh). Output is normalized to about -1 dBFS regardless of drive, so a
    distorted layer lands hot in the mix; lower its gain_db to balance."""

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
    """Feedback echo. wet is a mix ratio. On a layer the echoes are cut at the layer's end,
    so put delay on master and set tail_ms for the repeats to ring out."""

    type: Literal["delay"] = "delay"
    time_ms: float = Field(120.0, ge=1, le=2000)
    feedback: float = Field(0.3, ge=0, le=0.95)
    wet: float = Field(0.3, ge=0, le=1)


class Reverb(_Model):
    """wet is a mix ratio: dry is scaled by 1 - wet. Audible tail is roughly room x 800 ms
    (room 0.2 about 150 ms, 0.5 about 400 ms, 0.9 about 700 ms); set master.tail_ms to match.
    On a layer the tail is cut at the layer's end, so put reverb on master for tails."""

    type: Literal["reverb"] = "reverb"
    room: float = Field(0.3, ge=0, le=1, description="Room size. 0.1 is a closet, 0.9 is a hall.")
    damping: float = Field(0.5, ge=0, le=1, description="High-frequency damping of the tail.")
    wet: float = Field(0.2, ge=0, le=1)


class Chorus(_Model):
    """Modulated short delay. wet is a mix ratio: dry is scaled by 1 - wet."""

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
    """One voice. Signal chain: source -> pitch and amp envelope -> filter -> fx (in order) ->
    gain_db, then placed at start_ms and summed with the other layers."""

    id: str = Field("layer", description="Short label such as transient, body, tail.")
    source: Source = Field(default_factory=OscSource)
    pitch: Pitch | None = Field(
        None, description="Pitch for osc and fm sources. Omit for noise. Defaults to a steady 440 Hz."
    )
    amp: Amp = Field(default_factory=Amp)
    filter: Filter | None = None
    fx: list[Effect] = Field(default_factory=list)
    gain_db: float = Field(0.0, ge=-60, le=12)
    start_ms: float = Field(0.0, ge=0, description="When this layer starts relative to the sound.")

    def duration_ms(self) -> float:
        if isinstance(self.source, SfxrSource):
            s = self.source
            return (s.p_env_attack**2 + s.p_env_sustain**2 + s.p_env_decay**2) * 100000 / 44.1
        a = self.amp
        release = a.release_ms if a.sustain > 0 else 0.0
        return a.attack_ms + a.hold_ms + a.decay_ms + a.sustain_ms + release


class Master(_Model):
    """After the layers are summed: master fx (in order) -> DC removal -> gain to target_lufs ->
    true-peak limiter at true_peak_dbtp (the limiter runs even when target_lufs is null).
    Loudness is measured over at least 400 ms, so sounds shorter than that read quieter than
    they are and the peak ceiling usually stops them below target; long sounds with high crest
    factor (punch, distortion, a loud transient over a quiet body) miss for the same reason. The
    limiter contributes at most 3 dB; the render result reports target_miss_db and a warning. Fix it with
    a compressor, less punch, or a longer sound, not a higher target. For deliberately quiet
    sounds set target_lufs to null and use layer gain_db."""

    fx: list[Effect] = Field(default_factory=list)
    target_lufs: float | None = Field(
        -18.0, le=0, ge=-40, description="Integrated loudness target. null skips loudness normalization."
    )
    true_peak_dbtp: float = Field(-1.0, le=0, ge=-12, description="Peak ceiling after normalization.")
    tail_ms: float = Field(
        0.0, ge=0, description="Silence appended after the last layer so master reverb and delay tails ring out."
    )


class Variation(_Model):
    """Random jitter applied per variation render. Values are maximum deviations. Each variation
    also gets a new seed, so noise layers differ even when nothing else moves."""

    pitch_cents: float = Field(
        50.0, ge=0, le=1200,
        description="Applied to every osc and fm layer together. Noise ignores it; use filter_cents for noise sounds.",
    )
    filter_cents: float = Field(
        0.0, ge=0, le=1200, description="Random shift of filter cutoffs, the way to vary noise-based sounds like footsteps."
    )
    timing_ms: float = Field(
        0.0, ge=0, le=500, description="Random extra delay of 0 to timing_ms on every layer except the first, which stays put."
    )
    gain_db: float = Field(
        1.0, ge=0, le=12, description="Per-layer level jitter. Applied before normalization, so it changes balance between layers, not overall loudness."
    )


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


def compact_schema() -> str:
    """A short, readable field list for agents. The full JSON schema is at sfx://schema."""
    lines: list[str] = []

    def walk(model, prefix: str) -> None:
        doc = " ".join((model.__doc__ or "").split())
        lines.append(f"\n{prefix or model.__name__}: {doc}" if doc else f"\n{prefix or model.__name__}")
        for name, f in model.model_fields.items():
            ann = f.annotation
            bounds = []
            for m in f.metadata:
                for k in ("ge", "le", "gt", "lt", "min_length"):
                    v = getattr(m, k, None)
                    if v is not None:
                        bounds.append(f"{k}={v}")
            default = f.default if f.default is not None and not callable(f.default) else None
            typ = str(ann).replace("typing.", "").replace("sfx.spec.models.", "")
            typ = typ.replace("Annotated[Union[", "one of [").replace("], FieldInfo", "")
            typ = typ[:60]
            desc = f" - {f.description}" if f.description else ""
            dflt = f" (default {json.dumps(default)})" if default is not None and not isinstance(default, BaseModel) else ""
            b = f" [{', '.join(bounds)}]" if bounds else ""
            lines.append(f"  {prefix + '.' if prefix else ''}{name}: {typ}{b}{dflt}{desc}")

    walk(SoundSpec, "")
    walk(Layer, "layers[]")
    for src in (OscSource, NoiseSource, FMSource, SfxrSource):
        walk(src, f"source(type={src.model_fields['type'].default})")
    walk(Pitch, "pitch")
    walk(Amp, "amp")
    walk(Filter, "filter")
    for fx in (Bitcrush, Distortion, Clip, Compressor, Delay, Reverb, Chorus, Gain, PitchShift):
        walk(fx, f"fx[](type={fx.model_fields['type'].default})")
    walk(Master, "master")
    walk(Variation, "variation")
    return "\n".join(lines).strip()
