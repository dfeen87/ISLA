# Slowdown supplemental audit

**POST-FREEZE supplementary diagnostic. No gates were retuned.**

Verified 48 rendered WAV hashes, their 5 source files, the frozen source manifest and 40 frozen code/protocol files.

Measured output audio independently of synthesis coefficients. The nominal mapping is input frame center i*512 to output i*640 or i*768. No fitted time alignment was used. Local timing changes and different window mixtures contribute to the reported errors.

## Recorded-piano stereo reanalysis

|Source|Ratio|Path|Mean abs IPD error rad|Channel balance delta dB|
|---|---|---|---|---|
|recorded_piano|1.25|raw|0.289436|+0.195441|
|recorded_piano|1.25|protected|0.122475|-0.049397|
|recorded_piano|1.25|librosa independent|1.392131|-1.024556|
|recorded_piano|1.50|raw|0.280695|+0.396782|
|recorded_piano|1.50|protected|0.134245|-0.030600|
|recorded_piano|1.50|librosa independent|1.196202|+0.952609|
|recorded_piano_reserved|1.25|raw|0.238202|-0.736480|
|recorded_piano_reserved|1.25|protected|0.107528|+0.007023|
|recorded_piano_reserved|1.25|librosa independent|1.240289|+0.087239|
|recorded_piano_reserved|1.50|raw|0.241045|+0.764829|
|recorded_piano_reserved|1.50|protected|0.119009|+0.010065|
|recorded_piano_reserved|1.50|librosa independent|1.283965|-0.617312|

These are post-freeze mapped-frame statistics. They cannot be promoted to a preregistered recorded-stereo acceptance test. The independent-channel librosa control has no transient treatment; it is not a proven transient-protecting comparator. The three synthetic fixtures have identical L/R signals, so their zero interchannel error is a narrow construction check.

## Known impulse fixture

|Ratio|Path|Detected/expected|Max timing error ms|Local 90% energy spreads ms|Extra peaks|
|---|---|---|---|---|---|
|1.25|raw|3/3|7.583|7.667, 9.000, 6.333|0|
|1.25|protected|3/3|4.917|13.333, 11.333, 11.333|0|
|1.25|librosa|3/3|17.083|0.000, 0.000, 42.667|0|
|1.50|raw|3/3|7.500|27.333, 27.000, 23.667|0|
|1.50|protected|3/3|8.500|21.333, 16.000, 18.667|0|
|1.50|librosa|3/3|15.167|0.000, 42.667, 0.000|0|

This separate 48 kHz fixture does not replace the strict 16 kHz development tests. Those retained protected failures were 14.5 ms and 29 ms at ratios 1.25 and 1.50 respectively. Robust slowdown remains INCOMPLETE regardless of source-specific outcomes here.

## Independent isolated-tone check

|Ratio|Path|Pitch vs input cents|Sine-fit residual RMS ratio|Duration error samples|
|---|---|---|---|---|
|1.25|raw|-0.00000004|0.01444274|0|
|1.25|protected|-0.00000000|0.00000415|0|
|1.25|librosa|-0.00000000|0.00517782|0|
|1.50|raw|-0.00000001|0.08514900|0|
|1.50|protected|-0.00000000|0.00000648|0|
|1.50|librosa|-0.00000000|0.00752236|0|

## Harmonic-sustain phase-prediction proxy

|Ratio|Path|Input weighted abs prediction error rad|Output weighted abs prediction error rad|Output weighted cosine|
|---|---|---|---|---|
|1.25|raw|0.010346|0.051731|0.985919|
|1.25|protected|0.010346|0.037132|0.989667|
|1.25|librosa|0.010346|0.036800|0.988693|
|1.50|raw|0.010346|0.086860|0.971040|
|1.50|protected|0.010346|0.022507|0.997374|
|1.50|librosa|0.010346|0.032517|0.994123|

This proxy measures reliable-bin temporal predictability. Input/output hop lengths differ; the scores do not establish a harmonic phase-coherence improvement or perceptual benefit. Synthesized exact harmonics are a narrow test, and no individual piano-string trajectory is identified.

## Measurement definitions and limits

- **status:** POST-FREEZE SUPPLEMENTARY DIAGNOSTIC; no gates retuned
- **frame_reanalysis:** Periodic Hann N=2048; zero-padded centered frames. Input center i*512; output center i*round(512*ratio). Identical frequency bins in Hz.
- **alignment_assumption:** The nominal stretch map is t_out=ratio*t_in. No delay, waveform-correlation or dynamic time alignment is fitted. Reanalysis errors therefore include local timing/remapping differences and fixed-window mixture changes.
- **ipd_reliability:** Exclude DC/Nyquist. All four L/R input/output magnitudes must exceed max(1e-10, own channel/frame maximum*1e-4). Weight is fourth root of product of all four magnitudes. Report common-bin coverage of input reliable bins.
- **ipd_error:** Weighted mean absolute principal angle of (phase_out_L-phase_out_R)-(phase_in_L-phase_in_R), in radians; also weighted RMS. This compares reanalyzed audio, not internal synthesis coefficients.
- **channel_balance:** 20*log10(RMS_L/RMS_R), full file; delta=output-input. Return null if either channel RMS is zero. Frame statistic is arithmetic mean absolute mapped-frame balance delta over frames where each channel RMS exceeds 1e-10.
- **phase_prediction:** For each channel/bin use omega_hat[n-1]=omega+wrap(phi[n-1]-phi[n-2]-omega*H)/H. Error=wrap(phi[n]-phi[n-1]-H*omega_hat[n-1]). Three-frame magnitudes must each exceed max(1e-10, channel/frame maximum*1e-4); exclude DC/Nyquist; weight geometric mean magnitude. Report weighted cos(error) and absolute error. Input uses H=512; output uses H=round(512*ratio). Different hop lengths confound a direct score comparison.
- **phase_prediction_scope:** A causal reliable-bin predictability proxy only. It does not identify partials, validate vertical harmonic coherence, estimate note identity, or establish perceptual quality.
- **impulse_detection:** max(abs(channel)) trace; scipy find_peaks distance=round(0.10*sr), prominence=0.10*maximum trace. Known source nonzero samples must agree with manifest events. Expected output sample=round(source event sample*ratio). Minimum-total-absolute-distance one-to-one assignment; unmatched peaks are extra, unmatched source events missing.
- **impulse_spread:** Within +/-50 ms of each expected event, duration between cumulative squared multichannel-summed energy quantiles 0.05 and 0.95. Also report fraction of output energy outside union of those neighborhoods.
- **impulse_unchanged_screen:** Any extra/missing detected event or matched timing error>10 ms is flagged. This supplemental 48 kHz corpus result never overrides either preserved 16 kHz strict development failure.
- **independent_tone_pitch:** Middle third; Hann-windowed FFT with nfft=8*segment length, log-magnitude quadratic interpolation around strongest positive-frequency bin. Report output/input and output/440 Hz cents.
- **tone_reconstruction_artifact:** Unwindowed least-squares fit of sin/cos at independently estimated frequency plus DC on middle third. Residual RMS / signal RMS, fitted amplitude and DC. This reflects deviations from one sinusoid, not audible quality.
- **peaks:** Read stored FLOAT WAVs as float64; sample peak and scipy resample_poly factor 4 peak estimate. No normalization, clipping or loudness matching; estimate is not certified true peak.
- **decision_scope:** Descriptive post-freeze evidence only. No new threshold is used to promote a candidate. Frozen strict impulse failures and pending creator listening keep robust slowdown incomplete.

Full per-file results, reliable-bin counts/coverage, phase-prediction proxies, channel balances, sample/4x peaks, waveform hashes and event matches are in SUPPLEMENTAL_AUDIT.json. No listening preference, musical improvement or robust-piano acceptance is inferred.
