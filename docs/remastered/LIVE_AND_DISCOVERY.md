# LIVE Remastered, Bluetooth outputs and song discovery

The merged PR #48 preview was ALIVE-only. LIVE still used the original harmonic
profiles. This change adds actual continuous Remastered DSP to LIVE and fixes
related device-discovery and local-song loading issues.

## Listening through Bluetooth or speakers

| Setting | Required choice |
|---|---|
| macOS Sound **Output** | BlackHole 2ch |
| ISLA Step 1 Capture | BlackHole 2ch |
| ISLA Step 1 Listening Device | Paired AirPods/Bluetooth speakers, Mac speakers, or a verified physical stereo output |

Pair Bluetooth devices through macOS first. Their available stereo outputs appear
with **(Bluetooth)** in Step 1. Click **Find Connected Devices** to set up an unambiguous connected output,
or choose an output and **Use These Devices**. Then **Check My Setup** and
**Start LIVE**. Discovery never starts playback or changes macOS routing. The status shows the output actually opened. Pairing and changing macOS
Sound defaults remain in macOS; ISLA never writes those properties. Selecting
BlackHole on macOS's **Input** tab alone does not route system playback to ISLA.

The application now requests the driver's more robust buffering instead of low
latency. A newly selected output suggests its usual supported 44.1/48 kHz rate;
an explicit rate choice stays selected. Terminal `monitor start` also matches
the selected output's supported default rate (48 kHz fallback); specifying
`monitor start 44100` or `monitor start 48000` overrides that suggestion. These
choices do not write the devices' nominal rates or macOS routing. Extra buffering
can add noticeable listening delay, especially with Bluetooth. The callback size,
bounded application rings and capture-loss/recovery guards remain unchanged.

If LIVE stops after repeated capture interruptions, **Check My Setup**,
apply any device/rate changes, then click **Start LIVE** to retry. Failure details
remain in LIVE Telemetry; a failed stream never restarts automatically. See the
[native buffering investigation](../alive/capture-recovery/BUFFERING_2026-10-27.md)
for measurements and limits.

Choose **v4.0 Remastered LIVE** as the processing engine and select Velvet,
Legato or Melt from the sound-effect menu. Start still begins in Original/Bypass.
The LIVE depth slider uses 5% increments; release it or click **Apply LIVE Engine
/ Depth**. Keyboard slider changes need Apply. **0% is original audio, not
mute**; 100% uses the governed baseline depths .16/.30/.30. Listening Volume
remains a separate output attenuation control.

The original LIVE profiles remain available. Engine/mode/depth changes retain
the same stream and timeline. The worker confirms the requested engine/depth and
displays applied control depth, veto counts and measured sample peak.

The terminal uses the same engine and immutable settings:

```text
isla> source system
isla> setup audio
isla> engine remastered 50
isla> monitor start
isla> mode melt
isla> status
```

`engine production` returns to the original profiles. `bypass` selects original
audio within either engine. CLI and GUI share the same session settings.

## LIVE processing telemetry (post-v4.1.0 engineering preview)

The Control Center's **Diagnostics — ALIVE / LIVE** workspace now places a
read-only **LIVE Processing — Engine & Budget** category before the two existing
ALIVE/LIVE telemetry columns. It reports which engine was requested and actually
applied, whether the Remastered FFT/WOLA bank is active, the nominal per-block
time budget (512 frames / sample rate), last and peak worker-side DSP wall times
for Production, Remastered, and the complete LIVE engine, cumulative processed
blocks, nominal-budget exceedances, and how many inactive research banks have
been retired. The original device-overflow, capture-gap, recovery and ring-fault
status stays in LIVE Telemetry and remains necessary to diagnose a shutdown.

**Do not interpret a processing peak as CPU utilization or a confirmed crash
cause.** These are approximate worker wall-clock observations, which may include
thread preemption and scheduling; they are not PortAudio's own capture timings.
The 50 ms interface poll reads scalar statistics, never raw callback buffers.

After **returning to Production**, the existing 5 ms audio fade finishes first,
then the unused Remastered bank is released on the DSP worker. Re-entering
Remastered starts with fresh history and the original 1536-sample warmup.
While Remastered is selected, Production DSP remains active to preserve
continuous history for an immediate, click-safe return. The improvement reduces
idle cost **after** Remastered is deselected, not dual-engine cost **during**
Remastered listening. It does not by itself establish a native-audio fix.

When comparing listening sessions, retain the complete Processing and LIVE
Transport telemetry before restarting. Use identical physical device, sample
rate, source, processing mode and listening gain; compare Production-only,
Remastered, and the return to Production. Native BlackHole/Bluetooth reliability
must be assessed on the creator's Mac, separately from hosted/synthetic tests.

## Device refresh fixes

- macOS PortAudio can retain a cached device list. Initial discovery, manual
  refresh, Start preflight, and the deferred refresh after Stop rebuild that cache
  while the owned ALIVE/LIVE streams are idle. Native inventory changes also
  trigger a safe idle refresh. The sounddevice 0.5.x private initialization hooks
  are isolated in `device_refresh.py`; unsupported lifecycle states fail visibly.
- Stop releases audio first. Discovery occurs on the next command-worker poll;
  a slow device driver cannot delay the Stop operation. No background PortAudio
  rescan occurs while either stream is active. A safety stop schedules refresh
  after the stream has actually closed as well.
- Missing BlackHole no longer empties the physical-output list. Failed/partial
  first discovery can recover on a later refresh.
- Bluetooth may expose identically named microphone and playback entries. Each
  direction is resolved independently in CoreAudio and PortAudio. Genuine
  same-direction ambiguity, virtual/aggregate outputs, missing devices, and mono
  playback profiles remain rejected.
- A PortAudio index change can rebind to the **same native ID and name** after
  refresh. A same-named replacement with a different native ID cannot silently
  inherit the selection. The existing actual-opened-stream identity and routing
  checks remain authoritative. The former test expecting *every* index change
  to fail is replaced by positive same-native-ID reindex coverage plus negative
  same-name/different-ID coverage; no native identity guard is removed.

## LIVE mathematics and timing

`remastered_streaming.py` is a bounded-state adaptation of the unchanged frozen
`tools/resonance02/core.py`. It does not repeatedly render isolated chunks. It
retains the preceding observations, resonance history, magnitude history,
frequency tracking, phase offsets, control, and WOLA tails across hops.

Frame/hop remain 2048/512 samples. Analysis uses the same six regime weights,
tonality/coherence confidence and attack/silence/low-confidence vetoes. Each bank
receives a frozen configuration with only its own mode depth scaled by I/100.
Targets and recovery allowance scale together, with the unchanged 100 ms
recovery time. Velvet curvature, Legato's 80 ms history, Melt's 60 ms frequency
tracking/80 ms phase-offset decay, [.80,1.188502227] gain bounds and +/-.10 radian
phase ceiling are retained.

The newest hop completes a frame; reconstruction emits the oldest hop. Signal
delay is **1536 samples**: 32 ms at 48 kHz, 34.83 ms at 44.1 kHz, plus existing
transport/device buffering. This matches the original LIVE processor's delay;
callback queue-age and recovery rules are unchanged. These operational frame
labels do not identify physical notes or establish hammer timing.

The optional research engine is created and processed by the existing LIVE DSP
worker, outside PortAudio callbacks and Qt's event thread. Production remains
audible during three hops of new-engine history warmup. The aligned, ready
engine output then uses a 5 ms crossfade. Both engines stay warm after opt-in.
Capture-loss recovery builds fresh engine/history state through the unchanged
LiveMonitor factory. It does not reconstruct lost audio or replay old tails.

For a constant setting and fresh state, continuous streaming followed by three
zero flush hops is compared against the frozen offline renderer after removing
1536 samples of delay. Acceptance is <=1e-7 absolute error in normalized
float32 playback samples and <=1e-14 in control; feature/state comparisons use
2e-12. Actual measured bit equality is recorded separately. Fixed-setting
reproducibility does not mean changing a slider mid-song recreates an offline
render that used the new setting from the beginning.

A lowered user authority cap immediately clamps existing control to that cap;
this intentional external limit reduction is separate from the frozen ordinary
slew rule. WOLA and the output transition retain their histories. Settled 0% and
Bypass return an exact delayed float32 source copy, including signed zero;
transition samples briefly combine old/new outputs.

Finite, correctly shaped processed blocks enter the existing bounded output
ring. Selected Remastered processing exceeding sample full scale stops LIVE
with a request to lower the source application's volume. No limiter, clipping
or normalization is applied. This is a LIVE sample-peak guard, distinct from the
offline preview's .98 sample/4x admission screen; no certified true-peak claim
or arbitrary reconstructed-peak guarantee follows from spectral gain ceilings.

Unlike full-file ALIVE research preparation, continuous LIVE processing has no
30-second excerpt limit. Its retained arrays are fixed in size. Python worker
timings are measured on the test host, not a hard real-time/native Bluetooth
performance guarantee.

## Finding a local song

```text
isla> load "Dancing Queen.ACC"
```

An existing relative file or explicit full path retains its usual meaning. If a
**bare filename** is missing, ISLA starts a cancellable child-process search.
On macOS it queries Spotlight across the indexed computer with `mdfind -0 -name`
(without `-onlyin`), then checks accessible Music, Downloads, Desktop, Documents
and current folders. Fallback traversal has time/entry limits and does not follow
directory symlinks. It cannot promise discovery of unindexed or inaccessible
files, external volumes absent from Spotlight, or a song not downloaded locally.

Exact names take priority. `.ACC` can resolve a likely `.AAC` typo; title matches
can find Music-library names such as `03 Dancing Queen.m4a`. Case is ignored.
Multiple best matches or an incomplete scan produce a list for explicit full-path
selection. ISLA never silently picks the first ambiguous recording. Status shows
the resolved source path. Full-path errors do not trigger a substitute-song
search. Close/reload cancels both searching and subsequent preparation.

The existing native Apple importer from commit
`e768cad` is integrated so discovered DRM-free AAC/M4A files feed its macOS
`afconvert` adapter, followed by the original preparation/DSP pipeline. The
adapter preserves channel count and sample rate. Its protected-download and
unsupported-platform behavior remains intact. WAV/FLAC/AIFF/MP3 continue through
libsndfile when supported.

## Verification and scientific scope

```bash
python -m pip install -e '.[gui]' -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest -q tests
python -m tools.remastered_live_verify --output remastered-live-verification.json
```

`LIVE_MATRIX.json` records all 60 mode/intensity/mono/stereo/sample-rate cells,
requested/applied control, vetoes, coefficient bounds, RMS/peaks, residuals,
reference-equivalence errors, fixed retained array sizes and worker timings.
Tests also cover exact/deterministic output, stereo relationships, gaps,
same-stream transitions, real worker thread ownership, capture recovery,
Bluetooth discovery, Start/Stop refresh, stale identities, searching, ambiguity,
limits, native decoder routing and cancellation. Qt and transport tests do not
establish physical audio output.

Frozen research sources/results, production DSP kernels and PortAudio callbacks
are preserved. The Experiment 02 **REVISE / INCONCLUSIVE** verdict remains.
Native Mac/Bluetooth listening and creator acceptance are pending; engineering
equivalence does not establish perceptual superiority. No merge, tag or release
is performed by this change.
