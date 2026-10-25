# Final Control Center acceptance — v4.0.0

**Recommendation: HOLD publication.** Code/PCM regression acceptance is separate
from creator listening acceptance on physical MacBook Pro Speakers. The reported
bubbling remains unresolved. Research remains **REVISE / INCONCLUSIVE**. No merge,
tag, publication, release, version bump or scientific baseline change is authorized.

Baseline: `aae176d7deea053d740be39bf3cb2fe67bbb78e4`, merged Save Mix PR #67.
PRs #64–#67 are merged; no open related PR existed when inspected.

## Findings and resulting behavior

| Finding before this change | Result |
| --- | --- |
| Expanded Remastered settings had no exclusive backend state or saved traditional selection. | Browsing is inert. Explicit Enter checks source admission first, remembers Original/Velvet/Legato/Melt with the original array identity, then selects Bypass through the existing block-edge crossfade. Both GUI and service reject traditional selection during the workspace. |
| Cancel closed the render without a saved-mode restoration contract. | Cancel closes even a ready-but-unpolled render before restoring the remembered mode. Applied Remastered has a distinct Return to Previous Mode action; backend Cancel rejects pretending it is pending. |
| ALIVE attenuation captured a constant at stream creation. | The separate output adapter reads a scalar requested level and applies a preallocated 5 ms ramp to final callback PCM. New GUI default 25%; deliberate 50% is supported. No stream reopen. |
| LIVE gain existed before its output queue, but GUI default was 100% and required Apply. | New GUI sessions request 50%; slider changes and keyboard edits apply automatically. Mute uses the current local choice, so rapid actions cannot use a stale snapshot. The existing explicit physical output device path is retained. |
| Global command state could interfere with volume edits and held clicks. | Two scalar mailboxes coalesce volume edits independently of the one-slot audio command queue. An 80 ms GUI cadence bounds submissions. Only the existing serialized worker consumes them; locks never enter either audio callback. Status polls never rewrite initialized slider drafts. Buttons receive their final enabled state without transient disable/re-enable cycles. |
| Save Mix rejected unconsumed selections but could admit a partially completed short-block fade. | Save is unavailable throughout preparation and the entire mode crossfade. Diagnostics names the exact prepared buffer that would be saved. The tested float32 WAV/background writer/no-overwrite/cancel architecture is unchanged. |

The LIVE device backend already explicitly selects the output PortAudio ID and
validates native CoreAudio stream identity. This assignment found no reproducible
software defect specifically tied to MacBook Pro Speakers in that path. Automatic
updates and outgoing PCM attenuation are verified; **physical audibility is not**.
A borrowed terminal stream without the GUI adapter must be stopped/resumed or
restarted from this window; errors explain this rather than claiming applied gain.
Diagnostics uses “not observed” for an ALIVE stream without that adapter.

## State and restoration design

| State/action | Playback and publication |
| --- | --- |
| Traditional / Original | Existing prepared-buffer selection; Save Mix available when transition settles. |
| Browse / collapse settings | No playback change and no workspace entry/exit. |
| Entered | Admission: prepared file, mono/stereo, nonempty, ≤30 seconds, 44.1/48 kHz, no LIVE stream. Then remember mode/source and select Original. |
| Preparing / Validating | A spawned child owns preparation; current playback continues. No Save Mix; no incomplete publication. Intensity release alone no longer starts rendering. |
| Applying | Final source/request/report/PCM validation precedes publication through the unchanged player fade. |
| Remastered active | Complete validated buffer selected; Save Mix available after transition; explicit Return action. |
| Cancelled | Child closed; previous traditional selection restored without cursor/stream/volume changes. Existing safe transition consumed by playback. |
| Returning / Returned | Remembered mode selected; Returning lasts until playing callback completes fade, or a paused/stopped selection is ready. |
| Failed | Failed render closes; current selected buffer remains. Workspace retains the valid source/mode restoration target so Cancel/Return or retry remains available. |
| Pause / resume | Workspace/preparation survive; frozen player preserves audible position semantics. |
| Stop | Pending work cancelled, workspace left and previous traditional mode restored; ordinary Stop resets the cursor through the existing player. |
| New recording / source / shutdown | Workspace/job discarded. No old recording or stale mode restored. An unexpected replacement original-array identity also invalidates the job before polling its result. |
| Saving | Background export captures the immutable selected buffer and explicitly reports its mode, independent of later playback choices. Contextual Cancel Save cleans temporary data. |

The source buffer identity, not a filename alone, governs restoration. Changing a
recording or closing a borrowed session cannot retain the old restoration target.
No frozen playback, LIVE transport, streaming DSP, Experiment 02 core, research
hashes, historical result files or v4.0.0 source metadata changed.

## PCM evidence and audible-artifact investigation

Reproduce engineering evidence with:

```bash
python -m tools.control_acceptance_verify --output docs/control-center/final-volume-pcm.json
python -m tools.audio_control_verify --output docs/control-center/final-passage-pcm.json
```

[Volume PCM evidence](final-volume-pcm.json) exercises actual manually driven
ALIVE and LIVE outgoing callbacks. LIVE uses the real worker and bounded output
queue with a scheduled dry DSP to isolate output gain. Both rates use the same
float32 input amplitude 0.4; samples are inspected after processing and queue
handoff, before a memory device stands in for speaker delivery.

| Setting | Expected multiplier | Settled output amplitude | Maximum PCM error |
| --- | ---: | ---: | ---: |
| 0% | 0.00 | 0.00 | 0 |
| 25% | 0.25 | 0.10 | 0 |
| 50% | 0.50 | 0.20 | 0 |
| 100% | 1.00 | 0.40 | 0 |

All **16 gain cells** (two paths × two rates × four levels) pass exactly; source
capture is unchanged and there is one LIVE stream per rate. The dry LIVE fixture records one initial empty-pipeline output and zero ring failures per rate; this is not a native device underrun measurement. Ramps settle over
5 ms, including across short blocks. Tests separately change volume during a
real prepared-mode crossfade, verify sample continuity against its mathematical
expectation, and confirm saved PCM excludes every listening-gain setting.

[Passage evidence](final-passage-pcm.json) reruns the six exact hashed sources in
PR #66: 997 Hz sustained tones and attack/decay fixtures at 44.1/48 kHz, plus the
same first three seconds of preserved Ember and Outbreaker originals. Original,
Velvet, Legato, Melt and admitted Remastered 0/100% use identical decoded PCM.
All six input hashes match the earlier evidence. Static outgoing traditional
buffers and mode transitions again match expected attenuated PCM with **zero
sample error**. Historical evidence is retained unchanged.

| Possible source of bubbling | What the evidence establishes | Still unresolved |
| --- | --- | --- |
| Harmonic coloration / unwanted amplitude modulation | Traditional DSP adds reproducible gain-fitted residual and envelope variation before a stream exists. At 48 kHz sustained tone: Velvet 13.87%, Legato 19.73%, Melt 32.02% residual/source RMS. Melt smoother-only 33.50%, harmonic-only 4.68%. | Whether the creator considers those exact changes the unwanted audible “bubbling”; subjective harmonic coloration versus objectionable modulation requires listening. |
| Processing-window artifacts | Source-matched ablation and adjacent-step/envelope measurements isolate existing production processing contributions. | Causal listening attribution to a specific window/boundary operation requires a separate DSP proposal. |
| Mode transitions / underruns | Memory callbacks match frozen fade output; one-stream ownership, retained status/underflow/DAC-gap counters and real spawned-render regressions pass. | Native PortAudio deadlines, CoreAudio scheduling, device conversion/SRC and speaker rate behavior. |
| Compressed decoding | Existing decoder tests retained; preserved FLAC inputs decode to identical hashes. | Creator's exact compressed problem recording was not supplied here; native macOS codec tests are skipped on Linux. |
| Preparation CPU contention | Child niceness and worker isolation from PR #65 are preserved; concurrent real render/callback equality passes. | Actual Mac scheduling/load and acoustic artifacts during preparation. |

No control lock is presented as an audio-quality fix. No DSP threshold, kernel,
processing equation or historical scientific output was changed to pass acceptance.

## Regression results

Local final code results (Linux Python 3.12, optional GUI installed):

| Check | Result |
| --- | --- |
| Complete suite | **874 passed, 8 skipped, 1 existing xfailed** |
| Production-only suite | **492 passed, 8 skipped, 1 existing xfailed** |
| Remastered intensity matrix | **60 cells PASS** |
| LIVE Remastered equivalence matrix | **60 cells PASS** |
| Output gain callback matrix | **16 cells PASS, zero PCM error** |
| Same-passage probe | **6 matching source hashes, zero transport PCM error** |
| Frozen code / historical evidence | **Unchanged; full-suite freeze checks pass** |

Final hosted CI status is recorded in the implementation PR. Local
commands preserve all assertions and the complete research suite:

```bash
python -m pytest -q tests
python -m pytest -q tests --ignore-glob='tests/test_resonance02_*.py' --ignore-glob='tests/test_remastered*.py'
python -m tools.remastered_verify --output remastered-verification.json
python -m tools.remastered_live_verify --output remastered-live-verification.json
```

The new tests cover every traditional mode × playing/paused/stopped restoration,
rapid cancellation/supersession (including a newer traditional choice during Return), rejected admission before any playback change,
ready-result cancellation, load/source identity invalidation, shutdown, failed
render retry/restore, deliberate return, all gain levels, short ramps, live worker
output, no gain-induced restart, export PCM and fade guards, held native clicks,
keyboard/focus edits, bounded mailboxes under a blocked command, and inert panel
browsing/collapsing. Existing Save Mix no-overwrite, cleanup and real-render tests
remain. Existing tests were adapted to explicit Enter and automatic sliders;
none of their buffer/stream/frozen-math assertions was weakened.

The Linux host needed a supplied PortAudio runtime and a local virtual environment
for genuine console-entrypoint tests. Neither required repository changes. The
existing expected failure is non-zero-strength chunked harmonic continuity;
eight native macOS codec skips are retained. Hosted CI is not acoustic evidence.

## Native MacBook Pro Speakers acceptance — creator checklist

Record commit, macOS/PortAudio versions, source filename/hash, sample rate,
physical volume and outcomes. Begin at a low hardware and source level; leave
hardware volume fixed during comparisons. Do not use a 100% hardware setting.

1. Stop other ISLA sessions. ALIVE: select **MacBook Pro Speakers**, Play a quiet
   local source, and verify the opened output identity in Diagnostics. New GUI
   level must be **25%**. Test slider drag and keyboard edits at 0/25/50/100%,
   waiting a second after each. Confirm requested/callback-applied gain, digital
   silence at 0%, obvious attenuation, unchanged position and no stream reopen.
   Repeat during mode transitions and Pause/resume. Unity output may be louder;
   begin with physical volume low and stop if uncomfortable.
2. LIVE: pause the source; macOS Sound Output = standalone **BlackHole 2ch**.
   Inside ISLA choose BlackHole capture and **MacBook Pro Speakers** physical
   playback. Apply at 48 kHz, recheck, Start in Bypass at default **50%**. Diagnostics
   must name MacBook speakers with PortAudio index/native ID, distinct from the
   system-default BlackHole route. Avoid any parallel Aggregate/Multi-Output path.
3. Resume a quiet steady source. Test 0/25/50/100%, Mute/Unmute, rapid keyboard and
   drag edits. Wait for ramp/queue settling. Confirm requested and worker-applied
   gain, continued input RMS and output/input amplitude near 0/.25/.50/1 at unity
   Bypass. 25% is about −12.04 dB; 50% is about −6.02 dB digital amplitude. If 0%
   output RMS is silent digitally yet music remains audible, identify another
   listening path. Record observations; do not infer hardware proof from CI.
4. Stop LIVE, verify cleanup, restore normal macOS speaker output. Test the exact
   troublesome passage in Original/Velvet/Legato/Melt at fixed listening level;
   record artifact timestamps and callback underflow/DAC-gap counters. Compare
   lossless PCM against the original compressed recording where available.
   Repeat with actual 44.1/48 kHz sources and record native device rate settings.
5. With a supported ≤30-second excerpt and headroom, choose Legato; show/hide
   settings and confirm no audible change. Enter Remastered: Original becomes
   selected and traditional controls lock. Prepare Velvet, Cancel: Legato returns
   at the preserved position. Repeat from Original/Velvet/Melt, paused and stopped.
6. Enter, prepare and apply each admitted Remastered mode on the same passage.
   Observe Preparing/Validating/Applying/Completed. Save Mix only after validation
   and fade completion. Use **Return to Previous Mode** and confirm prior mode,
   cursor continuity and output level. Test a new file and shutdown with a pending
   request; old results must never reappear. Repeat under ordinary and busy CPU
   conditions while watching transport counters.
7. Save traditional and validated Remastered mixes at several listening levels.
   Open WAVs externally at low hardware volume; verify rate/channel/float32 format,
   selected mode, unchanged original, no overwrite and no listening attenuation
   baked in. Cancel a background save and confirm no partial destination or
   staging files. Test unavailable long-file/rate admission without losing the
   traditional selection, and close with no child/stream left behind.

**GO requires creator acceptance of physical attenuation, routing, playback,
exports and the reported audible quality. Until that is recorded: HOLD.**

## Files changed

- `isla/remastered_session.py`, `isla/control.py`: source-bound exclusive workspace,
  restoration lifecycle, gain setters/snapshots and export transition gate.
- `isla/listening_gain.py`, `isla/alive_listening_gain.py`, `isla/monitor_gain.py`:
  independent output-only ramp and requested/applied levels.
- `isla/qt_window.py`: explicit entry/return, automatic sliders/mailboxes, centered
  values, always-visible Save/Return controls and consolidated Diagnostics.
- New `test_control_final*` / `test_remastered_final*` regressions and existing
  Control Center/Remastered/Save Mix tests adapted to the requested interaction.
- `tools/control_acceptance_verify.py`, two new engineering PCM JSON reports,
  this report and README. Existing evidence and export implementation retained.
