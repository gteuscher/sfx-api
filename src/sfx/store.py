"""Render output folder, sidecar specs, preset library, and playback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from importlib import resources
from pathlib import Path

import numpy as np

from sfx.engine.analyze import analyze
from sfx.engine.render import render, render_variations
from sfx.engine.wav import read_wav, write_wav
from sfx.spec.models import SoundSpec

_SAFE = re.compile(r"[^A-Za-z0-9_\-]+")


def default_out_dir() -> Path:
    return Path(os.environ.get("SFX_OUT_DIR", Path.cwd() / "out")).resolve()


def user_presets_dir() -> Path:
    base = os.environ.get("SFX_PRESETS_DIR")
    if base:
        return Path(base)
    home = Path(os.environ.get("APPDATA", Path.home())) if sys.platform == "win32" else Path.home() / ".config"
    return home / "sfx-api" / "presets"


def safe_name(name: str) -> str:
    return _SAFE.sub("_", name).strip("_") or "sound"


# --------------------------------------------------------------------------- presets


def builtin_presets() -> dict[str, dict]:
    out: dict[str, dict] = {}
    root = resources.files("sfx") / "presets"
    for entry in sorted(root.iterdir()):
        if entry.name.endswith(".json"):
            out[entry.name[:-5]] = json.loads(entry.read_text(encoding="utf-8"))
    return out


def user_presets() -> dict[str, dict]:
    d = user_presets_dir()
    if not d.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))}


def all_presets() -> dict[str, dict]:
    merged = builtin_presets()
    merged.update(user_presets())
    return merged


def get_preset(name: str) -> SoundSpec:
    presets = all_presets()
    if name not in presets:
        raise KeyError(f"unknown preset {name!r}; available: {', '.join(sorted(presets))}")
    return SoundSpec.model_validate(presets[name])


def save_preset(name: str, spec: SoundSpec) -> Path:
    d = user_presets_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{safe_name(name)}.json"
    path.write_text(json.dumps(spec.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- merge patch


def merge_patch(target: dict, patch: dict) -> dict:
    """RFC 7396 style merge. Lists are replaced wholesale."""
    out = dict(target)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_patch(out[k], v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- renders


def _make_id(spec: SoundSpec) -> str:
    digest = hashlib.sha1(spec.model_dump_json().encode() + str(time.time_ns()).encode()).hexdigest()[:6]
    return f"{safe_name(spec.name)}-{digest}"


def write_render(spec: SoundSpec, audio: np.ndarray, out_dir: Path | None = None, sound_id: str | None = None) -> dict:
    out_dir = Path(out_dir) if out_dir else default_out_dir()
    sound_id = sound_id or _make_id(spec)
    wav_path = write_wav(out_dir / f"{sound_id}.wav", audio, spec.sample_rate)
    json_path = out_dir / f"{sound_id}.json"
    json_path.write_text(json.dumps(spec.model_dump(mode="json"), indent=2), encoding="utf-8")
    info = analyze(np.asarray(audio, dtype=np.float64), spec.sample_rate)
    return {"id": sound_id, "path": str(wav_path), "spec_path": str(json_path), **info}


def render_to_file(spec: SoundSpec, out_dir: Path | None = None) -> dict:
    return write_render(spec, render(spec), out_dir)


def render_variations_to_files(spec: SoundSpec, count: int, out_dir: Path | None = None) -> list[dict]:
    base = _make_id(spec)
    results = []
    for i, (s, audio) in enumerate(render_variations(spec, count)):
        results.append(write_render(s, audio, out_dir, sound_id=f"{base}-v{i + 1}"))
    return results


def resolve_path(path_or_id: str, out_dir: Path | None = None) -> Path:
    p = Path(path_or_id)
    if p.suffix.lower() == ".wav" and p.exists():
        return p.resolve()
    out_dir = Path(out_dir) if out_dir else default_out_dir()
    cand = out_dir / f"{path_or_id}.wav"
    if cand.exists():
        return cand.resolve()
    raise FileNotFoundError(f"no WAV at {path_or_id!r} or {cand}")


def load_spec(path_or_id: str, out_dir: Path | None = None) -> SoundSpec:
    wav = resolve_path(path_or_id, out_dir)
    sidecar = wav.with_suffix(".json")
    if not sidecar.exists():
        raise FileNotFoundError(f"no sidecar spec for {wav}; only sfx-api renders can be tweaked")
    return SoundSpec.model_validate(json.loads(sidecar.read_text(encoding="utf-8")))


def analyze_file(path_or_id: str, out_dir: Path | None = None) -> dict:
    wav = resolve_path(path_or_id, out_dir)
    x, sr = read_wav(wav)
    return {"path": str(wav), "sample_rate": sr, **analyze(x, sr)}


# --------------------------------------------------------------------------- playback


def play(path_or_id: str, out_dir: Path | None = None, block: bool = True) -> dict:
    wav = resolve_path(path_or_id, out_dir)
    if os.environ.get("SFX_NO_PLAYBACK") == "1":
        return {"path": str(wav), "played": False, "reason": "SFX_NO_PLAYBACK=1"}
    if sys.platform == "win32":
        import winsound

        flags = winsound.SND_FILENAME | (0 if block else winsound.SND_ASYNC)
        winsound.PlaySound(str(wav), flags)
        return {"path": str(wav), "played": True, "backend": "winsound"}
    try:
        import sounddevice as sd  # type: ignore

        x, sr = read_wav(wav)
        sd.play(x, sr)
        if block:
            sd.wait()
        return {"path": str(wav), "played": True, "backend": "sounddevice"}
    except ImportError:
        return {"path": str(wav), "played": False, "reason": "install sounddevice for playback on this platform"}
