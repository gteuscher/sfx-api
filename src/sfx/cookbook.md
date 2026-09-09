# sfx-api cookbook

How to turn a description into a SoundSpec. Read the schema resource for exact field names and
ranges. Start from the closest preset, then adjust. Render, play it for the user, ask what to
change, patch, repeat. Keep sounds short: most game one-shots are 80 to 600 ms.

## Workflow

1. Pick a category below and copy its recipe or call `sfx_render_preset`.
2. Render with `sfx_render`, then `sfx_play` so the user hears it. Read the returned features:
   `duration_ms`, `attack_ms`, `decay_to_minus40db_ms`, `spectral_centroid_hz`, `lufs`.
3. Translate feedback into parameter moves using the vocabulary table, then `sfx_tweak` by id.
4. When the user is happy, `sfx_variations` for engine random containers and `sfx_save_preset`.

## Vocabulary: what the user says, what you change

| User says | Move |
|---|---|
| punchier, more impact | raise `amp.punch` (0.3 to 0.7), shorten `attack_ms` to 0 or 1, add a `distortion` or `compressor` on master, add a noise transient layer |
| softer, gentler | raise `attack_ms` (10 to 40), use sine or triangle, lower `filter.cutoff_hz`, lower `distortion.drive_db` |
| brighter | raise `filter.cutoff_hz`, use saw or square with low duty, raise FM `index`, add a higher-pitched layer |
| darker, duller, muffled | lower `filter.cutoff_hz` (800 to 2500), use sine or triangle, add `end_cutoff_hz` sweeping down |
| longer, more tail | raise `decay_ms` or `release_ms`, add `reverb` with `master.tail_ms` 100 to 400 |
| shorter, tighter, snappier | lower `decay_ms` and `release_ms`, remove reverb, set `tail_ms` 0 |
| more retro, more 8-bit | square or bit noise, `bitcrush` bits 4 to 8 with `rate_hz` 8000 to 16000, `curve` step or arpeggio |
| less harsh, less fizzy | lower `bitcrush` drive (raise bits), lower `q`, add `lowpass` at 4000 to 8000 |
| bigger, heavier | add a sub layer (sine 40 to 90 Hz, punch 0.5), raise `distortion`, lower pitch overall |
| smaller, cuter | raise pitch by an octave, shorten everything, use square duty 0.25, add a rising pitch |
| more movement, more alive | `vibrato_cents` 20 to 80, `arpeggio_semitones`, `chorus`, `end_hz` slides |
| lower / higher | scale `start_hz` and `end_hz` together by 2^(semitones/12) |
| louder / quieter | change `master.target_lufs` (-14 loud, -18 normal, -22 background); do not touch layer gains |
| more layered, richer | add a second layer with a different source, offset by `start_ms` 10 to 40 |

## Recipes by category

Values are starting points. One layer is often enough. Two or three is rich.

**Laser, shoot, zap.** Saw or square, pitch falling fast: `start_hz` 800 to 2000 down to 150 to
400 over 100 to 250 ms with `curve` exp. Lowpass sweeping down (`cutoff_hz` 7000 to
`end_cutoff_hz` 1000, `q` 1 to 2) makes it feel like it moves away. `bitcrush` 8 bits for retro.
Chunkier: add `distortion` 8 to 12 dB and `punch` 0.4. Thinner: square with `duty` 0.15.

**Jump.** Square, pitch rising: 300 to 700 Hz over 120 to 200 ms, exp. Short hold, decay 150 ms.
Bigger jump: wider range, longer slide. Double jump: second layer starting 60 ms later, a fifth
higher.

**Coin, pickup, collect.** Square, two notes with `curve` step: B5 988 Hz to E6 1319 Hz at
`step_at_ms` 70 to 90, decay 250 ms. Bright add: a sine layer at the octave, gain -14, `start_ms`
equal to the step time. Rarer pickup: more steps via `arpeggio_semitones` [0, 4, 7, 12] at 20 Hz.

**Hit, punch, impact.** Two layers. Transient: white noise, attack 0, decay 50 to 90 ms, lowpass
sweeping from 5000 to 500. Body: sine 150 to 200 Hz falling to 50 to 60 Hz over 100 ms, punch 0.5
to 0.7, distortion 8 to 12 dB. Master compressor threshold -12, ratio 4. Metallic hit: FM body
with `mod_ratio` 3.5 to 7 and high `index`. Wooden: bandpass 400 to 900 Hz on the noise.

**Explosion.** Three layers. Sub: sine 90 down to 30 Hz, decay 600 ms, punch 0.5. Blast: brown
noise, decay 800 to 1200 ms, lowpass sweeping 3500 down to 150, distortion 12 to 16 dB. Crackle:
bit noise with `bit_rate_hz` 6000 sweeping to 500, highpass 800, gain -10. Master reverb room 0.5
wet 0.2 with `tail_ms` 300. Target -14 LUFS.

**UI click, tick, confirm.** FM: `mod_ratio` 3 to 5, `index` 3 decaying to 0, pitch 1200 to 2400
Hz, attack 0.5 ms, decay 30 to 60 ms. Highpass 400 Hz. Confirm: two of these with `curve` step
up a fourth. Cancel or error: same but step down, or square with `duty` 0.25 falling from 400 to
200 Hz.

**Menu move, blip.** Square `duty` 0.25, fixed pitch 700 to 1200 Hz, hold 20 to 40 ms, decay 40
ms. Highpass 300. Quiet: `target_lufs` -20.

**Powerup, level up.** Square `duty` 0.3, pitch rising 300 to 1300 Hz over 400 to 600 ms with
`retrigger_hz` 12 to 16 so it stutters upward. Sustain 0.85 for most of the length. Light reverb.
Grander: add an FM bell layer with `arpeggio_semitones` [0, 4, 7, 12] and a longer release.

**Hurt, damage, lose.** Square `duty` 0.25 falling 500 to 140 Hz over 150 ms, `bitcrush` 6 bits
at 11025 Hz for crunch, plus a short bandpassed white-noise grit layer at -10 dB. Death: longer
(400 to 700 ms), add `vibrato_cents` 60 at 10 Hz and a slower fall.

**Magic, sparkle, spell.** FM bells (`mod_ratio` 1.41 or 2.76 for inharmonic shimmer, `index` 4
to 0.5) with `arpeggio_semitones` [0, 7, 12, 19, 24] at 20 to 30 Hz, chorus, and a triangle
shimmer layer with vibrato. Master reverb room 0.6, wet 0.3, `tail_ms` 400. Dark magic: lower
everything two octaves, saw instead of FM, lowpass 1500, add brown noise bed.

**Footstep.** Noise burst: white or pink, attack 0, decay 40 to 80 ms, bandpass 200 to 900 Hz
(`q` 1 to 2) tuned per surface: stone 700, wood 400, grass 250 with pink noise, metal FM with
`mod_ratio` 5. Always render 4 to 8 variations with `pitch_cents` 150 and `gain_db` 2.

**Whoosh, swipe.** Pink noise, attack 40 to 80 ms, decay 120 to 200 ms, bandpass sweeping
`cutoff_hz` 400 up to 3000 (or down for a swing back), `q` 1.5 to 3.

**Alarm, siren.** Square with `vibrato_cents` 700 at 2 to 6 Hz, or two layers alternating via
`retrigger_hz`. Sustain 1.0 for 500 to 1500 ms.

**Engine, motor loop.** Saw at 40 to 120 Hz with `retrigger_hz` equal to the pitch divided by 4
for a chug, lowpass 800, distortion 6 dB. Ambience and loops are not seamless yet; keep them short
or crossfade in the engine.

## sfxr compatibility

If you already know sfxr or jsfxr, use `{"type": "sfxr", ...}` as a layer source with the original
`p_*` field names and 0 to 1 ranges (signed fields are -1 to 1). The layer's own `pitch` and `amp`
are ignored because sfxr brings its own; `filter`, `fx`, `gain_db`, and `start_ms` still apply, so
you can stack an sfxr voice with native layers. Quick reference: `p_base_freq` 0.3 is about 440 Hz,
`p_freq_ramp` negative falls, `p_arp_mod` positive with `p_arp_speed` 0.5 to 0.7 gives the coin
jump, `p_repeat_speed` 0.4 to 0.7 stutters, `p_lpf_freq` 1.0 bypasses the filter. Classic sfxr
starting points: pickup = square, sustain 0.1, decay 0.4, base 0.5, arp_mod 0.4, arp_speed 0.6;
laser = saw, base 0.6, freq_limit 0.2, freq_ramp -0.3; explosion = noise, base 0.15, freq_ramp
-0.1, decay 0.5, punch 0.3; jump = square, base 0.35, freq_ramp 0.25, sustain 0.15.

## Mixing rules of thumb

- Layer gains are relative. Let the master `target_lufs` set overall loudness.
- One-shots played often (footsteps, UI) want -18 to -22 LUFS. Big events want -14 to -16.
- Sounds under 100 ms read as quieter than the meter says. Raise `target_lufs` by 2 for them.
- `true_peak_dbtp` -1 is safe for all engines. Unreal converts to 16-bit internally, so keep it.
- Use `seed` to make noise layers reproducible. Variations pick their own seeds.
