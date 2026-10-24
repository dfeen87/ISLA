# Experiment 02 · Creator listening guide

**Creator listening is pending.** No audibility, preference, smoother connection,
piano-character preservation or successful research PASS is inferred from a
residual, a spectrogram, a state label or a numerical screen.

## Original-duration study

Use the randomized A/B WAV pairs linked in the generated trial index. Work in
short sessions at a comfortable playback level. Keep the same playback chain
and volume while comparing a pair; replay freely and record uncertainty.
Complete the response sheet before opening the separate blind key.

There are 40 trials across four stereo 48 kHz passages: the original six-second
piano diagnostic crop, a later crop from the same recording, deterministic
connected melody, and deterministic harmonic sustain. The later piano crop is
a separate passage from the same artist/instrument source, not independent
recording validation. Sources are described and hashed in SOURCE_MANIFEST.json.

Pairs compare each governed identity with dry Bypass, the input-dose-matched
fixed control, and the preserved Experiment 01 candidate. A/A duplicate trials
check reliability. The key identifies all controls after responses are saved.
The old failed .30 Melt remains in the comparison; it was not replaced after
seeing its failure. Each pair uses a scalar RMS match and one common headroom
gain, identical across channels. These gains are logged in the blind key.
RMS matching is an engineering level control, not certified perceptual equality.

A separate **post-freeze listening supplement** adds 12 direct cross-mode pairs:
Velvet/Legato, Velvet/Melt and Legato/Melt on each of the same four sources.
It uses only saved governed WAVs, with scalar RMS matching and common 4×
estimated-peak headroom. It does not tune DSP or alter the primary 40 trials.
Its separate key and blank sheet are `listening/MODE_DISTINCTNESS_KEY.json` and
`listening/MODE_DISTINCTNESS_RESPONSES.csv`. These comparisons support an
independent mode-distinctness question; their outcomes remain pending.

Raw original-duration WAVs retain actual processing levels under `raw/`. They
support file/metric inspection; the matched blind pairs are the preference
comparison. Browser playback does not replace saved-file QA.

## Eight separate responses

Record the following independently in `listening/RESPONSES.csv`; fields start
blank. An audible change need not be preferred, and a preferred result may still
lose attack or resonance detail. Use “unsure” whenever appropriate.

| Field | Prompt and suggested response |
| --- | --- |
| Discrimination | Can you hear a difference? Same / different / unsure. |
| Preference | Which would you choose? A / B / no preference / unsure. |
| Smoothness | Which has smoother perceived continuity? A / B / equal / unsure. |
| Piano character | Which better retains recognizable piano character? A / B / equal / not applicable / unsure. |
| Expressive attacks | Which better preserves articulation and expressive note beginnings? A / B / equal / unsure. |
| Resonance preservation | Which better retains meaningful beating, decay and resonance motion? A / B / equal / unsure. |
| Mode distinctness | Describe a distinct processing character, or write no clear distinction / unsure. Do not guess hidden mode names. |
| Artifacts | Any clicks, pumping, hollowing, smearing or unnatural modulation? None / A / B / both / unsure; describe in notes. |

After recording the blind session, consult `listening/BLIND_KEY.json` to inspect
candidate identities, pair gains and checksums. Do not convert repeated frames
or correlated trials into independent music samples for significance claims.
The response sheet contains no invented positive result and is never silently
overwritten when presentation figures are regenerated.

## What to inspect

Velvet tests within-note upper-spectrum texture; listen for retained beating and
partial detail as well as any softer impression. Legato tests bounded temporal
magnitude continuity; listen for incoming-note clarity and whether connection
actually improves. It does not extend absent notes. Melt tests bounded shared
phase correction on reliable sustained trajectories; listen for meaningful
resonance motion, new modulation, and whether any difference justifies complexity.

For attacks, distinguish a changed envelope-detector peak from displacement of
the waveform itself. Zero local waveform lag does not resolve competing peaks,
changed attack character or novelty-detector disagreement. The six historical
Experiment 01 recorded-piano failures remain documented. Do not erase a failed
finding because a second diagnostic gives a different answer.

State plots show an operational mixture of attack, bloom, sustain, decay,
overlap and silence evidence. These labels do not identify physical notes or
validate a universal model of musical expression. Phase consistency is a proxy;
stereo and waveform behavior are separately measured after reconstruction.

## Slowdown is a separate incomplete prototype

The 1.25× and 1.50× offline slowdown files explore a different factor. Original-
duration identity results remain primary. Compare unchanged stretch with stretch
followed by an identity only as a clearly labeled exploratory study; do not infer
improvement in the original-duration processor from a slowed passage alone.

**Known failure:** protected slowdown failed the frozen 10 ms repeated-impulse
timing screen at both ratios and showed substantial energy spread. The raw 1.50×
path also produced extra strong events. Accurate sustained pitch and stereo
construction do not clear this transient gate. Slowed audio is provided as an
incomplete research prototype, not a robust completed piano slowdown feature.

The raw slowed prototype WAVs retain their recorded file levels and separate
prototype metrics. A **post-freeze matched slowed-piano supplement** provides
12 blind pairs: two recorded crops × 1.25×/1.50× expansion × three identities,
comparing protected untreated stretch against protected stretch plus an identity.
Use the generated trial index and [separate blank response sheet](listening/SLOWDOWN_RESPONSES.csv);
its key is `listening/SLOWDOWN_KEY.json`. Each pair uses scalar RMS matching and
common 4× estimated-peak headroom, with gains and file hashes logged. No DSP is
retuned or rerendered for these pairs. The comparison isolates identity processing
after slowdown, while the underlying transient failures remain unresolved.
All creator outcomes remain pending; original-duration findings remain separate.
