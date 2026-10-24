# Listening comparison guide

These files were rendered through the unchanged LIVE `StreamingDSP` path. All files in a row use the same passage, fixed 1536-frame delay removal and shared integrated loudness target. **There is no new owner listening verdict, improved candidate, or ABX result.**

Use the loudness-matched files below for comparison. They are 48 kHz stereo FLOAT WAVs, include the same silence guards, and use only a constant stereo-linked gain. Targets are at or below Bypass minus 3 LU and −23 LUFS; no limiter, dynamic normalization, device route or volume change is involved. Keep the playback level fixed while switching within a row. Compare attack, sustain/decay, tonal texture and stereo image separately. A measurable difference does not imply a preferred result.

## Verified CC0 recordings

The original bytes, published licensing statements, authorship and hashes are in [source provenance](study/recordings/RECORDING_PROVENANCE.md). Descriptions do not establish whether the instruments were physical, sampled or synthesized. Each measured excerpt is 12 s plus 0.125 s guards at each end.

| Passage | Target LUFS | Bypass | Velvet | Legato | Melt |
|---|---:|---|---|---|---|
| emotional_piano_00s | -23.00 | [Bypass](study/music/audio/loudness_matched/emotional_piano_00s_bypass.wav) | [Velvet](study/music/audio/loudness_matched/emotional_piano_00s_velvet.wav) | [Legato](study/music/audio/loudness_matched/emotional_piano_00s_legato.wav) | [Melt](study/music/audio/loudness_matched/emotional_piano_00s_melt.wav) |
| katanga_00s | -23.00 | [Bypass](study/music/audio/loudness_matched/katanga_00s_bypass.wav) | [Velvet](study/music/audio/loudness_matched/katanga_00s_velvet.wav) | [Legato](study/music/audio/loudness_matched/katanga_00s_legato.wav) | [Melt](study/music/audio/loudness_matched/katanga_00s_melt.wav) |
| katanga_24s | -23.00 | [Bypass](study/music/audio/loudness_matched/katanga_24s_bypass.wav) | [Velvet](study/music/audio/loudness_matched/katanga_24s_velvet.wav) | [Legato](study/music/audio/loudness_matched/katanga_24s_legato.wav) | [Melt](study/music/audio/loudness_matched/katanga_24s_melt.wav) |

## Original synthetic controls

Six seconds each. Piano is explicitly a piano-like additive model, not an acoustic recording. Melody, percussion, mixture, oscillator/noise sources and event metadata are original deterministic fixtures.

| Passage | Target LUFS | Bypass | Velvet | Legato | Melt |
|---|---:|---|---|---|---|
| solo_piano | -26.14 | [Bypass](study/audio/loudness_matched/solo_piano_bypass.wav) | [Velvet](study/audio/loudness_matched/solo_piano_velvet.wav) | [Legato](study/audio/loudness_matched/solo_piano_legato.wav) | [Melt](study/audio/loudness_matched/solo_piano_melt.wav) |
| connected_melody | -24.20 | [Bypass](study/audio/loudness_matched/connected_melody_bypass.wav) | [Velvet](study/audio/loudness_matched/connected_melody_velvet.wav) | [Legato](study/audio/loudness_matched/connected_melody_legato.wav) | [Melt](study/audio/loudness_matched/connected_melody_melt.wav) |
| percussion | -26.97 | [Bypass](study/audio/loudness_matched/percussion_bypass.wav) | [Velvet](study/audio/loudness_matched/percussion_velvet.wav) | [Legato](study/audio/loudness_matched/percussion_legato.wav) | [Melt](study/audio/loudness_matched/percussion_melt.wav) |
| dense_mix | -26.77 | [Bypass](study/audio/loudness_matched/dense_mix_bypass.wav) | [Velvet](study/audio/loudness_matched/dense_mix_velvet.wav) | [Legato](study/audio/loudness_matched/dense_mix_legato.wav) | [Melt](study/audio/loudness_matched/dense_mix_melt.wav) |

## Other files and interpretation

Each corpus has `audio/raw/`, `audio/rms_matched/` and `audio/loudness_matched/`. Raw FLOAT files preserve the measured DSP output, including source-conversion overshoot; RMS copies are analytical controls and do not claim LUFS equivalence. Use the loudness-matched directory for the comparisons above. Raw copies are not dynamically protected playback masters.

The [synthetic loudness manifest](study/listening_loudness.json) and [recording loudness manifest](study/music/listening_loudness.json) record measured raw/target/saved LUFS, constant gains, peaks and output SHA-256. Remeasured targets differ by less than 0.01 LU (observed less than 1e-8 LU). A 4× oversampled peak probe is supplied, not a certified true-peak measurement. Equal integrated LUFS does not ensure identical momentary or human-perceived loudness.

For optional blind work, have a separate person randomize file labels while keeping levels/time ranges fixed, and collect discrimination, preference and descriptions separately. No blind trial has been conducted. The historical owner preference for Melt does not supply answers for these samples.

No native macOS monitoring, live system capture, acoustic output or physical latency was measured during this study. Playing these files later would be a separate listening event. [Results](MODE_DIFFERENTIATION_RESULTS.md) · [Recommendation](DSP_EXPERIMENT_REPORT.md) · [Executed/pending tests](TEST_AND_REGRESSION_SUMMARY.md).
