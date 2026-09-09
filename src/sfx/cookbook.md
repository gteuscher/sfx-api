# sfx-api cookbook

How to turn a description into a SoundSpec. The schema (from `sfx_docs` or `sfx://schema`) has
exact field names, ranges, and semantics in every docstring; read those too. Start from the
closest preset, then adjust. Render, play it for the user, ask what to change, patch, repeat.
Keep sounds short: most game one-shots are 80 to 600 ms. With the default exp curve a layer is audible for about two thirds of its decay_ms.

## Workflow

1. Pick a category below. Start from its preset with `sfx_render_preset` (preset names are
   listed with each recipe) or write a spec from the recipe.
2. Render with `sfx_render`, then `sfx_play` so the user hears it. Read `features` and
   `warnings` in the result (definitions at the end of this document).
3. Translate feedback into parameter moves using the vocabulary table, then `sfx_tweak` by id.
   The patch is a JSON merge: nested objects merge, lists such as `layers` are replaced whole.
4. When the user is happy, `sfx_variations` for engine random containers and `sfx_save_preset`.

Signal chain: per layer, source, pitch and amp envelope, filter, fx in order, gain_db, placed at
start_ms. Layers are summed, then master fx, then loudness normalization to target_lufs, then a
true-peak limiter at true_peak_dbtp. Layer-level reverb and delay are cut at the layer's end;
put them on master and set `tail_ms` for tails.

## Vocabulary: what the user says, what you change

| User says | Move |
|---|---|
| punchier, more impact | raise `amp.punch` (0.3 to 0.7), `attack_ms` 0 or 1, add a noise transient layer, add a master `compressor` (threshold -12, ratio 4) |
| softer, gentler | raise `attack_ms` (10 to 40), use sine or triangle, lower `filter.cutoff_hz`, lower `distortion.drive_db` |
| brighter | raise `filter.cutoff_hz`, use saw or square with low duty, raise FM `index`, add a higher-pitched layer |
| darker, duller, muffled | lower `filter.cutoff_hz` (800 to 2500), use sine or triangle, add `end_cutoff_hz` sweeping down |
| longer, more tail | raise `decay_ms`, or add master `reverb` with `tail_ms` about room x 800 |
| slow, long rumble | brown noise layer, `decay_ms` 800 to 1500 with `curve` linear, lowpass sweeping 2500 down to 120, sub sine 60 to 30 Hz |
| shorter, tighter, snappier | lower `decay_ms`, remove reverb, set `tail_ms` 0 |
| more retro, more 8-bit | square or bit noise, `bitcrush` bits 4 to 8 with `rate_hz` 8000 to 16000, `curve` step or arpeggio |
| less harsh, less fizzy | raise `bitcrush.bits`, lower `q`, add `lowpass` at 4000 to 8000, lower FM `index` |
| bigger, heavier | add a sub layer (sine 40 to 90 Hz, punch 0.5), raise `distortion`, lower pitch overall |
| smaller, cuter | raise pitch by an octave, shorten everything, use square duty 0.25, add a rising pitch |
| more movement, more alive | `vibrato_cents` 20 to 80, `arpeggio_semitones`, `chorus`, `end_hz` slides |
| flutter, trill, wobble | `vibrato_cents` 50 to 100 at `vibrato_hz` 15 to 30 for a smooth flutter; `retrigger_hz` 15 to 25 for a choppy one; both together read as buzz |
| lower / higher | scale `start_hz` and `end_hz` together by 2^(semitones/12) |
| louder / quieter (long sounds) | change `master.target_lufs` (-14 loud, -18 normal, -22 background) |
| quieter (short or UI sounds) | set `master.target_lufs` to null and use layer `gain_db` (-12 to -24), or lower `true_peak_dbtp` to -6 or -12 |
| more layered, richer | add a second layer with a different source, offset by `start_ms` 10 to 40 |

## Recipes by category

Values are starting points. One layer is often enough. Two or three is rich.

**Laser, shoot, zap.** Preset `laser`. Saw or square, pitch falling fast: `start_hz` 800 to 2000
down to 150 to 400 over 100 to 250 ms with `curve` exp. Lowpass sweeping down (`cutoff_hz` 7000
to `end_cutoff_hz` 1000, `q` 1 to 2) makes it feel like it moves away. `bitcrush` 8 bits for
retro. Chunkier: add `distortion` 8 to 12 dB and `punch` 0.4. Thinner: square with `duty` 0.15.

**Jump.** Preset `jump`. Square, pitch rising: 300 to 700 Hz over 120 to 200 ms, exp. Short
hold, decay 150 ms. Bigger jump: wider range, longer slide. Double jump: second layer with
`start_ms` 60 to 80, a fifth higher (multiply both Hz by 1.5); for a flutter on the second hop
add `vibrato_cents` 70 at `vibrato_hz` 20, not retrigger.

**Coin, pickup, collect.** Preset `coin`. Square, two notes with `curve` step: B5 988 Hz to E6
1319 Hz at `step_at_ms` 70 to 90, `hold_ms` 70 so the second note is still loud, decay 250 ms.
Bright add: a sine layer at 2637 Hz (octave of the second note), gain -14, `start_ms` 80.
Rarer pickup: FM bell layer with `arpeggio_semitones` [0, 4, 7, 12] at 20 Hz and a longer decay.

**Hit, punch, impact.** Preset `hit`. Two layers. Transient: white noise, attack 0, decay 50 to
90 ms, lowpass sweeping from 5000 to 500. Body: sine 150 to 200 Hz falling to 50 to 60 Hz over
100 ms, punch 0.5 to 0.7, distortion 8 to 12 dB. Master compressor threshold -12, ratio 4.
Metallic: FM body with `mod_ratio` 3.7 or 5.3 and `index` 8 to 14 with decay 400 to 700 ms for
ring; above index 15 it turns to noise. Wooden: bandpass 400 to 900 Hz on the noise. Flesh, wet,
gore: pink noise with bandpass sweeping 1400 down to 300 Hz, `q` 2, attack 8 ms, decay 90 ms,
plus a brown noise slap lowpassed at 600 Hz; keep the sine body, drop the distortion to 6 dB.

**Explosion.** Preset `explosion`. Three layers. Sub: sine 90 down to 30 Hz, decay 600 ms, punch
0.5. Blast: brown noise, decay 800 to 1200 ms with `curve` linear, lowpass sweeping 3500 down to
150, distortion 12 to 16 dB. Crackle: bit noise with `bit_rate_hz` 6000 sweeping to 500,
highpass 800, gain -10. Master reverb room 0.5 wet 0.2 with `tail_ms` 400. Target -14 LUFS.
Debris: one or two extra short layers starting 150 to 400 ms in, white noise bandpass 1500 to
3000 Hz, decay 40 ms, `retrigger_hz` 8 to 12 so they read as separate pebbles, gain -8.
Small grenade: halve every decay and drop the sub to 60 Hz.

**UI click, tick, confirm.** Preset `ui_click`. FM: `mod_ratio` 3 to 5, `index` 3 decaying to
0, pitch 1200 to 2400 Hz, attack 0.5 ms, decay 30 to 60 ms. Highpass 400 Hz. Confirm: two
layers, the second with `start_ms` 70 to 90 and pitch a fourth or fifth higher, for example 880
Hz then 1175 Hz (fourth) or 1320 Hz (fifth); a single layer with `curve` step only works if
`hold_ms` is at least as long as `step_at_ms`. Hover or very
quiet: `target_lufs` null, `gain_db` -18. Cancel or error: square with `duty` 0.25 falling from
400 to 200 Hz, or a `retrigger_hz` 40 square at 150 Hz with distortion 10 dB for a buzz.

**Menu move, blip.** Preset `blip`. Square `duty` 0.25, fixed pitch 700 to 1200 Hz, hold 20 to 40
ms, decay 40 ms. Highpass 300. Quiet: `target_lufs` -20.

**Powerup, level up.** Preset `powerup`. Square `duty` 0.3, pitch rising 300 to 1300 Hz over 400
to 600 ms with `retrigger_hz` 12 to 16 so it stutters upward. `sustain` 0.85 with `sustain_ms`
380 so the rise has a body (sustain_ms defaults to 0). Light reverb. Grander: add an FM bell layer with `arpeggio_semitones` [0, 4, 7, 12] and
a longer release. Fanfare or short melody: one layer per note with `start_ms` offsets (notes of
120 to 200 ms each) is clearest; `curve` step gives two notes; `arpeggio_semitones` at 8 to 12 Hz
gives a fast run, at 20 Hz or more it reads as a chord-like buzz.

**Hurt, damage, lose.** Preset `hurt`. Square `duty` 0.25 falling 500 to 140 Hz over 150 ms,
`bitcrush` 6 bits at 11025 Hz for crunch, plus a short bandpassed white-noise grit layer at
-10 dB. Grunt-like: saw 280 to 110 Hz with `vibrato_cents` 60 at 12 Hz and a resonant lowpass
(`q` 4) sweeping 1200 down to 300. Death: longer (400 to 700 ms), slower fall, bit noise layer
with `bit_rate_hz` sweeping 9000 down to 600.

**Magic, sparkle, spell.** Preset `magic_sparkle`. FM bells (`mod_ratio` 1.41 or 2.76 for
inharmonic shimmer, `index` 4 to 0.5) with `arpeggio_semitones` [0, 7, 12, 19, 24] at 20 to 30
Hz, chorus, and a triangle shimmer layer with vibrato. Master reverb room 0.6, wet 0.3,
`tail_ms` 500. Ice or crystal: `mod_ratio` 2.76, highpass 1500 on the bells, a white-noise frost
layer bandpassed at 6000 with `q` 3 at -20 dB (keep it quiet, white noise dominates the centroid
fast). Dark magic: lower everything two octaves, saw instead of FM, lowpass 1500, brown noise bed.

**Footstep.** Noise burst: white or pink, attack 0, decay 40 to 80 ms, bandpass 200 to 900 Hz
(`q` 1 to 2) tuned per surface: stone 700, wood 400, grass 250 with pink noise, metal FM with
`mod_ratio` 5. Add a quiet sine thud at 90 Hz, decay 40 ms. Always render 4 to 8 variations with
`filter_cents` 200 and `gain_db` 2 (noise ignores `pitch_cents`).

**Whoosh, swipe.** Pink noise, attack 40 to 80 ms, decay 120 to 200 ms, bandpass sweeping
`cutoff_hz` 400 up to 3000 (or down for a swing back), `q` 1.5 to 3, `gain_db` +6 to make up for
the narrow band. Avoid adding a white-noise edge layer above -20 dB; it takes over.

**Alarm, siren, beep pattern.** Siren: square with `vibrato_cents` 700 at 2 to 6 Hz, sustain 1.0
for 500 to 1500 ms. Beep pattern: one square layer per beep (880 Hz, hold 100 to 130 ms, decay
20 ms) with `start_ms` spaced by the gap; a double beep is two layers at 0 and 170 ms. A
lowpass at 6000 softens the edges.

**Creak, scrape, friction (doors, chests, hinges).** Stick-slip approximation: saw at 160 to 260
Hz with `vibrato_cents` 90 at `vibrato_hz` 7, `retrigger_hz` 18 to 25 for grain, resonant
bandpass `q` 4 sweeping 650 up to 1100 Hz, 500 to 900 ms with `curve` linear. Add a brown noise
body lowpassed at 500 Hz at -6 dB and a small room reverb. The schema cannot jitter retrigger
timing, so it stays somewhat mechanical; layering two of these at slightly different
`retrigger_hz` (19 and 23) breaks the regularity.

**Engine, motor loop.** Saw at 40 to 120 Hz with `retrigger_hz` equal to the pitch divided by 4
for a chug, lowpass 800, distortion 6 dB. Ambience and loops are not seamless yet; keep them short
or crossfade in the engine.

## sfxr compatibility

If you already know sfxr or jsfxr, use `{"type": "sfxr", ...}` as a layer source with the original
`p_*` field names and 0 to 1 ranges (signed fields are -1 to 1). Preset `sfxr_pickup` shows it.
The layer's own `pitch` and `amp` are ignored because sfxr brings its own; `filter`, `fx`,
`gain_db`, and `start_ms` still apply, so you can stack an sfxr voice with native layers. Quick
reference: `p_base_freq` 0.3 is about 440 Hz, `p_freq_ramp` negative falls, `p_arp_mod` positive
with `p_arp_speed` 0.5 to 0.7 gives the coin jump, `p_repeat_speed` 0.4 to 0.7 stutters,
`p_lpf_freq` 1.0 bypasses the filter. Classic starting points: pickup = square, sustain 0.1,
decay 0.4, base 0.5, arp_mod 0.4, arp_speed 0.6; laser = saw, base 0.6, freq_limit 0.2,
freq_ramp -0.3; explosion = noise, base 0.15, freq_ramp -0.1, decay 0.5, punch 0.3; jump =
square, base 0.35, freq_ramp 0.25, sustain 0.15.

## Loudness

- Layer gains are relative. Let `master.target_lufs` set overall loudness for sounds longer than
  about 300 ms: -14 to -16 for big events, -18 normal, -20 to -22 for frequent sounds.
- Loudness is measured over at least 400 ms. Shorter sounds read quieter than they are, the
  true-peak ceiling then stops the gain early, and the result carries a warning with
  `normalization.target_miss_db`. That is expected for clicks, footsteps, and short hits; they
  are effectively peak-normalized to `true_peak_dbtp`. Do not chase the target by raising it.
  A master `compressor` or lower `punch` closes the gap when it matters.
- For deliberately quiet sounds (hover ticks, background blips) set `target_lufs` to null and use
  `gain_db` -12 to -24, or set `true_peak_dbtp` to -6 or -12.
- `true_peak_dbtp` -1 is safe for all engines. Unreal converts to 16-bit internally, so keep it.
- Use `seed` to make noise layers reproducible. Variations pick their own seeds.

## Reading the features

`features` in every render result:

- `duration_ms` is the file length; `active_ms` is onset to the last sample above -40 dB, the
  audible length. `tail_silence_ms` is what is left after that.
- `attack_ms` is onset to the first envelope maximum that reaches half the peak. For a
  two-note sound it describes the first note, not the loudest.
- `decay_ms` runs from that first maximum until the envelope stays below -40 dB for 20 ms. For
  retriggered or sustained sounds it runs to the end of activity, so read `active_ms` instead.
- `pitch_hz_start` and `pitch_hz_end` are autocorrelation estimates over the first and last 40
  ms of activity; use them to confirm slides. They are null for noise-dominated sounds, can fold
  an octave down, and are skewed by reverb tails and overlapping notes; trust the spec over the
  estimate when they disagree by exactly an octave.
- `onsets_ms` lists where the envelope rises past 30 percent of peak after a dip below 10
  percent. A two-note confirm shows two entries; a 14 Hz stutter shows one every 71 ms.
- `spectral_centroid_hz` is magnitude weighted; any white noise layer drags it up fast.
  `band_db` (energy share below 250 Hz, 250 to 2000, above 2000, in dB relative to total) is the
  better balance check: a meaty hit has `low` near 0 and `high` below -15.
- `lufs` and `peak_dbfs` are after normalization and limiting.
