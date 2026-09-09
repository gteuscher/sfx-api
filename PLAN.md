# sfx-api plan

Local text-to-game-SFX server. A coding agent (Claude Code or Codex) describes a sound, emits a
layered synthesis spec, and the server renders a WAV, normalizes it, and can play it on the
machine so the user can react.

Kickoff: 2026-09-09.

## Decisions from the interview

| Topic | Decision |
|---|---|
| Sound style | Retro/chiptune and stylized/cartoony. Not realistic. |
| Generator | Multi-voice parametric synthesis only. Neural text-to-audio descoped. |
| Consumers | MCP hosts: Claude Code and OpenAI Codex. Host-agnostic stdio server. |
| Sound-design brain | The host model. No local LLM in v1; keep the text-to-spec step pluggable. |
| Feedback loop | User listens and gives text feedback. Server exposes a play tool plus cheap audio features. |
| Output | 16-bit mono WAV at 44.1 kHz (48 kHz optional), loudness normalized, written to a folder. |
| Language | Python 3.13. |
| Hardware | Target machine is a separate PC with an RTX 2080. Everything in v1 runs on CPU; no GPU needed. |

## Research digest

- The "LLM emits sfxr-style JSON, engine renders WAV" pattern already exists as several small MCP
  wrappers (jsfxr-mcp-wrapper, bfxr-mcp, bfxr2-mcp, bfxr2-cli). None is a reference implementation;
  all are single-voice sfxr. They validate the idea and show the tool surface agents like.
- LLM2Fx (WASPAA 2025) showed general LLMs can zero-shot numeric audio parameters from text
  with good prompting. CTAG (ICML 2024) optimized a 78-param modular synth against CLAP; useful
  later if we ever want automatic scoring, not needed for v1.
- Synthesis engine choice: NumPy/SciPy + soundfile is license-clean, Windows-native, needs no
  audio device, and is fast enough for sub-second renders. Heavier engines (SuperCollider via
  Supriya, Faust via DawDreamer, pyo) are escape hatches, not the core.
- Effects: Spotify pedalboard 0.9.24 has Python 3.13 Windows wheels and covers reverb, distortion,
  compression, chorus, delay, bitcrush, pitch shift. It is GPLv3 via JUCE. Fine for a tool you run
  yourself; wrap it behind an interface so it can be swapped for NumPy effects if you ever
  distribute the server.
- MCP: spec 2026-07-28; Python SDK `mcp` 2.2.0; FastMCP 4.0.3 sits on top of it. Transports are
  stdio and Streamable HTTP. Tool results support an `audio` content block, but no host plays it
  and Claude Code cannot. Every production audio MCP server writes to disk and returns a path.
  So: return a path plus metadata, and add a server-side play tool.
- Game engine targets: Unity, Unreal, Godot all accept 16-bit PCM WAV at 44.1 kHz. Console SFX
  loudness convention is around -24 LUFS with -1 dBTP true peak; individual assets are often mixed
  hotter, so the target is a per-render parameter. Variations (pitch and timing jitter) map onto
  Unity AudioRandomContainer, Godot AudioStreamRandomizer, FMOD Multi Instrument.
- Neural models, for the record: Stable Audio Open 1.0 and Stable Audio 3 Small-SFX are the only
  commercially usable local options. Kept out of scope; the generator interface leaves room.

## Architecture

```
user: "a chunky retro laser with a short tail"
  -> host model (Claude Code / Codex) reads sfx://schema and sfx://cookbook
  -> emits a SoundSpec (JSON)
  -> MCP tool sfx_render(spec)
  -> engine: layers -> mix -> master fx -> loudness normalize -> WAV
  -> returns path, duration, peak, LUFS, spectral summary
  -> sfx_play(path) so the user hears it
  -> user: "punchier, shorter tail" -> host patches the spec -> sfx_render again
```

Three packages in one repo:

- `sfx.engine`: pure functions, NumPy in, NumPy out. Sources, envelopes, pitch curves, filters,
  effects, mixer, normalizer, WAV writer. No MCP or IO concerns beyond the writer.
- `sfx.spec`: Pydantic models for SoundSpec, presets, variations. The JSON schema exported from
  here is what agents read.
- `sfx.server`: MCP server (stdio) built on the official `mcp` SDK. Thin adapters over the engine.
  A CLI (`sfx render spec.json`) uses the same core.

## SoundSpec

One sound is a list of layers rendered in parallel, mixed, then mastered. Every layer has a source,
a pitch curve, an amplitude envelope, an optional filter, and an optional effect chain.

```json
{
  "name": "coin_pickup",
  "seed": 42,
  "sample_rate": 44100,
  "layers": [
    {
      "id": "body",
      "source": {"type": "osc", "wave": "square", "duty": 0.5},
      "pitch": {"start_hz": 988, "end_hz": 1319, "curve": "step", "step_at_ms": 80,
                "vibrato_cents": 0, "vibrato_hz": 0},
      "amp": {"attack_ms": 1, "hold_ms": 60, "decay_ms": 250, "sustain": 0.0,
              "release_ms": 40, "punch": 0.2},
      "filter": {"type": "lowpass", "cutoff_hz": 6000, "end_cutoff_hz": 2500, "q": 0.7},
      "fx": [{"type": "bitcrush", "bits": 8}],
      "gain_db": -3,
      "start_ms": 0
    }
  ],
  "master": {
    "fx": [{"type": "reverb", "room": 0.15, "wet": 0.1}],
    "target_lufs": -18,
    "true_peak_dbtp": -1,
    "tail_ms": 50
  },
  "variation": {"pitch_cents": 50, "timing_ms": 10, "gain_db": 1}
}
```

Sources in v1:

- `osc`: sine, triangle, saw, square/pulse with duty and duty sweep.
- `noise`: white, pink, brown, and bit-noise (LFSR style) for chiptune.
- `fm`: 2-operator FM with carrier ratio, modulator ratio, and an index envelope. Covers bells,
  UI blips, metallic hits.
- `sfxr`: a faithful port of the sfxr parameter model as a single source, so the thousands of
  existing sfxr presets and the agent's prior knowledge of sfxr fields carry over.

Pitch curves: linear, exponential, step (arpeggio), slide with delta-slide (sfxr style), vibrato.
Amplitude: attack, hold, decay, sustain, release, plus sfxr "punch".
Filters: lowpass, highpass, bandpass with cutoff sweep and resonance (biquad, scipy sosfilt).
Layer and master effects: bitcrush, distortion/clip, compressor, delay, reverb, chorus, retrigger
(sfxr repeat), gain, pitch shift.

## MCP tools and resources

Resources:

- `sfx://schema` - JSON schema for SoundSpec with descriptions and ranges on every field.
- `sfx://cookbook` - short recipes per category: laser, jump, coin, hit, explosion, UI, powerup,
  hurt, magic, footstep. What layers to use, typical values, how to adjust for "punchier",
  "brighter", "longer tail". This is where the sound-design knowledge lives for the host model.
- `sfx://presets` - the preset library as JSON.

Tools:

- `sfx_render(spec, out_dir?, name?)` - render one sound. Returns path, id, duration, peak,
  LUFS, spectral centroid, attack time, and the resolved spec (defaults filled in).
- `sfx_render_preset(name, overrides?)` - render a named preset with partial overrides.
- `sfx_variations(spec_or_id, count, variation?)` - render N siblings with pitch/timing/gain
  jitter for engine random containers.
- `sfx_tweak(id, patch)` - apply a JSON merge patch to a previous render and re-render.
- `sfx_play(path_or_id)` - play on the server machine. Windows first via winsound, cross-platform
  via sounddevice later.
- `sfx_analyze(path)` - features for any WAV, including ones the user supplies as references.
- `sfx_save_preset(name, spec)` / `sfx_list_presets()`.

Every render stores the spec next to the WAV as a sidecar JSON, so sounds are reproducible and
"like the laser from before but lower" works by id.

## Milestones

Status 2026-09-09: M1 and M2 done, M3 done except the sfxr source port. M4 not started.

1. Engine and CLI. Sources, envelopes, pitch curves, filters, mixer, loudness normalize, WAV
   writer. `sfx render spec.json` works. Tests with numeric assertions on envelopes and pitch.
   Ten hand-tuned presets that sound right.
2. MCP server. stdio server exposing render, render_preset, play, schema, presets. Configured
   in Claude Code and Codex. First end-to-end session: describe, render, listen, adjust.
3. Depth. FM and sfxr sources, layer and master effect chains via pedalboard, variations, tweak,
   analyze, preset save. Cookbook resource written and tested by asking both hosts to design
   sounds cold.
4. Polish. Evaluation session against a list of 20 target sounds, tune cookbook from what the
   agents got wrong, optional REST endpoint (FastAPI mount) and an HTML preview page listing
   renders with play buttons.

## Repo layout

```
sfx-api/
  pyproject.toml
  src/sfx/
    engine/   sources.py envelopes.py pitch.py filters.py fx.py mix.py normalize.py wav.py
    spec/     models.py presets/*.json cookbook.md
    server/   mcp_server.py cli.py
  tests/
  out/        default render folder, gitignored
  PLAN.md
```

Dependencies: numpy, scipy, soundfile, pyloudnorm, pydantic, mcp, pedalboard (optional extra).
All have Python 3.13 Windows wheels, verified 2026-09-09.

## Open questions

- Pedalboard is GPLv3. Acceptable for a self-run tool? Default plan says yes, wrapped behind an
  interface.
- Playback tool plays through the machine's default output device. Acceptable?
- Default output folder: `./out` under the host project's working directory, overridable per call.
- Package manager: `uv` is not installed. Recommend installing it; pip and venv work too.
