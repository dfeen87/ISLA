# Post-freeze slowdown successor 01

This is an engineering successor to the frozen Experiment 02 prototype, not a
replacement for its implementation, parameters, reports, audio or verdict. The
original `slowdown.py`, `run.py`, `FREEZE.json` and 1,976 primary records remain
authoritative for Experiment 02. Production does not import either stretcher.

## Diagnosis and candidate registered before successor measurements

The strict 16 kHz tests reproduce maximum errors of 14.5 and 29 ms. For an input
impulse at sample p, resetting phase to analysis phase at analysis center c and
placing that frame at synthesis center r*c puts the impulse at
`p + (r-1)*c`, rather than `r*p`. The measured reset frames 6, 19 and 31 predict
all six protected output peak locations exactly. Disabling identity phase locking
leaves these errors unchanged. Removing resets does not solve them and produces
additional strong peaks in the raw 1.50 path. This is a time-map/reset-origin
error, not an FFT pitch error or a constant padding offset. Subsequent phase
propagation and differently placed overlapping windows also spread attack energy.

Candidate 01 uses the original detector and refines each reset frame to the
largest positive sample-energy difference inside its analysis window, summing
channel energy before deciding. This is a heuristic anchor, not a physical
hammer-strike annotation. No known fixture event times are supplied to processing.

For isolated anchors p, all analysis frames with `abs(center-p) <= 1024` retain
analysis phase and are placed at `center + round(r*p)-p`. Thus both their audio
and their Hann synthesis windows share one integer translation, preserving local
unit-rate reconstruction and locating the anchor at the nominal scaled sample.
Between these regions, synthesis centers interpolate linearly to compensate the
duration expansion. Phase propagation uses each actual synthesis-center increment
minus the 512-sample analysis increment. Squared-window normalization uses the
same actual frame placements. Both channels share anchors, timing and offsets.

An anchor is admitted only if its nearest detected neighbor is at least 4096
samples away (twice the 2048-sample window). Closer anchors are explicitly recorded
as unsupported and receive no such protection. This separation bounds interior
synthesis increments to 1024 samples at the registered ratios and avoids competing
unit-rate regions. No-anchor, bypass, raw and reset-disabled controls delegate to
the frozen implementation. To reuse its detector exactly, candidate 01 first runs
the frozen path; admitted material incurs a second synthesis pass. This offline
cost is deliberate and is not suitable for LIVE integration.

No frozen thresholds are changed: 10 ms timing, event count, 3 cents pitch, 0.05 rad
stationary stereo, exact duration and silence screens all remain. Development
checks will cover both ratios, sub-hop offsets, boundaries, three sample rates,
channel polarity/balance, non-impulse attacks, dense unsupported events, phase
propagation and window normalization. These are engineering fixtures, not a new
held-out piano evaluation. No primary Experiment 02 matrix will be repeated.

This follows established nonuniform transient-preserving phase-vocoder practice;
it does not implement or validate the complete cited method. See Ravelli, Sandler
and Bello, DAFx 2005, sections 3–4, especially onset location, synchronized stereo
decisions and normalization for variable synthesis hops:
[primary paper](https://www.dafx.de/paper-archive/2005/P_182.pdf).

## Limits retained

Dense or missed onsets, ambiguous waveform-energy anchors, overlapping notes,
recorded-piano stereo and perceptual quality require further evidence. Analysis
phase reinitialization can disturb a simultaneous sustained tone. Short-window
reconstruction and stationary pitch tests cannot establish listening acceptance.
No gain normalization, limiter, clipping, promotion or research PASS is permitted.

## Measured engineering result

The registered input at 16 kHz contains samples `[4000, 10400, 16800]`.

| Expansion | Expected peaks | Frozen peaks | Successor peaks | Maximum timing error, frozen → successor |
| --- | --- | --- | --- | --- |
| 1.25 | 5000, 13000, 21000 | 4768, 12832, 20768 | 5000, 13000, 21000 | 14.5 → 0 ms |
| 1.50 | 6000, 15600, 25200 | 5536, 15264, 24736 | 6000, 15600, 25200 | 29 → 0 ms |

Both retain exactly three detected events. Frozen 90% energy spreads were
`[48.125, 0.0625, 48.125]` ms and `[64.0625, 64, 64.0625]` ms. Successor spreads
are `[0, 0, 0]` ms at both ratios: the 5% and 95% quantiles fall on the same
sample. This describes a discrete impulse, not zero-duration physical sound.
The successor retains the 0.5 sample peak without normalization; frozen output
peaks were approximately 0.478282 and 0.340566. This does not establish arbitrary
recording headroom. Repeated executions are bit-identical on the measured host.
The same isolated fixture at 44.1 and 48 kHz also has zero-sample peak error and
no extra detected events in the successor. All original 20 development checks
pass with their assertions unchanged; the implementation import and explanatory
module docstring are the only changes to the original test file.

Additional checks exercise 19 hop/boundary positions at three rates and both
ratios, nonzero short lengths, channel swapping and signed balance, Gaussian,
noise and damped-tone packets, raw/reset-disabled byte identity, explicit dense
anchor rejection, variable-hop tonal pitch and all 40 original freeze hashes.
The protected windows are shifted with the reconstructed frame, not independently
of it; actual placement drives the normalization denominator. Between attacks,
the tested tonal fixture has nonconstant synthesis hops and still meets 3 cents.

An independent replay of the original test file from `9cef83b` still produces
**18 passed, 2 ordinary failures** against the frozen engine. Its 10 ms screen
has not become an expected failure, skip, or passing claim. The historical
four-platform CI and native test failures remain accessible in their original
runs. Green current CI evaluates the explicitly named successor; it cannot
retroactively turn Experiment 02's frozen transient gate green.

## Verification and reproduction

Local macOS / Python 3.13.5 verification: **142 targeted research DSP checks
passed**; **305 production checks passed, 1 existing expected failure**; full
suite **447 passed, 1 existing expected failure**. Production sources, package
version 3.1.1, MIT license and author Don Michael Feeney Jr. are unchanged.
Hosted Linux/macOS × Python 3.10/3.13 and the native Linux strict build are
required separately; exact run links and results are recorded in PR #33.

The workflow adds a separately named production step using
`--ignore-glob='tests/test_resonance02_*.py'` solely to select production checks.
The following complete suite has no research exclusion and runs even if the
production step fails. The strict native workflow retains its existing exclusion
of pybind11's vendor tests only. No new xfail, skip or continue-on-error is added.

Run the new, small engineering audit in a **new external directory**:

```sh
python -m tools.resonance02.slowdown_successor_audit --output /absolute/external/new-audit
python -m pytest -q tests/test_resonance02_slowdown.py tests/test_resonance02_slowdown_successor.py
python -m pytest -q tests --ignore-glob='tests/test_resonance02_*.py'
python -m pytest -q tests
```

The audit records detector settings, before/after observations at three rates,
phase-lock/reset ablations, source/environment hashes and four external FLOAT
WAV hashes. The small [measurement record](evidence/SLOWDOWN_SUCCESSOR_01.json)
is reviewable in Git; WAVs remain in the external successor evidence package.
The original matrix and its listening exports are not rerun. Original package
verification still passes for 473 Experiment 02 package files, 76 source cells,
40 frozen files, and 405 Experiment 01 package files / 877 logical originals.
The original archive checksum is unchanged. Recovery instructions remain in
[the evidence index](EVIDENCE_INDEX.md).

Next smallest experiment: independently annotate a small set of dense and
overlapping attacks, compare this successor with a proven transient-preserving
stretcher, and measure mapped stereo, pitch, spread and pre-echo before listening.
Do not extend the accepted anchor density or claim recorded-piano acceptance
from the isolated-impulse repair.
