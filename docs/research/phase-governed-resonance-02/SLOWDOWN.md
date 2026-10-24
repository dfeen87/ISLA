# Offline slowdown prototype: frozen development contract

This research adapter implements established phase-vocoder equations. It is not a
new time-stretch algorithm, a validated high-quality piano stretcher, or a LIVE
feature. Original-duration identity evaluations must remain separate.

This file fixes the following development screen **before the implementation is
measured**. Development unit tests are not held-out candidate evaluations. The
parent Experiment 02 protocol must be frozen and hashed before those evaluations.
Failures remain failures; exploratory revisions require a new labelled record.

| Measurement | Fixed screen |
| --- | --- |
| Expansion ratios | 1.25 and 1.50; 1.0 is exact bypass |
| Duration | `abs(len(output) - round(len(input) * ratio)) <= 1` sample |
| Sustained isolated-tone pitch | absolute error <= 3 cents, measured away from boundaries |
| Digital-zero input | maximum absolute output <= 1e-12 |
| Stereo | normalized reliable-bin interchannel phase error <= 0.05 rad on stationary stereo fixtures; exact antiphase must remain antiphase |
| Peaks | report input/output sample peaks and 4x polyphase oversampled peak estimates; never conceal a peak failure with normalization or clipping |
| Repeated impulses | report event count, peak timing, energy spread, and extra strong peaks; any extra strong event or >10 ms event error keeps the transient gate incomplete |
| Determinism | identical finite input/configuration gives bit-identical output on the recorded environment |

Pitch uses a Hann-windowed, eight-times-zero-padded FFT and quadratic interpolation
of the log-magnitude maximum on a middle segment. Reliable-bin stereo error is the
weighted mean absolute wrapped difference between input and output L/R cross-phase,
using bins that are at least 1e-4 of each channel's maximum magnitude, and weights
`sqrt(abs(L) * abs(R))`. Stationary fixtures can use matching-frequency spectra;
recorded material requires time-mapped windows and remains a separate evaluation.
The internal synthesis-coefficient phase error is a construction diagnostic, not
proof that post-overlap-add stereo is perceptually intact. A 4x estimate is not a
certified true-peak measurement.

The impulse screen uses known event times, detects output peaks at least 0.10 s
apart with prominence at least 0.10 of the largest output peak, and compares them
against rounded ratio-scaled event times. Event spread is the duration containing
90% of energy in a +/-50 ms event neighborhood. A small timing error does not prove
absence of smearing. There is no universal perceptual acceptance threshold for
smearing in this development contract; listening and a transient-protecting
external reference are still required.

## Interface and reconstruction

`tools.resonance02.slowdown.stretch(x, sr, ratio, protected=True, *,
identity_phase_locking=True, transient_resets=True)` returns `(y, diagnostics)`.
Input is float-convertible `N x C`, with one or two channels; a one-dimensional
mono input is also accepted and is returned one-dimensional. Sample rate is in Hz.
Finite input and positive sample rate are required. Supported non-bypass ratios
are deliberately restricted to 1.25 and 1.50. Output is float64. Bypass returns a
copy of the input without a Fourier reconstruction. Empty input is supported.

Analysis uses an explicit rFFT with periodic Hann window, `N=2048`, analysis hop
`Ha=512`, and synthesis hop `Hs=round(Ha*ratio)` (640 or 768). Half a window of
zeros precedes the signal; sufficient zeros follow it to complete the final
centered frame. Synthesis uses the same window, weighted overlap-add, and division
by the local accumulated squared window. Since neither synthesis hop is assumed
to satisfy a constant overlap sum, pointwise normalization is necessary. The
denominator is checked on the retained interval and must exceed 1e-12. The first
1024 synthesis samples are removed to align frame centers, then the output is
trimmed to exactly `round(input_samples*ratio)`. Padding and trimming are explicit
boundary conventions; they are not evidence of accurate transient stretching.

There is no amplitude normalization, gain compensation, limiter, clipping, added
spectral floor, or artificial retained tail. Peaks and RMS changes are reported.
Finite FFT reconstruction is checked, and an invalid denominator raises an error.

## Phase policy and controls

Let `phi_c[n,k]` be input phase and `omega_k=2*pi*k/N`. A shared phase-offset
`psi[n,k]` is added to every channel. The instantaneous frequency is estimated from
one reference channel at each bin:

```
delta = wrap(phi_ref[n,k] - phi_ref[n-1,k] - omega_k*Ha)
omega_hat = omega_k + delta/Ha
psi[n,k] = wrap(psi[n-1,k] + omega_hat*(Hs-Ha))
Y_c[n,k] = abs(X_c[n,k]) * exp(1j*(phi_c[n,k] + psi[n,k]))
```

The dominant-magnitude channel is used, retaining the previous reference while its
magnitude is at least 85% of the maximum. On a switch the phase difference uses
the **same newly selected channel in both adjacent analysis frames**, avoiding a
spurious cross-channel phase jump. Bins below `max(1e-12, frame_max*1e-6)` use the
nominal frequency, without interpreting unreliable phase. At initial or silent
frames offsets reset. These operations preserve input interchannel phase in each
synthesis coefficient by construction; they do not prove post-reconstruction
stereo transparency.

`protected=False` is the raw elementary phase-vocoder control: shared stereo
propagation, without phase locking or transient resets. It intentionally shares
the stereo policy so the comparison isolates the protection methods.

`protected=True` enables two established optional techniques:

* **Identity phase locking:** find local maxima in the combined channel magnitude
  above `1e-4` of the frame maximum, partition bins by nearest peak, and use each
  peak's common phase offset throughout its region. This preserves each channel's
  analysis-frame phase differences around a spectral peak. It does not track
  physical partials or separate notes. Peak reassignment can still cause artifacts.
* **Transient phase resets:** reset offsets to analysis phase when positive
  combined-magnitude spectral flux divided by prior magnitude sum is at least
  0.60, frame RMS has increased by at least a factor 1.50, and 50 ms of analysis
  time has elapsed since the last reset. The first nonzero frame also resets.
  This is a heuristic onset guard, not a verified physical strike detector.

The controls are independently disableable. The raw and protected paths use no
harmonic-percussive separation. Their conventional external comparator should be
an established transient-protecting stretcher when available. An elementary
independent-channel library phase vocoder is a useful extra control but cannot
stand in for a stereo-preservation reference.

## Gate status

Implementation and development results are recorded below after running tests.
No creator listening outcome or research PASS is inferred from these unit tests.
Robust offline piano slowdown remains **INCOMPLETE** until transient, stereo,
recorded-piano and listening screens pass against suitable references.

## Development evidence, 2026-10-24

The first unit run produced **18 passed, 2 failed**. Both failures are preserved
as ordinary failing assertions in `tests/test_resonance02_slowdown.py`; they are
not skipped, marked expected failures, or hidden by changed limits. A full test
run that includes this research file is therefore expected to remain red until
the algorithm is revised and satisfies the original screen.

Development environment: Python 3.13.5, NumPy 2.5.4, SciPy 1.18.1. The deterministic
random fixture uses seed 20261024. The root experiment records the complete host
and dependency environment separately.

The 16 kHz, 440 Hz, amplitude-0.2 isolated-tone fixture gave:

| Path | Ratio | Pitch error, cents | Stationary stereo IPD error, rad | Sample peak, in / out | 4x peak estimate, in / out |
| --- | --- | --- | --- | --- | --- |
| Raw | 1.25 | -0.000254 | 3.52e-10 | 0.200000 / 0.284201 | 0.200166 / 0.284382 |
| Raw | 1.50 | +0.000076 | 4.67e-10 | 0.200000 / 0.251309 | 0.200166 / 0.251557 |
| Protected | 1.25 | +0.000000027 | 3.22e-10 | 0.200000 / 0.200926 | 0.200166 / 0.201706 |
| Protected | 1.50 | +0.000000012 | 4.77e-10 | 0.200000 / 0.206444 | 0.200166 / 0.206613 |

The raw path's boundary peaks are substantial despite accurate middle-segment
pitch. No level adjustment was applied. These results do not establish headroom
safety for arbitrary full-scale recordings. All tested zero lengths and boundary
lengths remained zero; both channels of the antiphase fixture remained opposite
within 1e-12. Replay was bit-identical on this environment. Minimum retained
squared-window overlap sum was 1.09527 at 1.25 and 0.95591 at 1.50.

Three impulses at 0.25, 0.65 and 1.05 s exposed the transient blocker:

| Path | Ratio | Detected / expected events | Nearest event error, ms | Local 90% energy spread, ms |
| --- | --- | --- | --- | --- |
| Raw | 1.25 | 3 / 3 | -22.5, -18.5, -22.5 | 26.0, 10.0, 26.0 |
| Raw | 1.50 | **5 / 3** | -19.0, -27.0, -19.0 | 54.0, 30.0, 54.0 |
| Protected | 1.25 | 3 / 3 | **-14.5, -10.5, -14.5** | 48.125, 0.0625, 48.125 |
| Protected | 1.50 | 3 / 3 | **-29.0, -21.0, -29.0** | 64.063, 64.0, 64.063 |

For the raw 1.50 path, detected sample indices were `[5696, 7328, 15168, 24896,
26528]`, against expected `[6000, 15600, 25200]`. Nearest-event errors in this
table do not excuse the two additional peaks. Protected resets occurred at
analysis frames 6, 19 and 31. Input impulse sample/4x peak was 0.500000/0.500318;
protected output sample/4x peaks were 0.478282/0.478587 (1.25) and
0.340566/0.349769 (1.50). Reduced peaks do not prove preserved attacks.

The protected prototype fails the unchanged 10 ms event-timing screen at both
ratios, and its impulse energy is spread substantially. It may be rendered only
as an explicitly incomplete research listening prototype. It must not be called
a completed robust slowdown feature. Next work should compare a proven
transient-protecting implementation and investigate transient relocation or
time-domain/percussive treatment; successful stationary phase tests alone are
insufficient.
