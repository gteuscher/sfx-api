"""MCP server exposing the synthesis engine over stdio.

Run with `sfx-mcp` or `python -m sfx.server.mcp_server`.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from sfx import store
from sfx.spec.models import SoundSpec, spec_json_schema

INSTRUCTIONS = """\
sfx-api renders short video-game sound effects from a JSON SoundSpec using layered
parametric synthesis (oscillators, noise, FM, envelopes, pitch slides, filters, effects).

Workflow: read sfx://cookbook and sfx://schema once, pick the closest preset or write a spec,
call sfx_render, then sfx_play so the user hears it. Ask what to change, apply it with
sfx_tweak (a JSON merge patch by id), and repeat. Finish with sfx_variations and
sfx_save_preset. Audio is written as 16-bit mono WAV; tools return the file path and
audio features, never inline audio.
"""

mcp = MCPServer(name="sfx-api", instructions=INSTRUCTIONS, version="0.1.0")


def _out(out_dir: str | None) -> Path | None:
    return Path(out_dir) if out_dir else None


# --------------------------------------------------------------------------- resources


@mcp.resource("sfx://schema", mime_type="application/json", description="JSON schema for SoundSpec")
def schema_resource() -> str:
    return json.dumps(spec_json_schema(), indent=2)


@mcp.resource("sfx://cookbook", mime_type="text/markdown", description="Sound-design recipes and feedback vocabulary")
def cookbook_resource() -> str:
    return (resources.files("sfx") / "cookbook.md").read_text(encoding="utf-8")


@mcp.resource("sfx://presets", mime_type="application/json", description="All presets, built-in and user-saved")
def presets_resource() -> str:
    return json.dumps(store.all_presets(), indent=2)


# --------------------------------------------------------------------------- tools


@mcp.tool(description="Return the SoundSpec JSON schema and the cookbook. Call once before designing sounds.")
def sfx_docs() -> dict[str, Any]:
    return {"schema": spec_json_schema(), "cookbook": cookbook_resource()}


@mcp.tool(description="List available presets with a one-line summary of each.")
def sfx_list_presets() -> dict[str, Any]:
    out = {}
    for name, raw in store.all_presets().items():
        spec = SoundSpec.model_validate(raw)
        out[name] = {
            "layers": [f"{l.id}:{l.source.type}" for l in spec.layers],
            "duration_ms": round(spec.duration_ms(), 1),
        }
    return {"presets": out}


@mcp.tool(
    description=(
        "Render a SoundSpec to a 16-bit mono WAV. Returns the file path, an id for later tweaks, "
        "and audio features (duration, peak, LUFS, attack, decay, spectral centroid)."
    )
)
def sfx_render(spec: dict[str, Any], out_dir: str | None = None) -> dict[str, Any]:
    model = SoundSpec.model_validate(spec)
    result = store.render_to_file(model, _out(out_dir))
    result["spec"] = model.model_dump(mode="json")
    return result


@mcp.tool(description="Render a named preset, optionally with a JSON merge patch of overrides applied first.")
def sfx_render_preset(
    name: str, overrides: dict[str, Any] | None = None, out_dir: str | None = None
) -> dict[str, Any]:
    base = store.get_preset(name).model_dump(mode="json")
    merged = store.merge_patch(base, overrides or {})
    model = SoundSpec.model_validate(merged)
    result = store.render_to_file(model, _out(out_dir))
    result["spec"] = model.model_dump(mode="json")
    return result


@mcp.tool(
    description=(
        "Apply a JSON merge patch to a previous render (by id or WAV path) and re-render. "
        "Example patch: {\"layers\": [...]} replaces all layers; {\"master\": {\"target_lufs\": -14}} "
        "changes one field. Lists are replaced wholesale, so send the full layers list when editing a layer."
    )
)
def sfx_tweak(sound_id: str, patch: dict[str, Any], out_dir: str | None = None) -> dict[str, Any]:
    base = store.load_spec(sound_id, _out(out_dir)).model_dump(mode="json")
    model = SoundSpec.model_validate(store.merge_patch(base, patch))
    result = store.render_to_file(model, _out(out_dir))
    result["spec"] = model.model_dump(mode="json")
    return result


@mcp.tool(
    description=(
        "Render N randomized siblings of a sound (by id, path, or inline spec) for engine random "
        "containers. Jitter amounts come from spec.variation: pitch_cents, timing_ms, gain_db."
    )
)
def sfx_variations(
    count: int = 4,
    sound_id: str | None = None,
    spec: dict[str, Any] | None = None,
    out_dir: str | None = None,
) -> dict[str, Any]:
    if spec is None and sound_id is None:
        raise ValueError("pass sound_id or spec")
    model = SoundSpec.model_validate(spec) if spec is not None else store.load_spec(sound_id, _out(out_dir))
    count = max(1, min(int(count), 32))
    return {"variations": store.render_variations_to_files(model, count, _out(out_dir))}


@mcp.tool(description="Play a WAV (by id or path) through the machine's default audio output so the user can hear it.")
def sfx_play(sound_id: str, out_dir: str | None = None) -> dict[str, Any]:
    return store.play(sound_id, _out(out_dir))


@mcp.tool(description="Measure a WAV: duration, peak, LUFS, attack, decay, spectral centroid, dominant pitch.")
def sfx_analyze(sound_id: str, out_dir: str | None = None) -> dict[str, Any]:
    return store.analyze_file(sound_id, _out(out_dir))


@mcp.tool(description="Save a spec (inline, or from a render id) to the user preset library under a name.")
def sfx_save_preset(
    name: str, spec: dict[str, Any] | None = None, sound_id: str | None = None, out_dir: str | None = None
) -> dict[str, Any]:
    if spec is None and sound_id is None:
        raise ValueError("pass spec or sound_id")
    model = SoundSpec.model_validate(spec) if spec is not None else store.load_spec(sound_id, _out(out_dir))
    model.name = store.safe_name(name)
    path = store.save_preset(name, model)
    return {"name": model.name, "path": str(path)}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
