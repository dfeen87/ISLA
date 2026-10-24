# Musical Identity Lab · Experiment 01 protocol

Written before candidate measurements, October 24, 2026. Research only.

Baseline: verified `v3.1.0` lightweight tag, commit
`6a732e03c3f0adc3f555e0ecb002e365b7e3385f`. Current main was separately
observed at `14d91646b51a383da8839e4885e826808d399829` (v3.1.1).
Use the explicitly requested 3.1.0 baseline; do not roll back current main.

All candidates reuse unchanged LIVE 2048/512 framing, 1536-sample delay,
5 ms selection fades, warm banks, primed Hann-squared weights and bounded
phase-reference reconstruction. Nothing imports these adapters in production.
The original strengths remain .35/.55/.75. Only one bank is altered per sweep.

Hypotheses and single-variable sweeps:

* Velvet: additional three-bin curvature weighting above a smooth 3 kHz knee
  could change upper-partial texture with less low-band movement. Sweep depth
  .10/.20/.30; frequency weight is f²/(f²+3000²). This is not a harshness model.
* Legato: a bounded one-pole history of the shared spectral shaping transfer
  could reduce timbral variation between frames. Sweep memory coefficient
  .25/.50/.75 (nominal ungated e-folding times 7.7/15.4/37.1 ms at 48 kHz).
  It carries no waveform or old magnitude into the current frame and does not
  bridge missing notes. Current transfer is clamped to [.75,1.25], applied
  ratio to [.8,1.2]. Novelty/decay protection can shorten memory to one frame.
* Melt: five-bin binomial envelope curvature could produce broader texture
  movement than the original three-bin law. Sweep depth .15/.30/.45.
  This is local FFT-envelope shaping, not harmonic tracking or pitch shifting.

Fixed safeguards: shared stereo RMS magnitude drives every additional gain;
positive spectral flux gates processing from full at <=.08 to zero at >=.30.
Frame magnitude-sum decay ratio gates from zero at <=.50 to full at >=.85.
First active frames use the original bank. Exact silence clears memory.
Additional gain is bounded, followed by a shared attenuation-only frame-energy
cap relative to the original bank. No limiter, clipping or makeup gain.
These heuristic constants stay fixed; no retuning after inspecting results.

Numerical screening gates (engineering screens, not perceptual thresholds):

* Finite outputs, exact settled silence, exact original result at amount zero,
  exact delayed Bypass, fixed state shapes, unchanged delay and routing code.
* Original startup and near-null thresholds remain untouched. Candidate near-null
  perturbation relative change <.01. No new sample >=1 for the generated corpus.
* Candidate versus original: absolute RMS movement <=1 dB; main attack detector
  shift <=1 ms and first-10-ms attack RMS movement <=1 dB; strongest 440 Hz
  tone estimate movement <1 cent; stereo correlation movement <=.02 and
  channel-balance movement <=.25 dB. Exact no crossfeed, dual mono and polarity
  controls. Failure rejects that amount for further listening recommendation.
* Legato benefit proxy: RMS-matched 1-ms-envelope first-difference RMS should
  not increase >5% on connected melody. A reduction would support continuity
  only as a proxy; no proxy establishes musical connection or preference.

Measure every amount, including unsuccessful ones. Center amounts (.20/.50/.30)
are fixed in advance for the listening showcase, not selected for residual size
or perceived quality. A failed center remains labeled rejected in the report.

Use the existing deterministic generated corpus (11 fixtures, six seconds,
both rates and channel counts), plus near-silence, gap and pitch controls.
Generated piano-like oscillators test attacks, not the full behavior of a real
piano recording. Preserve raw float measurements and source/event provenance.
Listening copies use one constant gain per file, the same gain in both channels,
shared integrated loudness per passage and peak headroom. Near-silence retains
its contrast via one common gain; digital silence has no loudness target.
No listening preference, hardware acceptance, merge or release is inferred.
