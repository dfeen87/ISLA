# Audio Control Center hardening and release decision

Base: `a588ae28b9e1ce102a6d2cd9ab64d12870516aaf`, including merged PR #65.
PR #65 was inspected before implementation; its eligibility, indeterminate progress,
child priority reduction and consolidated Diagnostics were retained.

**v4.0.0 recommendation: HOLD.** The reproducible control/publication defects are
repaired. Physical MacBook Pro Speakers acceptance and the creator's reported
bubbling remain open. Research designation: **REVISE / INCONCLUSIVE**. This work
does not authorize merge, a release tag, publication or production promotion.

## Root-cause matrix

| Report | Reproduced cause / evidence | Implementation | Remaining acceptance |
| --- | --- | --- | --- |
| LIVE volume has no audible effect | Confirmed Qt draft-value race. Keyboard edit to 25%, focus moves to Apply, 180 ms held press: the old 100% snapshot replaces the edit before release. Existing post-DSP gain itself works. | Preserve uncommitted slider values across focus changes and polling; synchronize committed state after dispatch. Native Qt mouse events now reach ControlService, real LiveMonitor worker, output ring and callback PCM at 0/25/100%, plus Mute. Source samples and one-stream ownership stay intact. | Native MacBook Pro Speakers identity, audible attenuation and exclusion of a parallel listening path. Hosted PCM evidence does not establish acoustic output. |
| Bubbling in Velvet/Legato/Melt | Unchanged production preparation produces envelope variation and non-scalar waveform changes before any output stream exists. Sustained tone analysis selects 54 boundary candidates in 3 seconds; isolated smoother and harmonic stages both add residual. Complete manually pumped outgoing buffers and existing 5 ms mode transitions add zero sample error to the expected prepared-buffer signal at GUI gain 0.25. | Preserve DSP and baselines. Add retained ALIVE callback status/underflow and DAC-gap counters; move changing LIVE research counters into Diagnostics. Provide reproducible identical-passage comparisons and actual spawned-render/playback regression. | DSP contribution is supported, but its relationship to the creator's exact audible bubbling remains an inference. Native underruns, device configuration, M4A decode, SRC and CPU scheduling still need observation. No blanket quality-fix claim. |
| Prepare / Apply and Cancel appear unresponsive | PR #65 correctly rejects >30-second files and unsupported rates. Cancel is intentionally disabled without a pending job. Explanations were not attached to disabled controls; LIVE-lock feedback could be masked by a generic load-file message. Additional malformed-result tests found a forged safe-peak report admitted unsafe PCM, and a missing summary field caused failure after publication. | Exact accessible tooltips and visible admission feedback, source/channel checks, explicit stages, independent final PCM/report checks before publication. Keep old arrays/stream on rejection; held Prepare and Cancel presses survive real 50 ms refreshes. Cancel closes the owned job and cannot publish stale results. | Full-song ALIVE Remastered remains inadmissible. Use an eligible excerpt; no research-limit bypass. Native interaction/listening checks remain required. |

The LIVE backend already explicitly opens `(capture_id, output_id)`, validates
the native stream identities, and sends worker output through the existing
bounded ring. No evidence supports changing CoreAudio hardware volume, BlackHole
gain or that routing path. A window borrowing an already-running CLI stream
without the gain adapter still requires Stop/restart, with an actionable error.
Diagnostics now reports the opened output's name, PortAudio index and native ID,
separately from requested output and the system-default capture route.

## Controlled PCM investigation

Reproduce with:

```bash
python -m tools.audio_control_verify --output docs/control-center/hardening-pcm.json
```

The evidence file contains source PCM hashes, waveform residuals, adjacent-step
counts, sample peaks, envelope statistics, render timings, full-passage outgoing
PCM equality, zero-filled final-block tails and mode-transition checks. Cases:
997 Hz sustained tone and synthetic attacks/decays at 44.1/48 kHz; first three
seconds of the preserved Ember and Outbreaker original excerpts. Each mode uses
identical decoded float32 source samples without resampling. Remastered 0/100%
is measured separately from traditional processing. No baseline audio is rewritten.

For the 48 kHz sustained tone, residuals below are RMS differences after fitting
a scalar gain, divided by source RMS. Envelope CV uses a Hilbert envelope on
the central 2.6 seconds. Neither metric is a listening or acceptance score.

| Processing | Gain-fitted residual / source RMS | Envelope CV | Sample peak |
| --- | ---: | ---: | ---: |
| Original | 0% | 0.00323 | 0.25000 |
| Traditional Velvet | 13.87% | 0.03332 | 0.24844 |
| Traditional Legato | 19.73% | 0.04587 | 0.24843 |
| Traditional Melt | 32.02% | 0.06751 | 0.25404 |
| Remastered Melt, 100% | 0.173% | 0.00333 | 0.25331 |

With Melt's smoother alone the residual is 33.50%; harmonic blending alone is
4.68%. This isolates a reproducible production-DSP contribution without a device,
decoder/SRC ambiguity, mode transition or background render. It does **not** prove
that those changes sound like the creator's bubbling, nor validate Remastered
as a better algorithm. Further mathematical work belongs in a separate reviewed
proposal (below), preserving these measurements as the baseline.

Across all six cases, full static traditional-mode playback and transitions
match expected float32 PCM exactly after the preserved 25% GUI attenuation.
No manually supplied DAC timestamp gaps or status flags occurred. Callback wall
times are host observations, not guaranteed native deadlines. A separate regression
pumps every source frame while a real child renders and validates Remastered;
every output sample matches the selected buffer/crossfade and only one stream opens.
This verifies publication continuity, not real hardware scheduling under load.

## Preparation and diagnostics contract

- **Ready** means an admitted local excerpt; otherwise show the actual unavailable reason.
- **Preparing** follows accepted job ownership; **Validating** is a real child
  output/numerical screen stage. The final worker also rechecks identity, metadata
  and actual float32 PCM. A validated result is retained only after those checks.
- **Applying** means the validated buffer reference was selected. While playing,
  **Completed** waits for a callback to consume it and finish the existing fade.
  While stopped/paused it means the selection is ready for playback.
- **Canceled / Failed** retains existing audio and last status even when an older
  Remastered mode remains selected. A retry owns a new job.
- Progress is indeterminate while preparing/validating/applying. No elapsed-time
  percentage is invented. No partial buffer can be published.

Diagnostics distinguishes selected versus callback-applied ALIVE mode, opened
ALIVE output, gain/transport evidence, requested versus worker-applied LIVE mode
and gain, eligibility, preparation stage and validation measurements. Worker gain
is before the bounded output queue, not proof of a DAC or acoustic measurement.
ALIVE status totals survive Stop; a new output-stream open starts new totals.
LIVE safety-stop counters remain governed by the existing retained-session policy.
DAC gaps count timestamp deviations over two samples, not audible glitch events.
The callback adds only bounded scalar counters/timestamp arithmetic outside frozen
BufferPlayer; no logging, locks, file access, waveform analysis or callback DSP.
Changing detailed counters stay inside the scroll-preserving Diagnostics viewport.

## Before/after verification

Before changes, focused regressions reproduced the 25→100% slider reset, missing
disabled-control reasons, unsafe PCM accepted under a stale safe-peak report, and
missing report fields causing failure after replacing active audio. New tests
also cover 0/25/100% outgoing LIVE callback PCM, Mute, held native mouse gestures,
cancel during playback, malformed-result recovery/retry, real child rendering,
continuous sample cursor/fade output, stream cleanup and retained ALIVE evidence.

Existing tests retain long-file/rate admission, supersession, real process
cancellation, decode, mode switching, safety stops, output identity safeguards,
launch commands, full research regressions and frozen-hash verification.
The only existing test-fixture updates add explicit stereo metadata to synthetic
loaded-file snapshots; no acceptance assertion or gate was removed.

Local final code verification (Linux, Python 3.12, optional GUI installed):

| Check | Result |
| --- | --- |
| Focused hardening regressions | 8 passed |
| Complete suite, no research exclusions | 825 passed, 8 skipped, 1 expected failure |
| Production-only suite, existing exclusions | 471 passed, 8 skipped, 1 expected failure |
| Remastered intensity matrix | 60 cells PASS |
| LIVE Remastered equivalence/retained-state matrix | 60 cells PASS |
| PCM comparison probe | 6 sources; exact expected static and transition output |
| Frozen-hash verification | Passed in complete suite; no frozen code/audio changed |

The strict expected failure is the existing non-zero-strength chunked harmonic
continuity risk (`test_harmonics_adversarial.py`), not a new failure or a waived
gate. ALIVE's production preparation processes whole files; do not silently apply
that known chunking limitation as the explanation for this separate observation.
The eight local skips are existing native macOS codec cases. The
complete suite also ran with the optional GUI installed, exercising the new Qt tests.
Full GitHub matrix results are recorded in the PR's verification update.
The initial local baseline had four launch failures because this container lacked
PortAudio; supplying the installed runtime resolved them without repository changes.
No native MacBook sound quality or physical routing claim follows from CI.

## Native MacBook Pro Speakers acceptance

1. Use the PR checkout with `python -m pip install -e '.[gui]'`. Keep hardware
   volume at a manually selected low listening level throughout. Record commit,
   macOS/PortAudio version, source filename/hash, source rate and mode.
2. Stop competing ISLA sessions. In macOS Sound choose standalone **BlackHole 2ch**
   as system output. In ISLA choose System Audio, BlackHole capture and **MacBook
   Pro Speakers** as physical playback; apply at 48 kHz and recheck routing.
   Avoid a Multi-Output/Aggregate parallel listening path.
3. Start LIVE in Bypass with a quiet, steady source. In Diagnostics confirm opened
   physical output is MacBook Pro Speakers and differs from system-default
   BlackHole. Record its native ID/index. Never change hardware or source volume
   to compensate during the comparison.
4. Apply 100%, 25%, 0%, 100%, then Mute/Unmute, waiting a second after each.
   Check requested/worker-applied gain, continued input RMS, output RMS and audible
   level. With a steady tone, after delay/ramp settling, output/input RMS should
   be near 1, 0.25, 0, 1; 25% is about −12.04 dB amplitude. 0% must be digitally
   silent (0.00000 output RMS); audible sound then suggests another path.
   Also use keyboard slider edits followed by a deliberately slow Apply click.
5. Stop LIVE and confirm cleanup/retained counters. Disconnect/reconnect or change
   the output only while stopped, refresh and verify identity before another start.
   Restore normal macOS physical output after LIVE stops.
6. ALIVE: load the exact source associated with bubbling. Keep the automatic 25%
   output level. Compare identical timestamps in Original, Velvet, Legato, Melt;
   record every artifact time and Diagnostics counters before/after it. Repeat
   at 44.1/48 kHz with actual source files at those rates; do not silently relabel
   samples. Save source and processed offline copies for blind listening review.
7. Compare the same passage as PCM WAV/FLAC versus the original compressed file
   where available. If Original also bubbles, investigate decoding/device timing
   first. If only processed offline PCM bubbles without counter changes, advance
   the DSP proposal. Measure output/callback status; do not infer underruns from
   the word “bubbly.” Native SRC/device conversion remains outside this host probe.
8. Use a ≤30-second mono/stereo 44.1/48 kHz excerpt with headroom. While playing,
   prepare each Remastered mode, observe stage/loading, continue listening and
   cancel a second request. Position and stream should continue; cancellation
   preserves prior audio. Repeat under normal and deliberately busy CPU load,
   recording underrun/DAC-gap changes and artifact timestamps.
9. Check a >30-second file and unsupported-rate excerpt: exact reason visible and
   accessible; standard ALIVE still works. Test failure/retry with the automated
   malformed/peak fixtures; no rejected buffer may become audible. Close normally
   and confirm no stream/child remains.

Native acceptance is complete only when the creator records outcomes and agrees
the reported audible behavior is resolved or explicitly accepted. Until then HOLD.

## Separate scientific review proposal — no algorithm change here

Investigate sustained-signal boundary-candidate clusters and the time-domain
neighborhood mixing independently of harmonic spectral smoothing. Replay the
same hashed inputs with isolated-stage ablations, inspect boundary-local waveforms
and sidebands, and use level-matched blind comparisons on the creator's exact
problem passages. Predefine transient-preservation, modulation, peak and listening
criteria. Any candidate DSP must live outside the frozen implementation with its
own version/evidence; changing thresholds or kernels here would obscure causality.
