import numpy as np
import pytest

from sfx import store
from sfx.engine.analyze import analyze
from sfx.engine.envelopes import amp_envelope, pitch_track
from sfx.engine.render import render, render_variations
from sfx.spec.models import Amp, Layer, Pitch, SoundSpec

SR = 44100


def test_envelope_length_and_shape():
    amp = Amp(attack_ms=10, hold_ms=10, decay_ms=100, sustain=0.5, sustain_ms=50, release_ms=30, curve="linear")
    env = amp_envelope(amp, SR)
    assert len(env) == round(0.2 * SR)
    assert env[0] == 0.0
    assert env[int(0.015 * SR)] == pytest.approx(1.0)
    assert env[int(0.15 * SR)] == pytest.approx(0.5, abs=0.02)
    assert env[-1] < 0.05


def test_pitch_exp_slide_hits_target():
    f = pitch_track(Pitch(start_hz=1000, end_hz=250, curve="exp", slide_ms=100), int(0.2 * SR), SR)
    assert f[0] == pytest.approx(1000)
    assert f[int(0.05 * SR)] == pytest.approx(500, rel=0.02)
    assert f[-1] == pytest.approx(250)


def test_pitch_step():
    f = pitch_track(Pitch(start_hz=988, end_hz=1319, curve="step", step_at_ms=80), int(0.2 * SR), SR)
    assert f[int(0.079 * SR)] == 988
    assert f[int(0.081 * SR)] == 1319


def test_render_has_expected_duration_and_level():
    spec = SoundSpec(name="t", layers=[Layer(amp=Amp(attack_ms=1, decay_ms=200, release_ms=50))])
    x = render(spec)
    assert len(x) == round(0.201 * SR)  # release skipped when sustain is 0
    assert np.max(np.abs(x)) <= 10 ** (-1 / 20) + 1e-3
    assert np.max(np.abs(x)) > 0.1


def test_every_builtin_preset_renders():
    for name, raw in store.builtin_presets().items():
        spec = SoundSpec.model_validate(raw)
        x = render(spec)
        assert len(x) > 0, name
        assert np.isfinite(x).all(), name
        assert np.max(np.abs(x)) > 0.05, name
        info = analyze(x.astype(np.float64), spec.sample_rate)
        assert info["duration_ms"] > 20, name


def test_loudness_target_is_hit():
    spec = store.get_preset("explosion")
    x = render(spec)
    info = analyze(x.astype(np.float64), spec.sample_rate)
    # peak ceiling can pull it below target; it must never be above
    assert info["lufs"] <= spec.master.target_lufs + 1.0
    assert info["active_ms"] > 500
    assert info["peak_dbfs"] <= -0.9


def test_variations_differ_but_keep_length_roughly():
    spec = store.get_preset("coin")
    vs = render_variations(spec, 3)
    assert len(vs) == 3
    pitches = {round(s.layers[0].pitch.start_hz, 3) for s, _ in vs}
    assert len(pitches) == 3
    base = len(render(spec))
    for _, x in vs:
        assert abs(len(x) - base) < 0.2 * base


def test_merge_patch_replaces_lists_and_nests():
    base = {"a": {"b": 1, "c": 2}, "l": [1, 2]}
    out = store.merge_patch(base, {"a": {"b": 9}, "l": [3]})
    assert out == {"a": {"b": 9, "c": 2}, "l": [3]}


def test_render_to_file_roundtrip(tmp_path):
    spec = store.get_preset("blip")
    res = store.render_to_file(spec, tmp_path)
    assert (tmp_path / f"{res['id']}.wav").exists()
    loaded = store.load_spec(res["id"], tmp_path)
    assert loaded == spec
    info = store.analyze_file(res["id"], tmp_path)
    assert info["sample_rate"] == 44100
    assert "features" in res and "warnings" in res


def test_sfxr_source_renders_and_matches_declared_length():
    from sfx.spec.models import SfxrSource

    src = SfxrSource(wave="square", p_env_sustain=0.1, p_env_decay=0.4, p_base_freq=0.5, p_arp_mod=0.4, p_arp_speed=0.6)
    layer = Layer(id="s", source=src)
    spec = SoundSpec(name="sfxr", layers=[layer], master={"target_lufs": None})
    x = render(spec)
    assert abs(len(x) - round(layer.duration_ms() * SR / 1000)) <= 2
    assert np.max(np.abs(x)) > 0.05
    # the same params at 48 kHz give the same duration in seconds
    spec48 = SoundSpec(name="sfxr48", sample_rate=48000, layers=[layer], master={"target_lufs": None})
    assert abs(len(render(spec48)) / 48000 - len(x) / SR) < 0.002


def test_sfxr_freq_limit_stops_early():
    from sfx.engine.sfxr import render_sfxr
    from sfx.spec.models import SfxrSource

    laser = SfxrSource(wave="saw", p_env_sustain=0.2, p_env_decay=0.25, p_base_freq=0.6, p_freq_limit=0.2, p_freq_ramp=-0.3)
    full = SfxrSource(wave="saw", p_env_sustain=0.2, p_env_decay=0.25, p_base_freq=0.6, p_freq_ramp=-0.3)
    rng = np.random.default_rng(0)
    assert len(render_sfxr(laser, rng)) < len(render_sfxr(full, rng))


def test_pulse_wave_has_no_dc():
    from sfx.engine.sources import oscillator
    from sfx.spec.models import OscSource

    sig = oscillator(OscSource(wave="square", duty=0.15), np.full(SR, 200.0), SR)
    assert abs(sig.mean()) < 0.01
    assert np.max(np.abs(sig)) <= 1.0


def test_analyze_pitch_and_attack():
    spec = SoundSpec(
        name="p",
        layers=[Layer(pitch=Pitch(start_hz=1600, end_hz=300, curve="exp"), amp=Amp(attack_ms=1, decay_ms=200))],
    )
    info = analyze(render(spec).astype(np.float64), SR)
    assert info["pitch_hz_start"] is not None and 1300 < info["pitch_hz_start"] < 1900
    assert info["pitch_hz_end"] is not None and info["pitch_hz_end"] < 0.7 * info["pitch_hz_start"]
    assert info["attack_ms"] < 10
    assert info["active_ms"] < 220


def test_analyze_onsets_for_two_notes():
    from sfx.spec.models import FMSource

    note = dict(source=FMSource(mod_ratio=3, index=2.5, index_end=0.3), amp=Amp(attack_ms=1, decay_ms=60))
    spec = SoundSpec(
        name="confirm",
        layers=[Layer(id="a", pitch=Pitch(start_hz=880), **note), Layer(id="b", pitch=Pitch(start_hz=1320), start_ms=85, **note)],
    )
    info = analyze(render(spec).astype(np.float64), SR)
    assert len(info["onsets_ms"]) == 2
    assert 70 < info["onsets_ms"][1] < 100
