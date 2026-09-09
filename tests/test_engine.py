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
    assert len(x) == round(0.251 * SR)
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
