# Frozen primary protocol · Experiment 02

Frozen hash and commit are recorded in FREEZE.json before candidate evaluation.
Development unit fixtures may check correctness; primary configurations are not
selected from evaluation outputs. Parameters are the defaults in core.Config;
no sweep winner is claimed. Any later change requires a labeled exploratory run.

## Hypotheses and nulls

V02: governed upper-band texture processing preserves attacks/beating better
than unconditional processing of comparable depth and may be preferred as softer.
L02: governed temporal spectral memory may improve event connectedness while
preserving incoming attacks relative to fixed and scalar-envelope controls.
M02: bounded phase-trajectory correction may perceptibly alter sustain evolution
while retaining pitch, recognizable piano identity and attacks, independently
of slowdown. G02: governance earns its complexity only by improving registered
attack preservation at comparable effect dose, without worsening other gates.
S02: stereo-consistent offline slowdown retains pitch/duration/stereo within
screens, with acceptable attack smearing confirmed by listening.

Nulls: no audible difference; no creator preference; no improvement beyond fixed
or matched conventional DSP; state misalignment performs equally; phase score
does not distinguish controlled stable/noisy inputs. A residual is not a benefit.

## Source and design separation

Reuse the 56 Experiment 01 source/format cells: 11 deterministic fixtures plus
gapped_tone, near_silence and the six-second recorded-piano crop, at 44.1/48 kHz,
mono/stereo. Source equality against recovered Experiment 01 manifests is
verified, with any mismatch explicitly reported. The 16 s source recording is
SHA256 9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15.
Its seconds 2–8 reproduce the old diagnostic domain; seconds 9–15 are a
separate uncalibrated evaluation excerpt from the **same** recording, not an
independent artist/instrument. License is CC0 per the authoritative Freesound
page, with instrument/recording-method limitations preserved.

Additional ground-truth fixtures use two tones at 440 and 440+Δf Hz, each .12
amplitude, Δf=.2/1/1.5/3 Hz, undamped or τ=6 s exponential damping, 20 s signal
with .125 s leading/trailing silence. Seed=20261024. A second carrier at 3520 Hz
exercises the upper-band path; it is a distinct additive test, not a piano model.
Development cases are .5 s tones, steps and simple impulses. They are not held
out. The reused corpus and prior failures are also known development history;
claims of broad held-out generalization are forbidden.

Before evaluation, write all input WAVs, event metadata, exact formats, source
hashes and source-generation code hash in SOURCE_MANIFEST.json. FLOAT WAV copies
are auditable inputs, with generation gain fixed independent of candidates.

## Comparison matrix

Each original-duration cell: exact Bypass; original production Velvet/Legato/Melt;
recovered Experiment 01 .20/.50/.30; governed/fixed/fixed_matched/attack_gated/
shuffled/noop for each identity; conventional scalar-envelope continuity control.
Noop and fixed are falsification controls. .30 Melt remains labeled prior failed
candidate; it is not retrospectively replaced by .15.

The scalar-envelope control tracks the 1 ms pooled-power RMS envelope with
5 ms attack / 80 ms release one-pole time constants and applies shared gain
clip(history/current,.80,1.188502227), returning unity below 10⁻⁵ envelope.
It has no additive output or global normalization. Its incoming-attack behavior
is measured alongside the spectral-memory path.

Slowdown only on selected original-duration piano/controlled tone and impulse
fixtures: raw shared-phase PV, protected PV, optional established librosa PV
reference, ratios 1.25/1.50. Untreated stretch plus each governed identity is
measured and supplied for creator comparison. No LIVE integration.

## Registered engineering screens

These numerical tolerances are conservative research screens, not validated
perceptual thresholds. Failure is retained and prevents a research PASS.

* Exact Bypass/noop array equality. FFT reconstruction max error ≤1e−10 in
  float64, shape unchanged; production delay unchanged. Deterministic replay
  bit equality in the same environment. Reject nonfinite input/output.
* No raw sample or 4× polyphase oversampled absolute peak ≥.98 for new candidates.
  Estimate is **not** certified true peak. No hidden limiter/normalization.
  RMS shift ≤2 dB; settled silence after 100 ms gap ≤1e−10 amplitude.
* Independent-original-reference local normalized waveform-correlation lag
  ≤1 ms for ≥.8 correlation; low correlation remains unresolved. First 10 ms
  transient RMS movement ≤2 dB where original energy is measurable. Any envelope
  or novelty detector shift >1 ms remains flagged for listening, even with zero
  correlation lag. No detector is disabled to clear a failed case.
* Beat-frequency absolute error ≤max(.03 Hz,.03Δf), detrended envelope correlation
  ≥.98, inferred two-component spacing retained within same tolerance. Damped
  fitted amplitude-decay τ movement ≤10%. High-band and low-band cases separate.
* Sustained-pitch displacement ≤3 cents on known tones. Report harmonic-envelope
  change and amplitude-modulation residual; arbitrary recorded notes lack ground truth.
* Stereo reanalysis reliable-bin RMS IPD movement ≤.10 rad, channel-balance
  movement ≤.5 dB, no energy in the silent channel of single-channel probes.
  Antiphase and dual-mono controls must preserve their exact relationships.
* Governed control values within config bounds, ordinary slew within maxΔt/.10 s
  except logged attack/silence/confidence veto; finite resettable memory. Report
  state changes, ambiguity, confidence, veto %, limit %, effective depth and
  processing %. Do not equate regime labels with precise note stages.
* Phase-proxy diagnostic: median C(stationary-tone) > median C(seeded-noise) is
  a weak discrimination screen; detuned-tone behavior reported separately.
  It is insufficient to validate a universal coherence measure.
* Slowdown duration within one sample of round(input*r), tone pitch ≤3 cents,
  exact silence ≤1e−12, phase/stereo and transient-smear results recorded.
  See SLOWDOWN.md for additional independently frozen development limits.

Continuity proxy: RMS first-difference of 1 ms RMS envelope, evaluated on original
reference transition windows. Report relative change and energy change, without
converting reduction into a claim of connectedness. Phase/beat/attack safeguards
take priority over target magnitude. Fixed_matched depth mismatch is disclosed.
No significance test from treating correlated frames as independent music samples.

## Attack-failure investigation and listening

Revisit all six originally selected recorded-piano failed cells. Keep original
detector findings plus original-only onset reference, normalized waveform lag,
envelope slope, competing-peak ranking, novelty timing and 10 ms local energy.
Distinguish ambiguous peak ranking, actual waveform displacement and altered
transient character. Low-correlation and detector disagreements remain unresolved
until independent creator listening, even if the waveform peak lag is zero.

Raw WAVs preserve actual processing level. Separate paired listening copies use
one scalar RMS match to original and one common pair headroom gain (4× peak ≤.8),
same gain for both channels; all gains logged. This is energy matching, not
certified perceptual loudness equality. Randomized A/B order fixed by seed; key
separate from response sheet. Include duplicate A/A and deliberately processed
controls. Eight independent questions: discrimination, preference, smoothness,
piano character, expressive attacks, resonances, mode distinctness, artifacts.
No positive response is filled in. Browser playback is not accepted as file QA.

## Decisions and preservation

PASS requires all relevant safety/target gates **and creator evidence**. REVISE
means a potentially useful mechanism with unresolved or failed gates; REJECT
means failure/no justified complexity; INCONCLUSIVE means insufficient evidence.
No automatic production promotion follows any classification. Record raw metrics,
all failures, environments, runtime/peak RSS, actual source and output checksums,
exact research commit, tested regression logs and restoration instructions.
No generated WAV/dataset enters ordinary Git. A second independent offline/cloud
copy is recommended; local duplicate verification is not an independent backup.
