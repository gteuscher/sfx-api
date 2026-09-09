# sfx-api

Parametric video-game sound-effect synthesis for coding agents. You describe a sound to
Claude Code or Codex, the agent writes a layered synthesis spec, and this server renders a
normalized 16-bit WAV and plays it so you can react in words.

Runs on CPU, no GPU or model downloads. Python 3.11+, Windows first.

## Install

```powershell
cd C:\dev\sfx-api
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,fx]"
.venv\Scripts\sfx demo --play     # renders every preset into .\out and plays them
```

The `fx` extra installs Spotify pedalboard for better reverb, chorus, compressor, and pitch
shift. It is GPLv3. Without it, built-in NumPy effects are used.

## Hook into Claude Code

```powershell
claude mcp add sfx -- C:\dev\sfx-api\.venv\Scripts\sfx-mcp.exe
```

Or add to `.mcp.json` in a project:

```json
{
  "mcpServers": {
    "sfx": {
      "command": "C:\\dev\\sfx-api\\.venv\\Scripts\\sfx-mcp.exe",
      "env": { "SFX_OUT_DIR": "C:\\path\\to\\game\\Assets\\Audio\\Generated" }
    }
  }
}
```

## Hook into Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.sfx]
command = "C:\\dev\\sfx-api\\.venv\\Scripts\\sfx-mcp.exe"

[mcp_servers.sfx.env]
SFX_OUT_DIR = "C:\\path\\to\\game\\Assets\\Audio\\Generated"
```

Then in either host: "Read the sfx cookbook, then make me a chunky retro laser with a short
tail and play it."

## REST API and preview page

```powershell
.venv\Scripts\sfx serve-http --port 8765
```

Opens a preview page at http://127.0.0.1:8765/ that lists every render in the output folder
with play buttons, features, warnings, the spec, a merge-patch box to tweak and re-render, a
variations button, and A/B comparison. The REST API is documented at `/api/docs`: render a
spec, render or save presets, tweak by id, variations, analyze, play, and download WAVs. The
MCP server is also mounted at `/mcp` over Streamable HTTP for hosts that prefer it to stdio.

## Tools

| Tool | Purpose |
|---|---|
| `sfx_docs` | Compact schema, cookbook, and preset names; sections available. Agents call this once. |
| `sfx_list_presets` | Built-in and saved presets. |
| `sfx_render` | Render a SoundSpec. Returns path, id, features, normalization info, and warnings. |
| `sfx_render_preset` | Render a preset with optional overrides. |
| `sfx_tweak` | JSON merge patch on a previous render by id, re-render. |
| `sfx_variations` | N pitch, filter, timing, and gain jittered siblings for random containers. |
| `sfx_play` | Play through the default output device. |
| `sfx_analyze` | Features for any WAV, including reference sounds. |
| `sfx_save_preset` | Save a spec to the user preset library. |

Resources: `sfx://schema`, `sfx://cookbook`, `sfx://presets`.

## Environment

| Variable | Effect |
|---|---|
| `SFX_OUT_DIR` | Where renders and sidecar specs go. Default `./out`. |
| `SFX_PRESETS_DIR` | User preset folder. Default `%APPDATA%\sfx-api\presets`. |
| `SFX_NO_PLAYBACK=1` | Make `sfx_play` a no-op. |
| `SFX_NO_PEDALBOARD=1` | Force NumPy effects even if pedalboard is installed. |

## CLI

```
sfx render spec.json --play
sfx preset laser --set '{"layers":[...]}' --play
sfx variations coin -n 6
sfx tweak is MCP-only; use render with an edited sidecar JSON from ./out
sfx analyze out\coin-ab12cd.wav
sfx list | sfx schema | sfx cookbook | sfx demo | sfx serve
```

## Spec at a glance

```json
{
  "name": "coin",
  "layers": [
    {
      "id": "body",
      "source": {"type": "osc", "wave": "square", "duty": 0.5},
      "pitch": {"start_hz": 988, "end_hz": 1319, "curve": "step", "step_at_ms": 80},
      "amp": {"attack_ms": 1, "hold_ms": 70, "decay_ms": 260, "release_ms": 40, "punch": 0.15},
      "filter": {"type": "lowpass", "cutoff_hz": 6000, "end_cutoff_hz": 2500, "q": 0.7},
      "fx": [{"type": "bitcrush", "bits": 8}]
    }
  ],
  "master": {"target_lufs": -16, "true_peak_dbtp": -1}
}
```

Sources: `osc` (sine, triangle, saw, square with duty), `noise` (white, pink, brown, bit), `fm`
(two operators), `sfxr` (a jsfxr-compatible voice with the original `p_*` fields). Effects: bitcrush, distortion, clip, compressor, delay, reverb, chorus, gain,
pitch_shift. See `PLAN.md` for the design and roadmap.

## Evaluating the docs with real agents

`eval/run_group.sh <claude|codex> <A|B|C|D>` runs a non-interactive host session that reads the
docs, designs five target sounds from `eval/targets.json`, and reports what was unclear. Codex
needs `--dangerously-bypass-approvals-and-sandbox` (already in the script) to call MCP tools
without a human approving each one; interactive Codex sessions prompt instead. Results land in
`eval/results/` and renders in `out/eval/`. The cookbook's feature definitions, loudness notes,
and several recipes came out of the first round.

## Tests

```powershell
.venv\Scripts\python -m pytest
```
