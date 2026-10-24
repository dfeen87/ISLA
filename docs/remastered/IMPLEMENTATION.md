# v4.0 Remastered research preview

This opt-in ALIVE preview connects the frozen Experiment 02 governed renderer
to the existing file player. It adds independent processing-depth control for
Velvet, Legato and Melt. This codebase's Python package, HTTP API and CMake/JUCE
source version is 4.0.0. The published v3.3.0 release and existing production
DSP/LIVE behavior remain unchanged. This version alignment does not constitute
a published v4.0.0 GitHub Release, production promotion or native/creator
listening acceptance. The historical Experiment 02 freeze and its original
3.x-versioned file hashes remain pinned to their original source revisions.

## Use the preview

Install a checked-out v4.0.0 source candidate in a separate environment, then run:

```bash
python -m pip install -e '.[gui]'
python -m isla window
```

1. Open a WAV excerpt at 44.1 or 48 kHz, mono or stereo, up to 30 seconds.
2. Wait for ordinary ALIVE preparation; Play is optional.
3. Click **Show v4.0 Remastered Research Preview**.
4. Choose Velvet, Legato or Melt Remastered. Set the slider and click
   **Prepare / Apply Remastered**. Releasing the mouse slider also requests a render;
   keyboard edits take effect when Apply is clicked.
5. Read the active mode, confirmed intensity, preparation state and measurements.
   Editing a choice alone does not change the active buffer. A newer request
   cancels its predecessor. Audio continues while preparation runs.
6. **Cancel Preparation**, **Stop**, a production mode, **Original / Bypass**,
   a replacement file, switching to LIVE devices, or closing the window cancels
   a pending research render. Bypass selects the original decoded samples.

The panel starts collapsed. Its controls do not alter LIVE monitoring, the LIVE
listening-volume slider, offline CLI export, or the production DSP algorithms.
ALIVE and LIVE retain exclusive stream ownership and routing checks.

## Mathematical contract and source authority

Authority: [core.py](../../tools/resonance02/core.py),
[SPECIFICATION.md](../research/phase-governed-resonance-02/SPECIFICATION.md),
[FREEZE.json](../research/phase-governed-resonance-02/FREEZE.json), and
[RESEARCH_REPORT.md](../research/phase-governed-resonance-02/RESEARCH_REPORT.md).
The adapter checks the frozen core SHA256 before rendering. None of these files
or the historical results is edited. [PRESERVATION.json](PRESERVATION.json)
records preservation against the inspected main commit.

For integer slider ticks I in {0,5,...,100}, s=I/100 and
`dataclasses.replace(Config(), selected_mode_depth=baseline_depth*s)` constructs
a new frozen per-render configuration. All other fields retain their values.

| Mode | Baseline depth | 25% | 50% | 75% | 100% |
|---|---:|---:|---:|---:|---:|
| Velvet | .16 | .04 | .08 | .12 | .16 |
| Legato | .30 | .075 | .15 | .225 | .30 |
| Melt | .30 | .075 | .15 | .225 | .30 |

The unchanged renderer computes:

\[
t_V=.16s\,h(1-a)(g_S+.5g_B+.3g_D),\quad
t_L=.30s\,h(1-a)(g_D+g_O),\quad
t_M=.30s\,h(1-a)g_S.
\]

It vetoes control to zero on attack >=.5, confidence <.2, or silence.
Otherwise its ordinary control change is bounded by
`effective_depth * (512 / sample_rate) / .10` each hop. Scaling the depth
therefore scales **both target and recovery allowance**, retaining the 100 ms
recovery time. The immediate safety veto still overrides the ordinary slew.

Unchanged mechanisms: 2048-sample periodic-Hann STFT / 512 hop, the six regime
weights, `tonality * max(0, phase_coherence)` confidence, Velvet logarithmic
spectral curvature, Legato 80 ms log-magnitude history, and Melt shared bounded
phase trajectories. Melt frequency tracking remains **60 ms**, with **80 ms**
phase-offset decay; these are separate constants in the frozen renderer.
The per-bin gain interval [.80, 1.188502227] and phase ceiling +/- .10 radians
do not scale with intensity. Channels share the same gain/phase operations and
are never mixed.

The percentage is processing authority. It is not an amplitude multiplier,
wet/dry ratio, perceived loudness percentage, waveform-residual percentage,
or promise of a monotonic audible difference. The nonlinear operations,
accumulated phase and reconstruction preclude those interpretations.

## Exactness and admission

- **0%:** the frozen renderer observes zero control and returns `x.copy()`.
  Output shape, dtype and bytes, including signed zero, match the input.
  Analysis runs for veto evidence; FFT reconstruction is bypassed.
- **100%:** the configuration equals the governed frozen default. Raw output is
  required to be **bit-identical** to `core.render(x, sr, mode)` on the same
  decoded input, dtype and environment. Playback is required to equal that
  reference cast to float32. No cross-platform bit identity is assumed.
- **Intermediate:** raw output must equal the frozen renderer with only that
  mode's depth replaced. Deterministic replay, depth/rate/veto checks, phase/gain
  ceilings, shape and finite samples are checked independently.
- Prepared float32 samples also undergo finite, shape, sample-peak and 4x
  polyphase peak-estimate screens. The research admission ceiling is .98.
  This estimate is not certified true peak. A hot source can be rejected even
  at 0%; its computed zero-depth buffer is still an exact copy. Production
  Original / Bypass remains available. Rejection never normalizes, limits or
  clips the audio to obtain a pass.

The research renderer returns float64 reconstructed audio for transformed
float32 inputs. That raw result is retained for equivalence measurements;
only the separately validated playback buffer is cast to float32 for PortAudio.
The common spectral gain/phase ceilings alone do not bound waveform peaks.
For a mode/intensity transition, the existing 5 ms player crossfade briefly
combines the old and new buffers; exactness assertions describe the prepared
buffer and settled playback, rather than that transition interval.

## Preparation and publication

`isla/remastered.py` is the mathematical adapter and diagnostics layer.
`remastered_preparation.py` spawns a cancellable child process, reading the
original `.npy` saved by ALIVE preparation. It never rereads a potentially
changed WAV or processes an already transformed buffer. Results and a JSON
report are written to temporary files; small progress messages travel on a pipe.

`remastered_session.py` publishes only a completed, validated result, on the
existing command worker. It copies the ready temporary mapping into an owned
float32 array, closes the process and removes its temporary files. Only one
research buffer is retained in the selectable bank. The player retains old
array references as needed for its existing crossfade. Superseded jobs cannot
publish; failed jobs leave active audio, cursor and stream intact.

Publication uses `BufferPlayer.select`, never `install`, `stop`, a new stream,
or callback DSP. Playing, paused and stopped positions retain their semantics.
The source, three production buffers and callback implementation remain intact.
The 30-second limit bounds admission to this whole-file research implementation;
it does not convert it into a streaming or bounded-memory algorithm.

`setup.cfg` includes the frozen research package in wheels; normal production
operations do not import the research core. The complete regression suite runs
all research and preview tests. CI's separate production-only check excludes
both experiment and preview tests, preserving its independent purpose. The ALIVE
CI matrix additionally exports post-freeze intensity evidence on Linux/macOS and
Python 3.10/3.13. No historical failed screen is hidden or relaxed.

## Reproduce and inspect the evidence

```bash
python -m pip install -e '.[gui]' -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest -q tests
python -m tools.remastered_verify --output remastered-verification.json
```

[INTENSITY_MATRIX.json](INTENSITY_MATRIX.json) contains **60 cells**:
3 modes x 5 intensities (0/25/50/75/100) x mono/stereo x 44.1/48 kHz.
Its reproducible synthetic source includes attacks, tonal vibrato, decay, noise
and settled silence. It records source/output hashes, requested/target/applied
depth, recovery allowance, veto/limit counts, sample/RMS/4x peak levels, waveform
differences, ceiling/veto/recovery checks, deterministic replay, and endpoint
identity. Raw and delivered float32 measurements are distinguished.

This is new engineering evidence, **not a repeat of the historical 76-cell
scientific study**, a recording of a real piano, or creator listening acceptance.
Stereo tests additionally check identical channels, antiphase, a silent channel,
and settled silence at all five levels. They do not establish universal stereo
perceptual transparency. [VALIDATION.md](VALIDATION.md) records execution results.

## Scientific disposition and native acceptance

The frozen **REVISE / INCONCLUSIVE** musical/governance verdict, estimator false
onsets, effect-dose confounds, pending listening judgments and rejection of
production promotion remain in force. This preview does not retune the
estimator, establish superiority, or introduce slowdown. Tests run real DSP and
real Qt widgets with fake audio transport; they do not establish audible quality
or physical Mac output.

Native Mac acceptance remains open: play a permitted excerpt through physical
headphones; compare source and each mode at the five registered levels; change
depth while playing and paused; cancel and replace requests; return to Bypass;
test a rejected hot render; then close/reopen and verify normal ALIVE/LIVE
operation. Record device/rate, underruns, artifacts, preferences and whether a
change is audible. Unheard or disliked results must be retained without retuning
this frozen baseline. Merge/release requires a separate user decision.
