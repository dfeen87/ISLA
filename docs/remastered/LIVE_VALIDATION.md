# LIVE Remastered and discovery verification — October 24, 2026

Base main: `339fa59bbf1c9bb7e95ce972b48fa6e835917cc9`, including the existing
native Apple-audio preparation from PR #50. This change adds continuous LIVE
Remastered, device refresh/Bluetooth discovery, and missing-filename search.
It does not modify frozen Experiment 02 evidence or publish a release.

## Recorded results

| Check | Result |
|---|---|
| Complete Python suite with Qt installed | **791 passed, 8 skipped, 1 existing xfailed** |
| Independent production-only acceptance | **438 passed, 8 skipped, 1 existing xfailed** |
| Qt follow-up after CI ordering correction | **29 passed** |
| Streaming matrix | **60/60 passed**, all bit-identical to the frozen float32 reference on this host |
| Matrix formats | 3 modes × 0/25/50/75/100% × mono/stereo × 44.1/48 kHz |
| Maximum sample error to float32 reference | **0.0** on the recorded matrix |
| Retained research NumPy arrays | **288,169 bytes** before/after 1024 benchmark hops, both rates |
| Frozen research / legacy DSP, callback and metadata preservation | **46/46 byte-identical** to the inspected main base |
| Wheel build | PASS; new engine, discovery adapters, verifier and frozen core included |
| Offscreen GUI visual inspection | PASS; engine, depth, actual-device status and routing controls readable |
| Patch whitespace | `git diff --check` passed |

The eight skips are native macOS codec cases on this Linux host. They remain
enabled on macOS CI. No test was newly marked xfail. One existing Starlette/httpx
deprecation warning remains.

The first PR head (`80ecc12`) passed all four ALIVE platform jobs and three Qt
platform jobs. The macOS/Python 3.13 combined Qt run exposed an outdated
post-Stop scheduling assertion: a correctly deferred refresh sometimes finished
before the test thread inspected its rescan list. That run is retained in
[GitHub Actions](https://github.com/dfeen87/ISLA/actions/runs/40124366377/job/120962512841).
The follow-up test records Stop's return and requires the stream to be closed
before a rescan may start, then requires the new post-Stop refresh to complete.
The corrected Qt suites passed 29 tests locally; no DSP or device implementation
was changed for this follow-up. Current-head CI results are tracked on PR #51.
The follow-up log is [pytest-live-qt-followup.log](pytest-live-qt-followup.log).

The complete run is in [pytest-live-complete.log](pytest-live-complete.log).
[LIVE_MATRIX.json](LIVE_MATRIX.json) contains per-cell requested and applied
depth, veto counts, control-reference error, coefficient ceilings, RMS/peaks,
waveform residuals and equivalence results. [LIVE_PRESERVATION.json](LIVE_PRESERVATION.json)
contains the source preservation hashes. These are new engineering evidence,
not replacements for historical scientific results.

## Worker benchmark

Measured on Linux x86_64 / Python 3.12 with production and research engines warm,
stereo Melt at 100%, 32 warmup hops and 1024 measured hops:

| Sample rate | Hop budget | Mean | P99 | Maximum | Hops over budget |
|---|---:|---:|---:|---:|---:|
| 44.1 kHz | 11.610 ms | 1.168 ms | 2.252 ms | 4.148 ms | 0 |
| 48 kHz | 10.667 ms | 1.161 ms | 1.698 ms | 3.302 ms | 0 |

These are host measurements, not native Bluetooth latency or a hard real-time
guarantee. Array-size checks concern retained research state, not total process
RSS. LIVE's 1536-sample signal delay and existing bounded rings remain unchanged.

## Behavioral coverage

- Continuous analysis features, six state weights and control sequences are
  compared with frozen offline authority, including attack/confidence/silence
  vetoes, ordinary slew, gain/phase ceilings, stereo relationships and silence.
- Real LIVE worker tests identify the thread running research DSP, exercise
  same-stream engine/depth changes, restart, and both-rate capture-loss recovery
  against a freshly initialized reference engine. No FFT enters a callback.
- CLI and GUI use shared immutable processing requests. Original LIVE profiles
  remain available and match their existing processor when selected.
- Device tests cover first discovery, partial discovery without BlackHole,
  same-native-ID reindexing, rejection of a same-named replacement, actual-open
  status, no PortAudio reset while running, and automatic post-Stop refresh.
- Bluetooth tests include separate identically named input/output endpoints and
  verify direction-specific resolution in both terminal and graphical pickers.
- Song discovery tests cover computer-wide Spotlight invocation, indexed-search
  failure, bounded fallback, track-number names, case, ACC/AAC aliasing, exact-name
  priority, ambiguous/incomplete results, explicit-path errors, real child-process
  preparation and cancellation. Existing Apple decoder tests remain intact.

An old test treated every PortAudio index change as a failure. Its reindex case
is replaced by explicit acceptance of a refreshed **same native ID/name** and
retained rejection of changed/ambiguous native identities. No opened-stream
identity, routing, stereo-channel, recovery or queue guard is relaxed.

## Native review still required

Pair AirPods/Bluetooth speakers, confirm they appear in Step 2, apply them, set
macOS Sound **Output** to BlackHole and start LIVE. Select Remastered and each
effect; compare 0/25/50/75/100% at safe listening levels. Check diagnostics,
transitions, Stop/reconnect/refresh, actual opened output and return to Original.
Load a known local purchased AAC/M4A by bare filename, verify the resolved path,
and test duplicate-name selection. Retain errors, dropouts and listening
judgments. These physical Mac/Bluetooth and creator-listening checks remain
pending. The research **REVISE / INCONCLUSIVE** verdict remains unchanged.
