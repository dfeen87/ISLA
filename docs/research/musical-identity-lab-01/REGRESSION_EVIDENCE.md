# Regression Evidence

## Executed evidence

| Check | Result | Limits |
|---|---|---|
| Unchanged v3.1.0 suite | 269 passed, 1 expected failure | Existing offline chunk-continuity XFAIL retained |
| Final suite | 343 passed, 1 expected failure | 74 additive research cases; original thresholds untouched |
| Every sweep amount, both rates/channels, bin 20/40 near-null perturbation | Pass below unchanged .01 relative bound | Finite controls, not all possible spectra |
| Zero-amount path | Bit-exact original mode output including rapid changes | Same installed numerical environment |
| Delayed Bypass | Bit-exact float32 through warm research banks | Fixed delay 1536 samples |
| Cold step, impulse, subnormal, invalid input, silence | Pass | Named half-scale controls peak <=.5; settled zero after full support |
| Warm mode changes | Match independently running banks with original 5 ms fade | Software mixer oracle, no device callbacks |
| Stereo swap, polarity, dual mono, silent-channel controls | Exact invariants pass | Additional common control does not mix channels |
| Whole-file driver vs varied hop groupings and repeated runs | Bit-exact | Persistent 512-hop state; no alternate arbitrary-block DSP API |
| All 504 candidate measurement cells | Finite; no clipping/pitch/gap/stereo-screen failures | Six recorded-piano attack-screen failures remain |
| Wheel build | `isla_audio-3.1.0` builds | Validation only; no publication; research tools excluded from runtime package |
| Preservation check | All previously tracked files unchanged at experiment completion | Additive research paths only |

Initial baseline service tests could not bind four loopback sockets in the
sandbox: 265 passed, 1 XFAIL and four setup errors. The unchanged suite passed
with authorized local loopback access. These are environment restrictions,
not baseline DSP failures. The intermittent simulated-worker CI issue described
in PRs #27–29 did not reproduce in these successful runs and was not retuned,
relaxed or conflated with the musical experiments.

An initial new tail test asserted settled silence at the last sample of a
full-support WOLA flush. That assertion also fails on the original modes, which
legitimately emit their finite tail there. The test now supplies 2048 additional
input-zero samples before asserting exact settled zero. The strict zero and
half-scale requirements are unchanged; the initial log is retained as a test
coordinate error, not mislabeled a candidate DSP defect.

## Timing, delay and retained state

The original worker benchmark body includes input/output rings, finite scans,
RMS meters and all warm DSP banks. Twenty sequential cells cover both rates,
channels, the baseline, each center adapter and all maximum amounts together.
Each records 1500 timed hops after 32 warmups: **30,000 timed hops**, with zero
worker-body budget exceedances. Largest observed worker body: **0.464 ms**;
hop budgets are 11.610 ms at 44.1 kHz and 10.667 ms at 48 kHz. At 48 kHz stereo,
the all-maximum p99 was 0.355 ms, versus baseline 0.212 ms in this sequential run.
These observations do not establish real-time deadlines or a speed improvement.

Retained NumPy arrays including nested research adapters total 182,376 bytes
mono / 254,056 bytes stereo versus baseline 108,576 / 180,256. An additional
20,000-hop cyclic input run confirms finite outputs and unchanged retained
array shapes. Scratch allocation/RSS bounds and arbitrary-duration numerical
behavior are not proven. Experimental frame history adds no transport hop;
the declared delay remains 1536 samples (34.830 ms / 32.000 ms).

No explicit CPU competitor, native callback/GIL timing, route inspection,
PortAudio buffering, device latency, physical disconnect, acoustic test or
sustained hardware acceptance was performed. Local JUCE/CMake builds were not
rerun because no native source/build input changed. Hosted baseline and current
main Linux build and ALIVE checks were separately verified as successful.

## CI snapshot and remaining risks

Baseline commit: [ALIVE](https://github.com/dfeen87/ISLA/actions/runs/40069623988),
[Linux Strict Build](https://github.com/dfeen87/ISLA/actions/runs/40069624010).
Inspected main commit: [ALIVE](https://github.com/dfeen87/ISLA/actions/runs/40074005242),
[Linux Strict Build](https://github.com/dfeen87/ISLA/actions/runs/40074005239).
The latter was initially running and was rechecked successful. These checks
belong to their pinned commits, not this research branch. No hosted research
branch CI run is claimed; workflows trigger on main pushes or PRs to main.

The attack ranking failures remain blocking screens for Legato and higher Melt.
Small waveform residuals do not establish benefit or indistinguishability.
The linked raw measurements and plots preserve conflicting evidence. The
shared nonlinear control can make stereo fold-down differ from processing a
mono fold-down; exact mono compatibility for arbitrary stereo mixes is not
claimed. The additional frame cap could introduce modulation on other material.
Broader source coverage, creator listening and further transient/stereo study
are required before a new engineering proposal.

The listening page script and asset references were checked without playback.
An interactive browser preview of the local HTML was blocked by the browser
tool’s file-URL policy; browser playback/seek behavior remains unverified.
Labeled files are independently usable in a local audio player.

Logs and [worker measurements](evidence/benchmark.json) are retained. Existing
research evidence, offline code, runtime routing and production defaults are
unaltered. No native acceptance is inferred.
