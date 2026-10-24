# ISLA v3.0.0 — ALIVE + LIVE: implementation and acceptance

ALIVE is a release target. Package, service, and CMake versions remain 2.1.0;
no release tag is created by this change.

## Authoritative baseline

- PR #12 is merged at `88ab60d087a130fe1ad6dea3fd08b05684e0f35a`.
- PR #13 is merged at `e7b984b0bc3471b3b7d07d936f686758029d919f`.
- ALIVE branches from that current `main`, independently of the identity PR.
- `isla` forwards to the original `phased_music_notes` DSP source. The public and
  legacy aliases, HTTP/gRPC wire interfaces, JUCE/CMake configuration, and strict
  BEDROCK tests are retained. No DSP algorithm source is changed.

## Implementation

`drivers.cli:main` opens ALIVE with no arguments; the existing `--input`,
`--output`, and `--mode` file-processing route remains available. Partial offline
arguments report a usage error instead of accidentally opening the shell.

`isla.terminal` handles commands with case-insensitive verbs and modes, quoted
paths, tilde expansion, status, and cleanup for exit/EOF/Ctrl-C at the prompt.

`isla.preparation` decodes the recording and calls the existing
`drivers.api.IslaBuffer.process_buffer` once for each mode. A spawned process
keeps DSP off the command and audio threads, reports progress through a pipe,
and writes four float32 NumPy buffers to an owned temporary directory. Read-only
memory maps expose the ready buffers to playback without copying them through
the pipe. Invalid shapes/non-finite output are rejected. Replacement or exit
terminates/joins the preparation process and removes its temporary files.
The original is the float32-decoded recording, without DSP or normalization.

`isla.playback` owns one sounddevice/PortAudio OutputStream. On macOS it uses
Core Audio's default output, with the file's sample rate and channel count.
The 512-frame callback only copies prepared samples and performs a bounded 5 ms
crossfade for mode changes with preallocated weights and scratch space. It does
no file I/O, FFTs, note analysis, or smoothing. Mode selection is a published
buffer reference; changes take effect at a callback block boundary. The cursor
continues across selections. Completion drains the final block before reporting
completed. Commands close the stream before resetting/repositioning the cursor.
Pause estimates the audible sample position from the DAC clock, excluding queued
samples as far as the backend timing permits. Stream cleanup is done on the
command thread. Unexpected stream inactivity and output status flags are shown
in `status`. Completed streams are reaped on the next command or exit.

## Verification

Verified on native Apple Silicon macOS with Python 3.14.6:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[playback]'
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Local result: **103 passed, 1 expected failure**. The expected failure is the existing
BEDROCK non-zero-strength chunk-streaming limitation. The unmodified service test
stack reports one FastAPI/Starlette deprecation warning. A second fresh virtual
environment with only `python -m pip install -e '.[playback]'` was also checked through both installed terminal entry points.

The editable install resolves the package's core dependencies and the playback
extra. Test/service dependencies stay in `requirements.txt`. The new ALIVE CI
matrix exercises Python 3.10/3.13 on macOS and Linux, independently of the
existing Linux JUCE build workflow. CI uses a deterministic output stand-in;
it does not assert that a hosted runner has audio hardware.

Automated acceptance covers shell launch and argument routing, a real WAV
roundtrip, missing/invalid/empty/multichannel/non-finite recordings, all prepared
modes matching the existing DSP, mono/stereo shape and rate preservation, exact
original-buffer selection, callback completion/replay, DAC-clock pause/resume,
stop/reset, crossfades, repeated commands and stream closure, output failure,
EOF/Ctrl-C cleanup, preparation cancellation, and preserved BEDROCK/identity/service
regressions. See `tests/test_alive.py`.

Native Core Audio acceptance used the Mac's selected **AirPods Pro #2 - Find My**
output. Actual OutputStreams played a quiet generated mono recording (0.30 s)
and stereo recording (5.00 s) at 44.1 kHz. The stereo run switched through
Velvet, Legato, Melt, and bypass during playback; checked continued position,
pause/resume, stop/reset/restart, full completion, and cleanup. No output status
warnings were reported. These are hardware transport/state checks, not a claim
that perceived musical quality has been accepted. Owner listening on real
recordings remains necessary before release.

## Owner macOS acceptance — required before release

1. Follow **After Cloning — Start ISLA on macOS** in README. For this PR before
   merge, check out its branch after cloning: `git checkout feature/isla-alive-terminal`.
   Select speakers/headphones in System Settings → Sound → Output at a comfortable
   volume. Launch `isla` and verify that the listed output is the intended device.
2. Run `load "~/Music/my piano.wav"` with a real mono or stereo WAV path containing
   note transitions. `status` should remain responsive throughout preparation.
   Repeat `status` until `Preparation: Ready`; confirm the file and duration.
3. Run `play`; confirm you hear the original recording. While playing, run
   `mode velvet`, `mode legato`, `mode melt`, then `bypass`. Listen for each mode
   on note transitions and confirm playback progresses without restarting.
   `status` must show the selected mode, original duration, and correct output.
4. Run `pause`, then `status`. Wait a few seconds and repeat `status`; position
   should remain fixed. Run `play` and confirm it resumes near the paused point.
5. Run `stop` and `status`; position must be 0.00. Run `play`; it starts at the
   beginning. Let it finish, then `status` must report `completed`. Run `play`
   again to verify replay from the beginning.
6. Repeat for a mono WAV and a stereo WAV, preferably at both 44.1 and 48 kHz.
   Use a stereo recording with distinct left/right content to check channel order.
   Compare original and bypass levels without changing the system volume.
7. Try `load /missing.wav`, a non-audio file, `mode invalid`, and an unknown
   command. The shell must report useful errors and remain usable. Paste a path
   containing spaces, use mixed-case commands, and run `help`.
8. Switch output while stopped and play again. Disconnect the device during
   playback; confirm status/error feedback and recovery after reconnecting. Device
   hot-plug recovery is manual in this MVP.
9. Repeat play/pause/stop/mode/bypass several times. Run `exit` while playing and
   confirm audio stops and the shell returns normally. Relaunch; test Ctrl-D and
   Ctrl-C at the prompt. Load a long file and immediately `exit` to check prompt
   preparation cancellation. No ALIVE child process should remain.
10. Retain CI results for the exact reviewed commit and record the listening
    outcome, device, macOS version, Python version, and recording properties.
    Do not tag/publish v3.0.0 until these checks are accepted.

## Known limits

- WAV mono/stereo is guaranteed; other libsndfile formats are opportunistic.
- Full-file preparation requires time, temporary disk space (four float32
  buffers), and DSP working memory. No streaming of arbitrarily large files.
- Progress/results appear when issuing commands (use `status`); the shell does
  not print unsolicited notifications while waiting for input.
- Stop during preparation resets playback; exit or a new load cancels preparation.
- Python callbacks are not hard real-time. Short transitions reduce clicks, but
  rapid switching, start/stop, device latency, and CPU pressure need listening tests.
  Sample-perfect gapless switching and pause positioning are not guaranteed.
- Source samples and DSP results are not loudness-normalized. Output conversion
  and hardware can clip values outside their representable range.
- File output defaults at stream open unless explicitly selected with `output`.
  There is no automatic device reconnect, system volume control, DAW, GUI or
  shell export command. LIVE system capture is described separately below;
  offline CLI export remains unchanged.
- The existing BEDROCK non-zero-strength chunk-streaming expected failure and
  JUCE Python callback risks remain documented in
  [RESIDUAL_RISKS](../bedrock/1.0/RESIDUAL_RISKS.md). ALIVE prepares whole files
  instead of executing those algorithms in its audio callback.

## LIVE follow-up baseline and capture decision

LIVE starts at verified `main` commit `bce8e690828eccb478bb28b86c47fa780b64b96b`,
merged PR #14; PRs #12 and #13 are retained. It is a new feature branch/PR,
not a modification of the merged ALIVE PR. Versions remain 2.1.0.

Two options were investigated:

- **BlackHole 2ch (selected):** existing sounddevice/PortAudio/Core Audio backend,
  separately installed virtual driver, explicit physical output. The vendor
  documents Intel/Apple Silicon, 44.1/48 kHz and newer rates, microphone/input
  permission, and manual routing. ISLA neither bundles nor installs the driver.
  See [vendor documentation](https://github.com/ExistentialAudio/BlackHole).
- **ScreenCaptureKit (not implemented):** Apple exposes `capturesAudio` and
  `excludesCurrentProcessAudio` from macOS 13.0; this was verified in the installed
  SDK's `SCStream.h`, as well as the [capture API](https://developer.apple.com/documentation/screencapturekit/scstreamconfiguration/capturesaudio)
  and [self-exclusion API](https://developer.apple.com/documentation/screencapturekit/scstreamconfiguration/excludescurrentprocessaudio).
  A native helper/bridge, permission lifecycle and output exclusion tests would be
  new integration work. It could offer cleaner driver-free onboarding later,
  but was not chosen for this Python MVP. No ScreenCaptureKit compatibility or
  latency acceptance is claimed.

Target configuration is macOS 13+, Python 3.10+, standalone BlackHole 2ch plus
stereo physical output. Native verification uses the owner's configuration
recorded below, not every supported OS/hardware combination.

## LIVE single-path routing and lifecycle

The only intended listening path is browser/system default → BlackHole 2ch →
ISLA → selected physical speakers/headphones. `SystemCaptureBackend` requires
explicit output selection, standalone BlackHole input, a supported 44.1/48 kHz
float32 stereo stream and separate devices. `CoreAudioRouting` uses **read-only**
Core Audio queries to verify default output, native identities, liveness, channel
direction and transport type. Unknown, virtual, Aggregate and Multi-Output sinks
are rejected, including aggregates renamed to look like speakers. Split Bluetooth
input/output objects sharing one name are disambiguated by stream direction;
genuinely ambiguous names are rejected. Default output must be standalone
BlackHole, never a Multi-Output that sends a second unprocessed path to speakers.

The worker rechecks the route/device identities and stream/callback activity
every 250 ms. Disconnection or routing change stops the owned stream, including
while the prompt is waiting for input. This is periodic validation, not an
instantaneous hardware interlock. ISLA cannot discover every browser per-app
output override or another application's monitor: the user must disable those.

The application never changes the system output. The README tells the user how
to select BlackHole, preserve their normal output choice, and manually select
that physical output again after stop/exit/failure. No guaranteed crash recovery
is claimed. The one-time engineering test temporarily changed routing only with
explicit owner consent and restored it; that test harness is not product behavior.
No capture is recorded, saved or transmitted by LIVE.

`source system` stops file playback; `source file` stops LIVE and retains prepared
file buffers. `output` works with both sources. Device changes require stopped
audio. A disconnected/stale PortAudio inventory may require exiting and
relaunching the shell; ISLA does not silently fall back to a different device.

## Pass A — transport and Bypass

Pass A's first validation was **11 deterministic tests passed**, before connecting
nonzero DSP to the terminal. These used mock devices and a transparent worker:
exact float32 Bypass copies (zero sample error after the transport delay), capture
discovery, missing/invalid devices/rates/channels, feedback/duplicate-path guards,
bounded rings, repeated starts/stops, initialization failure cleanup, and device
or route loss without a terminal poll. Mock results are not Mac hardware acceptance.

Native transport acceptance and owner observations are recorded separately below.

## Pass B — retained DSP state and continuity

`isla.streaming.StreamingDSP` is a separate continuous path. It never calls the
offline whole-buffer processor on arbitrary chunks. A 2048-sample periodic Hann
analysis window advances by 512 samples; 1536 samples of history, weighted
synthesis overlap tails, normalization weights and a matching dry delay survive
every hop. All three spectral banks remain warm in Bypass and other modes.
This directly avoids BEDROCK's per-chunk padding/tail-reset limitation.

The existing `HarmonicBlender` spectral smoothing kernel is reused with strengths
0.35/0.55/0.75 for LIVE Velvet/Legato/Melt. These are explicit **LIVE harmonic
profiles**, not substitutes for the offline note detector/phase-boundary
interpolator. No offline DSP source or public/legacy interface is changed.
All three profiles produce measured nonzero transformations. There is no claim
that their musical character reproduces full-file ALIVE output.

Bypass uses captured float32 samples through a 1536-frame delay: finite input is
bit-exact after alignment, with no gain, normalization or clipping. Selecting a
mode publishes a reference consumed at the worker's next hop; the worker mixes
warm, time-aligned banks using a 5 ms linear crossfade. Non-finite input blocks
are muted and counted before they can contaminate retained state; invalid DSP
output stops the session. Mono and stereo stay separate with no channel mixing.
The BlackHole capture adapter itself is two-channel and rejects mono output.

### Callback, buffers and shutdown

One duplex PortAudio stream connects input/output and owns the callback clock;
Core Audio/PortAudio handles its device synchronization. There are no separate
Python capture/playback clocks. Device clock behavior on arbitrary long sessions
still needs hardware acceptance.

The callback fills output with silence, copies capture into a preallocated input
ring and copies processed output from another preallocated ring. Each ring has
**8 × 512 frames**, a fixed allocation (32 KiB for stereo), timestamp slots and a
nonblocking lock attempt; it never waits for a worker lock. Python/GIL and these
locks still preclude hard-real-time guarantees. No FFT, note analysis, file I/O
or DSP runs in the callback. The worker performs FFTs and updates signal/timing
metrics. Worker polling sleeps at most 1 ms when idle.

Eight initial callbacks are muted/discarded (85.33 ms at 48 kHz; 92.88 ms at
44.1 kHz) before any DSP state is fed. Native testing exposed initial capture
overflows while duplex devices synchronize; discarding this bounded startup
interval addresses those without ignoring errors in active audio. Startup device
flags remain counted. Subsequent capture overflow/underflow stops the session.
Output-ring starvation emits silence and increments a counter; eight consecutive
empty callbacks stop. Input/output ring overflow or lock contention stops rather
than accumulating latency indefinitely. These failures can be audible; this is
an MVP, not a concealment/recovery algorithm.

The worker releases the stream in `finally`; stop signals it and joins with a
3-second bound, refusing another start if it is still alive. Partial stream-open
or start failures abort/close owned resources. Stop/exit discard pending audio.
A hung third-party audio driver cannot be guaranteed to obey bounded shutdown;
that error is surfaced rather than claiming release succeeded.

### Automated verification and timing

`tests/test_live.py` covers Pass A and Pass B, including a separate whole-signal,
batched WOLA reference at 44.1/48 kHz, mono/stereo, all nonzero profiles, every
512-frame seam and abrupt attacks. Agreement is checked at absolute tolerance
1e-7 / relative tolerance 1e-6. Suitable harmonic-rich signals require at least
1% RMS difference from aligned Bypass. Warm-bank mode switching matches an
independent crossfade reference, including rapid changes back to Bypass.

Other checks cover exact delayed Bypass, silence/non-finite input, fixed state
size over 1000 blocks, ring bounds/contention, underflow silence, overflow stop,
startup synchronization events versus active capture errors, real worker-thread
transformations and deterministic ADC/DAC latency, failed/repeated lifecycle,
disconnection, settings rejection, terminal source/mode/output commands and exit.
The unchanged ALIVE and BEDROCK/service/import suites remain regression gates.

Reproduce synthetic timing with `python tools/live_benchmark.py` after installation.
[Raw worker-only results](LIVE_BENCHMARK.json) on native Apple Silicon macOS
26.7.2 / Python 3.14.6 / NumPy 2.5.4 use 600 hops/configuration, discarding 20 warmup
measurements. Stereo processing p99 was approximately **0.25 ms** against
10.67/11.61 ms hop budgets; maximum about **0.26 ms** in that isolated run.
Retained DSP arrays are 180,256 bytes stereo / 108,576 mono, plus 65,536 bytes for
the two stereo rings and bounded per-hop scratch. This is not process RSS, a CPU
stress guarantee, or capture-to-speaker latency.

Algorithmic delay is **32.00 ms at 48 kHz / 34.83 ms at 44.1 kHz**, plus transport
queues and device latency. `status` associates each output block with its delayed
source ADC timestamp and estimates `outputBufferDacTime - sourceTime`. It is a
single-stream clock estimate; it excludes browser decoding and may omit hardware
processing. No acoustic/reference-loopback latency measurement is claimed.

## Native LIVE owner acceptance procedure

1. Follow the root README LIVE installation/routing instructions; record macOS,
   Python, driver version, capture/output names, sample rate and commit. Do not
   use Multi-Output or another software monitor. Set comfortable physical volume
   before changing the system default to BlackHole.
2. Launch `isla`; run `devices`, `source system`, `input "BlackHole 2ch"`,
   `output "<your physical device>"`, `bypass`, `monitor start`.
3. Open the Beethoven YouTube performance linked in README and click Play.
   Confirm Bypass is audible through the intended output with no doubled direct
   sound. `status` must show Running and nonzero RMS when music plays.
   **Do not advance Pass B if Pass A fails.** Stop and diagnose routing first.
4. Select Velvet, Legato and Melt for at least 15 seconds each; return to Bypass.
   Listen at note attacks and decays. Confirm responsiveness/continued performance,
   note differences, glitches, noise, level changes and echo/feedback. Record all
   failures and underflow/overflow/device counters, not just a successful prompt.
5. Compare the actual worker's processed samples to a parallel delayed dry
   reference where practical; retain scalar energy/error measurements only unless
   the owner explicitly wants audio saved. Bypass error must be zero; profiles
   must differ on nontrivial input. Owner listening determines musical acceptability.
6. Repeat at 44.1 kHz using `monitor stop`, matching Audio MIDI formats, then
   `monitor start 44100`. Check distinct left/right material and quieter passages.
   Run at least 30 minutes under realistic Mac/browser load before release.
7. Stop/restart repeatedly. Disconnect/reconnect the physical device; verify safe
   stop and manual recovery (relaunch for stale PortAudio inventory). Change the
   system default away from BlackHole and confirm safe stop. Do not test feedback
   by intentionally routing ISLA into its own capture.
8. Run `monitor stop`, pause YouTube and `exit`; confirm no ISLA worker/stream.
   Restore the original physical output in macOS Sound and play YouTube normally.
   Test EOF/Ctrl-C cleanup and the existing local-file ALIVE checklist too.
9. Record final-head GitHub Actions and review results, and explicitly accept or
   defer musical quality, glitches, latency and long-session reliability. No merge,
   version bump, tag, release or application publishing is automatic.

## Native results — owner Mac, October 23, 2026 (America/New_York)

Host: Apple Silicon **macOS 26.7.2**, Python **3.14.6**, sounddevice **0.5.6**,
BlackHole 2ch **0.7.1**, installed separately by the owner. The owner explicitly
authorized a Core Audio restart (administrator prompt), temporary BlackHole
routing, and restoration. The final intended physical output was the plugged-in
sound system, named **External Headphones** by Core Audio. It is a built-in wired
output, not AirPods. Initial built-in-speaker playback was audible to the owner,
but was the wrong listening device; selecting the wired output fixed that.

| Native run | Transport rate | Result / timing | Counters at stop |
|---|---|---|---|
| [48 kHz evidence](NATIVE_48000.json) | Stereo 48000 | Bypass + all three profiles + return to Bypass; timestamp estimate 79.2–100.5 ms | 3 output-ring underflows, 0 ring overflows, 2 early device status events; no final error |
| [44.1 kHz evidence](NATIVE_44100.json) | Stereo 44100, hardware defaults listed 48000 | Same sequence; timestamp estimate 83.9 ms; Core Audio negotiated the requested stream rate | 1 initial output-ring underflow, 0 ring overflows, 0 device status events; no final error |

These are actual native Core Audio streams capturing browser/system audio and
delivering output to the selected physical device. They are not mock results.
The terminal remained responsive. Both sessions stopped/exited, their test
processes completed, and routing restoration succeeded. The final read-only
Core Audio check confirmed normal default output **External Headphones**.
Normal browser playback continued after restoration.

The native probe kept a bounded parallel dry-delay reference in memory, skipped
ten blocks after each mode change, and accumulated scalar energy/errors only.
It did not save captured audio. Measured relative RMS change from the aligned
captured original was:

| Profile | 48 kHz | 44.1 kHz |
|---|---:|---:|
| Bypass | 0% (peak error 0) | 0% (peak error 0) |
| Velvet | 4.90% | 5.20% |
| Legato | 7.92% | 7.93% |
| Melt | 10.95% | 11.53% |

These values substantiate real transformations on captured source material;
they do not score musical quality or compare identical passages across modes.
The first run started with [Beethoven solo piano](https://www.youtube.com/watch?v=UHd8jwXBzXE);
YouTube later advanced to Mozart Requiem during that prolonged run. The 44.1 kHz
repeat was started again from Beethoven with autoplay disabled. No continuous
browser-source audit was retained, so the exact recording during every measured
mode interval is not asserted. The underlying system-audio stream was continuous.
Worker time peaked at 6.25 ms (48 kHz) / 3.94 ms (44.1 kHz) with native diagnostics
active. There was no acoustic output capture or independently measured physical
capture-to-speaker latency. The estimated range is roughly **79–101 ms**.

The owner confirmed sound-system playback: **“yes its working now.”** After mode
switching, the owner selected **“Audio works, but differences are subtle or quality
needs work.”** This is functional capture/playback evidence, **not musical-quality
acceptance**. No separate rate-specific owner verdict, detailed no-echo/glitch
verdict, 30-minute stress run, or physical hot-unplug test is claimed.

[Initial unsuccessful attempts](NATIVE_INITIAL_ATTEMPTS.json) are retained too:
initial low speaker level/no audibility, incorrect physical output selection,
a stale audio-unit/PortAudio failure when changing output in the same process,
and capture overflow at duplex startup. Relaunching refreshed devices. The final
startup-settling fix was tested natively and has deterministic coverage; it does
not suppress capture errors after the startup interval.

To reproduce scalar comparison on a user-configured safe route, while browser
audio plays: `python tools/live_native_probe.py --output "External Headphones" --rate 44100`. It automatically exercises Bypass/Velvet/Legato/Melt/Bypass for
10 seconds each, prints measurements, stops/releases audio, and reminds the user
to restore normal Mac routing. It never changes the system default or saves audio.

## Final acceptance state and remaining gates

- [x] New branch starts from merged PR #14 / verified main baseline.
- [x] Existing ALIVE file and BEDROCK/legacy interfaces retained.
- [x] Actual native system capture, audible physical playback and Bypass verified.
- [x] Real continuous transformations and time-aligned switching, with bounded state.
- [x] Deterministic mono/stereo + 44.1/48 kHz continuity and lifecycle tests.
- [x] Root README onboarding, both source command references and restoration steps.
- [x] Native stop/exit and normal physical-route restoration observed.
- [ ] Musical quality accepted by owner: **pending; owner reports subtle differences / quality needs work**.
- [ ] Long-session, stress, physical disconnect, all-device/OS coverage and explicit
      detailed echo/glitch acceptance: pending.
- [ ] Final-head CI/reviews: recorded in the follow-up PR, not inferred from local tests.
- [ ] Owner release acceptance: pending. No automatic merge, version bump or release.

Final local full-suite result: **150 passed, 1 expected failure**, with the existing
FastAPI/Starlette deprecation warning. The one XFAIL remains the unchanged BEDROCK
offline nonzero chunk-streaming test; the new LIVE continuity reference tests pass.
Local service tests need localhost socket access. A workspace-specific macOS
hidden-file flag caused Python 3.14 to skip an editable-install `.pth` file during
one run; regular package installation restored installed-entrypoint validation.
This environment issue is not hidden as a DSP test failure. The README editable install was also verified in a fresh temporary environment,
launched from outside the checkout, with only `.[playback]` dependencies.
CI separately checks it on Linux/macOS Python 3.10/3.13.
